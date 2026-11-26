# 019 — Ce que le musicien décide vit dans une couche à part, appliquée à la lecture

Date : 26 novembre 2026. État : en vigueur, pour les passages jugés bons. Complète les fiches 015 et 018.

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
- Les corrections de barres devront passer avant `grid.regular_bars`, qui ne doit pas déplacer
  une barre fixée par le musicien : ce n'est pas fait ici.
