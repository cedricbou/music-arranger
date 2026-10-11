# arr

CLI local pour réarranger des morceaux avec un groupe : transcrire l'original en partition,
faire rejouer le morceau entier par un groupe virtuel dans un autre style, puis en tirer les
parties de chaque musicien ou les greffer sur l'original.

Tout tourne sur la machine (Intel Arc). Rien de tes morceaux ne sort : seuls `arr models pull`
(téléchargement des modèles) et `arr lyrics fetch` (recherche des paroles par titre) utilisent
le réseau.

Ce fichier est un aperçu. Le **[manuel](docs/manual/README.md)** est la documentation
complète : installation, notions, parcours, configuration audio selon le matériel, référence
de chaque commande et dépannage.

## L'idée

Les modèles actuels savent très bien générer un **morceau complet**, et très mal ajouter une
piste isolée sur une bande existante. `arr` travaille donc par **prises** : chaque prise est
une interprétation complète du morceau (voix et groupe), fidèle à la partition de l'original.
Une prise sert d'abord de maquette : on l'écoute, on la découpe en parties par musicien.
Quand elle suit d'assez près la grille de l'original, ses stems peuvent aussi y être
greffés (sa guitare, sa batterie, tout le groupe) ; `arr split` mesure si c'est le cas.

## Installation

Prérequis : `uv`, `ffmpeg`, PipeWire (avec `pipewire-pulse` et `pipewire-jack`), `portaudio`,
pilotes Intel (`intel-compute-runtime`, `level-zero-loader`, `vulkan-intel`).

```
cd ~/dev/music-arranger
uv sync
uv run arr models pull   # modèles et moteurs (~6 Go) ; à relancer pour les mettre à jour
uv run arr doctor        # tout doit être « présent »
```

Pour taper `arr` partout, avec la complétion par Tab :

```
ln -s ~/dev/music-arranger/.venv/bin/arr ~/.local/bin/arr   # ~/.local/bin doit être dans le PATH
arr --install-completion                                    # puis ouvrir un nouveau terminal
```

N'utilise pas un alias : la complétion appelle `arr` hors du shell et ne le trouverait pas
(« env: arr: Aucun fichier ou dossier de ce nom » à chaque Tab).

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
arr split t001                          # stems de la prise, calés sur l'original section par section
arr nudge t001                          # le calage posé par arr split, section par section
arr nudge t001.vocals -s chorus --ms=-20   # l'ajuster à la main ; --reset pour l'annuler
arr graft t001 guitar piano             # ajoute guitare et claviers de la prise à l'original
arr graft t001 drums bass --replace     # remplace batterie et basse de l'original
arr tracks                              # ce qui joue dans le mix
arr play

arr share t001.guitar                   # dossier pour le guitariste
```

## Studio : capturer, jouer par-dessus, s'enregistrer

```
arr levels                         # vérifie que le son arrive sur 7/8 et règle le gain
arr capture --play                 # enregistre le morceau en cours dans Spotify, du début à la fin
cd freed-from-desire               # le projet porte le titre du morceau
arr lyrics fetch                   # artiste et titre sont déjà connus

arr split
arr play --without bass            # le morceau sans la basse, pour jouer par-dessus
arr play -o drums -o vocals        # seulement batterie et voix
arr play -s chorus --loop --count-in 1   # le refrain en boucle, après une mesure de décompte
arr play -s verse,chorus -w bass         # couplet puis refrain, sans la basse

arr calibrate                      # une fois : mesure la latence de ton installation
arr record bass                    # décompte d'une mesure, puis tu joues sur le playback
arr record bass --click -w guitar  # avec métronome, playback sans la guitare
arr tracks bass                    # tes prises, versionnées ; arr pick pour choisir
```

- **`arr capture`** enregistre ce que joue l'ordinateur tel qu'il revient sur la table :
  par défaut, les entrées 7/8 de la Soundcraft. Il démarre au premier son et s'arrête à la
  fin du morceau (changement de titre dans Spotify, sinon 3 s de silence). Avec `--play`,
  il relance lui-même le morceau depuis le début et met Spotify en pause à la fin. Sans
  Spotify : `arr capture mon-projet`, puis lance la lecture dans n'importe quel lecteur.
- **Volume des captures** : chaque capture est ramenée au même volume perçu (-16 LUFS par
  défaut) par un seul gain global, plafonné pour que les crêtes restent sous -1 dB. Le
  réglage de gain de la table n'a donc plus besoin d'être identique d'un jour à l'autre ;
  il suffit qu'il ne sature pas. `--raw` garde le niveau tel qu'enregistré.
- **`arr levels`** affiche un vumètre par canal de la table. Lance Spotify (ou
  `arr levels --tone`, qui joue un son de référence à -12 dB), regarde quels canaux bougent
  et règle le gain pour des crêtes entre -18 et -3 dB. Ctrl+C donne le bilan par canal.
- **Accords à l'écran** : après `arr transcribe`, `arr play` et `arr record` affichent la
  grille d'accords de la section en cours, une case par mesure et un `/` par temps tenu, et
  surlignent l'accord du moment, pour jouer par-dessus.
- **`arr record`** joue le mix sans la piste enregistrée et capte ton instrument dans le
  même flux. Le décompte mène au premier temps fort du morceau ; il lui faut le tempo
  (`arr transcribe` ou `arr analyze`). Tu t'entends par la table, pas par l'ordinateur. Une
  prise silencieuse n'est pas gardée.
- **`arr calibrate`** joue six clics et les réenregistre sur le canal où revient le son de
  l'ordinateur (le 7), puis note le retard mesuré : aucun câble à ajouter. Sans calibration,
  `arr record` compense 21 ms, le minimum du système.

### Réglages audio

`arr devices` montre ce qui est utilisé. Par défaut, avec la Soundcraft branchée :

| Usage | Défaut |
|---|---|
| Lecture (`play`, `record`) | sortie son habituelle de l'ordinateur |
| Capture de l'ordinateur (`capture`, `levels`) | entrées 7/8 de la Soundcraft |
| Instrument (`record`) | entrée 1 de la Soundcraft |

Pour changer, crée `~/.config/arr/audio.toml` :

```toml
[output]
device = ""              # fragment du nom ; "" = sortie par défaut du système
channels = [1, 2]

