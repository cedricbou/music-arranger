# Dépannage

Cherchez le message affiché ou le symptôme. `arr devices`, `arr levels` et `arr check` sont
les trois commandes de diagnostic.

## Installation

| Symptôme | Cause | Remède |
|---|---|---|
| `xpu: indisponible` | les pilotes Intel manquent, ou la machine n'a pas de carte Arc | installer `intel-compute-runtime` et `level-zero-loader` ; sans carte Arc, les commandes à modèle ne sont pas utilisables |
| `absent (arr models pull)` dans `arr doctor` | un moteur n'est pas installé, ou une mise à jour d'`arr` l'a changé de place | `arr models pull` |
| `poids de beat_this absents (arr models pull)` | les temps se mesurent avec un modèle qui n'est pas encore téléchargé | `arr models pull` |
| `audio.cpp ... : empreinte inattendue` | l'archive téléchargée n'est pas celle que publie la release (téléchargement coupé ou archive modifiée) | relancer `arr models pull` ; si le message revient, rester sur la version précédente : `arr models pull --audiocpp vX.Y.Z` |
| `release d'audio.cpp introuvable` | la version demandée n'existe pas, ou GitHub ne répond pas | vérifier le nom (`v0.9.0`, avec le `v`) ; réessayer plus tard |
| `arr render` échoue ou rend autrement depuis une mise à jour | la nouvelle version d'audio.cpp se comporte différemment | `arr doctor` donne la version ; revenir à la précédente : `arr models pull --audiocpp vX.Y.Z` |
| `env: « arr »: Aucun fichier ou dossier de ce nom` à chaque Tab | `arr` est un alias et non un programme | remplacer l'alias par un lien : voir [Installation](installation.md) |
| `aucun projet ici (lance arr init <nom>)` | la commande n'est pas lancée depuis un dossier de projet | `cd` dans le projet |

## Capture

| Symptôme | Cause | Remède |
|---|---|---|
| le fichier capturé est vide ou silencieux | `arr` écoute une source ou des canaux où le son n'arrive pas | `arr levels` pendant qu'un morceau joue : repérer les canaux qui bougent, corriger `[capture]` |
| `en attente du son...` ne démarre jamais | même cause, ou le lecteur joue sur une autre sortie | `arr levels` ; vérifier la sortie utilisée par le lecteur |
| `aucun son reçu` | arrêt par Ctrl+C avant tout signal | voir ci-dessus |
| la capture ne s'arrête pas en fin de morceau | sans Spotify, elle attend un silence ; le morceau suivant s'enchaîne | Ctrl+C à la fin, ou mettre le lecteur sur un seul morceau |
| la capture contient le début du morceau suivant | changement de titre non détecté | utiliser `--play`, ou couper la lecture automatique |
| `source PipeWire introuvable` | le nom dans `capture.source` n'existe pas | copier le nom exact depuis `arr devices` |
| le niveau varie d'une capture à l'autre | capture faite avec `--raw`, ou projet créé par `arr import` | laisser `arr capture` normaliser ; `arr check` montre le volume de chaque fichier |

## Lecture et enregistrement

