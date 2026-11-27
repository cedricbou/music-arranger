# 019 — Ce que le musicien décide vit dans une couche à part, appliquée à la lecture

Date : 26 novembre 2026, complétée le 27 pour les barres. État : en vigueur, pour les passages jugés bons
et les barres corrigées. Complète les fiches 015 et 018 ; remplace la commande de la fiche 016.

## Contexte

`arr` sait dire où il hésite (fiche 018), mais le musicien ne peut pas lui répondre : un « ? »
écouté reste un « ? », et les barres tapées dans `arr play --mark` (fiche 016) ne changent rien à
l'écran. La relecture (`arr review`) lui donne la parole : dire qu'un passage est bon, puis, dans
les stories suivantes, corriger des barres, des accords, une erreur qui court sur tout le morceau.
Il faut un endroit pour ces décisions, qui survive à `arr analyze` et à `arr transcribe`.

## Décision

- **Un seul endroit : `review/` du projet.** Un fichier par décision (`v001.toml`, `v002.toml`…),
  chacun portant tout l'état ; le dernier fait foi, aucun n'est récrit. Revenir en arrière, c'est
  reculer d'une version.
- **Ce que les détecteurs ont trouvé n'est jamais modifié** (`analysis.json`, `score/`), comme
  pour les temps entendus deux fois (fiche 015). La couche s'applique à la lecture, là où la
  grille et le doute se lisent déjà : `song_doubts(p, mine=True)` retire les mesures jugées
  bonnes. Écran, prompteur et antisèche suivent sans la connaître.
- **Une décision tient aux mesures sur lesquelles elle a été prise**, chacune gardée par ses
  temps. Elle s'applique à une mesure de la grille du jour si celle-ci commence au même endroit
  à un demi-temps près et porte les mêmes temps à 70 ms près, une fois les deux mesures
  superposées. Le détecteur redit la même chose : la décision tient. Il lit le passage
  autrement : elle ne s'applique pas, et la question revient.
- **Un passage à relire** : les mesures douteuses voisines, une mesure avant, une après ; deux
  passages qui se touchent n'en font qu'un. Ses états : à relire, jugé bon ; « corrigé » viendra
  avec les corrections.
- **`arr doubts` part** : `arr review --list` dit la même chose, avec l'état de chaque passage.

## Complément du 27 novembre 2026 : les barres corrigées

- **Le musicien donne le compte, `arr` garde ses temps.** Dans `arr review`, m joue le passage
  une fois après quatre clics ; Espace se tape sur le 1 de chaque mesure. Chaque frappe est
  datée à l'instant où elle s'entendait (fiche 016) puis menée au temps détecté le plus proche ;
  à plus d'un demi-temps de tout temps, elle est refusée.
- **Une correction porte ses barres et tous ses temps**, de la première frappe à la dernière.
  `review.fix_grid` les met à la place de ce que le détecteur a lu entre ces deux instants, à un
  quart de temps près. Elle vaut donc quoi que le détecteur relise : la sienne l'emporte, sans
  signature à comparer.
- **Rien ne bouge hors du passage.** Les barres régulières (`grid.regular_bars`, fiche 013) sont
  posées sur ce que le détecteur a lu, sans les corrections ; celles du passage sont remplacées
  ensuite. Une barre fixée ne peut donc pas être déplacée, et la première barre après le
  passage reste où elle était. Le prix : un 1 décalé dans tout le morceau laisse une mesure
  courte ou longue à chaque bord du passage, jusqu'à ce que la correction soit étendue (story
  « une erreur sur tout le morceau »).
- **Une mesure qui ne tient pas quatre temps se demande** : vraie mesure, ou temps manqué ou
  entendu deux fois. Pour la seconde réponse, quatre temps égaux sont posés entre les deux
  frappes. Cela couvre deux temps manqués de suite, que `grid.fill_beats` ne comble pas (fiche 017).
- **Les accords ne sont pas réécrits.** Ils sont replacés sur les barres du détecteur comme
  avant (`measure.seat_chords`, fiche 008), puis la grille est redessinée sur les barres du
  musicien : un accord reste à son instant, les barres bougent autour.
- **Deux lectures de la grille** : `song_bars` (barres régulières puis corrections) pour l'écran,
  le prompteur et l'antisèche ; `song_grid` (barres détectées puis corrections) pour le décompte,
  le clic et les sections, comme avant.
- **Les passages de `truth/` se lisent comme des corrections**, avant celles de `review/`. Le
  musicien y a écrit son nombre de temps par mesure : là où le détecteur en compte un autre, ce
  nombre de temps égaux est posé. `arr play --mark` et `arr truth` partent ; `truth.score` et
  `chord_score` notent la lecture brute contre les corrections dans `scripts/grid_score.py`.
- **`arr review --undo`** écrit une version sans la dernière correction : rien n'est effacé.

## Ce qui a été écarté

- **Un quart de mesure de tolérance sur le début d'une mesure**, comme prévu au cadrage : en
  4/4 c'est un temps entier, l'écart même d'un 1 décalé d'un temps. Un demi-temps sépare les
  deux cas.
- **Un fichier par passage**, comme `truth/` : un passage n'a pas de nom stable, ses bornes
  bougent quand une mesure voisine devient douteuse. L'état entier dans chaque version reste
  petit (quelques mesures par décision).

## Limites

- Aucune mesure sur la bibliothèque : combien de jugements survivent à un `arr analyze` réel
  reste à constater. beat_this est déterministe sur le même fichier ; un original remplacé par
  une autre édition décale tout, et tout serait redemandé.
- Une mesure de plus avant et après suffit-elle pour juger un passage ? À dire à l'oreille.
- Un 1 que le détecteur a manqué ne peut pas être tapé : la frappe tombe à un temps entier de
  tout temps détecté et est refusée. Taper les mesures voisines ne suffit pas : les deux mesures
  n'en feraient qu'une. Cette barre-là ne se corrige pas encore.
- Les accords sont replacés sur les barres du détecteur, pas sur celles du musicien : là où il
  s'est trompé de plusieurs temps, un accord peut rester décalé jusqu'à la correction des accords.
- Les numéros de mesure d'`arr sections` suivent les barres détectées, ceux de l'écran les barres
  régulières : l'écart existait avant, les corrections s'appliquent aux deux.
