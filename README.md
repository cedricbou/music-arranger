# arr

CLI local pour réarranger des morceaux avec un groupe : transcrire l'original en partition,
faire rejouer le morceau entier par un groupe virtuel dans un autre style, puis en tirer les
parties de chaque musicien ou les greffer sur l'original.

Tout tourne sur la machine (Intel Arc). Rien de tes morceaux ne sort : seuls `arr models pull`
(téléchargement des modèles) et `arr lyrics fetch` (recherche des paroles par titre) utilisent
le réseau.

## L'idée

Les modèles actuels savent très bien générer un **morceau complet**, et très mal ajouter une
piste isolée sur une bande existante. `arr` travaille donc par **prises** : chaque prise est
une interprétation complète du morceau (voix et groupe), fidèle à la partition de l'original.
Une prise sert d'abord de maquette : on l'écoute, on la découpe en parties par musicien.
Quand elle suit d'assez près la grille de l'original, ses stems peuvent aussi y être
greffés (sa guitare, sa batterie, tout le groupe) ; `arr split` mesure si c'est le cas.

## Installation

Prérequis : `uv`, `ffmpeg`, pilotes Intel (`intel-compute-runtime`, `level-zero-loader`,
`vulkan-intel`).

```
cd ~/dev/music-arranger
uv sync
uv run arr models pull   # modèles et moteurs, une seule fois (~6 Go)
uv run arr doctor        # tout doit être « présent »
```

Ajoute un alias dans `~/.zshrc` : `alias arr=~/dev/music-arranger/.venv/bin/arr`.

## Parcours type

```
arr init gala --from ~/Musique/freed-from-desire.flac
cd gala
arr transcribe                          # partition, tempo, tonalité, sections (3 à 12 min)
arr lyrics fetch "Gala" "Freed from Desire"
$EDITOR lyrics.txt                      # relire le découpage par section

arr render -s "funk pop cover, live band, female lead vocals, clean funk rhythm guitar, \
               slap bass, tight drums, Rhodes" -n 2      # deux prises fidèles (~5 min chacune)
arr takes
arr play t001

arr split                               # stems de l'original
arr split t001                          # stems de la prise ; dit si elle est greffable
arr graft t001 guitar piano             # ajoute guitare et claviers de la prise à l'original
arr graft t001 drums bass --replace     # remplace batterie et basse de l'original
arr tracks                              # ce qui joue dans le mix
arr play

arr share t001.guitar                   # dossier pour le guitariste
```

## Itérer

Cinq leviers, à changer un par un :

| Levier | Comment | Effet |
|---|---|---|
| Une autre prise | `arr render -s "..." -n 3` | même commande, autre interprétation |
| Le style | changer le texte de `-s` | formation, genre, couleur |
| La liberté | `--free` | mélodie seule : accompagnement réinventé, tempo parfois différent, non greffable |
| La partition | éditer `score/score.abc` | forme, accords, tonalité, mélodie |
| Les paroles | éditer `lyrics.txt` | texte et balises de section |

Chaque prise garde son style, son mode et sa graine (`arr takes`) ; rien n'est écrasé.

Le style se rédige en anglais, comme une liste : genre, formation, instruments, type de voix,
ambiance. Le modèle suit la formation et la couleur ; il ne permet pas de dicter la partie
d'un instrument note à note.

## Commandes

### Projet

| Commande | Effet |
|---|---|
| `arr init NOM [--from FICHIER]` | crée le projet, importe le morceau |
| `arr import FICHIER` | remplace le morceau original |
| `arr import FICHIER --as PISTE` | ajoute un enregistrement comme piste |
| `arr transcribe` | partition dans `score/`, tempo, tonalité, sections |
| `arr lyrics fetch ARTISTE TITRE [--force]` | paroles dans `lyrics.txt`, rangées par section |
| `arr analyze` | temps et tempo seulement, en quelques secondes (sans partition) |
| `arr sections list`, `arr sections set "intro:1-8 ..."` | sections, en numéros de mesure |

### Prises

| Commande | Effet |
|---|---|
| `arr render -s STYLE [--free] [-n N] [--seed N]` | rend une ou plusieurs prises complètes |
| `arr takes` | liste des prises |
| `arr play t001` | écoute une prise |

### Stems et mix

| Commande | Effet |
|---|---|
| `arr split [--model htdemucs_ft]` | stems de l'original : `drums`, `bass`, `guitar`... |
| `arr split t001` | stems d'une prise : `t001.drums`..., muets et calés sur l'original |
| `arr graft t001 STEM... [--replace]` | fait entendre des stems d'une prise, en plus ou à la place de l'original |
| `arr merge PISTE PISTE... --as NOM` | fusionne des pistes |
| `arr tracks [-v]`, `arr tracks PISTE` | ce qui joue (●), ce qui est muet (○), l'historique |
| `arr pick PISTE VERSION`, `arr gain PISTE DB`, `arr mute PISTE [--off]` | réglages du mix |
| `arr mix [-w PISTE] [-o PISTE]` | écrit `mix/mix.flac` |
| `arr play [PISTE] [VERSION]` | écoute le mix, une piste ou une version |
| `arr share PISTE` | `export/PISTE/` : `partie.mp3`, `mix.mp3`, `sans.mp3` |

Deux modèles de séparation : `htdemucs_6s` (6 stems, par défaut ; guitare et piano peu
fiables sur de la musique électronique) et `htdemucs_ft` (4 stems, plus précis).

## Dossier d'un projet

```
gala/
  song.toml        titre, tempo, tonalité, sections, état du mix
  lyrics.txt       paroles avec balises [Verse], [Chorus]...
  source/          morceau original, en FLAC 48 kHz stéréo
  score/           score.abc (éditable), fichiers MIDI, accords et structure horodatés
  takes/           t001.flac + t001.json (style, mode, graine)
  tracks/<piste>/  vNNN.flac + vNNN.json
  mix/  export/
```

`score/` contient aussi `melody_vocal.mid`, `melody_instrumental.mid` et `chords.mid`, à
ouvrir dans MuseScore ou un séquenceur pour les partager avec le groupe.

## À savoir

- **Durées** pour 3 min 40 : transcription 3 à 12 min (plus long la première fois) ; une prise ~4 min 30 ; séparation ~20 s.
- **Greffe** : elle ne marche que si la prise suit la grille de l'original. `arr split tNNN`
  étire et cale la prise, mesure la part de temps qui tombent juste et prévient en dessous
  de 60 %. Sur Gala, une prise fidèle sur trois était greffable : c'est la limite actuelle
  la plus gênante. En cas d'échec, rendre une autre prise ou relancer `arr transcribe`.
- **Paroles** : sans `lyrics.txt`, la prise est instrumentale. Le découpage automatique par
  section est approximatif, à relire.
- **Licence** : les poids de YuE2 et SheetSage2 sont sous CC BY-NC 4.0 (usage non commercial).
- **Paroles et réseau** : `arr lyrics fetch` envoie l'artiste et le titre à lrclib.net,
  rien d'autre.
