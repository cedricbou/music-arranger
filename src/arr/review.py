"""Relecture : les passages qu'`arr` donne à vérifier au musicien, et ce qu'il en a décidé.

Un passage à relire est une suite de mesures douteuses voisines (`grid.doubtful_bars`), avec une
mesure avant et une après. Ce que le musicien décide vit dans `review/` du projet, un fichier par
décision (`v001.toml`, `v002.toml`…) : chacun porte tout l'état, le dernier fait foi, aucun n'est
récrit. Ce que les détecteurs ont trouvé n'y est jamais copié ni modifié (fiche 019).

Un jugement tient aux mesures sur lesquelles il a été pris : chacune est gardée par ses temps.
Il vaut encore après un `arr analyze` si la mesure commence au même endroit, à un demi-temps
près, et porte les mêmes temps, à 70 ms près ; sinon il ne s'applique pas, et la question revient.

Une correction de barres (`Fix`) porte les barres que le musicien a tapées et les temps entre la
première et la dernière : `fix_grid` les met à la place de ce que le détecteur a lu là, et de
rien d'autre. Elle vaut quoi que le détecteur relise ensuite.
"""

from __future__ import annotations

import statistics
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import tomli_w

from arr.project import Project, ProjectError

FOLDER = "review"
SAME = 0.07  # deux temps sont le même à moins de 70 ms l'un de l'autre, une fois les mesures superposées
LEAD = 1  # mesures jouées avant et après les mesures douteuses


@dataclass
class Passage:
    """Des mesures à écouter d'une traite : `bars` donne les temps de chacune, `first` le numéro de la première."""

    start: float
    end: float
    first: int
    bars: list[list[float]]
    doubts: dict[float, str] = field(default_factory=dict)  # début d'une mesure douteuse → pourquoi
    right: bool = False  # plus rien à relire : ses mesures douteuses sont jugées bonnes ou corrigées
    fixed: bool = False  # le musicien y a corrigé des barres

    @property
    def state(self) -> str:
        return "corrigé" if self.fixed and self.right else "jugé bon" if self.right else "à relire"

    @property
    def where(self) -> str:
        last = self.first + len(self.bars) - 1
        return f"mes. {self.first}" if last == self.first else f"mes. {self.first} à {last}"


def measures(beats: list[float], bars: list[float]) -> list[list[float]]:
    """Les temps de la grille rangés par mesure ; ceux d'avant la première barre ne font pas une mesure."""
    out: list[list[float]] = []
    edges = iter([*sorted(bars), float("inf")])
    edge = next(edges)
    for t in beats:
        if t >= edge - 0.05:
            out.append([])
            edge = next(edges)
        if out:
            out[-1].append(float(t))
    return out


def same(now: list[float], then: list[float]) -> bool:
    """La mesure `now` est-elle celle, `then`, sur laquelle une décision a été prise ?"""
    if len(now) != len(then):
        return False
    beat = (then[-1] - then[0]) / (len(then) - 1) if len(then) > 1 else 0.5
    if abs(now[0] - then[0]) >= beat / 2:
        return False
    return all(abs((a - now[0]) - (b - then[0])) < SAME for a, b in zip(now, then, strict=True))


def judged(bar: list[float], right: list[list[float]]) -> bool:
    return any(same(bar, then) for then in right)


def unjudged(doubts: dict[float, str], bars: list[list[float]], right: list[list[float]], fixes=()) -> dict[float, str]:
    """Les mesures douteuses que le musicien n'a ni jugées bonnes ni corrigées : ce qui garde un « ? »."""
    settled = lambda bar: judged(bar, right) or any(fix.covers(bar[0]) for fix in fixes)
    return {bar[0]: doubts[bar[0]] for bar in bars if bar[0] in doubts and not settled(bar)}


def span(bars: list[list[float]], lo: int, hi: int, end: float, doubts: dict, right: list, fixes=()) -> Passage:
    """Le passage des mesures `lo` à `hi` comprises ; `end` est la fin du morceau."""
    inside = bars[lo : hi + 1]
    asked = {bar[0]: doubts[bar[0]] for bar in inside if bar[0] in doubts}
    return Passage(
        start=inside[0][0],
        end=bars[hi + 1][0] if hi + 1 < len(bars) else max(end, inside[-1][-1]),
        first=lo + 1,
        bars=inside,
        doubts=asked,
        right=bool(asked) and not unjudged(asked, inside, right, fixes),
        fixed=any(fix.covers(bar[0]) for bar in inside for fix in fixes),
    )


