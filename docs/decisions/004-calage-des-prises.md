# 004 — Mesurer le calage d'une prise au lieu de le supposer

Date : 4 octobre 2026. État : en vigueur, amélioration prévue (issue #5).

## Contexte

Une prise fidèle (`cot=full`, mélodie et accords imposés) est censée garder le tempo et
les mesures de l'original, ce qui permettrait de greffer ses stems sur l'original
(`arr graft`).

## Mesures

Trois prises fidèles de Gala, trois transcriptions :

| Partition | Durée de la prise | Temps calés après étirement et décalage |
|---|---|---|
| 129 BPM, 118 mesures | 219,9 s | 83 % : greffable |
| 130 BPM, 120 mesures | 219,4 s | 26 % |
| 129 BPM (corrigé par arr), environ 120 mesures | 223,8 s | 33 % |

Un écart de tempo de 0,8 % donne près de 2 s de dérive en fin de morceau. Une prise libre
(`cot=melody`) est sortie à 135,9 BPM : jamais superposable.

Causes : SheetSage2 ne rend pas la même grille de mesures d'un passage à l'autre (mesures
à 5/8 dans une intro silencieuse), et YuE2 ne tient pas le tempo au centième. Un ajustement
linéaire (une vitesse, un décalage) ne suffit pas.

## Décision

`arr split tNNN` étire la prise au tempo de l'original (`audio.stretch`, hauteur
conservée), la décale, puis **mesure** `on_beat` : la part de ses temps à moins de 35 ms
d'un temps de l'original. Sous 60 %, la prise est marquée non superposable et la commande
prévient. Au-delà de 3 % d'écart de tempo, elle n'essaie pas.

## Conséquences

- La greffe est aléatoire tant que le calage est linéaire. Piste retenue : synchronisation
  par déformation temporelle (DTW sur chroma ou attaques, étirement par morceaux).
- Les prises restent utilisables comme maquettes et pour en extraire les parties.
- Le tempo se mesure avec `analysis.period()`, qui écarte les intervalles anormaux ; une
  simple régression sur les temps est faussée par un temps manqué.
