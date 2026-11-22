# Guide pour agents

`arr` est un CLI Python local pour réarranger des morceaux avec un groupe, par **prises
complètes** du morceau. Ce fichier est le point d'entrée ; il renvoie vers le reste :

| Pour savoir | Lire |
|---|---|
| ce que fait l'outil, en aperçu | `README.md` |
| le mode d'emploi complet : parcours, configuration audio, dépannage | `docs/manual/` |
| pourquoi il est construit ainsi, et ce qui a déjà été essayé | `docs/decisions/` |
| le modèle d'un projet sur le disque, les moteurs externes | `docs/architecture.md` |
| ce qui reste à faire, et dans quel état sont les choses | les issues GitHub (`gh issue list`) |

## Contraintes non négociables

Vérifiées par `tests/test_rules.py`, sauf ce qui est dit « non vérifié ».
- **Local uniquement.** Aucun service distant ne reçoit l'audio. Réseau limité à deux commandes :
  `arr models pull` et `arr lyrics fetch` (artiste et titre à lrclib.net) ; sinon `engines.offline()`.
- **Intel Arc A770, 16 Go.** PyTorch XPU et Vulkan ; pas de CUDA, ni float64 ni bf16 sur le GPU (non vérifié).
- **Non destructif.** Une opération crée une nouvelle prise ou une nouvelle version, jamais
  elle n'écrase un fichier audio (non vérifié). Seul `arr rm` retire, vers `trash/` par défaut.
- **Usage non commercial** : YuE2 et SheetSage2 sont sous CC BY-NC 4.0. **Dépôt public** : ni musique,
  paroles ni poids ; artistes inventés ; le hook refuse les noms des projets (`scripts/check_names.py`).

## Avant de proposer une idée

Générer une piste d'instrument qui s'accorde à une bande existante a été essayé de cinq
façons et abandonné. Ce qui marche : faire rejouer le morceau entier par YuE2 à partir de sa
partition, puis séparer la prise. Lire les fiches avant de toucher à la génération (001,
002), à la chaîne audio (003), au calage (004), au volume (005), à la grille (008) ou au MIDI (011).

## Comment travailler ici

