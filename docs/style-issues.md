# Style des issues

La backlog se lit **sans ouvrir le code**. Une issue dit ce que le musicien pourra faire et à quoi
on verra que c'est fait ; le détail technique vit à côté, dans un commentaire. Ces règles valent
pour toute issue créée ou modifiée, par un humain ou par un agent, et `scripts/feature.sh` refuse
celles qui se mécanisent. Les issues s'écrivent en anglais, ce guide en français.

## Quatre types, une étiquette chacun

| Étiquette | Ce que c'est | Se code ? |
|---|---|---|
| `epic` | une key feature : elle regroupe des stories et dit où on en est | non, on code ses stories |
| `story` | ce que le musicien veut pouvoir faire ; une issue, une branche, une PR | oui |
| `chore` | atelier : outillage, CI, documentation, sans effet pour le musicien | oui |
| `bug` | un comportement incorrect | oui |

Une issue porte **exactement une** de ces étiquettes. Deux autres s'y ajoutent au besoin :
`needs-ears` quand un essai à l'oreille ou sur le matériel reste dû, `needs-refinement` quand
l'issue est à cadrer.

## Le titre

Ce que je peux faire, ou le résultat visé, **dans les mots de celui qui joue** : « Loop the chorus
without a click at the wrap », pas « play: crossfade in loop_mix ». Ni préfixe de zone
(`play:`, `MIDI:`), ni nom de fonction, ni chemin de fichier. Une commande que le musicien tape
(`arr play`) ou un fichier qu'il édite (`sheet.toml`) est permis.

## Le corps

**Story**

```markdown
**As a** <musician in rehearsal / on stage / preparing a song…>, **I want** <what I do>,
**so that** <the benefit>.

## Today
2 to 4 sentences: what is in the way, as lived, with the telling number if there is one.

## Done when
- [ ] 3 to 6 observable criteria (what I see, hear, do)
- [ ] the listening trial, if there is one

## Out of scope
## To decide        (only if a real decision is left)
## Links            (epic, depends on, unblocks)
```

**Épique** : deux ou trois phrases sur ce que la key feature change, puis `## Where we are`,
`## Stories` (une case par story, cochée quand elle est livrée), `## Decisions already made` (en
mots simples, avec le lien vers la fiche de `docs/decisions/`), `## Later, maybe`.

**Chore** : `## Why`, `## Done when`, `## Links`.

**Bug** : `## What happens`, `## What should happen`, `## Context`.

Les modèles de `.github/ISSUE_TEMPLATE/` portent ces rubriques.

## Ce qui n'entre pas dans le corps

- un nom de module, de fonction, de classe ou de fichier source ;
- le plan de tests automatiques, les mesures de laboratoire, les pistes dans le code ;
- des consignes à l'agent qui réalise.

Tout cela va dans le **cadrage technique** : un commentaire de l'issue qui commence par
`## Technical framing`. C'est lui que lit l'agent avant de coder (modules, fiches de décision,
pistes, tests, mesures). Une précision qui arrive en cours de route s'ajoute en commentaire, pas
dans le corps.

## Une issue à cadrer

Une story ou une épique qui n'est pas assez approfondie pour être codée porte, en plus de son type,
l'étiquette `needs-refinement`. Sa rubrique `## To decide` est alors **obligatoire** : elle liste,
en questions courtes, ce qu'il reste à décider.

- **On ne code pas dessus** : `scripts/feature.sh start` la refuse, sans passe-droit.
- **On la cadre avec celui qui joue** : l'agent pose les questions de « To decide », propose une
  réponse par défaut pour chacune, et ne tranche pas seul.
- **Chaque décision prise quitte « To decide »** et rejoint le corps : un critère de « Done when »,
  une ligne de « Out of scope », une entrée de « Decisions already made » pour une épique, ou une
  nouvelle story. Ce qui est technique va dans le cadrage ; un choix structurant, dans une fiche.
- **Quand « To decide » est vide**, la rubrique et l'étiquette se retirent : l'issue se code.

Une rubrique « To decide » sans l'étiquette reste permise pour un détail qui se décide en codant.

## Écrire

- Première personne (« I »), phrases simples, vocabulaire du musicien.
- Les faits et chiffres parlants se gardent : « the takes peak at 0 dBFS and clip on export ».
- Un critère de « Done when » s'observe sans lire le code. « The loop wraps without a click » se
  garde ; « the crossfade is 20 ms » va dans le cadrage.
- Court : une story tient en 15 à 30 lignes.
- Une story se rattache à une épique quand il en existe une pour son sujet, et l'épique gagne une
  case.

## Le parcours d'une issue

1. Écrire le corps dans un fichier, et le cadrage technique dans un autre.
2. `scripts/feature.sh issue story "Title" body.md framing.md` : contrôle le style, crée l'issue
   avec son étiquette, et poste le cadrage en commentaire. Avec `--refine` devant le type,
   l'issue naît à cadrer.
3. `scripts/feature.sh start <n°>` relit le style de l'issue avant d'ouvrir la branche ;
   `scripts/feature.sh lint <n°>` fait ce contrôle seul.
4. Une limite découverte en chemin devient une issue du même style : une story si le musicien la
   subit, un chore sinon.
5. Une issue livrée dont il ne reste qu'un essai à l'oreille se ferme, et l'essai devient une case
   de l'issue de session d'écoute ouverte.

## Ce que le script refuse

Un type inconnu ou absent ; un titre préfixé d'une zone (`xxx: `), portant un chemin de source ou
un module, ou de plus de 100 caractères ; un corps sans les rubriques de son type ou sans case à
cocher ; un corps qui nomme un fichier `.py`, un chemin `src/` ou `tests/`, un module `arr.xxx`, ou
qui porte une rubrique « Technical framing ». Une issue `needs-refinement` sans rubrique
« To decide », et le démarrage d'une branche sur une épique ou une issue `needs-refinement`. Le
reste — un critère observable, un ton lisible — relève de la relecture.
