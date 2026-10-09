# Dépannage

Cherchez le message affiché ou le symptôme. `arr devices`, `arr levels` et `arr check` sont
les trois commandes de diagnostic.

## Installation

| Symptôme | Cause | Remède |
|---|---|---|
| `xpu: indisponible` | les pilotes Intel manquent, ou la machine n'a pas de carte Arc | installer `intel-compute-runtime` et `level-zero-loader` ; sans carte Arc, les commandes à modèle ne sont pas utilisables |
| `absent (arr models pull)` dans `arr doctor` | un moteur n'est pas installé | `arr models pull` |
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
| je n'entends rien avec `arr play` | la sortie configurée n'est pas celle de vos enceintes | `arr devices` ; régler `[output]` |
| le fichier `mix/mix.flac` semble muet dans un lecteur | le lecteur joue sur une autre sortie | `arr play` joue le même mix sur la sortie configurée ; `arr check` montre son niveau |

## Pistes et prises

| Symptôme | Cause | Remède |
|---|---|---|
| `piste inconnue` ou `prise inconnue` | faute de frappe, ou piste retirée | le message liste les noms connus ; `arr tracks`, `arr takes` |
| le mix sonne doublé | deux pistes du même instrument jouent ensemble | `arr tracks`, puis `arr mute` |
| du piano ou du synthé dans la guitare | le modèle à six pistes confond ces instruments | `arr split --model htdemucs_ft`, ou `arr merge` |
| `tNNN ne suit pas la grille de l'original` | la prise a dérivé en tempo ou en nombre de mesures | rendre une autre prise ; ses parties restent écoutables seules |
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
