# 019 — Ce que le musicien décide vit dans une couche à part, appliquée à la lecture

Date : 26 novembre 2026, complétée le 27 pour les barres, les accords et les
erreurs de tout un morceau. État : en vigueur, pour les
passages jugés bons, les barres et les accords corrigés. Complète les fiches 015 et 018 ; remplace la commande de la fiche 016.

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

## Complément du 27 novembre 2026 : les accords corrigés

- **Le musicien récrit les accords d'un passage dans son éditeur** (touche a) : un fichier
  temporaire, une ligne par mesure de la grille du moment, une case par temps, « / » pour tenir,
  « N.C. » pour aucun. Rien ne reste dans le projet que la correction elle-même, dans `review/`.
- **Une correction d'accords est gardée par instant** : (début, fin, nom) pour tout le passage.
  Elle ne dépend donc pas des barres : corrigées avant, a s'ouvre sur elles ; corrigées après,
  les accords restent où ils sonnent.
- **Le nom reste celui que le musicien a écrit** (`F#m7`), sans passer par la notation de la
  transcription : `sheet.chord_name` rend tel quel un nom sans « : ». Un nom qu'`arr` montrait
  et que le musicien n'a pas touché garde son étiquette d'origine.
- **Un seul endroit pose les corrections** : `song_chart`, après `measure.seat_chords`, par
  `chordfix.lay_chords`. L'écran, le fichier du prompteur et la proposition d'antisèche lisent
  tous `song_chart`. `sheet.toml`, une fois écrit, fait toujours foi (fiche 009).
- **Corriger les accords d'un passage, c'est aussi dire que ses barres sont bonnes** : le
  passage perd son « ? ». Après une correction gardée, le passage rejoue : barres, puis accords.
- **`arr review --undo`** reprend la correction la plus récente, de barres ou d'accords.

## Complément du 27 novembre 2026 : ce qui se trompe sur tout un morceau

- **Le signe** (`grid.tempo_split`) : par section, la médiane des écarts entre temps ; deux
  groupes dont l'un vaut le double de l'autre à 10 % près, seize temps au moins dans chacun.
  Sur les 40 projets de la bibliothèque, la question se pose pour deux morceaux : celui du
  constat (10 sections vers 67, 6 vers 136) et un second (2 sections à 71, 9 à 143). Un morceau
  à 115 et 158 selon les sections n'est pas concerné.
- **La réponse se prend à l'oreille** : une section lue au tempo rapide joue en boucle avec un
  clic par temps, à l'un ou l'autre tempo. Le clic lent tombe un temps sur deux, du côté des
  barres détectées de la section.
- **Recompter** (`review.retempo`, avant tout le reste dans `detected_grid`) : au tempo lent, un
  temps sur deux et une barre sur deux (celles qui continuent le compte de quatre depuis la
  section d'avant) ; au tempo rapide, un temps et une barre de plus au milieu de chaque écart.
  Simulé sur le morceau du constat : 101 mesures dont 2 hors quatre temps telles quelles ; 79
  dont 1 en gardant 67 ; 150 dont 3 en gardant 136. Une plage n'est recomptée que si elle est
  encore lue à l'autre tempo : une nouvelle analyse qui la lit bien n'est pas recomptée deux fois.
- **Un temps ajouté en recomptant n'est pas douteux** : il vient du musicien.
- **Le 1 décalé** (`grid.bar_shift`, `grid.shift_bars`) : après des barres tapées sans mesure
  recomptée, si chaque frappe suit la barre écrite du même nombre de temps, ce décalage est
  proposé pour la section ou le morceau, et rangé comme une plage et un nombre de temps. Il
  s'applique aux barres régulières avant les barres tapées.
- **`bpm` de `song.toml` et les bornes des sections ne sont pas touchés** : la relecture ne
  récrit rien de ce que les autres commandes ont écrit. Si le tempo gardé n'est pas celui de
  `song.toml`, la relecture le dit.

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
  s'est trompé de plusieurs temps, un accord peut rester décalé tant qu'il n'est pas corrigé (touche a).
- Un nom d'accord est accepté sur sa forme (une note, des chiffres et qualités usuels, une basse) :
  `Cmaj7#11` passe ; `Cmja7` et `Hm` sont refusés. Un nom bien formé mais faux à l'oreille ne se contrôle pas.
- Une correction d'accords n'est pas reportée sur les passages semblables, et l'antisèche déjà
  écrite ne la reçoit pas.
- Les numéros de mesure d'`arr sections` suivent les barres détectées, ceux de l'écran les barres
  régulières : l'écart existait avant, les corrections s'appliquent aux deux.
