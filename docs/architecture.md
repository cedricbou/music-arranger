# Architecture

Ce que `AGENTS.md` ne porte pas : le modèle d'un projet de morceau sur le disque, et les moteurs
externes. La carte du code et les règles de structure restent dans `AGENTS.md` ; le pourquoi des
choix, dans `docs/decisions/`.

## Modèle de projet

- `song.toml` : `[song]`, `[[sections]]` (name, start, end), `[tracks.<nom>]` (active, gain, mute).
- **Prises** : `takes/tNNN.flac` + `.json` (model, engine, mode, style, seed) ; `new_take()`
  réserve le nom.
- **Pistes** : `tracks/<nom>/vNNN.flac` + `.json`, créées par `add_track()`. Stems de
  l'original : `drums`, `bass`... ; ceux d'une prise : `t001.drums`..., et ils naissent muets.
- **Greffe** = sourdines : `graft` réactive `tNNN.<stem>` et, avec `--replace`, coupe `<stem>`.
- **Calage** : `nudges` dans `song.toml`, appliqués par `load_track()` ; rien de manuel n'est
  écrasé (fiche 006).
- Sections homonymes numérotées (`chorus2`). **Antisèche** : `sheet.toml` fait foi ; setlists à
  part (fiche 009).
- **Prompteur** : `export/<dossier>.cho`, réécrit en entier par `arr chordpro` à partir des
  sections, des accords et de `lyrics.txt` (fiche 012). Les paroles horodatées de LRCLIB restent
  telles quelles dans `lyrics.lrc`, recalées à chaque lecture : elles placent chaque ligne sur sa mesure.
- **Grille** : `analysis.json` (temps et barres de beat_this, tels quels) et `analysis_frames.npz`
  (ses activations à 50 trames par seconde) ; doublons, trous et barres se refont à chaque lecture
  (`song_grid`, fiches 013, 015, 017).
- **Passages de référence** : `truth/<passage>.vNNN.toml` (start, end, beats_per_bar, bars), une
  version par passe de `arr play --mark`, la dernière fait foi ; `truth/runs.json` garde les notes
  de chaque `arr truth` (fiche 016).

## Moteurs externes

Installés par `arr models pull` sous `~/.local/share/arr` (`ARR_HOME`), lancés en sous-processus :
`audiocpp/<version>/` (**vulkan-portable**, lien `current`), `yue2/` (GGUF Q8), `envs/ss2/`
(SheetSage2). Les poids viennent de Hugging Face, audio.cpp de sa release GitHub : fiches 002 et
007. Jamais lancés en test.