def passages(bars: list[list[float]], doubts: dict[float, str], right: list, end: float, fixes=()) -> list[Passage]:
    """Les passages à relire, dans l'ordre du morceau, jugés ou non.

    Chaque mesure douteuse est élargie de `LEAD` mesures de chaque côté ; les passages qui se
    touchent ou se recouvrent n'en font qu'un.
    """
    spans: list[list[int]] = []
    for i, bar in enumerate(bars):
        if bar[0] not in doubts:
            continue
        lo, hi = max(i - LEAD, 0), min(i + LEAD, len(bars) - 1)
        if spans and lo <= spans[-1][1] + 1:
            spans[-1][1] = hi
        else:
            spans.append([lo, hi])
    return [span(bars, lo, hi, end, doubts, right, fixes) for lo, hi in spans]


def between(bars: list[list[float]], start: float, end: float, doubts: dict, right: list, fixes=()) -> Passage | None:
    """Le passage fait des mesures qui commencent entre `start` et `end` (une section) ; None s'il n'y en a pas."""
    inside = [i for i, bar in enumerate(bars) if start - 0.05 <= bar[0] < end - 0.05]
    return span(bars, inside[0], inside[-1], end, doubts, right, fixes) if inside else None


# --- les barres corrigées


@dataclass
class Fix:
    """Des barres tapées par le musicien : `bars`, de la première à celle qui ferme la dernière mesure, et les temps entre elles."""

    bars: list[float]
    beats: list[float]
    fixed: str = ""  # quand ; vide pour un passage lu dans `truth/`

    @property
    def edge(self) -> float:
        """Un quart de temps : en deçà, un temps du détecteur est celui d'un bord de la correction."""
        return (self.bars[-1] - self.bars[0]) / max(len(self.beats) - 1, 1) / 4

    def covers(self, t: float) -> bool:
        return self.bars[0] - self.edge <= t < self.bars[-1] - self.edge


def local_period(beats: list[float], t: float, reach: int = 8) -> float:
    """La durée d'un temps autour de l'instant `t` : la médiane des écarts voisins."""
    if len(beats) < 2:
        return 0.5
    i = min(range(len(beats)), key=lambda k: abs(beats[k] - t))
    near = beats[max(i - reach, 0) : i + reach + 1]
    return statistics.median(b - a for a, b in zip(near, near[1:], strict=False))


def snap(marks: list[float], beats: list[float]) -> tuple[list[float], list[float]]:
    """Chaque frappe menée au temps détecté le plus proche ; et les frappes à plus d'un demi-temps de tout temps.

    Deux frappes menées au même temps n'en font qu'une. Une frappe trop loin reste où elle est.
    """
    out, far = [], []
    for mark in sorted(marks):
        near = min(beats, key=lambda b: abs(b - mark), default=mark)
        if abs(near - mark) > local_period(beats, mark) / 2:
            far.append(mark)
            near = mark
        if not out or near - out[-1] > 1e-6:
            out.append(near)
    return out, far


def counts(bars: list[float], beats: list[float]) -> list[int]:
    """Le nombre de temps détectés dans chaque mesure tapée (entre deux barres qui se suivent)."""
    return [sum(a - 0.05 <= t < b - 0.05 for t in beats) for a, b in zip(bars, bars[1:], strict=False)]


def make_fix(bars: list[float], beats: list[float], spread: set[int], per_bar: int = 4, fixed: str = "") -> Fix:
    """La correction que font les barres `bars`, déjà menées sur les temps `beats` du détecteur.

    Une mesure garde les temps détectés entre ses deux barres, sauf celles de `spread` (leur rang) :
    là le détecteur a manqué un temps ou en a entendu un deux fois, et `per_bar` temps égaux
    sont posés entre les deux frappes.
    """
    kept: list[float] = []
    for i, (a, b) in enumerate(zip(bars, bars[1:], strict=False)):
        if i in spread:
            kept += [a + (b - a) * k / per_bar for k in range(per_bar)]
        else:
            kept += [a, *(t for t in beats if a + 0.05 <= t < b - 0.05)]
    return Fix([round(t, 3) for t in bars], [round(t, 3) for t in [*kept, bars[-1]]], fixed)


