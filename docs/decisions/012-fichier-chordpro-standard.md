# 012 — Le prompteur de scène lit un fichier ChordPro standard, qui appartient à arr

Date : 24 novembre 2026. État : en vigueur.

## Contexte

Sur scène, Cédric lit le morceau sur le prompteur de namfoop, une autre application. Taper à
la main les accords d'un morceau de 74 mesures, puis les tenir à jour avec le projet, ne tient
pas. arr a déjà les accords sur la grille de mesures (fiche 008), les sections (fiche 010) et
les paroles rangées par section.

## Ce qui a été comparé

| Moyen | Pourquoi pas, ou pourquoi |
|---|---|
| directives propres à namfoop (`x_namfoop_…`) | lient arr à un lecteur ; le son d'une section se choisit de toute façon dans namfoop |
| `{flow}` d'OnSong pour la structure | pas du ChordPro standard ; les passages sont donc écrits en entier, dans l'ordre joué |
| accords sur les syllabes, paroles complètes | sur scène on lit des mesures ; les paroles ne sont qu'un repère |
| l'antisèche (`sheet.toml`) comme source | elle résume pour l'impression ; seule sa transposition est reprise |
| grilles standard `{start_of_grid}` | retenu : la façon standard d'écrire des mesures, lue par tout lecteur qui dessine les grilles |

## Décision

- **Un fichier par morceau**, `export/<dossier>.cho`, ChordPro 6 sans aucune directive `x_`.
  La première ligne est un commentaire `#` qui nomme arr et le projet.
- **Une grille par passage**, dans l'ordre joué, `label` = nom du passage, `shape` = mesures
  par ligne × temps : quatre mesures par ligne, une case par temps, l'accord où il commence,
  `.` tant qu'il tient, `N.C.` sans accord. Les paroles chantées sur la ligne suivent la
  dernière barre, jointes par ` / `.
- **Une mesure d'une autre longueur** a sa grille, de même nom, entre deux `{time}` : la forme
  d'une grille est uniforme. arr ne connaît que les temps : le dénominateur est toujours 4.
- **Les noms comptent** : le lecteur relie un son à un passage par son nom, donc tous les
  refrains portent le même ; les couplets sont numérotés dans l'ordre joué.
- **Le fichier appartient à arr** : il se réécrit en entier ; on corrige le projet, jamais le
  fichier, et on le copie soi-même vers le prompteur.
- **La structure** vient de l'original (un passage par section) tant que celle du groupe ne
  se décrit pas ; l'écriture ne dépend pas des outils qui la modifient.

## Conséquences

- Un lecteur qui ne dessine pas les grilles en montre les lignes comme du texte.
- Ce que le prompteur fait du fichier ne se vérifie pas ici : il dépend du lecteur.