| Symptôme | Cause | Remède |
|---|---|---|
| `périphérique introuvable : « X » avec N canaux` | le fragment de nom ne correspond à rien, ou le périphérique a moins de canaux | `arr devices`, puis corriger `device` ou `channels` |
| `impossible d'ouvrir l'entrée et la sortie ensemble` | l'entrée et la sortie ne peuvent pas partager un flux | nommer les deux périphériques dans `audio.toml`, avec des noms pris dans `arr devices` |
| `rien n'a été enregistré sur ce canal : la prise n'est pas gardée` | l'instrument n'est pas sur ce canal, ou le gain est à zéro | `arr levels`, puis `--channel N` ou `input.channels` |
| ma prise est en retard sur le morceau | latence non mesurée | `arr calibrate` |
| `rien n'est revenu sur l'entrée` pendant `arr calibrate` | la sortie ne revient sur aucune entrée | relier une sortie à l'entrée, ou `--channel` vers la voie où revient le son |
| `pas de décompte : le tempo est inconnu` | le projet n'a pas encore de grille de temps | `arr transcribe` ou `arr analyze` |
| le décompte tombe sur la musique | la section ne commence pas sur un temps fort | redéfinir les sections en mesures : `arr sections set` |
| pas d'accords à l'écran pendant `arr play` ou `arr record` | le projet n'a pas de transcription, ou c'est une prise brute (`arr play t001`), qui n'est pas calée sur l'original | `arr transcribe` ; pour une prise, jouer ses pistes : `arr play t001.guitar` |
| les accords affichés ne sont pas ceux que j'ai écrits dans `score/score.abc` | l'écran montre les accords transcrits de l'original (`score/chord.lab`), pas la partition modifiée | pas de remède pour l'instant : se fier à la partition |
| l'accord surligné change un peu avant ou après le temps | le moment du changement est celui que la transcription a trouvé, pas la grille des temps | lire l'accord suivant d'avance ; la grille entière de la section est affichée pour cela |
| je n'entends rien avec `arr play` | la sortie configurée n'est pas celle de vos enceintes | `arr devices` ; régler `[output]` |
| le fichier `mix/mix.flac` semble muet dans un lecteur | le lecteur joue sur une autre sortie | `arr play` joue le même mix sur la sortie configurée ; `arr check` montre son niveau |

## Pistes et prises

| Symptôme | Cause | Remède |
|---|---|---|
| `piste inconnue` ou `prise inconnue` | faute de frappe, ou piste retirée | le message liste les noms connus ; `arr tracks`, `arr takes` |
| le mix sonne doublé | deux pistes du même instrument jouent ensemble | `arr tracks`, puis `arr mute` |
| du piano ou du synthé dans la guitare | le modèle à six pistes confond ces instruments | `arr split --model htdemucs_ft`, ou `arr merge` |
| une partie greffée sonne décalée | la prise n'a pas la structure de l'original (temps d'avance, mesure en trop) | `arr align tNNN --report` pour voir le décalage par section, `arr align tNNN` pour le corriger |
| une section reste décalée après `arr align` | section « ambiguë » ou « sans mesure fiable » dans le rapport | la régler à la main : `arr nudge tNNN -s SECTION --beats=N` |
| le décalage change au milieu d'une section | le calage se fait par section entière | redécouper la section : `arr sections set` |
| `le tempo est inconnu : utilise --ms` | `--beats` sans grille de temps | `--ms`, ou `arr transcribe` / `arr analyze` d'abord |
| `No such option: -20` avec `arr nudge` | un nombre négatif pris pour une option | coller la valeur : `--ms=-20`, `--beats=-1` |
| `indique la piste ou la prise à décaler` | `arr nudge` avec une valeur mais sans nom | `arr nudge PISTE --ms=N` |
| je ne sais plus ce qui a été décalé | les réglages sont mémorisés | `arr nudge` les liste ; `--reset` les annule |
| `tNNN est à un autre tempo que l'original` | prise libre (`--free`) | une prise libre ne se greffe pas |
| `pas de partition (arr transcribe)` | `arr render` sans transcription | `arr transcribe` |
| `la prise sera instrumentale` | pas de `lyrics.txt` | `arr lyrics fetch`, ou écrire le fichier |
| les paroles sont mal rangées par section | le découpage automatique est approximatif | corriger `lyrics.txt` à la main |
| `aucune parole trouvée` | titre ou artiste différents dans la base | `arr lyrics fetch "Artiste" "Titre"` avec l'orthographe exacte |
| une piste retirée par erreur | `arr rm` sans `--purge` | la reprendre dans `trash/` et la remettre sous `tracks/` |

## Quand rien ne correspond

`arr check` mesure chaque fichier du projet et signale silence, saturation, longueur
inattendue et calage. Joignez sa sortie et celle de `arr devices` ou `arr doctor` à votre
signalement.
