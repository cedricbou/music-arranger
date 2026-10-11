# 008 — Une seule grille de mesures : celle d'`arr analyze`

Date : 12 octobre 2026. État : en vigueur.

## Contexte

Depuis l'affichage des accords, `arr play` et `arr record` lisaient deux grilles : les temps
de la transcription (SheetSage2, `score/beat.lab`) pour la grille d'accords et les flèches,
et ceux d'`arr analyze` (beat_this, `analysis.json`) pour le décompte et le clic. Sur « Man!
I Feel Like A Woman! », Cédric a vu les accords se décaler de deux temps dans le dernier
refrain : le morceau prend une mesure à deux temps à la fin du pont, que la transcription
n'a pas vue.

## Ce que la mesure a montré

Sur neuf projets, pour chaque barre de mesure, le changement d'harmonie entre avant et après
(chroma de l'original) :

- Les barres propres à `arr analyze` portent autant de changements d'harmonie que les barres
  communes aux deux grilles (0,65 contre 0,60 sur Gala ; 0,58 contre 0,65 sur Maldòn). Celles
  propres à la transcription n'en portent pas plus qu'un temps quelconque (0,37 ; 0,35).
- Les temps de la transcription sont irréguliers (intervalles de 0,34 à 0,65 s pour un temps
  de 0,46 s) : la moitié sont à plus de 100 ms d'un temps d'`arr analyze`, qui lui est régulier.
- Poser les accords tels quels sur la grille d'`arr analyze` ne suffit pas : ils changent
  alors au milieu des mesures (97 % des changements sur une barre avant, 58 % après, sur Gala).

## Décision

- **La grille d'`arr analyze` est la référence** pour tout ce qui se compte en mesures :
  décompte, clic, grille d'accords, flèches.
- **Les accords de la transcription sont replacés dessus** (`measure.seat_chords`) : là où
  les barres des deux grilles s'écartent d'un nombre entier de temps, les accords de la zone
  sont décalés pour retomber sur les barres de référence, vers l'avant ou vers l'arrière
  selon ce qui colle le mieux à l'harmonie de l'original.
- Rien n'est écrit dans le projet : le replacement est refait à chaque lecture (moins d'une
  seconde), et `score/` reste ce que la transcription a produit.
- Sans `analysis.json`, la grille reste celle de la transcription.

## Résultat mesuré

Ressemblance entre l'audio et les accords affichés (plus haut = mieux), et part des
changements d'accord qui tombent sur une barre :

| Projet | Avant | Après | Sur une barre, avant → après |
|---|---|---|---|
| Gala | 0,413 | 0,459 | 97 % → 99 % |
| Maldòn | 0,362 | 0,441 | 75 % → 73 % |
| The Less I Know The Better | 0,507 | 0,537 | 64 % → 65 % |
| Man! I Feel Like A Woman! | 0,454 | 0,455 | 84 % → 84 % |

La ressemblance monte sur les neuf projets. Sur « Man! I Feel Like A Woman! », la grille
montre désormais la mesure à deux temps à 178 s et le refrain qui suit sur ses barres.

## Limites

- Le choix entre « plus tôt » et « plus tard » repose sur l'harmonie : dans un passage sur un
  seul accord, les deux se valent et le choix est sans conséquence visible.
- Un accord que la transcription n'a pas vu (dans une mesure courte) reste absent.
- Les **étiquettes** d'accord ne sont pas corrigées : seul leur placement l'est.
- Aucun contrôle à l'oreille n'a été fait sur les huit autres projets.
