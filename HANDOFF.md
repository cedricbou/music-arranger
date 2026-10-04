# Handoff

État au 3 octobre 2026, fin de la première session.

## Où on en est

Les phases 0 à 2 du plan sont faites : environnement XPU validé, socle du CLI, commandes
génératives. La phase 3 (adaptation à la scène) n'est pas commencée.

| Élément | État |
|---|---|
| PyTorch XPU sur Arc A770 | fonctionne |
| ACE-Step 1.5 `base` sur XPU | fonctionne, avec un patch float64 |
| `init`, `import`, `split`, `analyze`, `sections`, `tracks`, `pick`, `gain`, `mute`, `mix`, `play`, `doctor`, `models pull` | faits, testés de bout en bout |
| `restem`, `polish`, `fix` | faits, vérifiés par la mesure |
| `derive` (plusieurs sources, texte, liste de fidélités, styles) | fait ; le texte n'agit que modestement, voir les mesures |
| `add` | fait, s'exécute ; qualité non vérifiée |
| `complete` | fait ; exécuté une seule fois, avant les dernières corrections |
| Tests | 17 tests : `project.py`, `audio.py`, et les commandes du CLI (`tracks`, `merge`, `split`, `derive`, `restem`, `polish`) avec des moteurs factices |
| `structure`, transposition, tempo, `export` | à faire |
| MIDI, partitions | à faire, prévu en dernier |

## Décision en attente : l'écoute

Aucun résultat n'a été écouté. Tout ce qui est « vérifié » l'est par la mesure (durée,
niveau, corrélation d'enveloppe et de forme d'onde). Cédric doit écouter, dans `demo/` :

- `arr play brass` : guitare rejouée en cuivres (`restem`, fidelity 0,35) ;
- `arr play bass` : passage 5–10 s refait (`fix`) ;
- `renders/add-brass-001.flac` : cuivres ajoutés sur le couplet (`add`).

Selon le verdict :

- `restem` trop proche de la guitare ou trop éloigné de la ligne : ajuster la valeur par
  défaut de `--fidelity` (0,35) et le prompt par défaut dans `cli.py`.
- `add` peu convaincant : essayer dans l'ordre le modèle de langage (`thinking=True`,
  non testé), puis `acestep-v15-xl-base` (4B, ~12 Go avec offload, à télécharger).
- `fix` sur un stem isolé génère peut-être un arrangement entier dans le trou : avant
  correction du niveau, le passage refait était 5 fois plus fort que la piste. Si c'est
  le cas à l'oreille, refaire le passage sur le mix puis re-séparer.

## Mesures de référence

Extrait de 30 s, `acestep-v15-base`, 50 pas, graine fixe.

| Mesure | Valeur |
|---|---|
| Génération turbo (8 pas) | 21 s, 6,7 Go |
| Génération base (50 pas) | 24 s, 8,3 Go |
| Chargement du modèle | ~9 s à chaud, ~25 s par commande au total |
| `split` Demucs 6 stems | 8 s (19 s pour 3 min 40) |
| `split` Demucs `htdemucs_ft` | 46 s pour 3 min 40 |
| `fix` hors plage | différence maximale 0,0 |

Effet de `fidelity` (corrélation d'enveloppe / de forme d'onde avec la source) :

| fidelity | basse → polish | guitare → cuivres |
|---|---|---|
| 0,0 | −0,09 / −0,02 | −0,26 / 0,00 |
| 0,3 | +0,72 / +0,38 | +0,41 / +0,17 |
| 0,5 | +0,90 / +0,85 | +0,81 / +0,54 |
| 0,7 | +0,96 / +0,95 | +0,94 / +0,79 |

### Ce que le texte pilote (4 octobre, issue #3)

Extrait de 40 s de Gala (synthés fusionnés), graine fixe, deux textes opposés : A « sparse,
slow, dark, mellow » et B « busy, fast, bright, aggressive ». « A/B » est la corrélation de
forme d'onde entre les deux sorties : 1,00 signifie que le texte n'a rien changé.

| Réglage | A/B | Suit la source (enveloppe, harmonie / témoin) | Lecture |
|---|---|---|---|
| strength 1, fidélité 0,2 à 0,5 | 0,99 à 1,00 | oui | texte ignoré |
| strength 1, fidélité 0 | 0,96 | non (0,0 ; 0,77 / 0,76) | timbre seul : centroïde 1686 contre 2173 Hz |
| strength 0,3, fidélité 0 | 0,87 | non | timbre : 1859 contre 2591 Hz |
| **strength 0, fidélité 0,2** | **0,90** | **oui (0,6 ; 0,89 / 0,77)** | seul réglage qui suit la source et réagit au texte |
| strength 0, fidélité 0,35 | 0,99 | oui (0,83 ; 0,95 / 0,75) | texte presque sans effet |
| strength 0, fidélité 0,35, guidance 12 | 0,96 | oui | léger effet dans le bon sens |
| flow edit | 0,99 | oui (0,99 ; 0,99 / 0,71) | léger décalage de timbre, ~95 s par génération |
| texte en français au lieu d'anglais | 1,00 | | sans effet propre |
| avec `reference_audio` | 0,99 | | sans effet |

