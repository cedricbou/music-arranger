# Guide pour agents

`arr` est un CLI Python local pour réarranger des morceaux avec un groupe, par **prises
complètes** du morceau. Ce fichier est le point d'entrée ; il renvoie vers le reste :

| Pour savoir | Lire |
|---|---|
| ce que fait l'outil, en aperçu | `README.md` |
| le mode d'emploi complet : parcours, configuration audio, dépannage | `docs/manual/` |
| pourquoi il est construit ainsi, et ce qui a déjà été essayé | `docs/decisions/` |
| ce qui reste à faire, et dans quel état sont les choses | les issues GitHub (`gh issue list`) |

## Contraintes non négociables

- **Local uniquement.** Aucun service distant ne reçoit l'audio de l'utilisateur.
- **Réseau limité à deux commandes** : `arr models pull` et `arr lyrics fetch` (artiste et
  titre envoyés à lrclib.net). Le reste tourne hors ligne (`engines.offline()`).
- **Intel Arc A770, 16 Go.** PyTorch XPU et Vulkan ; pas de CUDA, pas de float64 ni de bf16
  sur le GPU.
- **Non destructif.** Une opération crée une nouvelle prise ou une nouvelle version, jamais
  elle n'écrase un fichier audio. Seul `arr rm` retire, vers `trash/` par défaut.
- **Usage non commercial** : YuE2 et SheetSage2 sont sous CC BY-NC 4.0.

## Avant de proposer une idée

Générer une piste d'instrument qui s'accorde à une bande existante a été essayé de cinq
façons et abandonné. Ce qui marche : faire rejouer le morceau entier par YuE2 à partir de sa
partition, puis séparer la prise. Lire les fiches avant de toucher à la génération (001,
002), à la chaîne audio (003), au calage (004), au volume (005) ou à la grille de mesures (008).

## Comment travailler ici

1. **Une issue, une branche partie de `main`, une PR.** Jamais de commit direct sur `main`.
2. **Langues** : interface, docstrings et docs en français ; identifiants, issues et PR en anglais.
3. **Terminé** veut dire : tests ajoutés, `uv run pytest` et `uv run ruff check .` verts,
   `uv run ruff format .` appliqué, documentation à jour (ci-dessous), carte du code à jour
   si un fichier apparaît, fiche dans `docs/decisions/` si un choix structurant est fait.
4. **Un agent ne peut pas écouter.** Mesurer avec `arr check` et `arr.measure`, dire dans la
   PR ce qui est mesuré et ce qui reste à juger à l'oreille. Ne jamais annoncer une qualité sonore.
5. **Ne jamais jouer sur les enceintes ni piloter Spotify pour un test.** L'audio en direct
   se teste sur une sortie PipeWire virtuelle (voir « Audio en direct »).
6. **Ne rien supprimer hors du dépôt** sans que l'utilisateur le demande ; ses projets sont
   ailleurs (`~/Musique/...`) et se lisent sans les modifier.

## Tenir la documentation à jour

Le manuel (`docs/manual/`) fait partie du produit ; `tests/test_docs.py` échoue s'il dérive.

- **Une commande ou une option change** : écrire sa docstring et ses `help=` (la référence
  en sort), puis `uv run python scripts/gen_reference.py`. Ne jamais éditer `reference.md`.
- **Un comportement change** : `parcours.md` pour l'usage, `README.md` pour l'aperçu.
- **Un réglage d'`audio.toml` ou une variable `ARR_*` apparaît** : `audio.md`, `installation.md`.
- **Un message d'erreur pour l'utilisateur apparaît ou change** : `depannage.md`.

## Commandes de travail

```
uv sync                   # environnement (Python 3.11, épinglé dans .python-version)
uv run pytest -q          # ~5 s, sans GPU, sans modèle, sans carte son
uv run ruff check . && uv run ruff format .
uv run arr doctor         # GPU et présence des moteurs
uv run arr <commande>     # depuis un dossier de projet, ex. demo/gala-yue2 (hors git)
# La CI (.github/workflows/ci.yml) lance lint, format et tests sur chaque PR.
```

## Carte du code

