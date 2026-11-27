# 016 — Des passages comptés à l'oreille notent la grille

Date : 26 novembre 2026. État : remplacée par la fiche 019 pour la commande (`arr play --mark` et `arr truth`
sont retirées) ; en vigueur pour la datation d'une frappe et pour la note. Complète les fiches 008, 013 et 015.

## Contexte

Un changement de la grille se vérifiait contre la sortie du détecteur lui-même
(`scripts/beat_report.py`) et, le jour même, à l'oreille sur `arr play`. Une demi-heure d'écoute
pour la fiche 015 a donné cinq constats qu'aucun test ne peut rejouer. Il manquait une référence
fixe, indépendante du détecteur.

## Décision

- **Le musicien repère les barres dans `arr play --mark`** : Espace sur le 1 de chaque mesure
  d'un passage de 30 à 60 s, une seule passe. Les temps ne se tapent pas : ils se jugent au
  nombre de temps que la grille compte dans chaque mesure repérée.
- **Une frappe est datée par un fil qui lit le clavier**, pas par l'écran (qui ne passe que
  vingt fois par seconde), et rangée à la position qui s'entendait : chaque bloc audio annonce
  l'heure où il sortira du convertisseur, la frappe se lit sur la médiane des blocs voisins.
- **Les repères vivent dans le projet**, `truth/<passage>.vNNN.toml`, jamais dans le dépôt.
  Une nouvelle passe est une nouvelle version ; rien n'est écrasé.
- **La note** (`truth.score`, `arr truth`) porte sur la grille que lit `arr play` (fiches 008,
  013, 015) : barres à moins de 70 ms d'une barre repérée (F-mesure de `mir_eval.beat`, sans
  écarter les cinq premières secondes : les intros comptent), et mesures repérées où la grille
  compte le nombre de temps annoncé (4 par défaut). Un temps va à la mesure dont la barre
  repérée le précède à un demi-temps près : le compte ne dépend pas de la précision de la frappe.
- **Chaque lancement est gardé** (`truth/runs.json`) : un passage qui baisse sur l'une des deux
  notes est « moins bien », et la commande sort en erreur.

## Complément du 26 novembre 2026 : les accords

Chaque version d'un passage a son fichier d'accords (`.vNNN.chords.txt`), une ligne par mesure,
rempli des accords d'`arr play`, que le musicien corrige : un accord, ou deux par moitiés de
mesure. Le musicien a choisi le fichier pré-rempli en sachant que la référence penche alors vers
`arr` : la ligne garde donc l'accord transcrit à droite de la barre, et la note dit combien de
mesures ont été corrigées. Le fichier n'est jamais récrit. La note (`truth.chord_score`) est
celle de `mir_eval.chord`, `root` et `majmin`, pondérée par la durée, contre les accords
affichés (après `measure.seat_chords`), pas contre la transcription brute.

## Ce que la mesure a montré

Sur la sortie virtuelle (`scripts/loopback.sh`), 8 s de lecture, blocs de 1024 échantillons :

- l'écart entre l'heure annoncée d'un bloc et sa position varie de 1,0 ms en tout (écart-type
  0,15 ms) ; des frappes fictives espacées de 0,5 s d'horloge sont lues à 0,5 s ± 0,2 ms ;
- la position que suit l'écran (échantillons mis en file) est en avance de 0 à 21 ms sur la
  position entendue : un bloc entier, que la datation par bloc retire ;
- une frappe écrite dans un pseudo-terminal est datée moins de 30 ms après son envoi (borne du
  test, qui dort entre les deux).

## Limites

- La sortie virtuelle annonce un retard nul : le retard réel de la carte son (convertisseur,
  table) n'est vu que si le pilote l'annonce. L'essai sur un morceau au clic le dira ; un
  écart constant se lit dans la colonne « Écart » d'`arr truth`.
- L'anticipation propre au musicien n'est pas retirée : pas de réglage tant que l'essai n'en
  montre pas une.
- Un passage se nomme par ses sections : renommer ou redécouper une section laisse l'ancien
  passage sous son ancien nom, avec ses instants, toujours notés.
