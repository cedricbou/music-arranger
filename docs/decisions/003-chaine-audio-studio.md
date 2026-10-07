# 003 — Capturer sur les entrées de la table, jouer et enregistrer en duplex

Date : 5 octobre 2026. État : en vigueur.

## Contexte

Installation de Cédric : l'ordinateur joue sur une PreSonus AudioBox iTwo (sortie par
défaut du système) ; ses deux sorties arrivent en analogique sur les voies 7/8 d'une
Soundcraft Signature 12 MTK, qui renvoie 14 canaux à l'ordinateur par USB. Le gain se
règle sur la table. Tout passe par PipeWire.

## Erreurs à ne pas refaire

- Avoir pris la Soundcraft pour la **sortie** de lecture : le son sort par la PreSonus.
- Avoir capturé la copie numérique de la sortie par défaut : chez Cédric, la capture
  habituelle est sur les **entrées** 7/8 de la table (un fichier vide en a résulté).
- Avoir ouvert l'entrée par JACK et la sortie « par défaut » par ALSA : PortAudio refuse
  (« Illegal combination of I/O devices »). Les deux doivent venir du même pilote.
- Avoir fait confiance à la latence annoncée par PortAudio : elle est aberrante ici.

## Décision

- **Capture** (`arr capture`, `arr levels`) : `parec` sur une source PipeWire, par défaut
  les entrées de la Soundcraft, canaux 7/8. `source = "monitor"` prend la copie numérique.
- **Lecture et enregistrement** (`arr play`, `arr record`) : `sounddevice` sur l'API JACK
  de PipeWire, entrée et sortie dans un seul flux duplex. La sortie par défaut est celle
  du pilote de l'entrée (`studio.duplex_devices`).
- **Latence** : mesurée par `arr calibrate` (clics rejoués, corrélation), écrite dans
  `~/.config/arr/audio.toml`. Le son de l'ordinateur revient déjà sur le canal 7 : aucun
  câble à ajouter.
- **Spotify** : lecture du titre, relance et pause par D-Bus (MPRIS), en local.

## Mesures

Sur une sortie PipeWire virtuelle : décalage playback/prise de 21,3 ms, identique sur trois
essais ; `record` avec décompte sur 15 s : prise calée à +0,04 ms. Sur l'installation
réelle, `calibrate` a mesuré 68 ms.

## Conséquences

- Pour tester l'audio en direct, un agent crée une sortie virtuelle silencieuse et pointe
  `ARR_AUDIO` dessus. Il ne joue jamais sur les enceintes et ne pilote jamais Spotify.
- `arr record` refuse de garder une prise silencieuse.
