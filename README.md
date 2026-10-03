# arr

CLI d'arrangement audio 100 % local : séparer un morceau en stems, rejouer un stem avec un
autre instrument, refaire un passage, ajouter des instruments, le tout partie par partie.

Tout tourne sur la machine (Intel Arc via PyTorch XPU). Seule la commande `arr models pull`
utilise le réseau ; toutes les autres forcent le mode hors ligne.

## Installation

Prérequis : `uv`, `ffmpeg`, pilotes Intel (`intel-compute-runtime`, `level-zero-loader`).

```
cd ~/dev/music-arranger
uv sync                  # Python 3.11 + PyTorch XPU + ACE-Step
uv run arr models pull   # ~14 Go, une seule fois
uv run arr doctor        # doit afficher « xpu: disponible » et les modèles présents
```

Pour taper `arr` directement, ajoutez un alias dans `~/.zshrc` :
`alias arr=~/dev/music-arranger/.venv/bin/arr`. La suite suppose que cet alias existe.

## Démarrage rapide : réarranger une cover

```
arr init ma-cover --from ~/Musique/original.mp3
cd ma-cover
arr split                                   # 6 stems : drums bass guitar piano vocals other
arr analyze                                 # tempo, mesures, tonalité
arr sections set "intro:1-8 couplet:9-24 refrain:25-40"
arr restem guitar --as brass                # la guitare rejouée par des cuivres
arr play                                    # écouter le mix
```

Toutes les commandes se lancent depuis le dossier du projet (ou un sous-dossier).

## Partir d'une idée (basse, piano)

```
arr init idee-basse
cd idee-basse
arr import ~/Enregistrements/riff.wav --as bass
arr analyze
arr polish bass                              # la même ligne, rejouée proprement
arr complete --with drums,guitar -p "funk rock band, tight groove"
```

## Commandes

### Projet et pistes

| Commande | Effet |
|---|---|
| `arr init NOM [--from FICHIER]` | crée le projet, importe éventuellement le morceau |
| `arr import FICHIER` | remplace le morceau original |
| `arr import FICHIER --as PISTE` | ajoute un stem ou une idée comme piste |
| `arr split [FICHIER] [--model M] [--shifts N]` | sépare l'original (ou un rendu) en stems |
| `arr merge PISTE PISTE... --as NOM` | fusionne des pistes en une seule ; les sources deviennent muettes |
| `arr analyze` | tempo, mesures, tonalité |
| `arr sections set "nom:1-8 nom:9-16"` | sections en numéros de mesure, inclusifs |
| `arr sections list` | affiche les sections |
| `arr tracks` | pistes, versions, version active (`*`) |
| `arr pick PISTE VERSION` | choisit la version active |
| `arr gain PISTE DB` | volume dans le mix |
| `arr mute PISTE [--off]` | sort une piste du mix, ou la remet |
| `arr mix [-w PISTE] [-o PISTE]` | écrit `mix/mix.flac` |
| `arr play [PISTE]` | écoute une piste ou le mix |

### Améliorer la séparation

| Modèle | Stems | Quand l'utiliser |
|---|---|---|
| `htdemucs_6s` (défaut) | drums bass guitar piano vocals other | groupe avec de vraies guitares et un vrai piano |
| `htdemucs_ft` | drums bass vocals other | musique électronique, synthés en couches ; plus précis, environ 2,5 fois plus lent |

- Sur un morceau à base de synthés, la distinction guitare/piano n'a pas de sens : utilisez
  `arr split --model htdemucs_ft`, ou fusionnez après coup avec
  `arr merge guitar piano other --as synth`.
- `--shifts 2` (ou plus) moyenne plusieurs passes : moins de fuites entre stems, temps
  multiplié d'autant.
- Une nouvelle séparation crée de nouvelles versions et rend muets les stems et fusions de
  la précédente ; `arr pick` et `arr mute --off` permettent de revenir en arrière.

### Génération

| Commande | Effet | Résultat |
|---|---|---|
| `arr restem PISTE --as INSTRUMENT` | rejoue le stem avec un autre instrument | nouvelle piste ; l'ancienne devient muette |
| `arr polish PISTE` | rejoue proprement, même instrument | nouvelle version de la piste |
| `arr fix PISTE --from S --to S -p "..."` | refait un passage | nouvelle version ; le reste est intact |
| `arr add INSTRUMENT` | ajoute un instrument sur le mix | rendu complet dans `renders/` |
| `arr complete --with A,B -p "..."` | habille le mix avec plusieurs instruments | rendu complet dans `renders/` |

Options communes :

- `--section NOM` (`-s`) : ne traite que cette partie. Pour `restem`, la nouvelle piste ne
  joue que pendant la section et l'ancienne s'y tait.
- `--prompt "..."` (`-p`) : description du son, de préférence en anglais.
- `--seed N` : pour reproduire un résultat ; `-n 3` : trois variantes d'un coup.
- `--fidelity X` (`restem`, `polish`) : à quel point on colle à la prise d'origine.

| `--fidelity` | Résultat |
|---|---|
| 0 | partie réinventée, sans lien avec la source |
| 0.3 | garde le rythme, timbre nettement nouveau |
| 0.5 | même ligne, nettoyée |
| 0.7 | très proche de l'original, retouche légère |

`add` et `complete` rendent un **mix complet** (l'existant plus les nouveaux instruments),
pas une piste isolée. Pour retravailler le résultat stem par stem :

```
arr add brass --section refrain
arr split renders/add-brass-001.flac
```

### Versions

Rien n'est jamais écrasé. Chaque génération crée `tracks/<piste>/vNNN.flac` et un
`vNNN.json` qui garde le modèle, la graine, le prompt et la version d'origine. `arr tracks`
montre l'historique, `arr pick` revient en arrière.

## Instruments du groupe

Les instruments acceptés par `--as`, `add` et `--with` sont les familles d'ACE-Step :

`woodwinds brass fx synth strings percussion keyboard guitar bass drums backing_vocals vocals`

Pour nommer vos propres instruments, créez `~/.config/arr/band.toml` :

```toml
[trompette]
track = "brass"
sound = "bright trumpet, tight stabs"

[rhodes]
track = "keyboard"
sound = "warm rhodes electric piano"
```

Puis `arr restem guitar --as trompette`.

## Dossier d'un projet

```
ma-cover/
  song.toml        titre, tempo, tonalité, sections, version active et gain de chaque piste
  analysis.json    temps et mesures détectés
  source/          fichiers importés, convertis en FLAC 48 kHz stéréo
  tracks/<piste>/  vNNN.flac + vNNN.json
  renders/         mixes complets produits par add et complete
  mix/mix.flac     dernier mix
```

`song.toml` se modifie à la main, par exemple pour corriger la tonalité.

## À savoir

- Une génération prend environ 50 s pour 30 s d'audio, dont 25 s de chargement du modèle.
- La tonalité détectée est approximative : vérifiez-la dans `song.toml`.
- Les sections se définissent à la main ; lancez `arr analyze` d'abord pour avoir les mesures.
- Les poids sont dans `~/.local/share/arr/checkpoints` (ACE-Step), `~/.cache/huggingface`
  (Demucs) et `~/.cache/torch/hub` (beat_this).
