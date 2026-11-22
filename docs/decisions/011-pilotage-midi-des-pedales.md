# 011 — Le MIDI passe par le séquenceur ALSA, en sous-processus

Date : 3 novembre 2026. État : en vigueur.

## Contexte

Cédric joue de la basse avec un multi-effets Boss GT-6B, relié en MIDI à la prise MIDI OUT
de la PreSonus AudioBox iTwo, elle-même sortie par défaut de l'ordinateur (fiche 003).
D'autres pédales viendront. Le but, à terme : changer de son tout seul au passage d'une
section pendant `arr play` et `arr record`. Avant cela, il faut pouvoir **envoyer un
message à la main** pour vérifier le câble, le canal et les réglages de la pédale.

## Ce qui a été comparé

| Moyen | Pourquoi pas, ou pourquoi |
|---|---|
| `python-rtmidi` (+ `mido`) | une dépendance compilée de plus, et ses ports virtuels ne servent qu'aux tests ; aucun besoin d'un port tenu ouvert pour un message tous les quelques secondes |
| `amidi` (ALSA rawmidi) | n'adresse que les ports matériels : impossible de tester sans envoyer à la vraie pédale, ce que l'agent n'a pas le droit de faire |
| `aseqsend` (séquenceur ALSA) | **écarté après mesure** : il affiche « Sent : 2 bytes » et rien n'atteint la carte (voir Mesures) |
| `aplaymidi` / `aseqdump` (séquenceur ALSA) | retenu : aucune dépendance Python, les octets sortent vraiment, et le port noyau « Midi Through » sert de bouclage pour les tests |

Le projet parle déjà à l'extérieur de cette façon : `parec` et `pactl` pour l'audio, D-Bus
pour Spotify. Le MIDI suit la même règle.

## Décision

- **Envoi** : `aplaymidi -d 0 -p <adresse> <fichier>` en sous-processus. L'outil ne joue
  qu'un fichier MIDI, donc `midi.smf()` fabrique un fichier minimal (tous les messages au
  temps zéro, dans l'ordre) dans un dossier temporaire ; `-d 0` supprime les deux secondes
  d'attente qu'`aplaymidi` ajoute après la fin.
- **Écoute** : `aseqdump -p <adresse>`, dont les lignes sont rendues telles quelles par
  `midi.events()` ; `arr midi monitor` les affiche.
- **Ports** : `aplaymidi -l`, qui ne liste que des destinations possibles. `System`, `Midi Through` et `PipeWire` ne mènent à aucun
  instrument : jamais choisis automatiquement, mais utilisables si on les nomme.
- **Réglages** : section `[midi]` d'`audio.toml` (`port`, `channel`), à côté du son.
  `studio.user_settings()` reste le seul lecteur du fichier ; chaque module y complète sa
  propre section par ses défauts.
- **Numérotation** : les programmes vont de 1 à 128, comme les affichent les pédales, et la
  sortie reprend les octets réellement envoyés (`changement de programme 5, canal 1 (C0
  04)`). Un désaccord de numérotation avec la pédale se voit donc sans sonde.
- **Rien n'est écrit dans la pédale** : ni SysEx, ni sauvegarde, ni restauration de patches.
  `arr` n'envoie que des changements de programme, des contrôleurs et des sélections de
  banque, tous sans effet durable sur l'appareil.

## Mesures

Le compteur du noyau `/proc/asound/card<N>/midi0` (« Tx bytes ») dit combien d'octets sont
réellement partis vers l'appareil USB. Essais sur le clavier branché, jamais sur la pédale :

| Outil | Tx bytes après envoi |
|---|---|
| `amidi -S` (rawmidi, hors séquenceur) | +2 |
| `aplaymidi -d 0` | +2 |
| `aseqsend`, trois essais | **0**, alors qu'il affiche « Sent : 2 bytes » |

- `aseqsend` 1.2.16 (alsa-utils 1.2.16) n'atteint donc pas la carte, et son échec est muet.
  Le bouclage par « Midi Through » ne le voyait pas : ce port du noyau renvoie les événements
  du séquenceur sans passer par un pilote de carte. **Un bouclage logiciel ne prouve pas
  qu'un octet sort de l'ordinateur ; seul le compteur du noyau le prouve.**
- Un envoi par `aplaymidi -d 0` coûte **1,1 à 1,7 ms** (cinq essais, lancé depuis Python) :
  assez précis pour déclencher un changement de patch sur une frontière de section. Sans
  `-d 0`, l'outil attend deux secondes de plus (mesuré : 2002 ms).
- Bouclage par « Midi Through » : banque 2 puis programme 5 sur le canal 2 envoyés, relus
  par `aseqdump` dans l'ordre (`controller 0, value 0`, `controller 32, value 1`,
  `1, program 4`). C'est le test `test_midi_goes_out_and_comes_back_through_the_alsa_loopback`
  (`-m slow`, hors CI). Il vérifie les octets et leur ordre, pas la sortie physique.

## Ce qui n'est pas vérifié

La réaction de la pédale elle-même : un agent ne doit pas lui envoyer de message. Côté
pédale, le manuel du GT-6B demande que le canal de réception corresponde (ou « Omni On »),
et c'est sa table de correspondance qui décide quel patch répond à quel numéro : par défaut
le programme 1 appelle U1-1, le 5 appelle U2-1, et le réglage « MIDI Map Select » choisit
entre cette table par défaut (`Fix`) et celle de l'utilisateur (`Prog`). La table
d'implémentation du GT-6B n'a pas été retrouvée pour la sélection de banque ; `--bank` envoie
les contrôleurs 0 (MSB) et 32 (LSB) comme le font les Boss plus récents, à confirmer à
l'usage. Une pédale qui ignore la banque ne retient que le changement de programme.

## Conséquences

- Pour tester le MIDI, on envoie sur « Midi Through » et on relit avec `aseqdump`. Jamais
  vers la pédale, comme on ne joue jamais sur les enceintes.
- `alsa-utils` devient un prérequis, mais seulement pour `arr midi` : son absence est
  expliquée (`aplaymidi est absent : installe alsa-utils`), et rien d'autre n'en dépend.
- La suite, hors de cette fiche : un patch par section (plutôt dans `sheet.toml`, qui fait
  foi pour la scène, fiche 009), une avance au déclenchement parce que la pédale coupe le
  son le temps de changer de patch, le patch affiché à l'écran et sur l'antisèche imprimée,
  et plusieurs pédales nommées dans `[midi.<nom>]` quand la deuxième arrivera.
