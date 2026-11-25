# 015 — Un temps entendu deux fois compte pour un

Date : 25 novembre 2026. État : en vigueur. Complète les fiches 008 et 013.

## Contexte

beat_this pose parfois deux temps à 80–120 ms l'un de l'autre pour un seul temps joué. La
grille d'accords pose une barre tous les N temps (fiche 013) : chaque temps en trop avance
d'un temps toutes les barres qui suivent, jusqu'à ce que la phase se recale. À l'écoute d'`arr
play` sur cinq morceaux : la grille passe à la mesure suivante un temps avant le « un » à la
fin d'un refrain, se perd sur la fin d'un autre, et un troisième montre des mesures de 1 à 7
temps. Les doublons faussent aussi la période : 90 bpm enregistrés pour un morceau à 85.

## Ce que la mesure a montré

- 13 des 39 projets de la bibliothèque ont des doublons : 1 à 8 chacun, 102 dans un morceau.
- Dans un doublon, le **second** temps est le vrai : son pic d'activation est le plus fort dans
  114 paires sur 116, et beat_this lancé sur la seule batterie tombe sur lui dans 97 paires,
  jamais sur le premier. Garder le temps le plus proche de la grille (précédent plus une
  période) se trompe 35 fois sur le morceau aux 102 doublons, où le temps précédent est
  lui-même bruité : invisible sur la grille, audible au clic (80 ms d'avance).
- beat_this ne fusionne que les pics à moins de 60 ms ; les doublons sont à 80–100 ms.
- Deux morceaux ont un passage compté au double (des temps à une demi-période) et un autre
  des temps à deux périodes : ce ne sont pas des doublons, et rien n'y change.

## Décision

- **`measure.clean_beats` retire le premier temps d'une paire** : un écart de moins d'une
  demi-période locale, nettement plus court que ses deux voisins, et le second temps à une
  période de ses voisins une fois le premier retiré. Une barre posée sur le premier passe au
  second. La période est locale (25 écarts autour), sans les écarts des paires.
- **Tout ce qui lit la grille passe par là** : écran d'`arr play` et d'`arr record`, fichier
  ChordPro, horloge MIDI, décompte, clic, `arr nudge --beats`, le tempo écrit par `arr analyze`
  et `arr transcribe`, et la grille donnée à la réécriture d'une partition refusée.
- **`analysis.json` garde ce que beat_this a détecté** : le nettoyage est refait à chaque
  lecture (comme les fiches 008 et 013), et les projets déjà analysés en profitent sans
  nouvelle analyse. Le tempo de `song.toml` et de la partition ne change qu'au prochain
  `arr analyze` ou `arr transcribe`.
- **La mesure d'une barre reste le nombre de temps comptés**, jamais sa durée divisée par
  la période : des passages comptés au double ou aux deux tiers la fausseraient.

## Résultat mesuré

`scripts/beat_report.py` sur la bibliothèque, avant → après : les 26 projets sans doublon
donnent un fichier ChordPro identique à l'octet. Sur les 13 autres, aucune barre de plus hors
des temps forts détectés (40 → 8 au total), aucune mesure irrégulière de plus (98 → 7) ;
lignes `{time:}` 197 → 27, dont 145 → 1 sur le morceau aux 102 doublons, qui passe de 106 à
73 mesures et de 90,3 à 85,2 bpm.

## Limites

- Un temps manqué (un écart de deux périodes) n'est pas comblé : une mesure de trois temps
  peut rester dans le fichier ChordPro, là où `arr play` est juste.
- Un doublon dans un passage compté au double ou à moitié n'est retiré que si ses voisins
  sont à une période locale.
- Sur les morceaux qui changent, les numéros de mesure et les positions de l'horloge MIDI
  changent aussi.
- Seuls cinq morceaux ont été écoutés avant ; aucun après.
