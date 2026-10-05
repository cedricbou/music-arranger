# Guide développeur pour agents

`arr` est un CLI Python local pour réarranger des morceaux par **prises complètes**. Lire
`README.md` pour l'usage et `HANDOFF.md` pour l'état du travail, les mesures et la suite.

## Contraintes non négociables

- **Local uniquement.** Aucun service distant ne reçoit l'audio de l'utilisateur.
- **Enregistrer Spotify** reste local : `capture` écoute la sortie son de la machine.
- **Réseau limité à deux commandes.** `arr models pull` (modèles et moteurs) et
  `arr lyrics fetch` (artiste et titre envoyés à lrclib.net). Tout le reste tourne avec
  `HF_HUB_OFFLINE=1` (voir `engines.offline()`).
- **Intel Arc A770, 16 Go.** PyTorch XPU pour Demucs, beat_this et SheetSage2 ; Vulkan pour
  YuE2. Pas de CUDA, pas de float64 sur le GPU, pas de bf16 en Vulkan.
- **Non destructif.** Une opération crée une nouvelle prise ou une nouvelle version ; elle
  n'écrase jamais un fichier audio. Seul `arr rm` retire, vers `trash/` par défaut, et
  n'efface pour de bon qu'avec `--purge` et une confirmation.
- **Usage non commercial** : YuE2 et SheetSage2 sont sous CC BY-NC 4.0.

## Le principe à ne pas réapprendre

Générer une piste d'instrument cohérente sur une bande existante n'est pas faisable en local
aujourd'hui. Trois approches ont été essayées et abandonnées, mesures à l'appui dans
`HANDOFF.md` : ACE-Step (`cover`, `lego`, `complete`), Stable Audio 3, et le tri de riffs par
groove. Ne pas les réintroduire sans élément nouveau.

Ce qui marche : faire rejouer le **morceau entier** par YuE2 à partir de la partition, puis
séparer la prise en stems. Une prise fidèle (`cot=full`, mélodie et accords) garde la
tonalité et à peu près le tempo ; ses stems se greffent sur l'original **seulement** quand
elle suit sa grille de mesures, ce qui n'arrive pas à chaque fois (voir `HANDOFF.md`).

## Commandes de travail

```
uv sync                 # environnement (Python 3.11 épinglé dans .python-version)
uv run pytest -q        # tests rapides, sans GPU ni modèles
uv run arr doctor       # XPU et présence des modèles
uv run arr <commande>   # depuis un dossier de projet, ex. demo/gala-yue2
```

Les tests ne chargent aucun modèle : les moteurs sont remplacés par `monkeypatch`. Pour
valider une commande générative, la lancer sur un projet de `demo/` et **mesurer** (durée,
tempo, calage des temps, tonalité, parts des stems). Un agent ne peut pas écouter : dire
ce qui a été mesuré et ce qui reste à juger à l'oreille.

## Architecture

```
src/arr/
  cli.py                    toutes les commandes Typer ; point d'entrée `run()`
  project.py                Project : song.toml, pistes versionnées, prises, sections
  audio.py                  E/S et opérations numpy (mix, splice, fit, shift, scale_to, save_mp3)
  lyrics.py                 LRCLIB, et rangement des paroles horodatées par section
  studio.py                 audio en direct : capture (parec), lecture et duplex (sounddevice), audio.toml
  spotify.py                lecteur Spotify local par D-Bus MPRIS (titre, relance, pause)
  engines/__init__.py       chemins (HOME, AUDIOCPP, YUE2, SS2_PYTHON), device(), offline()
  engines/yue2.py           render() : sous-processus audio.cpp ; melody_only()
  engines/transcription.py  transcribe() : sous-processus SheetSage2 ; read() des résultats
  engines/_sheetsage2.py    script exécuté par l'environnement SheetSage2, n'importe pas arr
  engines/separation.py     Demucs ; MODELS liste les modèles acceptés par `split`
  engines/analysis.py       beat_this (temps), tempo, tonalité approximative
tests/test_core.py          projet et audio, sur signaux synthétiques
tests/test_cli.py           commandes via CliRunner, moteurs factices
```

Règles de structure :

- Les commandes ne parlent aux modèles que par `engines/`.
- Les imports lourds (`torch`, `demucs`) sont faits **dans** les fonctions, pour que
  `arr --help`, `tracks`, `takes`, `mix` restent instantanés.
- Les erreurs destinées à l'utilisateur sont des `ProjectError` ; `run()` les affiche sans trace.

## Moteurs externes

Installés par `arr models pull` sous `~/.local/share/arr` (`ARR_HOME`) :

