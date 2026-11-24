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
| la capture ne s'arrête pas en fin de morceau | sans lecteur multimédia qui annonce le morceau, elle attend un silence ; le morceau suivant s'enchaîne | Ctrl+C à la fin, ou mettre le lecteur sur un seul morceau |
| la capture contient le début du morceau suivant | changement de titre non détecté | utiliser `--play`, ou couper la lecture automatique |
| `lecteur « X » introuvable` | `--player` ou le réglage `capture.player` ne correspond à aucun lecteur ouvert | ouvrir le lecteur, ou reprendre un nom de la liste affichée |
| `plusieurs lecteurs ouverts` avec `--play` | aucun ne joue, ou plusieurs jouent, et la commande ne tourne pas dans un terminal où poser la question | `--player NOM`, ou la ligne `player = ...` proposée dans `audio.toml` |
| `aucun lecteur multimédia ouvert` | `--play` sans lecteur sur la machine | lancer la lecture à la main, sans `--play` |
| `... ne sait pas revenir au début du morceau` ou `n'annonce aucun morceau` | le lecteur (souvent un navigateur, une radio) ne permet pas de se placer au début | lancer le morceau à la main, sans `--play` |
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
| `pas de sections (arr transcribe ou arr sections set)` | le projet n'a pas encore de sections | `arr transcribe`, ou les poser à la main avec `arr sections set` |
| `pas de décompte : le tempo est inconnu` | le projet n'a pas encore de grille de temps | `arr transcribe` ou `arr analyze` |
| le décompte tombe sur la musique | la section ne commence pas sur un temps fort | `arr sections snap`, ou redéfinir les sections en mesures : `arr sections set` |
| une section en boucle saute un bout de mesure à chaque tour, ou l'écran change de section à côté de la barre | les bornes viennent d'une transcription plus ancienne et ne tombent pas sur les mesures | `arr sections snap`, une fois par projet |
| `plus courtes qu'une mesure, retirées : ...` | deux bornes d'une section tombaient sur la même barre | rien à faire ; `arr sections set` pour la redécouper autrement |
| le BPM affiché est trop bas de quelques unités | projet analysé avant que le tempo ne soit corrigé | `arr analyze` |
| pas d'accords à l'écran pendant `arr play` ou `arr record` | le projet n'a pas de transcription, ou c'est une prise brute (`arr play t001`), qui n'est pas calée sur l'original | `arr transcribe` ; pour une prise, jouer ses pistes : `arr play t001.guitar` |
| les accords affichés ne sont pas ceux que j'ai écrits dans `score/score.abc` | l'écran montre les accords transcrits de l'original (`score/chord.lab`), pas la partition modifiée | pas de remède pour l'instant : se fier à la partition |
| les accords affichés sont décalés d'un ou deux temps sur un passage | la transcription a compté les mesures autrement que le morceau (une mesure courte non vue) | `arr analyze` : la grille d'accords suit ses mesures et les accords y sont replacés ; si le décalage reste, le signaler avec le passage |
| une mesure de la grille n'a que deux temps | le morceau a une mesure courte à cet endroit, vue par `arr analyze` | rien à faire : c'est la mesure telle qu'elle est jouée |
| `il manque … pour l'antisèche` | le morceau n'est pas transcrit, ou `arr analyze` seul a tourné | `arr transcribe` |
| `sheet.toml est mal écrit` | une faute de syntaxe dans le fichier (guillemet, crochet) | corriger la ligne indiquée, ou `arr sheet --reset` pour repartir de la proposition |
| l'antisèche ne suit plus le projet (sections ou accords refaits) | `sheet.toml` existe : il fait foi et n'est jamais réécrit | `arr sheet --reset`, l'ancien fichier reste dans `trash/` |
| les accords proposés sont faux ou la tonalité aussi | ils viennent de la transcription et de la détection de tonalité | les corriger dans `sheet.toml` (`arr sheet --edit`) |
| `pas d'accords : lance arr transcribe` (`arr chordpro`) | le morceau n'est pas transcrit | `arr transcribe` |
| `pas de grille de mesures : lance arr analyze` | la transcription n'a pas de temps, et `arr analyze` n'a pas tourné | `arr analyze` |
| `aucune section ne couvre une mesure` | les sections sont absentes ou toutes plus courtes qu'une mesure | `arr sections list`, puis `arr sections set` |
| `lyrics.txt : N balises pour M sections` | les balises de `lyrics.txt` ne suivent pas les sections une à une | une balise par section, dans l'ordre de `arr sections list` ; le fichier `.cho` est écrit sans paroles en attendant |
| `aucun accord — relis la transcription` | la transcription n'a trouvé aucun accord sur ce passage | vérifier le passage dans `arr play` ; la grille est écrite avec `N.C.` |
| un passage du `.cho` n'a qu'une ou deux mesures, ou porte un nom inattendu | le fichier suit les sections de l'original, découpées par la transcription | `arr sections set`, puis `arr chordpro` |
| `setlist inconnue` | le nom ne correspond à aucun fichier de `setlists/`, ou la commande est lancée ailleurs que dans le dossier des projets | `cd` dans le dossier des projets ; le message cite les setlists connues |
| `… n'est pas un projet de …` | le morceau donné n'est pas un dossier de projet de ce dossier | donner le nom du dossier du morceau, tel que `ls` le montre |
| `antisèches impossibles à imprimer` | un morceau de la setlist n'est pas transcrit, ou son dossier a été renommé | `arr transcribe` dans ce morceau, ou corriger son nom avec `arr set edit` |
| `texte petit, difficile à lire debout` | trop de contenu pour le nombre de feuilles demandé | alléger des antisèches (`arr sheet --edit`), ou augmenter `--pages` |
| `ne tient pas en N feuille(s)` | même au plus petit texte, le concert déborde | augmenter `--pages`, ou alléger des antisèches |
| un caractère devient `?` dans le PDF | il n'existe pas dans la police d'impression (symboles, alphabets non latins) | l'écrire autrement dans `sheet.toml` ou dans le titre |
| `groove de … : temps illisible` | un groupe de `rhythm` n'a pas 2, 3 ou 4 signes, ou contient autre chose que `x`, `-` et `.` | écrire un groupe par temps, séparés par des espaces : `x..x ..x. x-x. ...x` |
| les silences du rythme imprimé se touchent | beaucoup de silences courts dans un même temps | écrire le rythme en croches (deux signes par temps) là où c'est possible, ou passer en tablature |
| Espace et les flèches ne font rien pendant `arr play` | la commande ne lit pas le clavier : son entrée est redirigée, ou elle est lancée par un autre programme | lancer `arr play` directement dans un terminal |
| ← ou → saute cinq secondes au lieu d'une mesure | le projet n'a pas de mesures connues, ou c'est une prise brute (`arr play t001`) | `arr transcribe` ou `arr analyze` ; pour une prise, jouer ses pistes : `arr play t001.guitar` |
| je n'entends rien avec `arr play` | la sortie configurée n'est pas celle de vos enceintes | `arr devices` ; régler `[output]` |
| le fichier `mix/mix.flac` semble muet dans un lecteur | le lecteur joue sur une autre sortie | `arr play` joue le même mix sur la sortie configurée ; `arr check` montre son niveau |

