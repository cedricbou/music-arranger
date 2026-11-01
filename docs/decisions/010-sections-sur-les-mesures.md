# 010 — Les sections tombent sur les mesures de référence

Date : 1er novembre 2026. État : en vigueur. Complète la fiche 008.

## Contexte

Sur Starlight, Cédric n'arrivait pas à boucler proprement `verse6`, et trouvait le suivi à
l'écran moins précis qu'au temps où tout venait de la transcription. La fiche 008 avait mis
décompte, clic, accords et flèches sur la grille d'`arr analyze`, mais pas les sections :
leurs bornes restaient celles de SheetSage2, sur sa propre grille.

## Ce que la mesure a montré

Sur les deux versions de Starlight, avec le kick du stem de batterie comme référence :

- Le morceau est parfaitement régulier : 127,52 BPM, une mesure de 1,882 s, aucune dérive. La
  basse se répète exactement toutes les 7,53 s (4 mesures). La musique n'est pas en cause.
- La grille d'`arr analyze` est bonne : 169 barres sur 169 sur le même rang de la pulsation,
  10 ms d'écart-type. Celle de la transcription place ses barres sur les quatre rangs, avec
  129 ms d'écart-type.
- Les bornes des sections sont jusqu'à 235 ms à côté de la pulsation, et leur écart n'est pas
  un nombre entier de mesures : `verse6` durait 14,76 s (14,54 s sur la radio edit) au lieu
  de 15,06 s. Chaque tour de boucle sautait donc 0,3 à 0,5 s trop tôt, et
  l'écran changeait de section à côté de la barre.
- `beat_this` donne des temps au pas de 20 ms. Une médiane d'intervalles reste sur ce pas :
  0,48 s, soit 125 BPM au lieu de 127,5. Le décompte et `song.toml` portaient cette erreur.
  Une boucle coupée sur deux barres brutes garde jusqu'à 20 ms d'erreur de durée.

## Décision

- **`arr transcribe` pose les bornes sur les barres les plus proches** (`measure.snap_sections`).
  `arr sections snap` fait de même pour un projet existant. Le début et la fin du morceau ne
  bougent pas, ni une borne qui tombe avant la première barre. Ce n'est pas refait à la lecture : une section posée à la main n'est jamais
  déplacée sans qu'on le demande.
- **Les barres utilisées sont lissées** (`measure.steady_bars`) : chacune est replacée sur la
  droite ajustée à ses huit voisines de chaque côté, pour retirer le pas de 20 ms. Une mesure
  de durée inhabituelle borne l'ajustement : une mesure à deux temps reste à sa place.
  `analysis.json` garde les valeurs brutes.
- **Le tempo se calcule par `audio.period`**, moyenne des intervalles normaux, partout.

## Limites

- Rien ne dit que la barre la plus proche est la bonne : une borne de transcription à deux
  temps d'une barre tombe sur l'une ou l'autre. `arr sections set` reste le dernier mot.
- Le découpage lui-même reste celui de SheetSage2 : sur Starlight, il garde des sections
  d'une mesure (`verse`, `verse7`).
- Les **accords** ne sont pas traités ici. Sur 13 projets, le replacement de la fiche 008 reste
  meilleur que l'accord brut sur 11 ; sur Starlight, aucune variante essayée ne gagne
  franchement. Le sujet est suivi dans une issue.