Conséquences : `derive` utilise strength 0 et une fidélité par défaut de 0,2 ; `--ref` et
l'enrichissement par le modèle de langage ont été abandonnés. Dans aucun réglage la densité
de notes (attaques par seconde) ne suit le texte : « sparse » et « busy » donnent la même.

Sur le morceau entier (220 s) : ~42 s par génération, niveaux recalés, enveloppe 0,56 à
fidélité 0,15, 0,78 à 0,25, 0,93 à 0,5.

À écouter : `demo/gala` (`funk-guitar` v001 et v002, `synth-light`) et `demo/mesures-texte`
(paires A/B des réglages marquants).

Pistes pour un vrai contrôle par le texte, non essayées : `lego` avec description locale
(génère dans le contexte du mix, rend un mix complet à re-séparer), le modèle XL
(`acestep-v15-xl-base`), ou un LoRA entraîné sur le son du groupe.

La VRAM sur un morceau entier n'a pas été mesurée. (3 à 5 min) : temps et VRAM inconnus à cette durée.

## Reste à faire

### Phase 3 : adaptation à la scène

1. `arr structure set "intro couplet refrain refrain outro"` : couper, répéter, réordonner
   les sections sur toutes les pistes, avec fondus calés sur les mesures. `audio.splice`
   et les sections existent ; il manque l'assemblage et la mise à jour de `analysis.json`
   et des sections après réordonnancement.
2. Lissage optionnel des raccords par `repaint` sur une courte plage autour de chaque coupe.
3. Transposition et changement de tempo. Aucun outil n'est choisi ; `rubberband` n'est pas
   installé (vérifier si le filtre `rubberband` de `ffmpeg` est disponible).
4. `arr export` : stems WAV alignés dans `export/`.

### Défauts connus

- **Fuites entre stems** : sur un morceau électro (Gala, « Freed from Desire »), Cédric
  entend du piano/synthé dans la voix et une confusion piano/guitare. Ajoutés depuis :
  `arr merge`, `--model htdemucs_ft` (4 stems) et `--shifts`. Sur ce morceau, la voix de
  `htdemucs_ft` diffère peu de celle de `htdemucs_6s` (corrélation 0,97) : la fuite dans
  la voix n'est donc probablement pas réglée. Piste suivante : un modèle vocal RoFormer
  (BS-RoFormer ou Mel-Band RoFormer), à charger en PyTorch sur XPU et depuis Hugging Face ;
  `audio-separator` ne gère pas XPU.
- **Tonalité peu fiable** : si mineur détecté pour un extrait demandé en mi mineur. Pas de
  commande pour la corriger (édition manuelle de `song.toml`). Ajouter `arr set --key --bpm`
  ou améliorer l'estimation.
- **Sections manuelles** : pas de détection automatique. Candidat : `all-in-one-infer`
  (dépendances lourdes, compatibilité XPU à vérifier).
- **beat_this** : poids téléchargés depuis le cloud de l'université JKU (Linz), pas depuis
  Hugging Face. À remplacer si la règle « Hugging Face exclusivement » est stricte.
- **Chargement à chaque commande** (~25 s). Prévu : `arr serve` qui garde le modèle en
  mémoire derrière un socket Unix.
- **`-n` avec graine fixe** incrémente la graine ; avec `--seed -1` chaque variante est aléatoire.
- **`render_mix` écrit `mix/mix.flac`** à chaque appel, y compris depuis `add`, `complete`
  et `analyze` sans original. Effet de bord à connaître.
- **`Engine.generate(strength=...)`** (audio_cover_strength) n'est plus utilisé par le CLI.

### Hygiène du dépôt

- Dépôt privé : https://github.com/cedricbou/music-arranger (branche `main`). Les fichiers audio et `demo/` sont ignorés ; les fonctionnalités et bugs se suivent dans les issues GitHub.
- ACE-Step est suivi sur sa branche principale ; seul `uv.lock` fige la révision. Épingler
  un `rev` dans `pyproject.toml`.
- Le patch float64 mériterait un correctif proposé à ACE-Step (le cas MPS y est déjà traité).
- Étendre les tests de `cli.py` (init → import → sections → mix, et les commandes génératives avec un `Engine` factice).

### Plus tard

- Transcription en MIDI et export MusicXML par instrument.
- Commande en langage naturel pilotée par un LLM local.
- Entraînement d'un LoRA sur le son du groupe (ACE-Step le permet ; `peft` est installé).

## Fichiers et emplacements

| Quoi | Où |
|---|---|
| Plan d'origine | `~/.claude/plans/je-veux-cr-er-un-serene-stroustrup.md` |
| Poids ACE-Step (14 Go) | `~/.local/share/arr/checkpoints` |
| Poids Demucs | `~/.cache/huggingface/hub/models--adefossez--HTDemucs-6s` |
| Poids beat_this | `~/.cache/torch/hub/checkpoints/beat_this-final0.ckpt` |
| Projet de démonstration | `demo/` |
| Profil du groupe (pas encore créé) | `~/.config/arr/band.toml` |