[input]
device = "Soundcraft"
channels = [3]           # un canal = mono, deux = stéréo

[capture]
source = ""              # "" = entrées de la Soundcraft ; "monitor" = copie numérique de
                         # la sortie, sans passer par la table ni régler de gain
channels = [7, 8]
loudness = -16.0         # volume cible des captures, en LUFS
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
| `arr lyrics fetch [ARTISTE TITRE] [--force]` | paroles dans `lyrics.txt`, rangées par section ; par défaut, le morceau du projet |
| `arr analyze` | temps et tempo seulement, en quelques secondes (sans partition) |
| `arr sections list`, `arr sections set "intro:1-8 ..."` | sections, en numéros de mesure |

### Studio

| Commande | Effet |
|---|---|
| `arr capture [NOM] [--play] [--silence S] [--raw]` | enregistre ce que joue l'ordinateur dans un nouveau projet |
| `arr record PISTE [-w PISTE] [-o PISTE] [--count-in N] [--click] [--channel N]` | enregistre ton instrument sur le playback |
| `arr levels [--tone] [--seconds S] [--source NOM]` | vumètre par canal, pour vérifier le câblage et régler le gain |
| `arr calibrate [--channel N]` | mesure et note la latence d'enregistrement |
| `arr devices` | réglages audio effectifs et périphériques |

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
| `arr align t001 [--report]` | mesure le décalage d'une prise par section et le corrige par des réglages de calage |
| `arr nudge [PISTE] [-s SECTION] [--beats=N] [--ms=N] [--add] [--reset]` | montre, règle ou annule le calage d'une piste, en entier ou par section |
| `arr merge PISTE PISTE... --as NOM` | fusionne des pistes |
| `arr rm NOM... [-v VERSION] [--purge]` | retire des pistes, une version ou une prise ; corbeille du projet par défaut |
| `arr tracks [-v]`, `arr tracks PISTE` | ce qui joue (●), ce qui est muet (○), l'historique |
| `arr pick PISTE VERSION`, `arr gain PISTE DB`, `arr mute PISTE [--off]` | réglages du mix |
| `arr mix [-w PISTE] [-o PISTE]` | écrit `mix/mix.flac` |
| `arr play [PISTE] [VERSION]`, `arr play -w PISTE`, `arr play -o PISTE` | écoute le mix complet ou partiel, une piste, une version |
| `arr play -s SECTION[,SECTION...] [--loop] [--count-in N]` | ne joue que ces sections, enchaînées dans l'ordre donné (`-s a,b` ou `-s a -s b`) ; `--loop` rejoue jusqu'à Ctrl+C ; `--count-in` clique N mesures avant de commencer, une seule fois |
| `arr share PISTE` | `export/PISTE/` : `partie.mp3`, `mix.mp3`, `sans.mp3` |

### Machine

| Commande | Effet |
|---|---|
| `arr models pull` | installe les modèles et leurs moteurs, et les met à jour (réseau) |
| `arr doctor` | vérifie le GPU et la présence des moteurs |
| `arr check` | mesure chaque fichier du projet : durée, niveaux, volume, anomalies (silence, saturation, longueur, calage) |

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
  trash/           ce que `arr rm` a retiré ; `arr rm --purge trash` le vide
```

`score/` contient aussi `melody_vocal.mid`, `melody_instrumental.mid` et `chords.mid`, à
ouvrir dans MuseScore ou un séquenceur pour les partager avec le groupe.

## À savoir

- **Durées** pour 3 min 40 : transcription 3 à 12 min (plus long la première fois) ; une prise ~4 min 30 ; séparation ~20 s.
- **Greffe et calage** : une prise n'a jamais exactement la structure de l'original (un
  temps d'avance ici, une mesure en trop là). `arr split tNNN` mesure son décalage section
  par section et le corrige par des réglages de calage, que `arr nudge` montre, ajuste ou
  annule ; les fichiers audio ne sont pas modifiés. Une section ambiguë est signalée et se
  règle à la main.
- **Paroles** : sans `lyrics.txt`, la prise est instrumentale. Le découpage automatique par
  section est approximatif, à relire.
- **Licence** : les poids de YuE2 et SheetSage2 sont sous CC BY-NC 4.0 (usage non commercial).
- **Paroles et réseau** : `arr lyrics fetch` envoie l'artiste et le titre à lrclib.net,
  rien d'autre.