def legacy_fix(marks: list[float], per_bar: int, beats: list[float]) -> Fix | None:
    """Un passage de `truth/` du projet, lu comme une correction ; None s'il a moins de deux barres.

    Le musicien y a dit son nombre de temps par mesure : une mesure où le détecteur en compte
    un autre reçoit ce nombre de temps égaux.
    """
    bars, _ = snap(marks, beats)
    if len(bars) < 2:
        return None
    odd = {i for i, n in enumerate(counts(bars, beats)) if n != per_bar}
    return make_fix(bars, beats, odd, per_bar)


def fix_grid(beats: list[float], bars: list[float], fixes: list[Fix]) -> tuple[list[float], list[float]]:
    """La grille avec les corrections du musicien : dans chaque passage corrigé, ses temps et ses barres.

    Hors des passages corrigés rien ne bouge ; une correction plus récente l'emporte sur une plus ancienne.
    """
    for fix in fixes:
        lo, hi = fix.bars[0] - fix.edge, fix.bars[-1] + fix.edge
        beats = sorted([*(t for t in beats if not lo < t < hi), *fix.beats])
        bars = sorted([*(t for t in bars if not lo < t < hi), *fix.bars])
    return beats, bars


# --- sur le disque


def _versions(p: Project) -> list[Path]:
    return sorted((p.root / FOLDER).glob("v[0-9][0-9][0-9].toml"))


def _latest(p: Project) -> dict:
    files = _versions(p)
    if not files:
        return {}
    try:
        return tomllib.loads(files[-1].read_text())
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"relecture illisible : {files[-1]} ({e})")


def _write(p: Project, data: dict) -> Path:
    """Une nouvelle version de l'état ; les précédentes restent."""
    files = _versions(p)
    path = p.root / FOLDER / f"v{(int(files[-1].stem[1:]) if files else 0) + 1:03d}.toml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(tomli_w.dumps({**data, "saved": datetime.now().isoformat(timespec="seconds")}))
    return path


def right_bars(p: Project) -> list[list[float]]:
    """Les mesures que le musicien a jugées bonnes, d'après la dernière version de `review/` ; vide avant toute relecture."""
    try:
        return [[float(t) for t in bar] for entry in _latest(p).get("right", []) for bar in entry["bars"]]
    except (KeyError, TypeError, ValueError) as e:
        raise ProjectError(f"relecture illisible : {_versions(p)[-1]} ({e})")


def bar_fixes(p: Project) -> list[Fix]:
    """Les barres corrigées dans `arr review`, de la plus ancienne correction à la plus récente."""
    try:
        return [
            Fix([float(t) for t in e["bars"]], [float(t) for t in e["beats"]], str(e.get("fixed", "")))
            for e in _latest(p).get("fixes", [])
        ]
    except (KeyError, TypeError, ValueError) as e:
        raise ProjectError(f"relecture illisible : {_versions(p)[-1]} ({e})")


def judge_right(p: Project, passage: Passage) -> Path:
    """Note que les mesures du passage sont bonnes, dans une nouvelle version."""
    data = _latest(p)
    now = datetime.now().isoformat(timespec="seconds")
    entry = {"judged": now, "bars": [[round(t, 3) for t in bar] for bar in passage.bars]}
    return _write(p, {**data, "right": [*data.get("right", []), entry]})


def save_fix(p: Project, fix: Fix) -> Path:
    """Garde une correction de barres, dans une nouvelle version."""
    data = _latest(p)
    entry = {"fixed": datetime.now().isoformat(timespec="seconds"), "bars": fix.bars, "beats": fix.beats}
    return _write(p, {**data, "fixes": [*data.get("fixes", []), entry]})


def undo_fix(p: Project, start: float = 0.0, end: float = float("inf")) -> Fix | None:
    """Reprend la dernière correction de barres qui touche à `start`–`end`, dans une nouvelle version ; None s'il n'y en a pas."""
    data, fixes = _latest(p), bar_fixes(p)
    last = next((i for i in reversed(range(len(fixes))) if fixes[i].bars[0] < end and fixes[i].bars[-1] > start), None)
    if last is None:
        return None
    _write(p, {**data, "fixes": [e for i, e in enumerate(data["fixes"]) if i != last]})
    return fixes[last]