```
src/arr/
  cli.py                    point d'entrée : importe les modules de commandes, dans l'ordre de `arr --help`
  app.py                    l'application Typer, ses sous-groupes, les constantes partagées, `run()`
  commands/_common.py       aides partagées : render_mix, add_track, convert, confirm, describe...
  commands/project.py       init, import
  commands/score.py         analyze, transcribe, lyrics fetch, sections
  commands/takes.py         render, takes, graft, share
  commands/tracks.py        split, merge, tracks, rm, pick, gain, mute, mix
  commands/_screen.py       l'écran de play et de record : pistes, calage, section en cours, grille d'accords
  commands/play.py          play : mix, piste ou prise, sections, boucle ; clavier (pause, mesure voisine)
  commands/align.py         nudge, align : le calage d'une piste par section
  commands/sheet.py         sheet, set new/add/show/edit/print : antisèches de scène et setlists
  commands/studio.py        capture, record, calibrate, levels
  commands/system.py        check, devices, doctor, models pull
  project.py                Project : song.toml, pistes versionnées, prises, sections, corbeille
  audio.py                  E/S et opérations numpy (mix, splice, fit, shift, stretch, normalize, clics)
  measure.py                mesures sans écoute : période, calage, retard, niveaux, accords replacés
  lyrics.py                 LRCLIB, et rangement des paroles horodatées par section
  sheet.py                  antisèche : proposition, sheet.toml, noms d'accords, transposition
  pdf.py                    impression A4 des antisèches (fpdf2) : blocs en colonnes, échelle qui tient
  studio.py                 audio en direct : capture (parec), lecture et duplex (sounddevice), audio.toml
  spotify.py                lecteur Spotify local par D-Bus MPRIS (titre, relance, pause)
  engines/yue2.py           render() : sous-processus audio.cpp ; melody_only()
  engines/transcription.py  transcribe() : sous-processus SheetSage2 ; read() des résultats
  engines/_sheetsage2.py    script exécuté par l'environnement SheetSage2, n'importe pas arr
  engines/separation.py     Demucs ; MODELS liste les modèles acceptés par `split`
  engines/analysis.py       beat_this (temps), tempo, tonalité approximative
tests/
  helpers.py                faux moteurs et projets d'essai partagés (fake_studio, song_project, tone...)
  test_core.py, test_measure.py   project.py, audio.py et measure.py, sur signaux synthétiques
  test_docs.py              la documentation suit le code (README, manuel, carte du code, fiches)
  test_slow.py              vrais moteurs sur signal synthétique : `uv run pytest -m slow`, hors CI
  test_project.py, test_score.py, test_takes.py, test_tracks.py, test_play.py, test_align.py,
  test_sheet.py, test_studio.py, test_system.py   un fichier par module de commandes (CliRunner)
```

Règles de structure :

- Une commande est une fonction dans le module de son domaine ; un nouveau domaine est un
  nouveau module, importé dans `cli.py`. Un fichier de plus de 400 lignes se découpe.
- Les commandes ne parlent aux modèles que par `engines/`, à la carte son que par `studio.py`.
- Imports lourds (`torch`, `demucs`, `sounddevice`) **dans** les fonctions : `arr --help` reste instantané.
- Les erreurs destinées à l'utilisateur sont des `ProjectError` ; `run()` les affiche sans trace.
- Les tests remplacent moteurs et carte son par `monkeypatch` sur `engines.*`, `studio`,
  `spotify`, `lyrics`. Tout ajout vient avec son test : signal synthétique ou `CliRunner`.
- Peu de commentaires (une contrainte non évidente), pas d'abstraction sans deuxième usage.

## Modèle de projet

- `song.toml` : `[song]`, `[[sections]]` (name, start, end), `[tracks.<nom>]` (active, gain, mute).
- **Prises** : `takes/tNNN.flac` + `.json` (model, engine, mode, style, seed) ; `new_take()` réserve le nom.
- **Pistes** : `tracks/<nom>/vNNN.flac` + `.json`, créées par `add_track()`. Stems de
  l'original : `drums`, `bass`... ; ceux d'une prise : `t001.drums`..., et ils naissent muets.
- **Greffe** = sourdines : `graft` réactive `tNNN.<stem>` et, avec `--replace`, coupe `<stem>`.
- **Calage** : `nudges` dans `song.toml`, appliqués par `load_track()` ; rien de manuel n'est écrasé (006).
- Sections homonymes numérotées (`chorus2`). **Antisèche** : `sheet.toml` fait foi ; setlists à part (009).

## Conventions audio

- Partout : 48 kHz, stéréo, `float32`, forme `(échantillons, 2)`. `audio.convert()` normalise
  tout import et toute sortie de modèle ; `audio.load()` refuse un autre taux.
- Les pistes d'un projet ont toutes la longueur de l'original (`audio.fit`) ; les prises
  gardent la leur, leurs stems sont ajustés par `split`.
- Une plage seulement : `audio.splice()`. Volume : `audio.normalize()`, jamais `loudnorm`.

## Moteurs externes

Installés par `arr models pull` sous `~/.local/share/arr` (`ARR_HOME`), lancés en sous-processus :
`audiocpp/<version>/` (**vulkan-portable**, lien `current`), `yue2/` (GGUF Q8), `envs/ss2/` (SheetSage2).
Les poids viennent de Hugging Face, audio.cpp de sa release GitHub : fiches 002 et 007. Jamais lancés en test.

## Audio en direct

L'ordinateur de Cédric joue sur une PreSonus iTwo, reliée en analogique aux voies 7/8 d'une
Soundcraft Signature 12 MTK : **capture sur les entrées 7/8 de la table**, **lecture sur la
sortie par défaut** (fiche 003). Les autres installations sont décrites dans `docs/manual/audio.md`.

- Capture : `parec` sur une source PipeWire ; `studio.gate()` est une fonction pure.
- Lecture et enregistrement : un flux duplex `sounddevice` sur l'API JACK de PipeWire, entrée
  et sortie du même pilote. La latence vient de `arr calibrate`, jamais de PortAudio.
- **Tester sans bruit** : `scripts/loopback.sh arr <commande>` crée une sortie PipeWire
  virtuelle, y pointe `ARR_AUDIO`, lance la commande et nettoie. Rien d'autre n'est permis.
