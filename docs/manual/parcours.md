# Parcours

Les enchaînements de commandes pour les usages courants. Le détail de chaque option est dans
la [référence](reference.md).

## Travailler un morceau

Capturer un morceau qui joue sur l'ordinateur, le découper en pistes, jouer par-dessus.

```
arr levels                    # le son arrive-t-il sur les bons canaux ? régler le gain
arr capture --play            # enregistre le morceau en cours dans Spotify, du début à la fin
cd murder-on-the-dancefloor   # le projet porte le titre du morceau
arr split                     # sépare en pistes : drums, bass, guitar, piano, vocals, other
arr tracks                    # ce qui joue dans le mix
arr play --without bass       # le morceau sans la basse
```

- Pendant la lecture, `arr play` affiche ce qu'il joue : le mix (chaque piste avec sa version
  et son gain, et les pistes laissées de côté), une piste seule, ou une prise telle que
  rendue. L'écran suit la lecture : la section en cours, la suivante, et pour chaque piste le
  calage de la piste, celui de cette section et le total appliqué.
- Après `arr transcribe`, l'écran montre aussi la grille d'accords de la section en cours,
  de quoi jouer par-dessus. Ses mesures sont celles du morceau telles qu'`arr analyze` les
  compte, mesures courtes comprises ; les accords transcrits y sont replacés. Elle se lit comme une grille de jazz : une case par mesure, quatre
  mesures par rangée (deux dans un terminal étroit), chaque accord écrit sur le temps où il
  commence, puis un `/` par temps où il est tenu. L'accord du moment est surligné sur toute
  sa durée. Sous un séparateur, la première rangée de la section suivante reste affichée en
  gris, pour préparer l'enchaînement.

  ```
  Accords · chorus
  │ Dm    /     /     /     │ Fmaj7 /     C     /     │ Bb    /     /     /     │ C     /     /     /     │
  ── puis verse2 ──
  │ Dm    /     /     /     │ Dm    /     /     /     │ Dm    /     /     /     │ Dm    /     /     /     │
  ```
- Pendant la lecture, **Espace** met en pause et reprend, **←** revient au début de la
  mesure d'avant (plusieurs appuis : plusieurs mesures) et **→** passe à la suivante, y
  compris en pause. En boucle, → sur la dernière mesure revient à la première. Sans
  `arr transcribe` ni `arr analyze`, les flèches avancent par pas de cinq secondes.
- Une piste écoutée seule joue sans son gain de mix ; une prise brute, sans calage.
- Sans Spotify : `arr capture mon-projet`, puis lancez la lecture dans n'importe quel
  lecteur. L'enregistrement démarre au premier son et s'arrête après 3 secondes de silence.
