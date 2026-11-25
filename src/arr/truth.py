"""Passages de référence : les barres de mesure que le musicien a comptées à l'oreille, et la note de la grille.

Chaque passage repéré vit dans `truth/` du projet, une version par passe (`chorus.v001.toml`) :
la plus récente fait foi, les autres restent. À côté, `chorus.v001.chords.txt` porte les accords
de ses mesures : ceux d'`arr`, que le musicien corrige. `truth/runs.json` garde les notes de chaque
lancement d'`arr truth`, pour dire ce qui va mieux ou moins bien que la fois d'avant.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import tomli_w

from arr.project import Project, ProjectError
from arr.sheet import chord_label, chord_name

FOLDER = "truth"
RUNS = "runs.json"
ON_BAR = 0.07  # une barre est « juste » à moins de 70 ms d'une barre repérée : la tolérance d'usage (mir_eval)
BOUNCE = 0.25  # deux frappes plus rapprochées sont une seule frappe (rebond, touche tenue)


@dataclass
class Passage:
    name: str
    version: str
    start: float
    end: float
    beats_per_bar: int
    bars: list[float]


class Taps:
    """Les frappes d'un repérage, et de quoi dire ce qui s'entendait à l'heure de chacune.

    Le flux audio annonce à chaque bloc sa position et l'heure où il sortira du convertisseur
    (`heard`, comme `studio.play` l'appelle) ; le clavier donne l'heure de chaque frappe (`tap`).
    """

    def __init__(self) -> None:
        self.blocks: list[tuple[float, float]] = []  # (heure de sortie, position du flux)
        self.times: list[float] = []

    def heard(self, seconds: float, at: float, paused: bool) -> None:
        self.blocks.append((at, seconds))

    def tap(self, at: float) -> None:
        self.times.append(at)

    def positions(self) -> list[float]:
        return heard_positions(self.blocks, self.times)


def heard_positions(blocks: list[tuple[float, float]], taps: list[float], around: float = 0.25) -> list[float]:
    """La position du flux qui s'entendait à l'heure de chaque frappe.

    `blocks` sont (heure de sortie, position) pour chaque bloc audio. L'heure annoncée d'un bloc
    tremble de quelques millisecondes : l'écart entre heure et position est la médiane de ceux
    des blocs à moins de `around` secondes de la frappe (le plus proche, s'il n'y en a pas).
    """
    if not blocks:
        return []
    at = np.array([b[0] for b in blocks])
    lag = at - np.array([b[1] for b in blocks])
    out = []
    for tap in taps:
        near = np.abs(at - tap) <= around
        out.append(float(tap - (np.median(lag[near]) if near.any() else lag[np.abs(at - tap).argmin()])))
    return out


def bar_marks(times: list[float], start: float, end: float) -> list[float]:
    """Les frappes gardées comme barres du passage : dans ses bornes, dans l'ordre, sans rebond."""
    kept: list[float] = []
    for t in sorted(times):
        if start - ON_BAR <= t < end and (not kept or t - kept[-1] >= BOUNCE):
            kept.append(round(max(t, 0.0), 3))
    return kept


# --- sur le disque


def _files(p: Project) -> dict[str, list[Path]]:
    """Les versions de chaque passage, de la plus ancienne à la plus récente."""
    found: dict[str, list[Path]] = {}
    for f in sorted((p.root / FOLDER).glob("*.v[0-9][0-9][0-9].toml")):
        found.setdefault(f.name[: -len(".v000.toml")], []).append(f)
    return found


def read(path: Path) -> Passage:
    name, version = path.name[: -len(".v000.toml")], path.name[-len("v000.toml") : -len(".toml")]
    try:
        data = tomllib.loads(path.read_text())
        bars = sorted(float(b) for b in data["bars"])
        return Passage(name, version, float(data["start"]), float(data["end"]), int(data.get("beats_per_bar", 4)), bars)
    except (tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as e:
        raise ProjectError(f"passage de référence illisible : {path} ({e})")


def passages(p: Project) -> list[Passage]:
    """Les passages repérés du projet, chacun dans sa dernière version."""
    return [read(versions[-1]) for versions in _files(p).values()]


def save(p: Project, name: str, start: float, end: float, bars: list[float]) -> Passage:
    """Écrit une nouvelle version du passage ; les précédentes restent, et donnent leur nombre de temps par mesure."""
    earlier = _files(p).get(name, [])
    number = int(earlier[-1].name[-len("000.toml") : -len(".toml")]) + 1 if earlier else 1
    beats_per_bar = read(earlier[-1]).beats_per_bar if earlier else 4
    path = p.root / FOLDER / f"{name}.v{number:03d}.toml"
    path.parent.mkdir(exist_ok=True)
    data = {
        "start": round(start, 3),
        "end": round(end, 3),
        "beats_per_bar": beats_per_bar,
        "marked": datetime.now().isoformat(timespec="seconds"),
        "bars": bars,
    }
    path.write_text(tomli_w.dumps(data))
    return read(path)


def last_run(p: Project) -> dict:
    """Les notes du dernier lancement, par passage ; vide la première fois."""
    f = p.root / FOLDER / RUNS
    runs = json.loads(f.read_text()) if f.exists() else []
    return runs[-1]["passages"] if runs else {}


def record_run(p: Project, scores: dict[str, dict]) -> None:
    """Ajoute ce lancement à l'historique du projet."""
    f = p.root / FOLDER / RUNS
    runs = json.loads(f.read_text()) if f.exists() else []
    runs.append({"at": datetime.now().isoformat(timespec="seconds"), "passages": scores})
    f.write_text(json.dumps(runs, indent=1))


# --- la note


def score(marks: list[float], beats_per_bar: int, beats: list[float], bars: list[float]) -> dict:
    """Note une grille (`beats`, `bars`) contre les barres repérées `marks` d'un passage.

    - `marks`, `shown`, `matched` : barres repérées, barres de la grille entre la première et la
      dernière repérée, et celles qui tombent à moins de 70 ms d'une repérée (une pour une) ;
    - `f` : la F-mesure de `mir_eval.beat` sur ces barres, sans écarter les cinq premières secondes ;
    - `offset` : écart médian, en secondes, des barres justes aux repérées (> 0 : la grille est
      après la frappe) ; None sans barre juste ;
    - `counted`, `right` : mesures repérées (entre deux barres) et celles où la grille compte
      `beats_per_bar` temps. Un temps appartient à la mesure dont la barre repérée le précède à
      un demi-temps près : une frappe un peu en avance ou en retard ne change pas le compte ;
    - `wrong` : pour chaque mesure repérée, si la grille s'y trompe (pas de barre juste à son
      début, ou pas le bon nombre de temps).
    """
    import mir_eval

    ref = np.asarray(marks, dtype=float)
    if not len(ref):
        return {"marks": 0, "shown": 0, "matched": 0, "f": 0.0, "offset": None, "counted": 0, "right": 0, "wrong": []}
    est = np.array([b for b in bars if ref[0] - ON_BAR <= b <= ref[-1] + ON_BAR], dtype=float)
    pairs = mir_eval.util.match_events(ref, est, ON_BAR) if len(est) else []
    t, on_line = np.asarray(beats, dtype=float), {i for i, _ in pairs}
    counts = [
        int(((t >= a - (b - a) / (2 * beats_per_bar)) & (t < b - (b - a) / (2 * beats_per_bar))).sum())
        for a, b in zip(ref, ref[1:], strict=False)
    ]
    right = sum(c == beats_per_bar for c in counts)
    return {
        "marks": len(ref),
        "shown": len(est),
        "matched": len(pairs),
        "f": float(mir_eval.beat.f_measure(ref, est, ON_BAR)) if len(est) else 0.0,
        "offset": float(np.median([est[j] - ref[i] for i, j in pairs])) if pairs else None,
        "counted": len(ref) - 1,
        "right": right,
        "wrong": [c != beats_per_bar or i not in on_line for i, c in enumerate(counts)],
    }


def doubted(marks: list[float], beats_per_bar: int, doubtful: list[float]) -> list[bool]:
    """Pour chaque mesure repérée, si la grille y marque une mesure douteuse (`doubtful` : leurs débuts).

    Une mesure de la grille va à la mesure repérée dont la barre la précède à un demi-temps près.
    """
    out = []
    for a, b in zip(marks, marks[1:], strict=False):
        half = (b - a) / (2 * beats_per_bar)
        out.append(any(a - half <= d < b - half for d in doubtful))
    return out


def verdict(now: dict, before: dict | None) -> str:
    """« mieux », « moins bien » ou « pareil » depuis la dernière fois ; « nouveau » sans note comparable.

    Moins bien dès qu'une note baisse (barres justes, mesures au bon compte, accords) : une
    hausse d'une autre ne rachète pas un recul.
    """
    if not before or before.get("version") != now.get("version"):
        return "nouveau"
    # Les accords comptent dès que les deux lancements les notent.
    keys = ["f", "right"] + [k for k in ("root", "majmin") if now.get(k) is not None and before.get(k) is not None]
    was, lines = [before[k] for k in keys], [now[k] for k in keys]
    if any(n < w - 1e-9 for n, w in zip(lines, was, strict=True)):
        return "moins bien"
    return "mieux" if any(n > w + 1e-9 for n, w in zip(lines, was, strict=True)) else "pareil"


# --- les accords des passages

CHORDS_HEAD = """# {name} {version} : les accords que tu entends, mesure par mesure.
# Un accord par mesure, deux s'il change au milieu (« A E »). Corrige ceux que tu entends
# autrement ; vide une mesure dont tu n'es pas sûr, elle ne comptera pas. Après la barre « | » :
# ce qu'arr avait transcrit, à ne pas toucher.
"""


def shown_chords(chart: list[tuple]) -> list[tuple[float, float, str]]:
    """Les accords de la grille d'`arr play` (`song_chart`), à plat : (début, fin, étiquette)."""
    return [(start, end, label) for bar in chart for _, _, label, start, end in bar[3]]


def _halves(a: float, b: float, chords: list[tuple[float, float, str]]) -> list[str]:
    """L'accord de chaque moitié de la mesure, lu en son milieu ; un seul s'ils sont les mêmes."""
    at = lambda t: next((label for start, end, label in chords if start <= t < end), "N")
    first, second = at(a + (b - a) / 4), at(a + 3 * (b - a) / 4)
    return [first] if first == second else [first, second]


def chords_path(p: Project, passage: Passage) -> Path:
    return p.root / FOLDER / f"{passage.name}.{passage.version}.chords.txt"


def read_chords(path: Path) -> list[tuple[int, list[str], list[str]]]:
    """Les lignes du fichier d'accords : (rang de la mesure, accords entendus, accords transcrits), en noms d'antisèche."""
    rows = []
    for line in path.read_text().splitlines():
        heard, _, given = line.partition("|")
        if line.lstrip().startswith("#") or not heard.split() or not heard.split()[0].isdigit():
            continue
        rows.append((int(heard.split()[0]) - 1, heard.split()[2:4], given.split()))
    return rows


def write_chords(p: Project, passage: Passage, chords: list[tuple[float, float, str]]) -> Path | None:
    """Écrit le fichier d'accords du passage, rempli de ceux d'`arr` ; None s'il existe déjà : il n'est jamais récrit.

    Une mesure corrigée dans le fichier d'une version précédente du passage, et qui commence
    au même endroit à un quart de mesure près, garde sa correction.
    """
    path = chords_path(p, passage)
    if path.exists() or len(passage.bars) < 2 or not chords:
        return None
    corrected: list[tuple[float, list[str]]] = []
    for earlier in map(read, _files(p).get(passage.name, [])[:-1]):
        if (old := chords_path(p, earlier)).exists():
            corrected += [(earlier.bars[i], heard) for i, heard, given in read_chords(old) if heard != given]
    lines = []
    for i, (a, b) in enumerate(zip(passage.bars, passage.bars[1:], strict=False)):
        given = [chord_name(label).replace("–", "N.C.") for label in _halves(a, b, chords)]
        heard = next((kept for start, kept in reversed(corrected) if abs(start - a) < (b - a) / 4), given)
        lines.append(f"{i + 1:>3}  {int(a) // 60}:{a % 60:05.2f}  {' '.join(heard):<16} | {' '.join(given)}")
    path.write_text(CHORDS_HEAD.format(name=passage.name, version=passage.version) + "\n".join(lines) + "\n")
    return path


def chord_score(passage: Passage, rows: list[tuple[int, list[str], list[str]]], chords: list[tuple]) -> dict:
    """Note les accords d'`arr` (`chords`) contre ceux du musicien, sur les mesures qu'il a remplies.

    `root` et `majmin` : part du temps, de 0 à 1, où la fondamentale est juste, puis fondamentale
    et majeur ou mineur (`mir_eval.chord`, pondéré par la durée ; un accord entendu ni majeur ni
    mineur ne compte pas pour `majmin`). Deux accords se partagent la mesure par moitiés.
    `seconds` : la durée notée ; `filled` et `corrected` : mesures remplies, et celles que le
    musicien a changées. Vide si aucune mesure n'est remplie.
    """
    import mir_eval

    ref, est, weight = [], [], []
    filled = [(i, heard, given) for i, heard, given in rows if heard and i + 1 < len(passage.bars)]
    for i, heard, _ in filled:
        cuts = np.linspace(passage.bars[i], passage.bars[i + 1], len(heard) + 1)
        for name, a, b in zip(heard, cuts, cuts[1:], strict=False):
            covered = 0.0
            for start, end, label in chords:
                if (shared := min(end, b) - max(start, a)) > 0:
                    ref.append(chord_label(name)), est.append(label), weight.append(shared)
                    covered += shared
            if b - a - covered > 1e-6:
                ref.append(chord_label(name)), est.append("N"), weight.append(b - a - covered)
    if not ref:
        return {}
    weights, majmin = np.array(weight), mir_eval.chord.majmin(ref, est)
    return {
        "root": float(mir_eval.chord.weighted_accuracy(mir_eval.chord.root(ref, est), weights)),
        "majmin": float(mir_eval.chord.weighted_accuracy(majmin, weights)) if (majmin >= 0).any() else None,
        "seconds": float(weights.sum()),
        "filled": len(filled),
        "corrected": sum(heard != given for _, heard, given in filled),
    }
