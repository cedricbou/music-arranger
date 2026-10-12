# Décisions

Une fiche par choix structurant : le contexte, ce qui a été essayé, les mesures, la décision.

- Une fiche est **datée et ne se réécrit pas**. Si une décision change, on ajoute une fiche
  qui dit laquelle elle remplace, et on note « remplacée par NNN » en tête de l'ancienne.
- Lire ces fiches **avant** de proposer une nouvelle approche de génération ou de toucher à
  la chaîne audio : la plupart des idées évidentes ont déjà été essayées et mesurées.
- Ce qui reste à faire n'est pas ici : c'est dans les issues GitHub.

| Fiche | Décision |
|---|---|
| [001](001-prises-completes-plutot-que-pistes.md) | Générer des prises complètes du morceau, pas des pistes isolées |
| [002](002-moteurs-en-sous-processus.md) | YuE2 et SheetSage2 tournent hors du processus d'arr |
| [003](003-chaine-audio-studio.md) | Capturer sur les entrées de la table, jouer et enregistrer en duplex |
| [004](004-calage-des-prises.md) | Mesurer le calage d'une prise au lieu de le supposer |
| [005](005-volume-des-captures.md) | Un seul gain vers une cible de volume pour chaque capture |
| [006](006-calage-par-sections.md) | Caler une prise par section, avec des réglages mémorisés (remplace la mesure de 004) |
| [007](007-provenance-des-modeles.md) | Les poids viennent de Hugging Face ; audio.cpp suit sa release officielle, version fixable |
| [008](008-grille-de-reference.md) | Une seule grille de mesures, celle d'`arr analyze` ; les accords transcrits y sont replacés |
| [009](009-antiseche-portee-par-le-morceau.md) | L'antisèche de scène vit dans le projet : proposition déduite, puis `sheet.toml` qui fait foi |
