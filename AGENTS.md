# Guide développeur pour agents

`arr` est un CLI Python d'arrangement audio local. Lire `README.md` pour l'usage et
`HANDOFF.md` pour l'état du travail et la suite.

## Contraintes non négociables

- **Local uniquement.** Aucun service distant, aucune API. Les poids viennent de Hugging Face.
- **Hors ligne par défaut.** Seul `arr models pull` touche le réseau. Tout nouveau modèle
  doit être téléchargé là, et chargé ailleurs avec `HF_HUB_OFFLINE=1` (voir `engines.offline()`).
- **Intel Arc A770, 16 Go, backend PyTorch XPU.** Pas de CUDA. Pas de float64 sur le GPU.
- **Audio d'abord.** Le MIDI et les partitions sont un export de fin de chaîne, pas le format pivot.
- **Non destructif.** Une opération crée une nouvelle version ; elle n'écrase jamais un fichier audio.

## Commandes de travail

```
uv sync                 # environnement (Python 3.11 épinglé dans .python-version)
uv run pytest -q        # tests rapides, sans GPU ni modèles
uv run arr doctor       # vérifie XPU et la présence des poids
uv run arr <commande>   # depuis un dossier de projet, ex. demo/
```

Les tests ne chargent aucun modèle. Pour valider une commande générative, la lancer sur
`demo/` et **mesurer** le résultat (durée, niveau, corrélation avec la source) : un agent
ne peut pas écouter. Dire clairement ce qui a été mesuré et ce qui reste à juger à l'oreille.

## Architecture

```
src/arr/
  cli.py                 toutes les commandes Typer ; point d'entrée `run()`
  project.py             Project : song.toml, pistes versionnées, sections, provenance
  audio.py               E/S et opérations numpy (mix, splice, fit, scale_to)
  band.py                profil du groupe (~/.config/arr/band.toml)
  engines/__init__.py    CHECKPOINTS, device(), offline()
  engines/acestep.py     Engine : enveloppe unique autour d'ACE-Step 1.5
  engines/separation.py  Demucs ; MODELS liste les modèles acceptés par `split`
  engines/analysis.py    beat_this (temps), tempo, tonalité (chroma + Krumhansl)
tests/test_core.py       projet et audio, sur signaux synthétiques
tests/test_cli.py        commandes via CliRunner, moteurs remplacés par monkeypatch
```

Règles de structure :

- Les commandes ne parlent aux modèles que par `engines/`. Changer de modèle ne doit pas
  toucher `cli.py`.
- Les imports lourds (`torch`, `acestep`, `demucs`) sont faits **dans** les fonctions, pour
  que `arr --help`, `tracks`, `mix` restent instantanés.
- Les erreurs destinées à l'utilisateur sont des `ProjectError` ; `run()` les affiche sans trace.

## Conventions audio

- Partout : 48 kHz, stéréo, `float32`, forme `(échantillons, 2)`. `audio.convert()` normalise
  tout import ; `audio.load()` refuse un autre taux.
- Toutes les pistes d'un projet ont exactement la même longueur. Passer toute sortie de
  modèle par `audio.fit(out, len(base))`.
- ACE-Step normalise le niveau de ses sorties. Toujours recaler avec `audio.scale_to()`
  avant d'enregistrer une piste, sinon le mix est faussé.
- Pour ne modifier qu'une plage, utiliser `audio.splice(base, patch, start, end)` : hors
  plage le résultat est identique à `base` au bit près.

## Modèle de projet

- `song.toml` : `[song]` (title, bpm, key, duration), `[[sections]]` (name, start, end en
  secondes), `[tracks.<nom>]` (active, gain, mute).
- `Project.new_version(track, meta)` réserve `vNNN` et écrit le `.json` ; l'appelant écrit
  le `.flac`, puis `Project.activate()`. Dans `cli.py`, passer par `add_track()`.
- Champs de provenance : `op`, `parent` (`piste/vNNN`), `model`, `task`, `prompt`, `seed`,
  `steps`, et selon le cas `fidelity`, `section`, `start`, `end`, `instruction`.
- Les sorties qui sont un mix complet (`add`, `complete`) vont dans `renders/`, pas dans `tracks/`.

## ACE-Step : ce qu'il faut savoir

Vérifié sur cette machine avec `acestep-v15-base` (50 pas, ~0,46 s par pas pour 30 s, 8 Go) :

| Tâche | Comportement réel | Usage dans `arr` |
|---|---|---|
| `cover` + `cover_noise_strength` (notre `fidelity`) | suit la source de façon réglable | `restem`, `polish` |
| `cover` avec `audio_cover_strength` seul | ne suit pas le rythme de la source | non utilisé |
| `repaint` | hors plage identique à la source | `fix` |
| `lego` | régénère la plage masquée, rend un **mix complet** | `add` |
| `complete` | rend un mix complet | `complete` |
| `extract` | renvoie le mix, ne sépare pas | non utilisé (Demucs à la place) |

Pièges :

- **float64.** `acestep.models.common.apg_guidance.project` appelle `.double()` sur le GPU,
  ce qui plante sur Arc (« Kernel is incompatible with all devices »). `Engine.__init__`
  remplace cette fonction par `_project`, qui calcule sur le CPU. Ne pas retirer ce patch
  sans revérifier.
- **Consignes.** Les noms de piste doivent être en majuscules, au format exact de
  `acestep.constants.TASK_INSTRUCTIONS`. Passer par `engines.acestep.instruction()`.
- **Masque.** Une plage (`start`/`end`) impose `chunk_mask_mode="explicit"` ; `lego` sans
  plage explicite ne génère rien d'utile.
- **Modèle de langage.** Il n'est pas chargé (`llm_handler=None`, `thinking=False`).
- **Journaux.** `Engine` remonte le niveau loguru à WARNING.

## Dépendances

- `torch==2.11.0`, `torchvision==0.26.0`, `torchaudio==2.11.0` depuis l'index XPU. Ce trio
  doit rester cohérent : un mélange de versions casse l'import de torchvision.
- `triton-xpu` est déclaré en dépendance directe car il n'existe que sur l'index XPU.
- ACE-Step vient de git et épingle torch en CUDA ; `[tool.uv] override-dependencies` le
  force en XPU, retire `torchcodec` et impose `torchao<0.16`.
- Ne pas utiliser le téléchargeur d'ACE-Step (`acestep-download`) : il peut basculer sur
  ModelScope. Utiliser `huggingface_hub.snapshot_download`.

## Style

- Messages, aides et docstrings en français ; identifiants en anglais.
- Peu de commentaires : seulement pour une contrainte non évidente.
- Pas d'abstraction sans deuxième usage. Une commande est une fonction dans `cli.py`.
- Tout ajout dans `audio.py` ou `project.py` vient avec un test sur signal synthétique.
