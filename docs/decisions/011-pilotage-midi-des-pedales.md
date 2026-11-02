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
| `aseqsend` / `aseqdump` (séquenceur ALSA) | retenu : aucune dépendance Python, et le port noyau « Midi Through » sert de bouclage pour les tests |

Le projet parle déjà à l'extérieur de cette façon : `parec` et `pactl` pour l'audio, D-Bus
pour Spotify. Le MIDI suit la même règle.

## Décision

- **Envoi** : `aseqsend -p <adresse> -s <fichier>` en sous-processus. L'outil n'envoie que
  le contenu d'un fichier (il n'accepte ni octets en argument, ni `/dev/stdin` : « cannot
  determine length »), donc `midi.send()` écrit les octets dans un fichier temporaire.
- **Écoute** : `aseqdump -p <adresse>`, dont les lignes sont rendues telles quelles par
  `midi.events()` ; `arr midi monitor` les affiche.
- **Ports** : `aseqsend -l`. `System`, `Midi Through` et `PipeWire` ne mènent à aucun
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

- Un envoi coûte **1,3 à 1,6 ms** (cinq essais, `aseqsend` lancé depuis Python) : assez
  précis pour déclencher un changement de patch sur une frontière de section.
- Bouclage par « Midi Through » : `C0 04` puis `B0 07 64` envoyés, relus par `aseqdump` en
  `Program change 0, program 4` et `Control change 0, controller 7, value 100`. C'est le
  test `test_midi_goes_out_and_comes_back_through_the_alsa_loopback` (`-m slow`, hors CI).

## Ce qui n'est pas vérifié

La réaction de la pédale elle-même : un agent ne doit pas lui envoyer de message. La table
d'implémentation du GT-6B n'a pas été retrouvée pour la sélection de banque ; `--bank` envoie
les contrôleurs 0 (MSB) et 32 (LSB) comme le font les Boss plus récents, à confirmer à
l'usage. Une pédale qui ignore la banque ne retient que le changement de programme.

## Conséquences

- Pour tester le MIDI, on envoie sur « Midi Through » et on relit avec `aseqdump`. Jamais
  vers la pédale, comme on ne joue jamais sur les enceintes.
- `alsa-utils` devient un prérequis, mais seulement pour `arr midi` : son absence est
  expliquée (`aseqsend est absent : installe alsa-utils`), et rien d'autre n'en dépend.
- La suite, hors de cette fiche : un patch par section (plutôt dans `sheet.toml`, qui fait
  foi pour la scène, fiche 009), une avance au déclenchement parce que la pédale coupe le
  son le temps de changer de patch, le patch affiché à l'écran et sur l'antisèche imprimée,
  et plusieurs pédales nommées dans `[midi.<nom>]` quand la deuxième arrivera.
