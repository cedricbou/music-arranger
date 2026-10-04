# Handoff

État au 4 octobre 2026.

## Où on en est

`arr` a changé de logique : on ne génère plus des pistes, on commande des **prises complètes**
du morceau à YuE2, à partir de la partition transcrite par SheetSage2, puis on en tire des
stems. Cédric a validé ce MVP à l'écoute sur « Freed from Desire » (Gala) : son au niveau,
mélodie reconnaissable, guitare funk audible.

| Élément | État |
|---|---|
| `transcribe` (SheetSage2) | fait ; vérifié sur Gala (ré mineur, 129 BPM, sections, accords) |
| `lyrics fetch` (LRCLIB) | fait ; rangement par section approximatif, à relire |
| `render`, `takes` (YuE2) | faits ; qualité validée à l'oreille par Cédric |
| `split tNNN`, `graft` | faits, mais **le calage n'aboutit qu'une fois sur trois** (voir plus bas) ; greffe à juger à l'oreille |
| `share` | fait ; non essayé avec un musicien |
| `capture`, `play -w/-o`, `record`, `calibrate`, `devices` | faits ; vérifiés sur une sortie virtuelle, **pas encore sur la Soundcraft ni avec Spotify en lecture** |
| Socle (`init`, `import`, `split`, `merge`, `tracks`, `mix`, `play`...) | inchangé |
| ACE-Step et ses commandes (`restem`, `polish`, `fix`, `add`, `complete`) | retirés |

## Mesures de référence (Gala, 3 min 40, Arc A770)

| Étape | Temps | Remarque |
|---|---|---|
| `transcribe` | 12 min 38 la première fois, 2 min 49 ensuite | sur XPU ; le résultat varie un peu d'un passage à l'autre (129 ou 130 BPM, 118 ou 120 mesures) |
| `render` (YuE2 Q8, Vulkan) | 4 min 35 | 219 s d'audio, 48 kHz stéréo |
| `split` 6 stems | ~20 s | |

### Calage des prises sur l'original : fragile

Trois prises fidèles de Gala, trois transcriptions différentes :

| Partition | Prise | Temps calés après étirement et décalage |
|---|---|---|
| 129 BPM, 118 mesures | 219,9 s | 83 % : greffable (essais `demo/essais-yue2/hybride_*`) |
| 130 BPM, 120 mesures | 219,4 s | 26 % |
| 129 BPM (corrigé par `arr`), ~120 mesures | 223,8 s | 33 % |

