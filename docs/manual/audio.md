# Configuration audio

`arr` a besoin de savoir quatre choses sur votre matériel :

| Question | Réglage | Commandes concernées |
|---|---|---|
| Où jouer le son ? | `[output]` | `arr play`, `arr record`, `arr calibrate`, `arr levels --tone` |
| Où écouter ce que joue l'ordinateur ? | `[capture]` | `arr capture`, `arr levels` |
| Sur quelle entrée est votre instrument ? | `[input]` | `arr record`, `arr calibrate` |
| Par où sortent les messages MIDI ? | `[midi]` | `arr midi send`, `arr midi monitor` |

Les réglages vivent dans `~/.config/arr/audio.toml`. Le fichier est facultatif : sans lui,
`arr` applique les valeurs par défaut décrites plus bas. La variable d'environnement
`ARR_AUDIO` désigne un autre fichier, par exemple pour garder un réglage par lieu :
`ARR_AUDIO=~/studio.toml arr record bass`.

## Trois commandes pour s'y retrouver

```
arr devices          # les réglages effectifs, et tout ce que la machine propose
arr levels           # un vumètre par canal de la source de capture ; Ctrl+C donne le bilan
arr levels --tone    # la même chose, en jouant un son de référence à -12 dB sur la sortie
```

`arr devices` affiche deux listes à ne pas confondre :

- les **sources PipeWire** (noms longs, `alsa_input...` ou `...monitor`) : ce sont les
  valeurs possibles de `source` dans `[capture]` ;
- les **périphériques** (noms lisibles, avec leurs nombres d'entrées et de sorties) : un
  fragment de leur nom suffit pour `device` dans `[output]` et `[input]`.

## Le fichier audio.toml

```toml
[output]
device = ""              # fragment du nom du périphérique ; "" = sortie par défaut du système
channels = [1, 2]        # canaux de sortie, à partir de 1

[input]
device = "Soundcraft"    # fragment du nom du périphérique ; "" = entrée par défaut du système
channels = [1]           # un canal = mono, deux = stéréo
latency_ms = 68.0        # écrit par arr calibrate ; à ne pas remplir à la main

[capture]
source = ""              # voir le tableau ci-dessous
channels = [7, 8]        # [] = la paire de canaux qui porte le signal
loudness = -16.0         # volume cible des captures, en LUFS

[midi]
port = ""                # fragment du nom du port MIDI, ou son adresse ; "" = le premier port matériel
channel = 1              # canal des messages envoyés aux pédales
```

| Clé | Valeurs | Sans réglage |
|---|---|---|
| `output.device` | fragment d'un nom de périphérique, ou `""` | sortie par défaut du système |
| `output.channels` | deux numéros de canaux | `[1, 2]` |
| `input.device` | fragment d'un nom de périphérique, ou `""` | la Soundcraft si elle est branchée, sinon l'entrée par défaut |
| `input.channels` | un ou deux numéros de canaux | `[1]` |
| `input.latency_ms` | écrit par `arr calibrate` | 21,3 ms, le minimum du système |
| `capture.source` | `""`, `"monitor"`, ou le nom d'une source PipeWire | voir ci-dessous |
| `capture.channels` | deux numéros de canaux, ou `[]` | `[7, 8]` avec la Soundcraft, sinon `[]` |
| `capture.loudness` | un volume en LUFS | `-16.0` |
| `midi.port` | fragment d'un nom de port MIDI, son adresse (`20:0`), ou `""` | le premier port matériel |
| `midi.channel` | un canal de 1 à 16 | `1` |

Les trois valeurs de `capture.source` :

| Valeur | Ce qui est enregistré |
|---|---|
| `""` | les entrées de la Soundcraft si elle est branchée ; sinon la copie numérique de la sortie par défaut |
| `"monitor"` | la copie numérique de la sortie par défaut : ce que l'ordinateur joue, sans passer par un câble |
| un nom de source | cette source précisément (copiez le nom depuis `arr devices`) |

## Quelle configuration pour quel matériel

### Une seule carte son, ou la carte intégrée

Le cas le plus simple : l'ordinateur joue sur une carte, votre instrument y est branché.

```toml
[input]
device = ""        # ou un fragment du nom de votre carte, ex. "Scarlett"
channels = [1]

[capture]
source = "monitor"
channels = []
```

- La capture prend la copie numérique de la sortie : aucun câble, aucun gain à régler.
- Sans ce fichier, c'est déjà le comportement par défaut quand aucune Soundcraft n'est
  branchée.
- Pour `arr calibrate`, il faut que la sortie revienne sur l'entrée : un câble de la sortie
  vers l'entrée de l'instrument, le temps de la mesure.

### Une carte de lecture et une table de mixage USB (l'installation de référence)

L'ordinateur joue sur une première carte (ici une PreSonus AudioBox iTwo), dont les sorties
arrivent en analogique sur les voies 7/8 d'une table USB (ici une Soundcraft Signature 12
MTK), qui renvoie tous ses canaux à l'ordinateur.

```toml
[output]
device = ""              # la carte de lecture est la sortie par défaut du système
channels = [1, 2]

[input]
device = "Soundcraft"
channels = [1]           # la voie de votre instrument

[capture]
source = ""              # les entrées de la table
channels = [7, 8]        # les voies où revient le son de l'ordinateur
```

