# 013 — Une barre tous les N temps : la grille d'accords ne suit pas les hésitations de beat_this

Date : 25 novembre 2026. État : en vigueur. Complète la fiche 008.

## Contexte

La grille d'accords (écran de `arr play` et `arr record`, `arr chordpro`) pose une mesure par
barre détectée par `arr analyze` (fiche 008). Sur « Dans un autre monde », en 4/4 régulier à
120 bpm, le deuxième refrain sortait en six grilles, alternant 4/4 et 2/4 : les temps étaient
réguliers (un toutes les 0,50 s), mais beat_this posait une barre tous les deux temps pendant
quelques mesures, puis revenait à quatre. Le prompteur montrait des mesures que personne ne joue.

## Ce que la mesure a montré

Sur les 23 projets de la bibliothèque, en comptant les mesures dont la longueur n'est pas la
plus fréquente :

- 205 mesures inhabituelles en tout, dont 39 sur « Black or White » et 25 sur « Dans un autre
  monde », presque toutes des paires 2 + 2 au milieu d'un passage en 4/4.
- Les vraies mesures courtes se reconnaissent à ce qui suit : les barres restent décalées
  d'une demi-mesure pour la suite (pont de « Man! I Feel Like A Woman! » à 178 s, fiche 008).
  Une paire 2 + 2 retombe sur la même place.

## Décision

- **Les barres sont reposées tous les N temps**, N la longueur de mesure la plus fréquente,
  avant de construire la grille d'accords (`measure.regular_bars`). La place des barres dans
  la mesure (leur phase) se lit sur l'ensemble des barres détectées : elle ne change que si au
  moins trois barres le confirment, et une seule mesure courte marque alors le décalage.
- **Rien n'est réécrit** : `analysis.json` garde les barres de beat_this, le clic et le
  décompte aussi. Seule la grille d'accords, refaite à chaque lecture, en change.
- **Un morceau sans longueur dominante** (moins de 60 % des mesures à la même longueur) garde
  ses barres telles quelles.
- **Dans le fichier ChordPro**, les temps avant la première barre deviennent un rappel
  (« levée de 2 temps ») plutôt qu'une grille, et la dernière mesure, coupée par la fin de
  l'enregistrement, est complétée. Le compte rendu donne l'instant de chaque mesure courte gardée.

## Résultat mesuré

Mesures inhabituelles sur la bibliothèque : 205 → 37, dont la plupart sont la dernière mesure
du morceau. Lignes `{time:}` des neuf fichiers ChordPro exportés : 111 → 23 ; « Black or
White » 39 → 1, « Dans un autre monde » 13 → 5 (une mesure de deux temps dans le deuxième
refrain, une dans le troisième, où les barres se décalent vraiment), « Man! I Feel Like A
Woman! » 11 → 7 (la mesure courte du pont reste).

## Limites

- Un temps manqué ou en trop dans la liste des temps décale le compte : une mesure d'un temps
  peut apparaître là (« What's Up » à 38 s, « Dieu m'a donné la foi » à 7 s).
- Un morceau qui change vraiment de mesure pour un passage (du 3/4 dans du 4/4) est compté
  dans la mesure dominante si elle reste à plus de 60 %.
- Les bornes des sections restent posées sur les barres de beat_this (fiche 010) : dans un
  passage où beat_this hésitait, une borne peut tomber au milieu d'une mesure de la grille ;
  la mesure va alors à la section où tombe son milieu.
- Aucune écoute n'a confirmé les mesures courtes gardées.
