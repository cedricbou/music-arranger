# Parcours

Les enchaînements de commandes pour les usages courants. Le détail de chaque option est dans
la [référence](reference.md).

## Travailler un morceau

Capturer un morceau qui joue sur l'ordinateur, le découper en pistes, jouer par-dessus.

```
arr levels                    # le son arrive-t-il sur les bons canaux ? régler le gain
arr capture night-drive       # enregistre le morceau que vous lancez ensuite dans votre lecteur
cd night-drive
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
- L'enregistrement démarre au premier son et s'arrête après 3 secondes de silence. Avec un
  lecteur multimédia de bureau, `arr capture --play` nomme le projet d'après le morceau et le
  relance depuis le début ([configuration audio](audio.md), qui dit aussi ce qu'on a le droit
  de capturer).
- Avec un fichier que vous avez déjà : `arr init mon-projet --from morceau.flac`.
- Le dossier porte l'artiste puis le titre, `ls` les trie donc par artiste. Les accents
  perdent leur signe : « Hélène Faure » donne `helene-faure`. Pour nommer ainsi des
  morceaux plus anciens, lancez `arr rename` depuis le dossier des projets : la commande
  montre les renommages prévus, demande confirmation, puis met les setlists à jour. Un
  morceau sans artiste, ou dont le nom voulu est déjà pris, garde son dossier.
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

Une section qui ne boucle pas proprement vient d'une transcription plus ancienne : `arr
sections snap` pose ses bornes sur les barres de mesure, une fois pour tout le projet.

### Suivre le prompteur de scène pendant la lecture

```
arr chordpro                             # le fichier .cho que lit le prompteur (namfoop)
arr play --clock --count-in 1            # le prompteur part sur la mesure 1, après le décompte
arr play --clock -s chorus --loop        # il se pose sur le refrain, et y revient à chaque tour
```

Avec `--clock`, `arr` ouvre le port MIDI virtuel « arr:transport » et y envoie l'horloge
(24 tops par noire, au tempo de l'enregistrement) et le transport : Start sur la mesure 1,
la position au début d'une section, à chaque flèche et à chaque tour de boucle, Stop à la
pause et à l'arrêt. Un prompteur sur le même ordinateur qui écoute tous les ports MIDI,
comme namfoop, le suit sans réglage ; choisissez-y d'abord le morceau.

- Les mesures sont celles du fichier ChordPro : la mesure 1 est la première mesure pleine,
  la levée n'en fait pas partie. Pendant le décompte et la levée, l'horloge ne donne que le tempo.
- `--clock` a besoin des mesures du morceau : `arr transcribe` d'abord. Une prise brute
  (`arr play t001`) n'est pas calée sur l'original et refuse l'horloge.

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

## Piloter sa pédale d'effets

Si votre carte son a une prise MIDI OUT reliée à l'entrée MIDI d'un multi-effets, `arr` peut
lui envoyer des messages. D'abord pour vérifier que tout est en place :

```
arr midi ports                  # les ports MIDI ; ▶ marque celui qu'arr utilise
arr midi send --pc 5            # la pédale doit changer de son
arr midi send --cc 7 --value 0  # un contrôleur, ici le volume à 0
arr midi monitor                # ce que la pédale envoie quand vous appuyez dessus
```

- Les numéros de programme vont de 1 à 128, comme sur la pédale. Les octets envoyés sont
  affichés : si votre pédale compte à partir de 0, l'écart se voit tout de suite.
- La pédale doit écouter le même canal : `--channel N`, ou `midi.channel` dans `audio.toml`.
- Rien n'est jamais écrit dans la pédale : aucun patch n'est modifié.

Les réglages, les autres installations et les pannes courantes sont dans [Configuration
audio](audio.md) et [Dépannage](depannage.md).

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
- `arr lyrics fetch` garde aussi `lyrics.lrc`, l'instant de chaque ligne. `arr lyrics show`
  montre les paroles section par section, chaque ligne avec la mesure où elle commence. Une
  ligne corrigée dans `lyrics.txt` garde la mesure de celle qu'elle remplace ; une ligne
  ajoutée n'en a pas. Pour un projet aux paroles déjà corrigées, `arr lyrics fetch --times`
  n'écrit que `lyrics.lrc`, sans toucher à `lyrics.txt`.
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
Night Drive – Paper Lanterns  Dm · 121 BPM
Intro 4 · C 16 · Pré 4 · R 16+2t · Int 4 · C 16 · R 16 · Fin 8
Couplet      Dm | Dm | Bb | C | Dm | Dm | Bb | A  ×2
Refrain      [F | C | Dm | Bb] ×2 | Gm | – ×3
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

Pour rappeler un **groove**, ajoutez un bloc `[[grooves]]` dans `sheet.toml` :

```toml
[[grooves]]
instrument = "basse"
part = "Couplet"
rhythm = "x..x ..x. x-x. ...x | x--- .... x-x- xxxx"

