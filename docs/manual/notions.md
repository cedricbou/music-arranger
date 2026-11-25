# Notions

## Le projet

Un projet est un dossier, un par morceau. Toutes les commandes se lancent depuis ce dossier
ou l'un de ses sous-dossiers.

```
mon-morceau/
  song.toml        titre, artiste, tempo, tonalité, sections, état du mix
  lyrics.txt       paroles, avec des balises [Verse], [Chorus]...
  sheet.toml       l'antisèche de scène, une fois que vous l'avez modifiée
  analysis.json    temps et mesures détectés
  analysis_frames.npz  ce que le détecteur entendait entre les temps : sert à compter un temps manqué
  source/          le morceau original, en FLAC 48 kHz stéréo
  score/           la partition (score.abc), des fichiers MIDI, accords et structure
  takes/           les prises : t001.flac, t002.flac...
  tracks/<piste>/  les versions de chaque piste : v001.flac, v002.flac...
  mix/             le dernier mix
  export/          ce que `arr share` prépare pour un musicien
  trash/           ce que `arr rm` a retiré
```

`song.toml`, `lyrics.txt`, `sheet.toml` et `score/score.abc` sont des fichiers texte que vous pouvez
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
secondes. `arr transcribe` les trouve et pose leurs bornes sur les barres de mesure ; deux
parties de même nom sont numérotées (`chorus`, `chorus2`). `arr sections set` les redéfinit
en numéros de mesure, `arr sections snap` remet celles d'un projet plus ancien sur les
mesures. Elles servent à `arr play -s` et au rangement des paroles.

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
- `arr graft` fait entendre ces pistes dans le mix, en plus de l'original ou à sa place.

## Le calage

Une prise n'a jamais exactement la structure de l'original : elle peut avoir un temps
d'avance sur tout un passage, ou jouer une mesure de plus. Le **calage** corrige cela sans
toucher aux fichiers : chaque piste porte une liste de décalages, pour toute la piste ou
pour une section, gardée dans `song.toml` et appliquée à chaque écoute, mix ou export.

- `arr split t001` et `arr align t001` mesurent le décalage de la prise section par section
  et posent les réglages correspondants (origine « automatique »).
- `arr nudge` les montre, en pose d'autres à la main (origine « manuel »), les ajuste ou les
  annule. Un réglage de section s'ajoute à celui de la piste.
- Un décalage positif joue plus tard, un négatif plus tôt. Il s'exprime en temps (`--beats`)
  ou en millisecondes (`--ms`).
- `arr align` ne remplace jamais un réglage posé à la main.
- `arr tracks` marque « calée » toute piste qui porte un réglage.

L'outil ne sait pas générer une piste isolée qui s'accorde à un morceau existant : c'est
pourquoi il passe par des prises complètes.