- C'est le comportement par défaut dès qu'une Soundcraft est branchée : ce fichier n'est
  utile que pour changer la voie de l'instrument.
- Le gain se règle sur la table, voies 7/8, avec `arr levels` sous les yeux.
- `arr calibrate` n'a besoin d'aucun câble : le son de l'ordinateur revient déjà sur la
  voie 7.
- Pour éviter la table lors des captures : `source = "monitor"`.

### Une interface à plusieurs canaux pour tout

L'ordinateur joue sur l'interface, sur une paire de sorties précise.

```toml
[output]
device = "MonInterface"
channels = [3, 4]        # la paire de sorties reliée à vos enceintes

[input]
device = "MonInterface"
channels = [1]

[capture]
source = "monitor"
channels = []            # arr garde la paire de canaux qui porte le signal
```

### Un instrument en stéréo

```toml
[input]
channels = [5, 6]
```

`arr record PISTE --channel 3` choisit une entrée mono pour une seule prise, sans toucher
au fichier.

## Régler le niveau

1. Lancez un morceau, puis `arr levels`.
2. Les canaux marqués `▶` sont ceux qu'`arr capture` enregistrera. Ils doivent bouger.
3. Réglez le gain pour des crêtes entre -18 et -3 dB. Ctrl+C affiche le bilan :

| Bilan | Sens |
|---|---|
| rien | pas de signal sur ce canal |
| faible : monte le gain | crêtes sous -18 dB |
| bon niveau | crêtes entre -18 et -3 dB |
| très fort | crêtes au-dessus de -3 dB |
| SATURE : baisse le gain | le signal touche le maximum |

`arr capture` ramène ensuite chaque capture au même volume (`loudness`), par un seul gain
global : le réglage n'a pas besoin d'être identique d'un jour à l'autre, seulement de ne pas
saturer. `arr capture --raw` garde le niveau tel qu'enregistré.

## Mesurer la latence

Quand vous vous enregistrez, votre prise arrive en retard sur le playback. `arr calibrate`
mesure ce retard une fois pour toutes : il joue six clics, les réenregistre et note le
résultat dans `audio.toml`. `arr record` décale ensuite chaque prise d'autant.

- Il faut que la sortie revienne sur une entrée. Avec une table où le son de l'ordinateur
  revient déjà, rien à faire ; sinon, reliez une sortie à l'entrée de l'instrument.
- `arr calibrate --channel N` mesure sur une autre entrée.
- Refaites la mesure si vous changez de carte son ou de réglage de tampon.
- Sans mesure, `arr record` compense 21,3 ms, et vos prises seront un peu en retard.

## Pédales MIDI

Si votre carte son a une prise MIDI OUT, `arr` peut y envoyer des messages : de quoi faire
changer de son un multi-effets (un Boss GT-6B, par exemple) depuis l'ordinateur. Rien n'est
jamais écrit dans la pédale : aucun SysEx, aucune sauvegarde ni restauration de patches.

```
arr midi ports                     # les ports MIDI, et celui qu'arr utilise (marqué ▶)
arr midi send --pc 5               # changement de programme : la pédale doit changer de son
arr midi send --cc 7 --value 0     # un contrôleur, ici le volume à 0
arr midi monitor                   # ce que la pédale envoie, quand vous appuyez dessus
```

Le port à retenir est celui de l'interface qui porte la prise MIDI OUT (ici `iTwo`) ; les
ports `System`, `Midi Through` et `PipeWire` ne mènent à aucun instrument et ne sont jamais
choisis tout seuls.

- Les numéros de programme vont de **1 à 128**, comme les affichent les pédales. Les octets
  réellement envoyés sont repris dans la sortie (`changement de programme 5, canal 1
  (C0 04)`) : si votre pédale compte à partir de 0, l'écart se voit tout de suite.
- `--channel N` pour un autre canal que celui d'`audio.toml`, `--port NOM` pour un autre
  port, `--bank N` pour une banque (contrôleurs 0 et 32) avant le programme.
- La pédale doit écouter le même canal, et sa table de correspondance décide quel patch
  répond à quel numéro de programme (chez Boss : « MIDI » dans l'utilitaire).
- `arr midi monitor` ne montre rien si la pédale n'envoie pas ses changements de programme
  (chez Boss, le réglage « MIDI PC OUT ») ou si son câble MIDI OUT n'est pas branché.

## Spotify

`arr capture` lit le titre et l'artiste dans le lecteur Spotify de la machine, s'arrête au
changement de morceau, et avec `--play` relance le morceau depuis le début puis le met en
pause à la fin. Tout cela se fait en local. Sans Spotify, la capture démarre au premier son
et s'arrête sur le silence (`--silence`, 3 secondes par défaut) ou sur Ctrl+C.

**Ce qu'on a le droit de capturer.** Une capture sert à travailler un morceau chez soi, avec
son groupe. Capturez seulement des sources dont vous avez le droit de faire une copie privée :
CD, fichiers achetés, vos propres enregistrements. Les conditions d'utilisation de Spotify,
comme celles de la plupart des services de streaming, interdisent d'enregistrer leurs
contenus : lisez-les avant de capturer depuis un tel service. Ni les captures, ni les stems,
ni les prises tirées d'un morceau protégé ne se redistribuent.