1. **Le cycle est imposé** : issue → branche → PR → CI verte → squash merge, par
   `scripts/feature.sh`, les hooks (`scripts/install-hooks.sh`, une fois) et la CI `pr-rules`.
   Jamais de commit ni de push sur `main` (`ARR_ALLOW_MAIN=1` : urgence demandée par l'utilisateur).
   ```
   scripts/feature.sh issue story "Title" body.md framing.md   # cadrage en commentaire
   scripts/feature.sh start 12             # branche feat/12-... ; relit le style de l'issue
   scripts/feature.sh pr --notes notes.md  # check.sh, push, PR « Closes #12 », ce qui est mesuré
   scripts/feature.sh merge                # attend la CI, squash merge, main à jour
   ```
2. **Les issues s'écrivent pour le musicien** (`docs/style-issues.md`, skill `ecrire-issue`) : type
   `epic`, `story`, `chore` ou `bug`, corps sans nom de module ni de fichier, critères « Done when »
   observables ; le détail technique, à lire avant de coder, est dans le commentaire `## Technical framing`.
   Une issue `needs-refinement` se cadre **avec** l'utilisateur. Une limite découverte devient une issue.
3. **Langues** : interface, docstrings et docs en français ; identifiants, issues et PR en anglais.
4. **Terminé** veut dire : tests ajoutés, `scripts/check.sh` vert (ruff, format, pytest),
   documentation à jour (ci-dessous), carte du code à jour si un fichier apparaît, fiche dans
   `docs/decisions/` si un choix structurant est fait.
5. **Un agent ne peut pas écouter.** Mesurer (`arr check`, `arr.measure`), dire dans la PR ce qui est
   mesuré et ce qui reste à l'oreille (`--notes`) ; jamais une qualité sonore. Livrée, une issue dont
   il ne reste que l'écoute se ferme : l'essai rejoint l'issue de session d'écoute.
6. **Ni enceintes, ni lecteur multimédia, ni MIDI vers la pédale pour un test** : sortie PipeWire virtuelle,
   « Midi Through » (« Audio en direct »). Ne rien supprimer hors du dépôt sans demande ; les projets
   (`~/Musique/...`) se lisent sans les modifier. `.claude/settings.json` refuse les lecteurs directs,
   le push sur `main` et l'écriture dans `~/Musique` ; le reste n'est pas vérifié.

## Tenir la documentation à jour

Le manuel (`docs/manual/`) fait partie du produit ; `tests/test_docs.py` échoue s'il dérive. On écrit
au présent, sans numéro d'issue ni chemin mort (`docs/style-doc.md`, skill `relire-docs` pour une zone).

- **Une commande ou une option change** : écrire sa docstring et ses `help=` (la référence
  en sort), puis `uv run python scripts/gen_reference.py`. Ne jamais éditer `reference.md`.
- **Un comportement change** : `parcours.md` pour l'usage, `README.md` pour l'aperçu.
- **Un réglage d'`audio.toml` ou une variable `ARR_*` apparaît** : `audio.md`, `installation.md`.
- **Un message d'erreur pour l'utilisateur apparaît ou change** : `depannage.md`.

## Commandes de travail

```
uv sync                   # environnement (Python 3.11, épinglé dans .python-version)
scripts/check.sh [--fix]  # ruff, format, pytest, sans GPU ni modèle ni carte son ; aussi en CI
uv run arr doctor         # GPU et moteurs ; `uv run arr <commande>` depuis un projet (par exemple sous demo/)
```

## Carte du code

```
src/arr/
  cli.py                    point d'entrée : importe les modules de commandes, dans l'ordre de `arr --help`
  app.py                    l'application Typer, ses sous-groupes, les constantes partagées, `run()`
  commands/_common.py       aides partagées : render_mix, add_track, convert, confirm, describe...
  commands/project.py       init, import, rename
  commands/score.py         analyze, transcribe, lyrics fetch, sections
  commands/takes.py         render, takes, graft, share
  commands/tracks.py        split, merge, tracks, rm, pick, gain, mute, mix
  commands/_screen.py       l'écran de play et de record : pistes, calage, section en cours, grille d'accords
  commands/play.py          play : mix, piste ou prise, sections, boucle ; clavier (pause, mesure voisine)
  commands/align.py         nudge, align : le calage d'une piste par section
  commands/sheet.py         sheet, set new/add/show/edit/print : antisèches de scène et setlists
  commands/studio.py        capture, record, calibrate, levels
  commands/midi.py          midi ports/send/monitor : tester et piloter les pédales de scène
  commands/system.py        check, devices, doctor, models pull
  project.py                Project : song.toml, pistes versionnées, prises, sections, corbeille
  audio.py                  E/S et opérations numpy (mix, splice, fit, shift, stretch, normalize, clics)
  measure.py                mesures sans écoute : période, calage, retard, niveaux, accords replacés
  lyrics.py                 LRCLIB, et rangement des paroles horodatées par section
  sheet.py                  antisèche : proposition, sheet.toml, noms d'accords, transposition
  pdf.py                    impression A4 des antisèches (fpdf2) : blocs en colonnes, échelle qui tient
  studio.py                 audio en direct : capture (parec), lecture et duplex (sounddevice), audio.toml
  midi.py                   MIDI en direct : ports et envoi (aplaymidi), écoute (aseqdump), messages
  player.py                 lecteur multimédia local par D-Bus MPRIS (choix, titre, relance, pause)
  engines/yue2.py           render() : sous-processus audio.cpp ; melody_only()
  engines/transcription.py  transcribe() : sous-processus SheetSage2 ; read() des résultats
  engines/_sheetsage2.py    script exécuté par l'environnement SheetSage2, n'importe pas arr
  engines/separation.py     Demucs ; MODELS liste les modèles acceptés par `split`
  engines/analysis.py       beat_this (temps), tempo, tonalité approximative
tests/
  helpers.py                faux moteurs et projets d'essai partagés (fake_studio, song_project, tone...)
  test_core.py, test_measure.py   project.py, audio.py et measure.py, sur signaux synthétiques
  test_docs.py, test_rules.py   la doc suit le code ; les règles écrites ici sont vérifiées
  test_workflow.py          le cycle de scripts/feature.sh, hors-ligne (faux gh)
  test_slow.py              vrais moteurs sur signal (`-m slow`, hors CI)
  test_project.py, test_score.py, test_takes.py, test_tracks.py, test_play.py, test_align.py,
  test_sheet.py, test_studio.py, test_system.py, test_midi.py   un fichier par module (CliRunner)
```

Règles de structure (vérifiées par `tests/test_rules.py`, sauf « non vérifié ») :

- Une commande est une fonction dans le module de son domaine ; un nouveau domaine est un
  nouveau module, importé dans `cli.py` (non vérifié). Un fichier de plus de 400 lignes se découpe.
- Les commandes parlent à la carte son par `studio.py`, au MIDI par `midi.py`, au lecteur par
  `player.py`, aux modèles par `engines/` (ce dernier point non vérifié).
- Imports lourds (`torch`, `demucs`, `sounddevice`) **dans** les fonctions : `arr --help` reste instantané.
- Non vérifiées : les erreurs pour l'utilisateur sont des `ProjectError` (`run()` les affiche sans
  trace) ; les tests remplacent moteurs et carte son par `monkeypatch` (`engines.*`, `studio`, `player`,
  `lyrics`), tout ajout vient avec son test ; peu de commentaires, pas d'abstraction sans deuxième usage.

## Conventions audio

- Partout : 48 kHz, stéréo, `float32`, forme `(échantillons, 2)`. `audio.convert()` normalise
  tout import et toute sortie de modèle ; `audio.load()` refuse un autre taux.
- Pistes à la longueur de l'original (`audio.fit`) ; une prise garde la sienne (stems par `split`).
- Une plage seulement : `audio.splice()`. Volume : `audio.normalize()`, jamais `loudnorm`.

## Audio en direct

L'ordinateur de Cédric joue sur une PreSonus iTwo, reliée en analogique aux voies 7/8 d'une
Soundcraft Signature 12 MTK : **capture sur les entrées 7/8 de la table**, **lecture sur la
sortie par défaut** (fiche 003). Les autres installations sont décrites dans `docs/manual/audio.md`.

- Capture : `parec` sur une source PipeWire ; `studio.gate()` est une fonction pure.
- Lecture et enregistrement : un flux duplex `sounddevice` sur l'API JACK de PipeWire, entrée
  et sortie du même pilote. La latence vient de `arr calibrate`, jamais de PortAudio.
- **Tester sans bruit** : `scripts/loopback.sh arr <commande>` crée une sortie PipeWire
  virtuelle, y pointe `ARR_AUDIO`, lance la commande et nettoie. Rien d'autre n'est permis.
- **MIDI** : `midi.py` envoie par `aplaymidi` (`aseqsend` n'atteint pas la carte), écoute par `aseqdump`.
  Tester sur « Midi Through », jamais la pédale ; `/proc/asound/card*/midi0` prouve ce qui sort (fiche 011).
