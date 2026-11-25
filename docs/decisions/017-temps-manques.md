# 017 — Un temps manqué se comble là où beat_this en a gardé la trace

Date : 26 novembre 2026. État : en vigueur. Complète les fiches 008, 013 et 015.

## Contexte

Dans une reprise symphonique, le chœur entre à 0:37 sans batterie : beat_this manque un temps,
la mesure montre 3 temps dans `arr play`, `{time: 3/4}` dans le fichier du prompteur, et
l'horloge MIDI ralentit le temps d'une mesure. La fiche 015 laissait ce cas en limite.

## Ce que la mesure a montré

beat_this ne pose un temps que là où son activation dépasse 0,5 (`File2Beats` jette ensuite les
activations). Sur les 39 projets de la bibliothèque, activations recalculées hors des projets
(elles redonnent, pour chacun, exactement les temps d'`analysis.json`) :

- au milieu d'un écart ordinaire entre deux temps (17 370 écarts), l'activation vaut 0,000 en
  médiane, 0,026 au 99e centile ; elle atteint 0,2 dans 0,2 % des cas ;
- au milieu des trous isolés (un écart de deux périodes entre des écarts d'une période), elle
  vaut 0,24 à 0,50 : 0,39 à 0:37 de la reprise ;
- la période se lit sur les seize écarts voisins : dans un passage compté à moitié, chaque
  écart vaut la période locale et rien n'y ressemble à un trou.

## Décision

- **`arr analyze` et `arr transcribe` gardent les activations** de beat_this dans
  `analysis_frames.npz` (temps et premiers temps, 50 trames par seconde), d'un seul passage du
  modèle. `analysis.json` reste ce que beat_this a détecté.
- **`grid.fill_beats` ajoute un temps** dans un écart de deux périodes locales (à 15 % près)
  dont les voisins font une période (à 15 % près), si l'activation atteint 0,2 à moins de 70 ms
  du milieu, à l'instant de ce pic. Après `clean_beats`, à chaque lecture de la grille
  (`song_grid`) : écran, fichier ChordPro, horloge, décompte, clic, tempo.
- **Sans activations** (projet analysé avant), rien n'est comblé : la sortie est identique.
- Les barres ne sont pas touchées : `regular_bars` les repose tous les N temps.

## Résultat mesuré

`scripts/beat_report.py --frames` sur la bibliothèque, sans → avec : 31 projets sans temps
ajouté donnent un fichier ChordPro identique à l'octet. Huit projets reçoivent 11 temps ; aucun
n'a plus de barres hors des temps forts détectés (17 → 11 au total) ni plus de mesures
irrégulières (8 → 7). La reprise : 2 temps ajoutés (0:37,94 et 3:40,02), la mesure de 3 temps
disparaît, lignes `{time:}` 3 → 1. Un autre morceau perd sa mesure de 3 temps dans un refrain ;
ailleurs une levée gagne un temps, une mesure de 1 temps en fait 2, une de 2 en fait 3.

## Limites

- Deux trous qui se suivent, ou un trou collé à un temps entendu deux fois, ne sont pas comblés.
- Le seuil de 0,2 n'est calé que sur l'écart entre ces deux populations : aucune écoute n'a
  confirmé les 11 temps ajoutés, et le plus faible (0,24) transforme une mesure de 2 temps en
  mesure de 3, pas de 4.
- Les stems (basse, « other ») entendent le temps manqué plus fort que le mix (1,00 et 0,93 à
  0:37) ; ils ne sont pas consultés, le mix suffisant ici.
- Les projets déjà analysés n'en profitent qu'après un nouvel `arr analyze`.
