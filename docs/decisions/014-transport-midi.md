# 014 — Le transport MIDI d'une lecture part d'un port virtuel tenu ouvert

Date : 25 novembre 2026. État : en vigueur. Complète la fiche 011, qui reste vraie pour les pédales.

## Contexte

Cédric répète avec `arr play` et lit les accords sur le prompteur de namfoop, sur le même
ordinateur. Ce prompteur suit déjà un logiciel de scène par le MIDI : l'horloge (`F8`, 24 tops
par noire) donne le tempo et compte la position ; `Start` (`FA`) le pose sur le 1 de la mesure 1
du morceau et lance la battue ; le Song Position Pointer (`F2`, en doubles-croches depuis la
mesure 1) le déplace, même en marche ; `Stop` (`FC`) l'arrête. Il écoute tous les ports du
séquenceur ALSA sauf « Midi Through », y compris ceux qui apparaissent en cours de route.
Sa carte des mesures vient du fichier `.cho` qu'écrit `arr chordpro` (fiche 012).

## Ce qui a été comparé

| Moyen | Pourquoi pas, ou pourquoi |
|---|---|
| `aplaymidi` (fiche 011) | ne lit pas les messages de temps réel (`F8`, `FA`, `FC`) dans un fichier MIDI, et un fichier joué ne s'arrête ni ne saute avec la lecture |
| un `aplaymidi` par top | un sous-processus toutes les 20 ms, à 1,1-1,7 ms chacun : la gigue du lancement s'ajoute à chaque top |
| `python-rtmidi`, port virtuel | retenu : un port tenu ouvert le temps de la lecture, nommé, que le prompteur entend sans réglage |

## Décision

- **`arr play --clock`**, jamais par défaut : rien ne part sans la demande, et une pédale
  branchée ne reçoit pas d'horloge par surprise.
- **Port virtuel** « arr:transport » du séquenceur ALSA (`python-rtmidi`, API ALSA), ouvert le
  temps de la lecture. Pas de port matériel : le prompteur est sur le même ordinateur.
- **Les mesures sont celles du `.cho`** : la structure de l'original, la levée retirée, la
  dernière mesure complétée. Chaque mesure reçoit 24 tops par temps, répartis également entre
  son début et sa fin : l'horloge suit le tempo de l'enregistrement, et une mesure de 2/4
  compte 48 tops comme le prompteur l'attend. La dernière mesure complétée garde le tempo joué.
- **Avant la mesure 1** (décompte, levée, intro) : des tops sans transport, au tempo de la
  première mesure, pour que le prompteur verrouille son tempo (il lui faut une noire).
- **Séquence** : `Start` sur le premier top de la mesure 1 ; un départ ailleurs (`-s`) envoie
  la position puis `Continue` ; un top qui ne suit pas le précédent (section suivante,
  flèche, tour de boucle) est précédé de sa position ; la pause envoie `Stop`, la reprise la
  position puis `Continue` ; la fin et Ctrl+C, `Stop`.
- **Calage sur le son** : à chaque bloc, le flux audio dit sa position et l'heure où ce bloc
  sortira (`outputBufferDacTime`, borné à 0-500 ms) ; un fil envoie chaque top à l'heure où son
  instant sortira. Un écart de plus de 20 ms entre la position annoncée et celle attendue est
  un saut : le plan reprend à la nouvelle position. Le retard de sortie vient donc du flux,
  jamais d'un réglage.

## Mesures

Projet d'essai de 20 s à 120 à la noire, levée d'un temps, sur la sortie virtuelle de
`scripts/loopback.sh`, le port relu par un client du séquenceur ALSA :

- `--count-in 1` : 96 tops avant `Start` (une mesure de décompte et un temps de levée),
  `Start` 1,995 s après le premier top (2,000 attendu) ; `Stop` à Ctrl+C.
- Intervalle moyen 20,821 ms pour 20,833 attendu (0,06 % : l'horloge de la carte contre celle
  du système) ; médiane 20,746 ms, extrêmes 17,2 et 22,3 ms. La gigue vient du recalage à
  chaque bloc ; le prompteur mesure le tempo sur 24 intervalles et compte la position en tops,
  ce qu'elle ne déplace pas.
- `-s chorus,verse` : position 128 (mesure 9) puis `Continue`, et position 64 (mesure 5)
  quatre secondes plus tard.

## Ce qui n'est pas vérifié

Le prompteur lui-même : un agent ne le regarde pas. Côté namfoop, `Continue` ne relance pas
encore la battue : une reprise après pause, ou un départ par `-s`, posent le prompteur au bon
endroit sans le faire avancer, jusqu'à ce que namfoop le fasse.

## Conséquences

- `python-rtmidi` devient une dépendance, importée seulement par `--clock`.
- `arr midi monitor` ne voit pas ce port (il ne liste que des destinations) : `aseqdump -p arr` le montre.
- La suite possible : choisir le morceau sur le prompteur depuis `arr play` (un changement de
  programme), et l'horloge pendant `arr record`.
