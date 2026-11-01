# 009 — L'antisèche de scène appartient au morceau

Date : 12 octobre 2026. État : en vigueur.

## Contexte

Cédric veut poser au sol trois feuilles A4 pour un set de 20 à 25 morceaux : ordre, titre,
tonalité, tempo, puis rappels, accords des passages clés, structure, parfois un groove. Il
veut une proposition automatique qu'il amende, et réutiliser l'antisèche d'un morceau d'une
setlist à l'autre.

## Décision

- **L'antisèche vit dans le projet du morceau** (`sheet.toml`), pas dans la setlist : elle se
  réutilise d'elle-même. La setlist, à venir, ne gardera que l'ordre et les réglages du concert.
- **Proposition, puis fichier.** Tant que `sheet.toml` n'existe pas, l'antisèche est déduite
  du projet à chaque affichage (`sheet.propose`). Dès qu'il existe, lui seul fait foi et
  aucune commande ne le réécrit, sauf `--note` et `--transpose` qui y ajoutent une valeur.
  `--reset` l'envoie dans `trash/`.
- **Pas de fusion** entre le fichier et une proposition recalculée : un fichier modifié à la
  main ne doit pas changer parce que la transcription a été relancée.
- **Le fichier est écrit dans la tonalité de l'original** ; `transpose` (demi-tons) s'applique
  à l'affichage et à l'impression (`sheet.played`). Une setlist pourra imposer une autre
  valeur pour un concert sans toucher au fichier.
- **La proposition** : structure en mesures par passage (sections voisines de même type
  réunies, temps en plus signalés), et pour couplet, pré-refrain, refrain, pont et solo, les
  accords du motif le plus fréquent parmi les occurrences, réduits à ce qui se répète et
  bornés à 16 mesures.

## Limites

- Les accords et la tonalité viennent de la transcription : la proposition est à relire.
- Un passage dont les sections sont mal découpées donne une ligne longue ou coupée.
- Rappels et groove ne sont pas proposés : ils se saisissent.
