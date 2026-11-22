---
name: ecrire-issue
description: Créer ou réécrire une issue GitHub de music-arranger dans le style de la backlog (épique, story, chore, bug), lisible par un musicien qui n'ouvre pas le code, avec le cadrage technique en commentaire. Utiliser dès qu'il faut ouvrir une issue — une fonctionnalité demandée, une limite découverte en codant, un bug, une dette — ou reformuler, cadrer une issue existante.
---

# Écrire une issue

La backlog se lit sans ouvrir le code. La référence est [`docs/style-issues.md`](../../../docs/style-issues.md) :
la lire en entier avant d'écrire. Les issues s'écrivent en anglais.

## Méthode

1. **Choisir le type** : `story` si le musicien voit ou entend le résultat, `chore` sinon, `bug`
   pour un comportement incorrect, `epic` seulement pour une key feature que l'utilisateur a nommée.
2. **Chercher l'épique** : `gh issue list --label epic`. Une story s'y rattache dans `## Links`.
3. **Écrire deux fichiers** dans le dossier temporaire de la session, hors du dépôt :
   - le **corps**, aux rubriques du type, à la première personne, sans nom de module, de fonction
     ni de fichier source ; les critères de « Done when » s'observent en jouant ou en écoutant ;
   - le **cadrage technique** : modules touchés, fiches de `docs/decisions/` à relire, pistes dans
     le code, tests, mesures avec `arr check` ou `arr.measure`, ce qui restera à l'oreille. Tout ce
     qu'un agent doit savoir avant de coder.
4. **Créer** : `scripts/feature.sh issue <type> "Title" body.md framing.md`. Le script contrôle le
   style et refuse ce qui s'en écarte : corriger le texte, ne pas contourner.
5. **Mettre à jour l'épique** : une case de plus dans `## Stories`.

## Une issue à cadrer

Si le besoin est réel mais que des décisions manquent pour coder — ce que contient la
fonctionnalité, son périmètre, un choix que seul l'utilisateur peut faire —, ne pas les inventer :
écrire ces questions dans `## To decide` et créer l'issue avec `--refine`
(`scripts/feature.sh issue --refine story "Title" body.md`). Elle porte alors `needs-refinement`
et ne se code pas.

Pour **cadrer** une issue (`scripts/feature.sh refine` les liste) :

1. Lire le corps, le cadrage technique et les commentaires.
2. Poser à l'utilisateur les questions de « To decide », peu à la fois, chacune avec une réponse
   proposée et ce qu'elle implique.
3. Reporter chaque décision dans l'issue : critère de « Done when », « Out of scope »,
   « Decisions already made » d'une épique, ou nouvelle story rattachée. Le technique va dans le
   cadrage ; un choix structurant, dans une fiche de `docs/decisions/`.
4. Quand « To decide » est vide, retirer la rubrique et l'étiquette.

## Réécrire une issue existante

Le corps d'origine ne se perd pas : le poster d'abord en commentaire `## Technical framing`, puis
remplacer le corps, le titre et l'étiquette de type, puis `scripts/feature.sh lint <n°>`.

## Le test de relecture

Quelqu'un qui joue dans le groupe et ne lit pas le Python comprend-il le titre, sait-il pourquoi
c'est gênant, et saura-t-il dire si c'est fait ? Si une phrase demande d'ouvrir le code, elle va
dans le cadrage.