## Pédales MIDI

| Symptôme | Cause | Remède |
|---|---|---|
| `aplaymidi est absent : installe alsa-utils` (ou `aseqdump`) | les outils du séquenceur ALSA ne sont pas installés | `pacman -S alsa-utils` (ou l'équivalent de votre distribution) |
| `port MIDI introuvable : « X »` | le fragment de nom ou l'adresse ne correspond à aucun port | `arr midi ports` donne la liste, puis corriger `midi.port` |
| `aucun port MIDI matériel` | l'interface qui porte la prise MIDI n'est pas branchée, ou elle n'expose pas de port MIDI | la rebrancher ; `arr midi ports` ; au besoin nommer un port à la main |
| `rien à envoyer` | `arr midi send` sans message | `--pc 5`, ou `--cc 7 --value 100` |
| la pédale ne réagit pas à `arr midi send` | câble MIDI absent ou inversé, mauvais canal, ou numéro de programme non attribué dans la pédale | d'abord vérifier que les octets sortent (ligne suivante) ; puis le câble (MIDI OUT de la carte vers MIDI IN de la pédale), le canal (`--channel`), et la table de correspondance de la pédale |
| savoir si les octets sortent vraiment de l'ordinateur | seul le noyau le dit ; une commande qui ne se plaint pas ne prouve rien | `cat /proc/asound/card<N>/midi0` avant et après un envoi : « Tx bytes » doit augmenter (le numéro de carte vient de `aplay -l`) |
| la pédale change de son, mais pas celui attendu | la pédale compte ses patches à partir de 0, ou sa table de correspondance en décide autrement | comparer avec l'octet affiché (`C0 04` = programme 5 chez `arr`) et régler la table de la pédale |
| `arr midi monitor` n'affiche rien | la pédale n'envoie pas ses changements de programme, ou son MIDI OUT n'est pas relié à l'entrée MIDI de la carte | activer l'envoi dans la pédale (chez Boss, « MIDI PC OUT »), vérifier le câble retour |

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
