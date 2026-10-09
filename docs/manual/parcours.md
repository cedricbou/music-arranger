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
arr split t001                        # pistes t001.drums, t001.guitar... ; dit si la prise est greffable
arr play t001.guitar                  # une partie de la prise, seule
arr graft t001 guitar piano           # ajoute ces parties à l'original
arr graft t001 drums bass --replace   # remplace batterie et basse de l'original
arr share t001.guitar                 # pour le guitariste
```

`arr split t001` mesure si la prise suit la grille de temps de l'original. S'il prévient
que la prise n'est pas superposable, ses parties restent écoutables seules, mais la greffe
sonnera décalée : rendez une autre prise.

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