Causes : SheetSage2 ne donne pas la même grille de mesures d'un passage à l'autre (118 ou
120, avec des mesures à 5/8 dans l'intro silencieuse), et YuE2 ne tient pas le tempo au
centième. Un ajustement linéaire (une vitesse, un décalage) ne suffit donc pas. `split tNNN`
mesure `on_beat` et prévient sous 60 %. Suite prévue : synchronisation par déformation
temporelle (DTW sur chroma ou attaques, puis étirement par morceaux), issue GitHub ouverte.

Première prise fidèle (`cot=full`) contre l'original : tempo 129,03 contre 128,93 ; 118 mesures des
deux côtés ; 83 % des temps à moins de 35 ms ; décalage médian 0 ms ; même tonalité.
Prise libre (`cot=melody`) : tempo mesuré à 135,9, 131 mesures, donc non superposable.
Parts des stems d'une prise « funk live » : batterie ~50 %, basse 14 à 26 %, voix 20 à 25 %,
guitare 1 à 4 % (peu, selon Demucs, alors que Cédric l'entend bien).

### Studio (4 octobre, issue #7)

Vérifié sur une sortie PipeWire virtuelle silencieuse, sans toucher aux enceintes :

- `capture` : démarre au premier son, choisit seul la paire 7/8 d'un flux 12 canaux,
  s'arrête après le silence demandé ;
- duplex : décalage playback/prise de 21,3 ms, identique sur trois essais ;
- `calibrate` : retrouve ces 21,3 ms ;
- `record` avec décompte sur 15 s de Gala : prise calée à +0,04 ms, longueur identique.

Non vérifié, à faire par Cédric sur son installation :

- `capture` avec Spotify en lecture réelle, et `--play` (relance et pause par MPRIS) ;
- la Soundcraft : sortie sur 7/8, entrée de l'instrument, `calibrate` avec un vrai câble ;
- le confort du décompte et du métronome à l'oreille.

## Ce qui a été essayé et abandonné

À ne pas refaire sans élément nouveau. Tous les essais portaient sur « une piste de guitare
funk pour Gala ».

| Approche | Résultat |
|---|---|
| ACE-Step `cover` à partir d'un stem (`restem`, `derive`) | rend la même piste avec un autre grain ; le texte est ignoré dès que la source est suivie |
| ACE-Step `lego` / `complete` sur un contexte | calé sur les temps (97 à 100 %) mais rend un groupe entier, de qualité moyenne ; la guitare isolée par Demucs est inexploitable |
| ACE-Step texte seul | génère toujours un groupe, même pour « solo guitar » (guitare 3 à 31 % du son) |
| Stable Audio 3 (`TrackType: Instrument`) | vraie guitare isolée, bon tempo ; mais n'écoute pas le morceau : groove décorrélé, même en partant de la batterie ou du mix |
| Tri de riffs de 2 mesures par ressemblance de groove | le score ne correspond pas à ce que Cédric entend |

Conclusion vérifiée dans la littérature : ajouter une piste cohérente à un mix existe en
ligne (Suno Studio) et en recherche (StemGen, Diff-A-Riff, Stemphonic), pas en local ouvert.

## Reste à faire

### Suite directe du MVP

0. **Calage robuste des prises** (voir « Calage des prises ») : sans lui, `graft` reste une
   loterie.
1. **Retour d'écoute de Cédric** sur la greffe (`arr graft`) et sur `arr share` avec son
   guitariste : ce sont les deux fonctions non jugées.
2. **Éditer la partition sans ouvrir le fichier ABC** : transposer pour les chanteuses,
   couper ou répéter des sections pour la scène (`arr structure`). Le fichier
   `score/score.abc` porte des commentaires `% verse`, `% chorus` qui délimitent les sections.
3. **Assembler par section** : prendre le refrain d'une prise et le couplet d'une autre.
   Possible entre prises fidèles, puisqu'elles partagent les mesures.
4. **Paroles** : le rangement par section dépend de l'alignement entre l'enregistrement de
   Cédric et les horodatages LRCLIB ; un décalage constant est possible. À vérifier sur Gala.
5. **Adaptateur instrumental de YuE2** (`Mothersuperior/YuE2-instrumental-cot-full-loras`),
   non essayé : pour des prises sans voix, ou pour faire ressortir un instrument.

### Défauts et dettes connus

- `transcribe` et `render` sont muets pendant plusieurs minutes (sortie capturée).
- `analyze` garde une estimation de tonalité peu fiable ; préférer `transcribe`.
- `render` ne sait pas rendre une seule section.
- Les tests ne couvrent ni `models pull` ni les vrais moteurs.
- `models pull` télécharge le binaire audio.cpp depuis GitHub, pas depuis Hugging Face.
- beat_this : poids hébergés par l'université JKU, pas sur Hugging Face.

### Ménage possible sur le disque de Cédric

Téléchargés pendant les essais, plus utilisés par `arr` :

- `~/.local/share/arr/checkpoints` : ACE-Step, 14 Go ;
- `~/.local/share/arr/yue2/yue2-3b-bf16.gguf` (6,8 Go) et `yue2-vae-f32.gguf` (0,5 Go) ;
- `~/.local/share/arr/sheetsage2` : copie inutile, le modèle est dans le cache Hugging Face ;
- `~/.cache/huggingface/hub/models--ACE-Step--*` et `models--stabilityai--stable-audio-3-*`.

## Fichiers et emplacements

| Quoi | Où |
|---|---|
| Dépôt | https://github.com/cedricbou/music-arranger (privé) |
| Moteurs et poids | `~/.local/share/arr` (`audiocpp/`, `yue2/`, `envs/ss2/`) |
| Projet Gala de référence | `demo/gala-yue2` (ignoré par git) |
| Essais d'écoute des approches abandonnées | `demo/essais-*` (ignorés par git) |
| Jeton Hugging Face | `.env` à la racine (ignoré par git) ; inutile pour YuE2 et SheetSage2 |
