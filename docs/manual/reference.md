# Référence des commandes

<!-- Fichier généré par scripts/gen_reference.py : ne pas l'éditer à la main. -->

Toutes les commandes d'`arr`, avec leurs arguments et leurs options, dans l'ordre de
`arr --help`. Cette page est produite à partir du code : elle est toujours à jour. Pour
des explications et des exemples, voir les autres pages du [manuel](README.md).

- [`arr init`](#arr-init) : Crée un projet dans le dossier NAME.
- [`arr import`](#arr-import) : Ajoute un morceau complet, ou une piste avec --as.
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
- [`arr capture`](#arr-capture) : Enregistre ce que joue l'ordinateur dans un nouveau projet.
- [`arr record`](#arr-record) : Enregistre ton instrument pendant que le playback joue, avec un décompte au tempo.
- [`arr calibrate`](#arr-calibrate) : Mesure le retard entre ce qui est joué et ce qui est enregistré, pour caler tes prises.
- [`arr levels`](#arr-levels) : Vumètres par canal, pour vérifier le câblage et régler le gain sur la table.
- [`arr check`](#arr-check) : Mesure chaque fichier audio du projet : durée, niveaux, volume, anomalies.
- [`arr devices`](#arr-devices) : Montre les réglages audio effectifs et les périphériques disponibles.
- [`arr doctor`](#arr-doctor) : Vérifie la carte Intel Arc et la présence des modèles.
- [`arr sections set`](#arr-sections-set) : Définit les sections en numéros de mesure (inclusifs, à partir de 1).
- [`arr sections list`](#arr-sections-list) : Affiche les sections.
- [`arr lyrics fetch`](#arr-lyrics-fetch) : Télécharge les paroles depuis LRCLIB et les range par section dans lyrics.txt.
- [`arr models pull`](#arr-models-pull) : Installe les modèles et leurs moteurs (seule commande qui télécharge des modèles).

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

## `arr analyze`

```
arr analyze
```

Détecte temps, mesures, tempo et tonalité.

## `arr transcribe`

```
arr transcribe
```

Transcrit l'original en partition : mélodie, accords, tempo, tonalité, sections.

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

Ctrl+C arrête.

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

## `arr capture`

```
arr capture [OPTIONS] [NAME]
```

Enregistre ce que joue l'ordinateur dans un nouveau projet.

Le volume est ramené à une cible commune (-16 LUFS par défaut), pour que toutes les captures soient au même niveau quel que soit le gain réglé sur la table ce jour-là.

L'enregistrement démarre tout seul au premier son et s'arrête à la fin du morceau (changement de titre dans Spotify, ou silence). Ctrl+C arrête aussi.

| Argument | Défaut | Rôle |
|---|---|---|
| `NAME` |  | Nom du projet à créer ; par défaut, le titre lu dans Spotify. |

| Option | Défaut | Rôle |
|---|---|---|
| `--play` | non | Relance le morceau Spotify courant depuis le début, et met en pause à la fin. |
| `--silence` | `3.0` | Secondes de silence qui terminent l'enregistrement. |
| `--raw` | non | Garde le niveau tel qu'enregistré, sans le ramener au volume cible. |

## `arr record`

```
arr record [OPTIONS] TRACK
```

Enregistre ton instrument pendant que le playback joue, avec un décompte au tempo.

Le playback est le mix courant sans la piste enregistrée. Ctrl+C arrête et garde la prise.

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

Lance Spotify (ou --tone), regarde quels canaux bougent et règle le gain pour que les crêtes arrivent entre -18 et -3 dB. Ctrl+C affiche le bilan.

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

| Argument | Défaut | Rôle |
|---|---|---|
| `ARTIST` |  | Par défaut, l'artiste du projet. |
| `TITLE` |  | Par défaut, le titre du projet. |

| Option | Défaut | Rôle |
|---|---|---|
| `--force` | non | Remplace un lyrics.txt existant. |

## `arr models pull`

```
arr models pull
```

Installe les modèles et leurs moteurs (seule commande qui télécharge des modèles).
