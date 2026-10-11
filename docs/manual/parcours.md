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
- Après `arr transcribe`, l'écran montre aussi les accords de la section en cours, quatre
  par rangée, celui du moment surligné, et les premiers accords de la section suivante :
  de quoi jouer par-dessus.
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
  section en cours et ses accords, celui du moment surligné.
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
