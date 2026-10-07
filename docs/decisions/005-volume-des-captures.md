# 005 — Un seul gain vers une cible de volume pour chaque capture

Date : 5 octobre 2026. État : en vigueur.

## Contexte

Les captures passent par la table : leur niveau dépend du gain réglé ce jour-là. Deux
captures mesurées : -21,0 LUFS (crête -10,4 dB) et -19,9 LUFS (crête -6,9 dB).

## Décision

`arr capture` mesure le volume perçu (LUFS, EBU R128, filtre `ebur128` de ffmpeg) et
applique **un seul gain global** vers une cible de -16 LUFS, plafonné pour que les crêtes
restent sous -1 dB (`audio.normalize`). `--raw` garde le niveau d'origine ; la cible se
règle dans `audio.toml`.

Sur les deux captures : +5,0 dB et +3,9 dB, pour -16,0 LUFS dans les deux cas, crêtes à
-5,4 et -3,0 dB.

## Ce qui est écarté

Le filtre `loudnorm` de ffmpeg en une passe : il compresse la dynamique.

## Conséquences

- Seules les nouvelles captures sont normalisées ; `arr import` ne normalise pas.
- Le gain de la table n'a plus besoin d'être identique d'un jour à l'autre, seulement de
  ne pas saturer (`arr levels`).
