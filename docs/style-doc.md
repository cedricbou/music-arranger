# Style de la documentation et des commentaires

Commentaires, docstrings, `AGENTS.md`, `README.md`, `docs/`, les skills de `.claude/`. Ces règles
gardent les contrats et retirent le récit du passé. `tests/test_docs.py` vérifie celles qui se
mécanisent.

## Le principe

**Un fait va à l'endroit qui le porte le mieux**, et du texte n'est le meilleur endroit que par
défaut :

| Le fait… | …vit dans |
|---|---|
| se vérifie | ce qui le vérifie (un test, un contrôle de `scripts/check.sh`) |
| s'exécute | ce qui l'exécute (un script de `scripts/`) |
| change avec le code | ce qui l'engendre (`docs/manual/reference.md`, engendré des `help=`) |
| est une décision | une fiche de `docs/decisions/` |
| est arrivé | `git log` : chaque PR y est un commit, titré comme son issue |
| reste à faire | une issue (`docs/style-issues.md`) |
| est un contrat, un piège, un invariant | le code, en commentaire ou en docstring |

Devant une phrase, la question n'est donc pas « est-ce de l'histoire ? » — on y répond mal — mais
**« existe-t-il un endroit qui porterait ce fait mieux que du texte ? »**

## Les règles

**1. Le présent de l'état actuel.** Proscrits : « désormais », « auparavant », « l'ancien X »,
« avant #N », « depuis #N », « ne … plus », « c'était », « a été retiré », « ont disparu ». Un
ancien texte faux se **supprime** ; vrai, il se réécrit au présent. « Ne … plus » et « l'ancien »
sont aussi du vocabulaire du domaine ici — une piste qui **n'est plus** active, l'**ancienne**
version d'une piste — donc hors du contrôle automatique et à la charge du relecteur.

**2. Pas de numéro d'issue ni de PR dans le code ni dans un document de référence.** L'historique
est dans git. **Exception** : les fiches de décision, dont le genre *est* la trace d'un choix. Les
renvois « fiche 006 » du code et des docs sont de **bonnes** références : ils pointent vers un
document qui fait foi.

**3. Un fait, un endroit.** `AGENTS.md` renvoie au manuel au lieu de le recopier ; le manuel
renvoie aux fiches. Un fait recopié devient faux dans l'une de ses copies.

**4. Une mesure remplace la précédente, elle ne s'empile pas.** Se garde : la valeur, les
conditions pour la reproduire (`arr check`, `arr.measure`, le morceau), la conséquence. Part : les
colonnes « avant / après », les alternatives « essayé, retiré » — vers la fiche de décision si la
rouvrir est plausible, sinon nulle part.

**5. La règle, pas son erratum.** Corriger la phrase plutôt que l'annoter : zéro « Corrigé le
JJ/MM », zéro proposition abandonnée conservée au-dessus de celle qui la remplace.

**6. Pas de récit, pas de journal de bug.** Le contrat qu'un bug a révélé se formule **comme
contrat** : « importer le vrai sounddevice initialise déjà PortAudio, qui échoue sans serveur de
son » (`tests/helpers.py`) se garde ; « la CI échouait parce que… » se jette.

**7. Pas d'état d'avancement dans un document de référence** : ni « où en est-on », ni
« prototype », ni liste « pas encore / à venir ». Ce rôle est aux issues, et à la rubrique
« Where we are » des épiques.

**8. Ce qui mérite un commentaire** : un invariant, un contrat, une unité ou une plage, un piège non
évident, une contrainte extérieure (un comportement de PipeWire, d'ALSA, d'audio.cpp, d'un format
de fichier). **Jamais la paraphrase de la ligne suivante.**

**9. Une règle écrite est soit vérifiée, soit annoncée comme non vérifiée.** Une règle **fausse
coûte plus qu'une règle absente** : elle est lue comme vraie et oriente le travail de travers.
Chaque interdiction porte donc soit son mécanisme de vérification (un test), soit la mention
qu'elle n'en a pas.

**10. Un savoir-faire exécutable va dans un script.** Tester l'audio sans bruit est
`scripts/loopback.sh`, où les pièges (le temps qu'il faut à PipeWire, le nettoyage après un
Ctrl+C) sont **implémentés**. Ne reste en texte que ce qu'un script ne peut pas absorber.

**11. Une formulation durable plutôt qu'un nombre exact.** Un nombre recopié à la main redevient
faux au prochain ajout. Écrire « chaque commande est dans le README », et laisser le compte au
test. Garder un nombre seulement si la grandeur porte un sens qu'une phrase ne rend pas — une
latence, un niveau cible, un seuil — et alors le **vérifier en l'écrivant**.

## Ce qui se garde, explicitement

Sans cette liste, un nettoyage zélé jette le bon :

- les **conventions audio** d'`AGENTS.md` (48 kHz, stéréo, `float32`, forme des tableaux) et les
  docstrings qui donnent unités, plages et valeurs par défaut ;
- le **câblage** de la carte son et de la table de mixage (« Audio en direct » d'`AGENTS.md`,
  `docs/manual/audio.md`) : une information non évidente et irremplaçable ;
- les **mesures actuelles** avec leurs conditions : niveaux cibles, latences, écarts de calage ;
- les renvois aux fiches (« fiche 006 ») ;
- une justification **durable** avec sa règle, comme « au-delà de 600 lignes, un agent lit en
  morceaux et rate des invariants » : la raison ne vieillit pas.

## Ce que la machine vérifie, et ce qu'elle ne vérifie pas

`tests/test_docs.py` tient les règles qui s'écrivent en expression régulière :

| Vérifié | Règle | Portée | Verdict |
|---|---|---|---|
| numéro d'issue ou de PR | 2 | commentaires et chaînes du Python, scripts shell | **échec** |
| mots-signaux temporels, errata datés | 1, 5 | commentaires et docstrings, documents rédigés | **échec** |
| chemin cité qui n'existe pas | — | documents rédigés | **échec** |
| taille d'un document rédigé | — | documents rédigés | avertissement au-delà de 600 lignes |

Les trois premiers **refusent le commit** : une règle qui avertit sans refuser finit ignorée. Le
quatrième reste un avertissement parce que découper un document est un chantier, pas une
correction. Une occurrence légitime se traite en **exception inscrite dans le test**, avec sa
raison — jamais en revenant à l'avertissement. Exceptions inscrites : les données d'essai du cycle
(`tests/test_workflow.py`), les fichiers d'un projet de morceau ou de l'utilisateur, que le manuel
nomme et qui ne sont jamais dans le dépôt.

Exemptés, pour une raison de genre : `docs/decisions/` (une fiche dit ce qui était le cas pour
justifier son choix, et se remplace au lieu de se réécrire), `docs/manual/reference.md` (engendré),
et ce fichier, qui doit nommer les mots qu'il proscrit.

**Les règles 3, 4, 6, 7, 8, 10 et 11 n'ont aucun mécanisme** : la duplication, la mesure qui
s'empile, le récit, l'état d'avancement, la paraphrase et le nombre recopié se voient à la lecture,
pas au `grep`. La skill `relire-docs` les cherche, une zone à la fois, à la demande.
