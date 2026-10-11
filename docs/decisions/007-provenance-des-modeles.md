# 007 — Les poids viennent de Hugging Face ; audio.cpp suit sa release officielle

Date : 10 octobre 2026. État : en vigueur. Précise 002 : la version d'audio.cpp n'est plus figée.

## Contexte

La règle du projet est que les poids viennent de Hugging Face. Deux téléchargements d'`arr
models pull` y échappaient (issue #28) : les poids de beat_this, pris sur le cloud de
l'université JKU, et le binaire audio.cpp, pris sur une release GitHub figée à la v0.9.0.

## Ce qui a été vérifié

| Élément | Constat |
|---|---|
| Demucs | déjà sur Hugging Face depuis demucs 4.1.0 (`adefossez/HTDemucs-6s`, `-ft`) |
| beat_this `final0` | `oulianov/beat_this` en publie une copie : même sha256 (`8c328b45…8331`) que le fichier de la JKU |
| audio.cpp | l'organisation Hugging Face `audio-cpp` ne publie que des poids GGUF, aucun binaire |

## Décision

- **beat_this** est pris sur Hugging Face, dans `oulianov/beat_this`, à une révision fixe.
  C'est le dépôt d'un tiers et non des auteurs : la révision garantit que le fichier reste
  celui des auteurs. Mêmes octets, donc mêmes temps et même calage qu'avant.
- **audio.cpp** reste la seule exception, et elle est assumée : c'est un programme, pas un
  modèle. `arr models pull` prend la **dernière release** officielle, vérifie le sha256 que
  GitHub publie, et la range dans `audiocpp/<version>/` ; le lien `current` désigne la
  version en service. `--audiocpp` (ou `ARR_AUDIOCPP_VERSION`) fixe une version ou y revient.
- Chaque prise note la version d'audio.cpp qui l'a rendue (`engine` dans son `.json`).

## Écarté

| Piste | Pourquoi |
|---|---|
| Remplacer beat_this par les temps de SheetSage2 | SheetSage2 varie d'un passage à l'autre (129 ou 130 BPM, 118 ou 120 mesures, fiche 002) et prend près de 3 min ; `analyze` et le calage de chaque prise en dépendraient |
| Paquet AUR `audio.cpp-git` | compile la tête de `main` et non une release, sans empreinte ni version fixable ; demande sudo, ne vaut que pour Arch |
| Compiler audio.cpp à un tag | faisable, mais plusieurs minutes et une chaîne de compilation à entretenir ; YuE2 calcule sur le GPU et la variante portable choisit déjà la bibliothèque CPU adaptée |
| Figer une version d'audio.cpp dans le code | le projet sort une release par semaine ; rester à jour est le comportement voulu, fixer est l'exception |

## Conséquences

- audio.cpp est en 0.x : une nouvelle release peut changer un rendu. Le garde-fou est la
  version notée dans chaque prise et le retour à une version installée, pas un plafond.
- Après cette mise à jour, relancer `arr models pull` une fois : le binaire change de
  dossier et les poids de beat_this changent de cache.
- L'ancien binaire (`audiocpp/audiocpp_cli`) et l'ancien fichier de beat_this
  (`~/.cache/torch/hub/checkpoints/`) ne servent plus ; `arr` ne les supprime pas.
- Si `oulianov/beat_this` disparaît, republier le même fichier (licence MIT) et changer
  `BEAT_THIS_REPO` dans `engines/analysis.py`.
