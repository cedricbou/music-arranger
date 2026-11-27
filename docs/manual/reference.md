# Référence des commandes

<!-- Fichier généré par scripts/gen_reference.py : ne pas l'éditer à la main. -->

Toutes les commandes d'`arr`, avec leurs arguments et leurs options, dans l'ordre de
`arr --help`. Cette page est produite à partir du code : elle est toujours à jour. Pour
des explications et des exemples, voir les autres pages du [manuel](README.md).

- [`arr sheet`](#arr-sheet) : Montre l'antisèche du morceau : tonalité, tempo, structure, accords des passages clés, rappels.
- [`arr init`](#arr-init) : Crée un projet dans le dossier NAME.
- [`arr import`](#arr-import) : Ajoute un morceau complet, ou une piste avec --as.
- [`arr rename`](#arr-rename) : Nomme le dossier de chaque morceau d'après son artiste et son titre (paper-lanterns--night-drive).
- [`arr analyze`](#arr-analyze) : Détecte temps, mesures, tempo et tonalité.
- [`arr transcribe`](#arr-transcribe) : Transcrit l'original en partition : mélodie, accords, tempo, tonalité, sections.
- [`arr render`](#arr-render) : Rend une prise complète du morceau (voix et groupe) à partir de la partition.
- [`arr takes`](#arr-takes) : Liste les prises.
- [`arr graft`](#arr-graft) : Greffe des stems d'une prise sur le mix : en plus de l'original, ou à sa place.
- [`arr share`](#arr-share) : Prépare un dossier pour le musicien : sa partie seule, le mix, et le mix sans lui.
- [`arr split`](#arr-split) : Sépare l'original ou une prise en stems.
- [`arr merge`](#arr-merge) : Fusionne des pistes en une seule, pour corriger une séparation qui a mal réparti un instrument.
- [`arr tracks`](#arr-tracks) : Montre ce qui joue dans le mix : pistes actives d'abord, muettes ensuite.
- [`arr rm`](#arr-rm) : Retire des pistes, une version ou des prises dont tu n'as plus besoin.
- [`arr pick`](#arr-pick) : Choisit la version active d'une piste.
- [`arr gain`](#arr-gain) : Règle le volume d'une piste dans le mix, en dB.
- [`arr mute`](#arr-mute) : Sort une piste du mix sans la supprimer.
- [`arr mix`](#arr-mix) : Mixe les versions actives dans mix/mix.flac.
- [`arr play`](#arr-play) : Écoute le mix (complet ou partiel), une piste ou une prise, en entier ou par sections.
- [`arr review`](#arr-review) : Fait écouter un par un les passages où `arr` n'est pas sûr du compte des mesures, pour les juger ou les corriger.
- [`arr nudge`](#arr-nudge) : Décale une piste dans le mix, en entier ou par section, sans toucher à ses fichiers.
- [`arr align`](#arr-align) : Cale les stems d'une prise sur l'original, section par section.
- [`arr chordpro`](#arr-chordpro) : Écrit le morceau en fichier ChordPro pour un prompteur de scène : export/<dossier>.cho.
- [`arr capture`](#arr-capture) : Enregistre ce que joue l'ordinateur dans un nouveau projet.
- [`arr record`](#arr-record) : Enregistre ton instrument pendant que le playback joue, avec un décompte au tempo.
- [`arr calibrate`](#arr-calibrate) : Mesure le retard entre ce qui est joué et ce qui est enregistré, pour caler tes prises.
- [`arr levels`](#arr-levels) : Vumètres par canal, pour vérifier le câblage et régler le gain sur la table.
- [`arr check`](#arr-check) : Mesure chaque fichier audio du projet : durée, niveaux, volume, anomalies.
- [`arr devices`](#arr-devices) : Montre les réglages audio effectifs et les périphériques disponibles.
- [`arr doctor`](#arr-doctor) : Vérifie la carte Intel Arc et la présence des modèles.
- [`arr sections set`](#arr-sections-set) : Définit les sections en numéros de mesure (inclusifs, à partir de 1).
- [`arr sections snap`](#arr-sections-snap) : Pose les bornes des sections sur les barres de mesure, pour des boucles qui retombent juste.
- [`arr sections list`](#arr-sections-list) : Affiche les sections.
- [`arr lyrics fetch`](#arr-lyrics-fetch) : Télécharge les paroles depuis LRCLIB et les range par section dans lyrics.txt.
- [`arr lyrics show`](#arr-lyrics-show) : Montre les paroles section par section, chaque ligne avec la mesure où elle commence.
- [`arr set new`](#arr-set-new) : Crée une setlist, à lancer depuis le dossier qui contient les projets.
- [`arr set add`](#arr-set-add) : Ajoute des morceaux, ou un entracte, à une setlist.
- [`arr set edit`](#arr-set-edit) : Ouvre le fichier de la setlist : réordonner, retirer, transposer un morceau pour ce concert.
- [`arr set show`](#arr-set-show) : Affiche l'ordre du concert : tonalité, tempo et durée de chaque morceau, et ce qui manque.
- [`arr set print`](#arr-set-print) : Écrit le PDF des antisèches du concert : une feuille A4 en colonnes, un bloc par morceau.
- [`arr midi ports`](#arr-midi-ports) : Liste les ports MIDI de la machine, et montre celui qu'arr utilise.
- [`arr midi send`](#arr-midi-send) : Envoie un changement de programme ou un contrôleur, pour tester une pédale.
- [`arr midi monitor`](#arr-midi-monitor) : Affiche les messages MIDI reçus, pour voir ce qu'envoie une pédale ou un clavier.
- [`arr models pull`](#arr-models-pull) : Installe les modèles et leurs moteurs, et les met à jour (seule commande qui télécharge des modèles).

## `arr sheet`

```
arr sheet [OPTIONS]
```

Montre l'antisèche du morceau : tonalité, tempo, structure, accords des passages clés, rappels.

Tant que sheet.toml n'existe pas, elle est déduite du projet. Dès qu'il existe, lui seul fait foi : modifie-le pour montrer moins, plus, ou autre chose.

| Option | Défaut | Rôle |
|---|---|---|
| `--edit` | non | Écrit la proposition dans sheet.toml s'il manque, et l'ouvre. |
| `--note` |  | Ajoute un rappel à l'antisèche. |
| `--transpose` |  | Demi-tons de transposition : --transpose=-2 joue un ton plus bas ; 0 pour l'original. |
| `--reset` | non | Revient à la proposition ; sheet.toml part dans trash/. |
| `--pdf` | non | Écrit aussi export/sheet.pdf, pour voir l'antisèche imprimée. |

## `arr init`

```
arr init [OPTIONS] NAME
```

Crée un projet dans le dossier NAME.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` | obligatoire | Nom du projet : un dossier de ce nom est créé ici. |

| Option | Défaut | Rôle |
|---|---|---|
| `--from` |  | Morceau à importer. |

## `arr import`

```
arr import [OPTIONS] SOURCE
```

Ajoute un morceau complet, ou une piste avec --as.

| Argument | Défaut | Rôle |
|---|---|---|
| `SOURCE` | obligatoire | Fichier audio à importer (tout format lu par ffmpeg). |

| Option | Défaut | Rôle |
|---|---|---|
| `--as` |  | Importer comme piste (stem ou idée), ex. bass. |

## `arr rename`

```
arr rename [OPTIONS]
```

Nomme le dossier de chaque morceau d'après son artiste et son titre (paper-lanterns--night-drive).

À lancer depuis le dossier qui contient les projets. Les setlists suivent. Un morceau sans artiste, ou dont le nouveau nom est déjà pris, garde son dossier.

| Option | Défaut | Rôle |
|---|---|---|
| `--yes`, `-y` | non | Renomme sans demander. |

## `arr analyze`

```
arr analyze
```

Détecte temps, mesures, tempo et tonalité.

Garde aussi ce que le détecteur entendait entre les temps : un temps manqué dans un passage sans batterie est alors compté partout où la grille se lit (écran, prompteur, horloge, décompte). La dernière ligne dit combien de passages restent à relire (`arr review`).

## `arr transcribe`

```
arr transcribe
```

Transcrit l'original en partition : mélodie, accords, tempo, tonalité, sections.

La dernière ligne dit combien de passages restent à relire (`arr review`).

## `arr render`

```
arr render [OPTIONS]
```

Rend une prise complète du morceau (voix et groupe) à partir de la partition.

Par défaut la prise est fidèle : mélodie et accords imposés, même tempo et mêmes mesures que l'original, donc ses stems peuvent y être greffés.

| Option | Défaut | Rôle |
|---|---|---|
| `--style`, `-s` | obligatoire | Formation et couleur, en anglais : genre, instruments, voix. |
| `--free` | non | Mélodie seule : accompagnement réinventé, tempo libre. |
| `--seed` | `-1` | Graine ; -1 pour aléatoire. |
| `-n` | `1` | Nombre de prises. |

## `arr takes`

```
arr takes
```

Liste les prises.

## `arr graft`

```
arr graft [OPTIONS] TAKE STEMS...
```

Greffe des stems d'une prise sur le mix : en plus de l'original, ou à sa place.

| Argument | Défaut | Rôle |
|---|---|---|
| `TAKE` | obligatoire | Prise dont viennent les stems (ex. t001), déjà séparée par arr split. |
| `STEMS` | obligatoire | Stems de la prise à faire entendre : guitar, drums... |

| Option | Défaut | Rôle |
|---|---|---|
| `--replace` | non | Coupe les mêmes stems de l'original. |

## `arr share`

```
arr share TRACK
```

Prépare un dossier pour le musicien : sa partie seule, le mix, et le mix sans lui.

| Argument | Défaut | Rôle |
|---|---|---|
| `TRACK` | obligatoire | Piste du musicien (ex. bass, ou t001.guitar). |

## `arr split`

```
arr split [OPTIONS] [TAKE]
```

Sépare l'original ou une prise en stems.

Les stems de l'original deviennent les pistes drums, bass... Ceux d'une prise deviennent t001.drums, t001.bass..., muets et calés sur l'original : `arr graft` les fait entendre.

| Argument | Défaut | Rôle |
|---|---|---|
| `TAKE` |  | Prise à séparer (ex. t001) ; sinon l'original. |

| Option | Défaut | Rôle |
|---|---|---|
| `--model` | `htdemucs_6s` | htdemucs_6s : 6 stems ; htdemucs_ft : 4 stems, plus précis. |
| `--shifts` | `1` | Passes moyennées : 2 ou plus réduit les fuites, temps multiplié d'autant. |

## `arr merge`

```
arr merge [OPTIONS] TRACKS...
```

Fusionne des pistes en une seule, pour corriger une séparation qui a mal réparti un instrument.

| Argument | Défaut | Rôle |
|---|---|---|
| `TRACKS` | obligatoire | Pistes à fusionner. |

| Option | Défaut | Rôle |
|---|---|---|
| `--as` | obligatoire | Nom de la piste résultante. |

## `arr tracks`

```
arr tracks [OPTIONS] [TRACK]
```

Montre ce qui joue dans le mix : pistes actives d'abord, muettes ensuite.

| Argument | Défaut | Rôle |
|---|---|---|
| `TRACK` |  | N'afficher que cette piste, avec son historique. |

| Option | Défaut | Rôle |
|---|---|---|
| `--versions`, `-v` | non | Afficher l'historique de chaque piste. |

## `arr rm`

```
arr rm [OPTIONS] NAMES...
```

Retire des pistes, une version ou des prises dont tu n'as plus besoin.

Par défaut tout part dans la corbeille du projet (trash/), d'où on peut le reprendre à la main. --purge libère la place tout de suite ; `arr rm --purge trash` vide la corbeille.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAMES` | obligatoire | Pistes ou prises à retirer (ex. guitar piano t002). |

| Option | Défaut | Rôle |
|---|---|---|
| `--version`, `-v` |  | Ne retirer que cette version d'une piste. |
| `--purge` | non | Efface définitivement au lieu de mettre à la corbeille. |
| `--yes`, `-y` | non | Ne demande pas de confirmation pour --purge. |

## `arr pick`

```
arr pick TRACK VERSION
```

Choisit la version active d'une piste.

| Argument | Défaut | Rôle |
|---|---|---|
| `TRACK` | obligatoire | Piste dont on change la version active. |
| `VERSION` | obligatoire | Version à rendre active (ex. v002) ; arr tracks PISTE les liste. |

## `arr gain`

```
arr gain TRACK DB
```

Règle le volume d'une piste dans le mix, en dB.

| Argument | Défaut | Rôle |
|---|---|---|
| `TRACK` | obligatoire | Piste à régler. |
| `DB` | obligatoire | Gain en dB, par rapport à la piste telle quelle : -5, 0, +3. |

## `arr mute`

```
arr mute [OPTIONS] TRACK
```

Sort une piste du mix sans la supprimer.

| Argument | Défaut | Rôle |
|---|---|---|
| `TRACK` | obligatoire | Piste à sortir du mix. |

| Option | Défaut | Rôle |
|---|---|---|
| `--off` | non | Réactive la piste. |

## `arr mix`

```
arr mix [OPTIONS]
```

Mixe les versions actives dans mix/mix.flac.

| Option | Défaut | Rôle |
|---|---|---|
| `--without`, `-w` |  | Piste à exclure. (répétable) |
| `--only`, `-o` |  | Ne garder que ces pistes. (répétable) |

## `arr play`

```
arr play [OPTIONS] [NAME] [VERSION]
```

Écoute le mix (complet ou partiel), une piste ou une prise, en entier ou par sections.

Pendant la lecture, l'écran montre ce qui joue (pistes, versions, gains), la section en cours, le calage qui s'y applique et sa grille d'accords, l'accord du moment surligné.

Espace met en pause et reprend ; flèche gauche revient à la mesure d'avant, flèche droite passe à la suivante. Ctrl+C arrête.

Une mesure marquée « ? » sur la grille est une mesure dont `arr` n'est pas sûr du compte : d saute au prochain passage douteux. La marque ne change ni la grille ni le fichier du prompteur ; elle part quand `arr review` a jugé le passage bon.

Avec --clock, un prompteur de scène sur le même ordinateur (namfoop) suit la lecture : l'horloge donne le tempo dès le décompte, Start part sur la mesure 1 du fichier ChordPro, la position suit les sections, les flèches et la boucle, la pause envoie Stop.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` |  | Piste ou prise (ex. t001) ; sinon le mix. |
| `VERSION` |  | Version d'une piste ; sinon la version active. |

| Option | Défaut | Rôle |
|---|---|---|
| `--without`, `-w` |  | Mix sans cette piste (ex. -w bass pour jouer par-dessus). (répétable) |
| `--only`, `-o` |  | Mix de ces seules pistes. (répétable) |
| `--section`, `-s` |  | Sections à jouer, enchaînées dans l'ordre donné : -s verse,chorus ou -s verse -s chorus. (répétable) |
| `--loop`, `-l` | non | Rejoue en boucle jusqu'à Ctrl+C. |
| `--count-in` | `0` | Mesures de décompte avant de commencer (pas à chaque boucle). |
| `--clock` | non | Envoie l'horloge et le transport MIDI sur le port « arr:transport » : un prompteur de scène suit le morceau. |

## `arr review`

```
arr review [OPTIONS]
```

Fait écouter un par un les passages où `arr` n'est pas sûr du compte des mesures, pour les juger ou les corriger.

Un passage, ce sont des mesures douteuses voisines (un de leurs temps a été entendu faiblement), avec une mesure avant et une après. Il joue en boucle, sur l'original, avec sa grille d'accords et la raison du doute. Entrée dit qu'il est bon et passe au suivant ; flèche gauche et flèche droite mènent à un autre passage sans répondre ; Espace met en pause ; q quitte.

m corrige les barres : après quatre clics au tempo, le passage joue une fois, et Espace se tape sur le 1 de chaque mesure, puis sur le 1 qui suit la dernière. Chaque frappe va au temps détecté le plus proche. Pendant les frappes, la grille du moment défile ; r recommence, Échap abandonne. Là où deux frappes ne tiennent pas quatre temps, `arr` demande si la mesure est vraiment plus courte ou plus longue, ou si un temps a été manqué ou entendu deux fois : il pose alors quatre temps égaux entre les deux frappes. Le passage rejoue avec la nouvelle grille sous l'ancienne : Entrée la garde, r refait les frappes, Échap abandonne.

Une correction se voit partout où le morceau se lit : `arr play`, `arr chordpro`, `arr sheet`, le décompte, les numéros de mesure. Les accords restent à l'instant où ils sonnent. Rien ne bouge hors des mesures tapées. --undo reprend la dernière correction.

Un passage jugé bon ou corrigé perd son « ? » dans `arr play`. Un jugement tient après un nouvel `arr analyze` tant que les mesures ne changent pas ; une correction tient toujours. La relecture reprend au premier passage qui reste ; quand il n'en reste aucun, le morceau est vérifié. Tout est rangé dans `review/` du morceau, une version par décision ; rien de ce qu'`arr` a détecté n'est modifié.

| Option | Défaut | Rôle |
|---|---|---|
| `--section`, `-s` |  | Relit cette section, douteuse ou non, au lieu des passages douteux ; plusieurs qui se suivent : -s intro,intro2. |
| `--list` | non | Liste les passages à relire et leur état, sans rien jouer. |
| `--undo` | non | Reprend la dernière correction de barres du morceau, ou de la section donnée par -s. |

## `arr nudge`

```
arr nudge [OPTIONS] [NAME]
```

Décale une piste dans le mix, en entier ou par section, sans toucher à ses fichiers.

Sans valeur, affiche ce qui est appliqué. Une valeur remplace celle de la même portée (--add pour l'ajuster) ; --reset l'annule. Les réglages sont gardés dans song.toml.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` |  | Piste, ou prise (ex. t001) pour tous ses stems ; sinon tout afficher. |

| Option | Défaut | Rôle |
|---|---|---|
| `--section`, `-s` |  | Ne décale que cette section ; sinon toute la piste. |
| `--beats` |  | Décalage en temps : --beats=+1 joue un temps plus tard, --beats=-0.5 plus tôt. |
| `--ms` |  | Décalage en millisecondes : --ms=-20 joue 20 ms plus tôt. |
| `--add` | non | Ajoute à la valeur existante au lieu de la remplacer. |
| `--reset` | non | Annule le calage : de la section donnée, sinon de toute la piste. |

## `arr align`

```
arr align [OPTIONS] TAKE
```

Cale les stems d'une prise sur l'original, section par section.

Mesure le décalage de la prise (harmonie, puis attaques) et l'inscrit comme réglages de calage sur chacun de ses stems : arr nudge les montre, les ajuste ou les annule. Relancer remplace les réglages automatiques, jamais ceux posés à la main.

| Argument | Défaut | Rôle |
|---|---|---|
| `TAKE` | obligatoire | Prise à caler (ex. t001), déjà séparée par arr split. |

| Option | Défaut | Rôle |
|---|---|---|
| `--report` | non | Mesure et affiche le décalage par section, sans rien régler. |

## `arr chordpro`

```
arr chordpro [OPTIONS]
```

Écrit le morceau en fichier ChordPro pour un prompteur de scène : export/<dossier>.cho.

Une grille d'accords standard par passage, dans l'ordre joué : quatre mesures par ligne, une case par temps, les paroles chantées sur ces mesures en repère après la dernière barre. Le fichier est dans la tonalité jouée (`transpose` de sheet.toml) et se réécrit en entier à chaque appel : c'est le projet qu'on corrige, jamais le fichier.

| Option | Défaut | Rôle |
|---|---|---|
| `--show` | non | Montre le morceau ici, passage par passage, sans l'écrire. |

## `arr capture`

```
arr capture [OPTIONS] [NAME]
```

Enregistre ce que joue l'ordinateur dans un nouveau projet.

Le volume est ramené à une cible commune (-16 LUFS par défaut), pour que toutes les captures soient au même niveau quel que soit le gain réglé sur la table ce jour-là.

L'enregistrement démarre tout seul au premier son et s'arrête à la fin du morceau (changement de titre dans le lecteur multimédia, ou silence). Ctrl+C arrête aussi. Le lecteur suivi est celui qui joue, ou celui que nomme --player (ou `player` dans audio.toml). Avec --play et plusieurs lecteurs ouverts, la commande demande lequel relancer.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` |  | Nom du projet à créer ; par défaut, l'artiste et le titre lus dans le lecteur multimédia (paper-lanterns--night-drive). |

| Option | Défaut | Rôle |
|---|---|---|
| `--play` | non | Relance le morceau courant du lecteur multimédia depuis le début, et le met en pause à la fin. |
| `--player` |  | Lecteur multimédia à suivre, un fragment de son nom (vlc, spotify) ; sinon celui d'audio.toml. |
| `--silence` | `3.0` | Secondes de silence qui terminent l'enregistrement. |
| `--raw` | non | Garde le niveau tel qu'enregistré, sans le ramener au volume cible. |

## `arr record`

```
arr record [OPTIONS] TRACK
```

Enregistre ton instrument pendant que le playback joue, avec un décompte au tempo.

Le playback est le mix courant sans la piste enregistrée. L'écran est celui d'`arr play` : les pistes du playback, la section en cours et sa grille d'accords, l'accord du moment surligné. Ctrl+C arrête et garde la prise.

| Argument | Défaut | Rôle |
|---|---|---|
| `TRACK` | obligatoire | Piste à enregistrer (ex. bass) ; une nouvelle version est créée. |

| Option | Défaut | Rôle |
|---|---|---|
| `--without`, `-w` |  | Piste à retirer du playback. (répétable) |
| `--only`, `-o` |  | Playback réduit à ces pistes. (répétable) |
| `--count-in` | `1` | Mesures de décompte avant le premier temps fort ; 0 pour aucun. |
| `--click` | non | Garde le métronome pendant tout le morceau. |
| `--channel` |  | Canal d'entrée de l'instrument ; sinon celui de audio.toml. |

## `arr calibrate`

```
arr calibrate [OPTIONS]
```

Mesure le retard entre ce qui est joué et ce qui est enregistré, pour caler tes prises.

Joue quelques clics et les réenregistre sur le canal où revient le son de l'ordinateur (7 par défaut avec la Soundcraft), puis note la latence dans audio.toml.

| Option | Défaut | Rôle |
|---|---|---|
| `--channel` |  | Canal d'entrée relié à la sortie ; sinon celui de audio.toml. |

## `arr levels`

```
arr levels [OPTIONS]
```

Vumètres par canal, pour vérifier le câblage et régler le gain sur la table.

Lance la lecture (ou --tone), regarde quels canaux bougent et règle le gain pour que les crêtes arrivent entre -18 et -3 dB. Ctrl+C affiche le bilan.

| Option | Défaut | Rôle |
|---|---|---|
| `--seconds` |  | Durée de la mesure ; sinon jusqu'à Ctrl+C. |
| `--tone` | non | Joue un son de référence à -12 dB sur la sortie pendant la mesure. |
| `--source` |  | Source PipeWire à mesurer ; sinon celle de arr capture. |

## `arr check`

```
arr check
```

Mesure chaque fichier audio du projet : durée, niveaux, volume, anomalies.

Sert à vérifier un résultat sans l'écouter (et à remplir une PR) : une piste silencieuse, saturée, de la mauvaise longueur ou mal calée se voit ici.

## `arr devices`

```
arr devices
```

Montre les réglages audio effectifs et les périphériques disponibles.

## `arr doctor`

```
arr doctor
```

Vérifie la carte Intel Arc et la présence des modèles.

## `arr sections set`

```
arr sections set SPEC
```

Définit les sections en numéros de mesure (inclusifs, à partir de 1).

| Argument | Défaut | Rôle |
|---|---|---|
| `SPEC` | obligatoire | Ex. "intro:1-8 couplet:9-24 refrain:25-40". |

## `arr sections snap`

```
arr sections snap
```

Pose les bornes des sections sur les barres de mesure, pour des boucles qui retombent juste.

`arr transcribe` le fait déjà ; cette commande sert aux projets transcrits avant, ou après un nouvel `arr analyze`.

## `arr sections list`

```
arr sections list
```

Affiche les sections.

## `arr lyrics fetch`

```
arr lyrics fetch [OPTIONS] [ARTIST] [TITLE]
```

Télécharge les paroles depuis LRCLIB et les range par section dans lyrics.txt.

Les paroles horodatées sont gardées telles quelles dans lyrics.lrc : elles disent sur quelle mesure chaque ligne est chantée (`arr lyrics show`).

| Argument | Défaut | Rôle |
|---|---|---|
| `ARTIST` |  | Par défaut, l'artiste du projet. |
| `TITLE` |  | Par défaut, le titre du projet. |

| Option | Défaut | Rôle |
|---|---|---|
| `--force` | non | Remplace un lyrics.txt existant. |
| `--times` | non | N'écrit que lyrics.lrc, les instants de chaque ligne : lyrics.txt reste tel quel. |

## `arr lyrics show`

```
arr lyrics show
```

Montre les paroles section par section, chaque ligne avec la mesure où elle commence.

## `arr set new`

```
arr set new [OPTIONS] NAME [SONGS...]
```

Crée une setlist, à lancer depuis le dossier qui contient les projets.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` | obligatoire | Nom de la setlist : setlists/NOM.toml est créé. |
| `SONGS` |  | Dossiers des morceaux, dans l'ordre du concert. |

| Option | Défaut | Rôle |
|---|---|---|
| `--title` |  | Titre imprimé en haut des feuilles ; sinon le nom. |

## `arr set add`

```
arr set add [OPTIONS] NAME [SONGS...]
```

Ajoute des morceaux, ou un entracte, à une setlist.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` | obligatoire | Setlist à compléter. |
| `SONGS` |  | Dossiers des morceaux à ajouter. |

| Option | Défaut | Rôle |
|---|---|---|
| `--at` |  | Rang où les insérer (1 = en tête) ; sinon à la fin. |
| `--break` | non | Ajoute un entracte (avant les morceaux donnés). |

## `arr set edit`

```
arr set edit NAME
```

Ouvre le fichier de la setlist : réordonner, retirer, transposer un morceau pour ce concert.

Un morceau s'écrit "dossier", ou { song = "dossier", transpose = -2, note = "enchaîner" } ; "---" marque un entracte.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` | obligatoire | Setlist à ouvrir. |

## `arr set show`

```
arr set show NAME
```

Affiche l'ordre du concert : tonalité, tempo et durée de chaque morceau, et ce qui manque.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` | obligatoire | Setlist à afficher. |

## `arr set print`

```
arr set print [OPTIONS] NAME
```

Écrit le PDF des antisèches du concert : une feuille A4 en colonnes, un bloc par morceau.

Chaque bloc porte le rang, le titre, la tonalité, le tempo, puis l'antisèche du morceau (arr sheet) et la note de la setlist. Un morceau sans antisèche possible est refusé.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` | obligatoire | Setlist à imprimer. |

| Option | Défaut | Rôle |
|---|---|---|
| `--pages` |  | Nombre de feuilles A4 à ne pas dépasser : le texte prend la plus grande taille qui tient. |
| `--columns` | `2` | Colonnes par feuille. |
| `--out` |  | Fichier PDF à écrire ; sinon setlists/NOM.pdf. |

## `arr midi ports`

```
arr midi ports
```

Liste les ports MIDI de la machine, et montre celui qu'arr utilise.

Le port à retenir est celui de l'interface qui porte la prise MIDI OUT (« iTwo » ici) : c'est par elle que les messages partent vers la pédale.

## `arr midi send`

```
arr midi send [OPTIONS]
```

Envoie un changement de programme ou un contrôleur, pour tester une pédale.

De quoi vérifier le câble, le canal et les réglages de la pédale avant de compter dessus :

arr midi send --pc 5 # la pédale doit changer de son arr midi send --cc 7 --value 0 # le contrôleur 7, à 0

Les numéros de programme vont de 1 à 128, comme les affichent les pédales ; les octets réellement envoyés sont repris dans la sortie. Rien n'est écrit dans la pédale.

| Option | Défaut | Rôle |
|---|---|---|
| `--pc` |  | Numéro de programme à envoyer, de 1 à 128 comme l'affiche la pédale. |
| `--cc` |  | Numéro de contrôleur à envoyer, de 0 à 127. |
| `--value` | `127` | Valeur du contrôleur, de 0 à 127. |
| `--bank` |  | Banque à sélectionner juste avant le programme (contrôleurs 0 et 32). |
| `--channel` |  | Canal MIDI ; sinon celui d'audio.toml (1 par défaut). |
| `--port` |  | Fragment du nom du port MIDI, ou son adresse ; sinon celui d'audio.toml. |

## `arr midi monitor`

```
arr midi monitor [OPTIONS]
```

Affiche les messages MIDI reçus, pour voir ce qu'envoie une pédale ou un clavier.

L'autre moitié du test : appuie sur un sélecteur de la pédale et regarde ce qui arrive. Rien ne vient si la pédale n'envoie pas ses changements de programme (chez Boss, un réglage « MIDI PC OUT » dans l'utilitaire) ou si son câble MIDI OUT n'est pas branché.

| Option | Défaut | Rôle |
|---|---|---|
| `--port` |  | Fragment du nom du port MIDI, ou son adresse ; sinon celui d'audio.toml. |
| `--seconds` |  | Durée de l'écoute ; sinon jusqu'à Ctrl+C. |

## `arr models pull`

```
arr models pull [OPTIONS]
```

Installe les modèles et leurs moteurs, et les met à jour (seule commande qui télécharge des modèles).

Les poids viennent de Hugging Face. Le moteur audio.cpp vient de sa release GitHub : la dernière à chaque appel, ou celle de `--audiocpp` pour rester sur une version ou y revenir.

| Option | Défaut | Rôle |
|---|---|---|
| `--audiocpp` | `` | Version d'audio.cpp à mettre en service (ex. v0.9.0) ; par défaut la dernière release. |
