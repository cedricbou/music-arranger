# 006 — Caler une prise par section, avec des réglages mémorisés

Date : 10 octobre 2026. État : en vigueur. Remplace la mesure de calage de la fiche 004.

## Contexte

Une prise fidèle de « Maldòn » semblait au bon tempo, mais ses voix sonnaient décalées sur
l'original. `arr split` l'avait pourtant déclarée « superposable » (67 % des temps calés).

## Ce que la mesure a montré

Comparaison de la prise et de l'original par fenêtres glissantes :

| Zone | Décalage de la prise |
|---|---|
| 20 à 186 s | un temps d'avance (-430 à -490 ms, pour un temps de 452 ms) |
| 188 s à la fin | trois temps de retard (+1290 à +1310 ms) |

- Ce sont des **temps entiers**, pas une dérive : la prise joue une mesure de plus vers
  187 s (552 temps contre 536). La partition transcrite contient des mesures à 1/4 et 3/4.
- Le décalage est **constant dans chaque section** et ne change qu'aux frontières.
- **Tous les stems d'une prise ont le même décalage** : un calage par prise suffit.
- La mesure de la fiche 004 (part des temps de la prise qui tombent sur un temps de
  l'original) est **aveugle à un décalage d'un temps entier**.

## Décision

1. **Mesurer avec l'harmonie et les attaques** (`measure.time_map`) : les attaques proposent
   des placements précis à 10 ms, l'harmonie choisit entre eux. `measure.by_section` en tire
   un décalage par section.
2. **Le calage est un réglage mémorisé, pas un nouveau fichier.** Chaque piste porte dans
   `song.toml` une liste `nudges` (`scope` : `track` ou une section ; `ms` ; `by` : `align`
   ou `manual`). `load_track()` l'applique à chaque écoute, mix ou export. On peut donc voir
   ce qui est appliqué, l'ajuster et l'annuler.
3. **`arr align`** inscrit ses mesures comme réglages `align` ; **`arr nudge`** pose des
   réglages `manual`. `align` ne remplace jamais un réglage manuel : il se cale dessus.

Sur Maldòn : de 0 % à 96 % du morceau à moins de 30 ms de l'original.

## Pièges rencontrés

- Affiner un placement grossier donné par l'harmonie s'accroche parfois au mauvais temps :
  il faut laisser les attaques proposer et l'harmonie choisir.
- Sans marge de silence aux deux bouts, la première fenêtre ne peut pas essayer un décalage
  négatif, et les mesures du début du morceau sont fausses.
- Une fenêtre à cheval sur un changement de décalage donne une valeur mélangée : une section
  est sûre quand 60 % de ses fenêtres s'accordent, pas quand toutes s'accordent.

## Limites

- Dans un passage répété à l'identique, plusieurs placements se valent. `by_section` retient
  celui qui prolonge la section précédente et le signale (`guessed`) ; à défaut la section
  reste ambiguë et se règle à la main.
- Le calage est par section : un changement de décalage au milieu d'une section demande de
  redécouper la section.
- Une frontière où le décalage change reçoit un fondu court, pas un raccord musical.
- Une intro pauvre en attaques n'a souvent pas de mesure fiable ; elle hérite du décalage
  général de la piste.
