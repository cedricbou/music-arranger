# 001 — Générer des prises complètes du morceau, pas des pistes isolées

Date : 4 octobre 2026. État : en vigueur.

## Contexte

Le besoin de départ : réarranger un morceau « stem par stem », par exemple ajouter une
guitare funk à « Freed from Desire » (Gala), ou rejouer une piste avec un autre instrument.
Contraintes : modèles locaux, Intel Arc A770 16 Go.

## Ce qui a été essayé

Tous les essais visaient « une piste de guitare funk pour Gala », jugés à l'oreille par
Cédric et mesurés (part de guitare selon Demucs, temps calés sur ceux du morceau).

| Approche | Mesure | Verdict à l'écoute |
|---|---|---|
| ACE-Step 1.5 `cover` d'un stem (`restem`, `derive`) | suit la source (enveloppe 0,56 à 0,93 selon la fidélité) ; deux textes opposés donnent des sorties identiques (corrélation 0,99 à 1,00) dès que la source est suivie | la même piste avec un autre grain |
| ACE-Step `lego` / `complete` sur un contexte | 97 à 100 % des temps calés si la rythmique est dans le contexte ; rend un groupe entier ; guitare 3 à 29 % du son | maladroit ; guitare isolée par Demucs inexploitable |
| ACE-Step texte seul | toujours un groupe, même pour « solo guitar » (guitare 3 à 31 %) | pas une piste |
| ACE-Step : `extract`, `flow_edit`, `reference_audio` | `extract` renvoie le mix ; `flow_edit` colle à 99 % à la source ; la référence audio n'a aucun effet | sans intérêt |
| Stable Audio 3 Medium, `TrackType: Instrument` | guitare isolée (100 % dans 9 essais sur 11), tempo exact ; partir de la batterie ou du mix : ignoré au-dessus de 75 % de bruit, recopié en dessous | bon son, mais « groove décorrélé du morceau » |
| Tri de riffs de 2 mesures par ressemblance d'accents avec le morceau | 531 riffs classés de 0,40 à 0,94 | le classement ne correspond pas à ce qui s'entend |

État de l'art vérifié : ajouter une piste cohérente à un mix existe en ligne (Suno Studio,
« Add Stem ») et en recherche (StemGen, Diff-A-Riff, Stemphonic), pas en local avec des
poids ouverts.

## Ce qui a marché

YuE2 rejoue le morceau **entier** à partir de sa partition (transcrite par SheetSage2),
de ses paroles et d'un texte de style. Sur Gala, Cédric a jugé les deux premières prises
« très qualitatives », mélodie « hyper reconnaissable », guitare funk audible.

## Décision

`arr` travaille par **prises** : des interprétations complètes (voix et groupe). Les
parties de chaque musicien sont tirées d'une prise par séparation. ACE-Step et ses
commandes (`restem`, `polish`, `fix`, `add`, `complete`, `derive`) sont retirés.

## Conséquences

- Les leviers sont la partition, le texte de style, le mode (fidèle ou libre) et la graine.
  On ne peut pas dicter la partie d'un instrument note à note.
- Chaque rendu rejoue tout : pas de « garde la batterie, refais la guitare ».
- Greffer une partie sur l'original dépend du calage de la prise : voir la fiche 004.
- Ne pas réintroduire la génération par piste sans élément nouveau (nouveau modèle local
  qui écoute un mix, par exemple).
