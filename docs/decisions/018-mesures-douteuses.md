# 018 — Une mesure douteuse est montrée, jamais corrigée

Date : 26 novembre 2026. État : en vigueur, un signal sur deux. Complète les fiches 013, 015 et 017.

## Contexte

Quand la grille est fausse, rien ne le dit : on le découvre en comptant. Dans les morceaux
écoutés pour la fiche 015, les passages faux étaient là où beat_this hésitait, mais cette
information était jetée. Deux signaux ont été retenus avec le musicien : un temps entendu
faiblement, et un désaccord sur la barre entre deux lectures des mêmes activations (le décodeur
de beat_this contre le DBN de madmom).

## Décision

- **`grid.doubtful_bars`** marque une mesure dont un temps a une activation sous 0,9 (le plus
  fort de sa trame et des deux voisines), et dit lequel. Les activations sont celles que garde
  `arr analyze` (fiche 017) ; sans elles, aucune marque.
- **Le doute se montre dans `arr play`** (« ? » devant la mesure, la raison sous la grille, d pour
  sauter au passage douteux suivant) et se relit par `arr review` (fiche 019). Il ne change ni la grille, ni
  les accords, ni le fichier du prompteur : `chart()` ne le reçoit pas.
- **`arr truth` mesure le doute contre les passages de référence** (fiche 016) : mesures fausses
  marquées, mesures justes marquées à tort.
- **Le plafond passe avant le rappel** : moins de 5 % des mesures d'un morceau sain.

## Ce que la mesure a montré

Sur les 39 projets de la bibliothèque (4 399 mesures), part des mesures marquées selon le seuil :
1,0 % à 0,6 ; 3,0 % à 0,8 ; 5,4 % à 0,9 ; 8,1 % à 0,95. À 0,9 : 26 morceaux sous 5 % (médiane
2,5 %), 7 de 5 à 10 %, 5 de 10 à 25 %, un à 49 % (le morceau dont le tempo se lit tantôt à la
noire, tantôt à la blanche). Un morceau a 2 passages douteux en médiane, 9 au plus. La reprise
symphonique : 14 %. À 0,95, quatre morceaux de plus passent les 5 %.

## Limites

- **Le second signal n'est pas livré** : le DBN de madmom ne s'installe que depuis son dépôt git,
  ce que la session n'a pas pu faire. Sans lui, une mesure fausse où beat_this est sûr de lui
  (une demi-mesure prise pour une mesure, activations de 0,64 à 0,99) n'est pas marquée.
- Le seuil de 0,9 n'est calé que sur le plafond : aucun passage de référence n'était repéré.
  Quels morceaux sont « sains » reste à dire par le musicien ; `arr truth` donnera le rappel.
- La probabilité de beat_this n'est pas une confiance calibrée : ses auteurs le disent trop sûr.
