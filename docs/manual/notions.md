# Notions

## Le projet

Un projet est un dossier, un par morceau. Toutes les commandes se lancent depuis ce dossier
ou l'un de ses sous-dossiers.

```
mon-morceau/
  song.toml        titre, artiste, tempo, tonalité, sections, état du mix
  lyrics.txt       paroles, avec des balises [Verse], [Chorus]...
  analysis.json    temps et mesures détectés
  source/          le morceau original, en FLAC 48 kHz stéréo
  score/           la partition (score.abc), des fichiers MIDI, accords et structure
  takes/           les prises : t001.flac, t002.flac...
  tracks/<piste>/  les versions de chaque piste : v001.flac, v002.flac...
  mix/             le dernier mix
  export/          ce que `arr share` prépare pour un musicien
  trash/           ce que `arr rm` a retiré
```

`song.toml`, `lyrics.txt` et `score/score.abc` sont des fichiers texte que vous pouvez
modifier à la main.

## L'original

Le morceau de départ, dans `source/original.flac`. Il vient de `arr capture`, de `arr init
--from` ou de `arr import`. Tout fichier importé est converti en FLAC 48 kHz stéréo.

## Les pistes et leurs versions

Une piste est un instrument ou un groupe d'instruments : `drums`, `bass`, `vocals`, ou votre
propre prise `bass-moi`. Elle a une ou plusieurs **versions** (`v001`, `v002`...), dont une
seule est **active** : celle qui joue dans le mix.

- Aucune commande n'écrase une version. Séparer à nouveau, s'enregistrer à nouveau, crée une
  version de plus.
- `arr tracks` montre ce qui joue (●) et ce qui est muet (○) ; `arr tracks PISTE` montre
  l'historique ; `arr pick` change la version active.
- Une piste a un **gain** (`arr gain`) et peut être **muette** (`arr mute`). Ces réglages
  agissent sur le mix, jamais sur le fichier.
- `arr rm` retire une piste ou une version vers `trash/` ; `--purge` efface pour de bon.

## Le mix

La somme des versions actives des pistes non muettes, avec leur gain. `arr play` le fait
entendre, `arr mix` l'écrit dans `mix/mix.flac`. `--without` et `--only` choisissent les
pistes pour une écoute sans changer les réglages.

## Les sections

Les parties du morceau (`intro`, `verse`, `chorus`...), chacune avec un début et une fin en
secondes. `arr transcribe` les trouve ; deux parties de même nom sont numérotées (`chorus`,
`chorus2`). `arr sections set` les redéfinit en numéros de mesure. Elles servent à `arr
play -s` et au rangement des paroles.

## La partition et les paroles

`arr transcribe` écrit `score/score.abc` : la mélodie, les accords, le tempo et la tonalité,
en notation ABC. `arr lyrics fetch` écrit `lyrics.txt`. Ces deux fichiers sont ce que `arr
render` donne au groupe virtuel.

## Les prises

Une prise (`t001`, `t002`...) est une interprétation **complète** du morceau, voix et groupe,
rendue par `arr render` à partir de la partition, des paroles et d'un texte de style.

- Une prise **fidèle** (par défaut) suit la mélodie et les accords de la partition.
- Une prise **libre** (`--free`) ne garde que la mélodie : l'accompagnement est réinventé.
- `arr split t001` sépare une prise en pistes `t001.drums`, `t001.guitar`..., créées muettes.
- `arr graft` fait entendre ces pistes dans le mix, en plus de l'original ou à sa place. La
  greffe ne sonne juste que si la prise suit la grille de temps de l'original ; `arr split
  t001` le mesure et prévient.

L'outil ne sait pas générer une piste isolée qui s'accorde à un morceau existant : c'est
pourquoi il passe par des prises complètes.
