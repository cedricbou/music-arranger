---
name: relire-docs
description: Relire la documentation d'une zone de music-arranger (un fichier ou un répertoire) selon docs/style-doc.md, et proposer un diff. Utiliser quand on veut nettoyer ou vérifier AGENTS.md, le manuel, les docstrings et commentaires d'un module, ou les skills — avant de travailler dans une zone dont la documentation semble douteuse, ou à la demande de l'utilisateur.
---

# Relire la documentation d'une zone

`tests/test_docs.py` refuse au commit ce qui s'écrit en expression régulière. **Cette relecture
attrape le reste** : un récit sans mot-signal, une mesure qui s'empile proprement, un fait devenu
faux sans que son chemin change, une duplication entre deux fichiers.

Argument : un chemin (`docs/manual`, `src/arr/studio.py`, `AGENTS.md`). Sans argument, demander la
zone plutôt que relire tout le dépôt.

## Ce que tu produis

Un **diff proposé** et rien d'autre : pas de commit, pas de PR. Pour chaque proposition, une ligne
qui dit la règle invoquée et, s'il s'agit d'un fait, **comment tu l'as vérifié**. Si tu ne peux pas
vérifier un fait, tu le signales au lieu de le retirer ou de le garder en silence.

Termine par un compte : lignes proposées en retrait, faits vérifiés, faits non vérifiables.

## La marche à suivre

1. **Lire [`docs/style-doc.md`](../../../docs/style-doc.md)** en entier — ses onze règles et sa
   section « Ce qui se garde, explicitement ». C'est la référence ; ce fichier-ci n'en est que le
   mode d'emploi.
2. **Lire la zone**, et la partie d'`AGENTS.md` qui la concerne.
3. **Passer les règles mécanisées d'abord** : `uv run pytest -q tests/test_docs.py`. Ce qu'il
   signale est déjà du travail identifié, et il bloque — commence par là.
4. **Puis chercher les quatre défauts qu'aucun `grep` ne voit** (règles 3, 4, 6, 7, 10, 11) :
   - **la duplication** : un paragraphe qui existe aussi ailleurs. Vérifie-le
     (`grep -rF "<début de phrase>" AGENTS.md README.md docs src`) ; le garder à l'endroit qui le
     porte le mieux, et renvoyer depuis l'autre ;
   - **la mesure empilée** : une colonne « avant / après », une alternative « essayée et écartée »,
     deux valeurs pour la même grandeur. Garder la valeur **actuelle**, ses conditions de
     reproduction et sa conséquence ;
   - **le récit** : un paragraphe qui raconte un bug, une PR, une migration. Le contrat qu'il cache
     se formule **comme contrat** (règle 6) ;
   - **l'état d'avancement** : « où en est-on », « à venir », « prototype », « pas encore ». Ce
     rôle est aux issues et aux épiques.
5. **Vérifier chaque fait que tu gardes.** C'est le cœur du travail :
   - un **chemin** ou un **symbole** cité : `git ls-files | grep <nom>`, `grep -rn "<symbole>" src/` ;
   - un **nombre** tiré du code (un seuil, une constante, un niveau cible) : le relire dans le code.
     S'il est engendré (`docs/manual/reference.md`), remplacer le nombre par un renvoi (règle 11) ;
   - une **mesure** (ms, dB, LUFS, BPM) : vérifier que la commande citée existe encore et que la
     valeur est celle du code actuel. Une mesure qu'on ne peut pas rejouer sans le matériel ou les
     modèles se garde avec ses conditions, et se signale comme non revérifiée ;
   - une **règle annoncée** (« jamais X », « seulement par Y ») : trouver le test qui la vérifie.
     Si rien ne la vérifie, la règle doit le dire (règle 9).
6. **Relire ta propre proposition contre la liste de ce qui se garde**, puis présenter le diff.

## Les genres exemptés, et pourquoi

Ne rien proposer sur : `docs/decisions/` (une fiche dit ce qui motive son choix et se remplace au
lieu de se réécrire), `docs/manual/reference.md` (engendré par `scripts/gen_reference.py` : corriger
la docstring ou le `help=` à la place), et `docs/style-doc.md` (il doit nommer les mots qu'il
proscrit).

## Vérifier avant de rendre

- `uv run pytest -q tests/test_docs.py` passe.
- Si la zone contient du `.py`, `scripts/check.sh` passe et `git diff -U0` ne montre **que** des
  lignes de commentaire ou de docstring : une relecture de documentation ne change aucun
  comportement.
- Sur une zone déjà relue, tu ne dois (presque) rien proposer. Si tu proposes beaucoup, dis-le :
  c'est soit la zone qui n'a jamais été traitée, soit ta lecture qui est trop zélée.
