"""Relecture : les passages qu'`arr` donne à vérifier au musicien, et ce qu'il en a décidé.

Un passage à relire est une suite de mesures douteuses voisines (`grid.doubtful_bars`), avec une
mesure avant et une après. Ce que le musicien décide vit dans `review/` du projet, un fichier par
décision (`v001.toml`, `v002.toml`…) : chacun porte tout l'état, le dernier fait foi, aucun n'est
récrit. Ce que les détecteurs ont trouvé n'y est jamais copié ni modifié (fiche 019).

Une décision tient aux mesures sur lesquelles elle a été prise : chacune est gardée par ses temps.
Elle vaut encore après un `arr analyze` si la mesure commence au même endroit, à un demi-temps
près, et porte les mêmes temps, à 70 ms près ; sinon elle ne s'applique pas, et la question revient.
"""

from __future__ import annotations

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
    right: bool = False  # le musicien a jugé bonnes toutes ses mesures douteuses

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


def unjudged(doubts: dict[float, str], bars: list[list[float]], right: list[list[float]]) -> dict[float, str]:
    """Les mesures douteuses que le musicien n'a pas jugées bonnes : ce qui garde un « ? »."""
    return {bar[0]: doubts[bar[0]] for bar in bars if bar[0] in doubts and not judged(bar, right)}


def span(bars: list[list[float]], lo: int, hi: int, end: float, doubts: dict, right: list) -> Passage:
    """Le passage des mesures `lo` à `hi` comprises ; `end` est la fin du morceau."""
    inside = bars[lo : hi + 1]
    asked = {bar[0]: doubts[bar[0]] for bar in inside if bar[0] in doubts}
    return Passage(
        start=inside[0][0],
        end=bars[hi + 1][0] if hi + 1 < len(bars) else max(end, inside[-1][-1]),
        first=lo + 1,
        bars=inside,
        doubts=asked,
        right=bool(asked) and not unjudged(asked, inside, right),
    )


def passages(bars: list[list[float]], doubts: dict[float, str], right: list, end: float) -> list[Passage]:
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
    return [span(bars, lo, hi, end, doubts, right) for lo, hi in spans]


def between(bars: list[list[float]], start: float, end: float, doubts: dict, right: list) -> Passage | None:
    """Le passage fait des mesures qui commencent entre `start` et `end` (une section) ; None s'il n'y en a pas."""
    inside = [i for i, bar in enumerate(bars) if start - 0.05 <= bar[0] < end - 0.05]
    return span(bars, inside[0], inside[-1], end, doubts, right) if inside else None


# --- sur le disque


def _versions(p: Project) -> list[Path]:
    return sorted((p.root / FOLDER).glob("v[0-9][0-9][0-9].toml"))


def right_bars(p: Project) -> list[list[float]]:
    """Les mesures que le musicien a jugées bonnes, d'après la dernière version de `review/` ; vide avant toute relecture."""
    files = _versions(p)
    if not files:
        return []
    try:
        data = tomllib.loads(files[-1].read_text())
        return [[float(t) for t in bar] for entry in data.get("right", []) for bar in entry["bars"]]
    except (tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as e:
        raise ProjectError(f"relecture illisible : {files[-1]} ({e})")


def judge_right(p: Project, passage: Passage) -> Path:
    """Note que les mesures du passage sont bonnes, dans une nouvelle version ; les précédentes restent."""
    files = _versions(p)
    data = tomllib.loads(files[-1].read_text()) if files else {}
    now = datetime.now().isoformat(timespec="seconds")
    entry = {"judged": now, "bars": [[round(t, 3) for t in bar] for bar in passage.bars]}
    data = {**data, "saved": now, "right": [*data.get("right", []), entry]}
    path = p.root / FOLDER / f"v{(int(files[-1].stem[1:]) if files else 0) + 1:03d}.toml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(tomli_w.dumps(data))
    return path