| Élément | Où | Pourquoi à part |
|---|---|---|
| `audiocpp/audiocpp_cli` | binaire audio.cpp v0.9.0, variante **vulkan-portable** | la variante non portable plante (SIGILL) sur ce CPU |
| `yue2/` | `yue2-3b-q8_0.gguf`, `yue2-vae-f16.gguf`, `sidecars/` | poids GGUF de YuE2 ; Q8 car Vulkan sur Arc n'a pas le bf16 |
| `envs/ss2/` | environnement Python de SheetSage2 | il exige `transformers==4.45.2` et `numpy<2` |

SheetSage2 se charge par son identifiant Hugging Face (`m-a-p/SheetSage2`, depuis le cache) :
le chargement depuis un dossier local échoue sur ses imports relatifs.

## Audio en direct (`studio.py`)

- **Installation de Cédric** : l'ordinateur joue sur une PreSonus iTwo, dont les sorties
  arrivent en analogique sur les voies 7/8 d'une Soundcraft Signature 12 MTK. On capture
  donc sur les **entrées** 7/8 de la Soundcraft, et la lecture reste sur la sortie par
  défaut. Ne pas confondre avec les sorties USB de la Soundcraft.
- **Volume des captures** : `audio.normalize()` applique un seul gain vers la cible LUFS
  (mesure `ebur128` de ffmpeg), plafonné à -1 dB de crête. Ne pas utiliser le filtre
  `loudnorm` en une passe : il compresse la dynamique.
- **Capture** : `parec` sur une source PipeWire (`capture_source()`), lu en continu ; `gate()` est
  une fonction pure (démarrage au premier son, arrêt sur silence ou sur `should_stop`).
- **Lecture et enregistrement** passent par `sounddevice` sur l'API JACK de PipeWire : un
  seul flux en duplex, donc un décalage constant entre playback et prise (21,3 ms mesurés
  en boucle logicielle, identiques d'un essai à l'autre).
- **Ne pas se fier à la latence annoncée par PortAudio** : elle est aberrante ici. La
  latence vient de `arr calibrate` (mesure par corrélation), sinon de `DEFAULT_LATENCY`.
- **Tester sans bruit** : créer une sortie virtuelle (`pactl load-module module-null-sink
  sink_name=arr_test sink_properties=device.description=arr_test`), pointer `ARR_AUDIO` vers
  un audio.toml qui la désigne, puis la retirer (`pactl unload-module`). Ne jamais jouer sur
  les enceintes de l'utilisateur ni piloter son Spotify pour un test.

## Conventions audio

- Partout : 48 kHz, stéréo, `float32`, forme `(échantillons, 2)`. `audio.convert()` normalise
  tout import et toute sortie de modèle ; `audio.load()` refuse un autre taux.
- Les pistes d'un projet ont toutes la longueur de l'original (`audio.fit`). Les prises
  gardent leur propre longueur ; leurs stems sont ajustés à celle de l'original par `split`.
- Pour ne modifier qu'une plage : `audio.splice(base, patch, start, end)`.

## Modèle de projet

- `song.toml` : `[song]` (title, bpm, key, duration), `[[sections]]` (name, start, end),
  `[tracks.<nom>]` (active, gain, mute).
- **Prises** : `takes/tNNN.flac` + `.json` (`model`, `mode` close/free, `style`, `seed`,
  `score`, `instrumental`). `Project.new_take(meta)` réserve le nom ; l'appelant écrit l'audio.
- **Pistes** : `tracks/<nom>/vNNN.flac` + `.json`. Les stems de l'original s'appellent
  `drums`, `bass`... ; ceux d'une prise `t001.drums`... et naissent muets. Passer par
  `add_track()` dans `cli.py`.
- **Greffe** = gestion des sourdines : `graft` réactive `tNNN.<stem>` et, avec `--replace`,
  coupe `<stem>`. Une nouvelle séparation de l'original ne touche pas aux pistes préfixées.
- `analysis.json` (temps et mesures) est écrit par `transcribe` ou par `analyze` ; `split
  tNNN` s'en sert pour étirer et caler la prise, puis mesure `on_beat` (part des temps à
  moins de 35 ms de ceux de l'original) ; sous 60 %, la prise est marquée non superposable.
- Les sections homonymes sont numérotées (`chorus`, `chorus2`...) ; `lyrics.tagged()` retire
  le numéro pour écrire la balise.

## Style

- Messages, aides et docstrings en français ; identifiants en anglais.
- Peu de commentaires : seulement pour une contrainte non évidente.
- Pas d'abstraction sans deuxième usage. Une commande est une fonction dans `cli.py`.
- Tout ajout dans `audio.py` ou `project.py` vient avec un test sur signal synthétique ;
  toute commande avec un test `CliRunner` à moteur factice.