- Avec un fichier que vous avez déjà : `arr init mon-projet --from morceau.flac`.
- Sur de la musique électronique, la distinction guitare/piano n'a pas de sens : `arr split
  --model htdemucs_ft` donne quatre pistes plus propres, ou `arr merge guitar piano other
  --as synth` réunit les pistes après coup.

## Répéter une partie

```
arr transcribe                           # trouve le tempo, les mesures et les sections
arr sections list
arr play -s chorus --loop --count-in 1   # le refrain en boucle, après une mesure de décompte
arr play -s verse,chorus -w bass         # couplet puis refrain, sans la basse
```

`arr analyze` suffit pour le tempo et les mesures, en quelques secondes ; les sections se
posent alors à la main : `arr sections set "intro:1-8 verse:9-24 chorus:25-40"`.

## S'enregistrer sur le morceau

```
arr calibrate                 # une fois par installation : mesure la latence
arr record bass-moi -w bass   # décompte d'une mesure, puis jouez ; le playback est sans la basse
arr tracks bass-moi           # vos prises, versionnées
arr play                      # le mix avec votre prise
arr gain bass-moi -5          # trop fort ? baissez-la dans le mix
arr pick bass-moi v001        # revenir à une prise précédente
arr rm bass-moi -v v002       # retirer une prise ratée
```

- Vous vous entendez par votre table ou votre carte son, pas par l'ordinateur.
- Pendant l'enregistrement, l'écran est celui d'`arr play` : les pistes du playback, la
  section en cours et sa grille d'accords, l'accord du moment surligné.
- `--click` garde le métronome pendant tout le morceau.
- Le décompte a besoin du tempo : `arr transcribe` ou `arr analyze` d'abord.

## Donner sa partie à un musicien

```
arr share bass
```

Crée `export/bass/` avec trois fichiers MP3 : `partie.mp3` (la piste seule), `mix.mp3` (le
mix avec elle) et `sans.mp3` (le mix sans elle, pour jouer par-dessus).

## Faire rejouer le morceau dans un autre style

```
arr transcribe                # la partition : mélodie, accords, tempo, tonalité, sections
arr lyrics fetch              # les paroles, rangées par section ; relisez lyrics.txt
arr render -s "funk pop cover, live band, female lead vocals, clean funk rhythm guitar, slap bass, tight drums, Rhodes" -n 2
arr takes                     # les prises, avec leur style et leur graine
arr play t001
```

- Le style se rédige en anglais, comme une liste : genre, formation, instruments, type de
  voix, ambiance. Il fixe la formation et la couleur, pas la partie de chaque instrument.
- `-n 2` rend deux prises de la même commande : comparez et gardez la meilleure.
- `--free` laisse l'accompagnement et parfois le tempo libres : plus surprenant, mais la
  prise ne se greffe plus sur l'original.
- Sans `lyrics.txt`, la prise est instrumentale.
- Pour changer la forme, les accords ou la tonalité, modifiez `score/score.abc`, puis
  relancez `arr render`.

Comptez 3 à 12 minutes pour la transcription et environ 5 minutes par prise.

## Tirer des parties d'une prise, ou les greffer sur l'original

```
arr split t001                        # pistes t001.drums, t001.guitar..., calées sur l'original
arr play t001.guitar                  # une partie de la prise, seule
arr graft t001 guitar piano           # ajoute ces parties à l'original
arr graft t001 drums bass --replace   # remplace batterie et basse de l'original
arr share t001.guitar                 # pour le guitariste
```

`arr split t001` cale la prise sur l'original et affiche le décalage trouvé dans chaque
section, avant et après. Une prise libre (`--free`), à un autre tempo, n'est pas calée : ses
parties restent écoutables seules.

## Caler une prise ou une piste

Quand une partie greffée sonne décalée, ou pour vérifier ce qui a été appliqué :

```
arr align t001 --report                       # le décalage mesuré par section, sans rien changer
arr nudge t001                                # les réglages en place sur tous les stems de la prise
arr nudge t001.vocals -s chorus7 --beats=-4   # cette section, quatre temps plus tôt
arr nudge t001.vocals -s verse2 --ms=-20      # un ajustement fin
arr nudge t001.vocals -s verse2 --add --ms=5  # ajouter 5 ms à la valeur en place
arr nudge t001.vocals -s chorus7 --reset      # annuler le réglage de cette section
arr nudge t001 --reset                        # tout annuler sur la prise
arr align t001                                # refaire le calage automatique
```

- Un décalage positif joue plus tard, un négatif plus tôt. Écrivez la valeur collée à
  l'option (`--ms=-20`), pour qu'un nombre négatif ne soit pas pris pour une option.
- Nommer une prise (`t001`) règle tous ses stems d'un coup ; nommer une piste n'en règle qu'une.
- `arr nudge` vaut pour n'importe quelle piste, y compris une que vous avez enregistrée.
- Dans son rapport, `arr align` signale les sections « ambiguës » (un passage qui se répète :
  plusieurs placements se valent) et celles « sans mesure fiable » (trop courtes, ou sans
  attaques nettes). Ce sont elles qu'il faut écouter et régler à la main.
- Le calage se fait par section. Si le décalage change au milieu d'une section, redécoupez-la
  d'abord avec `arr sections set`.

## Préparer son antisèche de scène

Un pense-bête par morceau : tonalité, tempo, structure, accords des passages clés, rappels.

```
arr sheet                             # l'antisèche, telle qu'elle est proposée
arr sheet --note "départ batterie"    # ajoute un rappel
arr sheet --edit                      # écrit sheet.toml et l'ouvre dans votre éditeur
arr sheet --transpose=-2              # le groupe joue un ton plus bas : tonalité et accords suivent
arr sheet --reset                     # revient à la proposition
arr sheet --pdf                       # écrit aussi export/sheet.pdf
```

```
Man! I Feel Like A Woman! – Shania Twain  F · 125 BPM
Intro 4 · C 20 · Pré 4 · R 17+2t · Int 3 · C 8 · Pré 4 · R 17 · Int 8 · Pont 4 · R 19 · Fin 12+2t
Couplet      Bb | Bb | Bb | Bb | Bb | Eb Bb | Bb | Bb | Bb | Eb Bb  ×2
Refrain      [F | F | F | F | F | Dm | Bb] ×2 | Gm | – ×3
```

- Il faut un morceau transcrit (`arr transcribe`).
- **La proposition** vient du projet. La structure compte les mesures de chaque passage
  (`C` couplet, `Pré` pré-refrain, `R` refrain, `Int` interlude) ; `+2t` signale deux temps
  en plus. Les accords sont ceux du passage tel qu'il revient le plus souvent, réduits à ce
  qui se répète : `×2` en bout de ligne pour tout le passage, `[...] ×2` pour un motif,
  `F ×4` pour une mesure tenue ; un long passage sans répétition est coupé (`…`).
- **Dès que `sheet.toml` existe, lui seul fait foi** : supprimez un bloc `[[parts]]` pour en
  montrer moins, ajoutez-en un pour un riff ou une fin, corrigez un accord ou la tonalité.
- Écrivez les accords dans la tonalité de l'original ; `transpose` les décale à l'affichage.
- `$EDITOR` choisit l'éditeur ; sans lui, `--edit` indique seulement le fichier à ouvrir.

## Préparer un concert : la setlist et ses feuilles

Une setlist est un fichier à part, `setlists/NOM.toml`, dans le dossier qui contient vos
projets. Elle ne garde que l'ordre du concert ; les antisèches restent avec les morceaux,
donc une nouvelle setlist les reprend telles quelles.

```
cd ~/Musique                                   # le dossier des projets
arr set new bar-du-port gala what-s-up maldon --title "Bar du Port, 14 novembre"
arr set add bar-du-port murder-on-the-dancefloor --at 2    # en deuxième
arr set add bar-du-port --break                            # un entracte
arr set show bar-du-port                       # ordre, tonalités, tempos, durée totale
arr set edit bar-du-port                       # réordonner, retirer, régler pour ce concert
arr set print bar-du-port --pages 3            # écrit setlists/bar-du-port.pdf
```

- **La feuille** : A4, deux colonnes, un bloc par morceau (rang, titre, tonalité, tempo, puis
  son antisèche). Chaque bloc prend la hauteur de son contenu : un morceau que vous connaissez
  bien, réduit à deux lignes dans son `sheet.toml`, laisse la place aux autres.
- **`--pages 3`** choisit la plus grande taille de texte qui fait tenir le concert sur trois
  feuilles. Sans lui, le texte garde sa taille normale. La commande prévient quand le texte
  devient petit : allégez alors des antisèches, ou ajoutez une feuille.
- **Pour un concert seulement** : dans le fichier, un morceau s'écrit `"gala"`, ou
  `{ song = "gala", transpose = -2, note = "enchaîner" }` ; `"---"` est un entracte. Cette
  transposition ne touche pas à l'antisèche du morceau.
- Un morceau non transcrit apparaît « incomplet » dans `arr set show` et bloque l'impression.
- `arr sheet --pdf` écrit `export/sheet.pdf` : l'antisèche d'un seul morceau, pour la voir.
- Les commandes `arr set` se lancent depuis le dossier des projets, ou depuis un projet.

## Vérifier un projet sans l'écouter

```
arr check
```

Une ligne par fichier : durée, niveaux, volume, et les anomalies (silence, saturation,
longueur différente de l'original, prise mal calée).

## Faire le ménage

```
arr rm guitar piano       # vers la corbeille du projet (trash/)
arr rm t002               # une prise et ses pistes
arr rm --purge trash      # vide la corbeille
```
