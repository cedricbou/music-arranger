# 002 — YuE2 et SheetSage2 tournent hors du processus d'arr

Date : 4 octobre 2026. État : en vigueur.

## Contexte

YuE2 annonce 24 Go de VRAM et une carte NVIDIA ; la machine a une Intel Arc A770 de 16 Go.
SheetSage2 exige `transformers==4.45.2` et `numpy<2`, incompatibles avec le reste d'arr.

## Décision

- **YuE2** passe par le binaire `audio.cpp` (v0.9.0), sur le GPU via Vulkan, avec les
  poids GGUF **Q8** (`yue2-3b-q8_0.gguf`, VAE F16). `engines/yue2.py` le lance en
  sous-processus.
- **SheetSage2** a son propre environnement Python (`~/.local/share/arr/envs/ss2`),
  lancé en sous-processus par `engines/transcription.py` avec le script `_sheetsage2.py`.
- `arr models pull` installe les deux.

## Pièges rencontrés

- La variante **non portable** du binaire audio.cpp plante (SIGILL) sur ce processeur
  AMD : prendre `vulkan-portable`.
- Vulkan sur Arc n'a pas le bf16 : les poids BF16 ne sont pas utilisés.
- SheetSage2 se charge par son identifiant Hugging Face (`m-a-p/SheetSage2`, depuis le
  cache) ; depuis un dossier local, ses imports relatifs échouent.
- Le dossier temporaire du système est un disque en mémoire de 16 Go : ne pas y créer
  d'environnement Python.

## Mesures (Gala, 3 min 40)

| Étape | Temps |
|---|---|
| Transcription SheetSage2 | 12 min 38 la première fois, 2 min 49 ensuite |
| Rendu YuE2 d'une prise | 4 min 35 à 4 min 48, 48 kHz stéréo |
| Séparation Demucs 6 stems | environ 20 s |

SheetSage2 varie d'un passage à l'autre (129 ou 130 BPM, 118 ou 120 mesures) : `arr
transcribe` mesure donc le tempo sur l'audio et l'écrit dans la partition.

## Conséquences

- Les deux modèles sont sous CC BY-NC 4.0 : usage non commercial.
- `transcribe` et `render` capturent la sortie du sous-processus et restent muets
  plusieurs minutes.
- Les tests ne lancent jamais ces moteurs : ils remplacent `transcription.transcribe` et
  `yue2.render`.