[[grooves]]
instrument = "basse"
part = "Refrain"
tab = ["G|----------------|", "D|--------5---5-7-|", "A|3---3-5---5-----|", "E|----------------|"]
```

- `rhythm` s'écrit un groupe par temps : quatre signes pour des doubles croches, trois pour
  un triolet, deux pour des croches. `x` est une attaque, `-` une note tenue, `.` un silence,
  `|` sépare deux mesures. Il est imprimé en notation rythmique : têtes, hampes, ligatures,
  points, liaisons et silences. Une tenue en début de temps lie la note à celle d'avant.
- `tab` est imprimé tel quel, en police à chasse fixe : alignez vos lignes.
- Rien n'est proposé automatiquement pour le groove : il se saisit.

## Emporter le morceau sur le prompteur de scène

Un prompteur de scène (celui de namfoop, ou tout lecteur ChordPro) lit le morceau dans un
fichier `.cho` : les accords mesure par mesure, les paroles en repère.

```
arr chordpro            # écrit export/<dossier du projet>.cho et dit ce qu'il contient
arr chordpro --show     # le montre ici, passage par passage, sans l'écrire
```

```
Night Drive → export/night-drive.cho   Dm · ♩121 · 4/4 · 74 mesures · 2:27
  structure de l'original · accords de la transcription · paroles de lyrics.txt, placées par lyrics.lrc

  Intro         4 mes.   1 ligne de mesures
  Couplet 1    16 mes.   4 lignes de mesures · 8 lignes de paroles en repère
  Refrain       8 mes.   2 lignes de mesures, dont une mesure de 2 temps à 1:02 · 4 lignes de paroles en repère
  Couplet 2    16 mes.   4 lignes de mesures · 8 lignes de paroles en repère
  Refrain       8 mes.   comme le premier
```

- Il faut un morceau transcrit et sa grille de mesures (`arr transcribe`).
- **La structure** est celle de l'original : un passage par section de `arr sections list`,
  dans l'ordre. Les couplets sont numérotés, tous les refrains portent le même nom : le
  prompteur relie un son à un passage par son nom. Corrigez d'abord les sections
  (`arr sections set`) si leur découpage est faux, le fichier le reprend tel quel.
- **Une grille par passage**, quatre mesures par ligne, une case par temps : l'accord là où il
  commence, `.` tant qu'il tient, `N.C.` quand rien ne joue. Une mesure d'une autre longueur
  (deux temps dans du 4/4) a sa propre grille, entre deux changements de mesure, et le compte
  rendu dit à quel instant elle tombe : vérifiez-la à l'oreille. arr compte les temps, pas
  l'unité : la mesure est toujours écrite sur 4 (`2/4`, `4/4`, `3/4`).
- **Les mesures suivent la mesure du morceau** : une barre tous les quatre temps dans du 4/4,
  même là où `arr analyze` hésite un moment entre quatre et deux temps. Une mesure courte ne
  reste que là où les barres se décalent vraiment pour la suite du morceau. Les temps avant
  la première barre sont une levée, écrite en rappel (« levée de 2 temps ») au-dessus du
  premier passage ; la dernière mesure, coupée par la fin de l'enregistrement, est complétée.
- **Les paroles** de `lyrics.txt` suivent la dernière barre de la ligne de mesures où elles
  sont chantées, d'après `lyrics.lrc` (`arr lyrics show` le montre). Une ligne sans instant
  suit celle d'avant ; sans `lyrics.lrc`, les lignes sont réparties à parts égales sur leur
  passage. Il faut une balise par section, dans le même ordre ; sinon le fichier est écrit
  sans paroles et la commande le signale.
- **La tonalité** est celle que joue le groupe : le `transpose` de `sheet.toml` s'il existe.
- **Le fichier appartient à arr** : chaque appel le réécrit en entier. Corrigez le projet
  (sections, paroles, transposition), jamais le fichier. Copiez-le ensuite vous-même sur le
  prompteur.
- Le fichier est du ChordPro standard, sans directive propre à un lecteur. Un lecteur qui ne
  dessine pas les grilles en montre les lignes telles quelles.

## Préparer un concert : la setlist et ses feuilles

Une setlist est un fichier à part, `setlists/NOM.toml`, dans le dossier qui contient vos
projets. Elle ne garde que l'ordre du concert ; les antisèches restent avec les morceaux,
donc une nouvelle setlist les reprend telles quelles.

```
cd ~/Musique                                   # le dossier des projets
arr set new printemps night-drive blue-hour riviere --title "Concert de printemps"
arr set add printemps fil-rouge --at 2         # en deuxième
arr set add printemps --break                  # un entracte
arr set show printemps                         # ordre, tonalités, tempos, durée totale
arr set edit printemps                         # réordonner, retirer, régler pour ce concert
arr set print printemps --pages 3              # écrit setlists/printemps.pdf
```

- **La feuille** : A4, deux colonnes, un bloc par morceau (rang, titre, tonalité, tempo, puis
  son antisèche). Chaque bloc prend la hauteur de son contenu : un morceau que vous connaissez
  bien, réduit à deux lignes dans son `sheet.toml`, laisse la place aux autres.
- **`--pages 3`** choisit la plus grande taille de texte qui fait tenir le concert sur trois
  feuilles. Sans lui, le texte garde sa taille normale. La commande prévient quand le texte
  devient petit : allégez alors des antisèches, ou ajoutez une feuille.
- **Pour un concert seulement** : dans le fichier, un morceau s'écrit `"night-drive"`, ou
  `{ song = "night-drive", transpose = -2, note = "enchaîner" }` ; `"---"` est un entracte. Cette
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
