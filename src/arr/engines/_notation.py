"""Réparation des entrées de la partition de SheetSage2, quand il refuse de l'écrire.

Fonctions pures, sans autre dépendance que la bibliothèque standard : le script
`_sheetsage2.py` les importe dans l'environnement de SheetSage2, arr dans ses tests.

SheetSage2 refuse la partition dans deux cas vus : une mesure comptée avec un temps de trop
(numéros de temps 1, 2, 3, 4, 4), et un intervalle (accord, tonalité, section) plus court
qu'une subdivision de sa grille. La réparation repose la partition sur la grille d'`arr
analyze` — ses temps, ses barres tous les N temps — et fond chaque intervalle trop court
dans son voisin.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from itertools import pairwise
from statistics import median

# Les raisons de SheetSage2, dites au musicien.
REASONS = (
    ("non-consecutive beat IDs", "une mesure comptée avec un temps de trop ou de moins"),
    ("shorter than the ABC subbeat grid", "un accord ou une section trop court pour la partition"),
)


def reason(error: str) -> str:
    """La raison d'un refus de SheetSage2, en mots de musicien quand elle est connue."""
    return next((plain for needle, plain in REASONS if needle in error), error)


def _extend(times: list[float], start: float, end: float) -> list[float]:
    """Prolonge les temps au même pas jusqu'à couvrir [start, end]."""
    out = list(times)
    head = median(b - a for a, b in pairwise(out[:9]))
    tail = median(b - a for a, b in pairwise(out[-9:]))
    while out[0] > start + 1e-6:
        out.insert(0, out[0] - head)
    while out[-1] < end - 1e-6:
        out.append(out[-1] + tail)
    return out


def beat_rows(times: list[float], bars: list[float], start: float, end: float, size: int = 4) -> list[list]:
    """Les lignes de temps de la partition : (instant, rang dans la mesure, temps de la mesure, 4).

    Les temps sont prolongés au même pas pour couvrir [start, end] ; chaque barre de `bars` est
    posée sur le temps le plus proche. N, la longueur de mesure la plus fréquente (ou `size`
    avec une seule barre), prolonge les barres avant la première et après la dernière. Les temps
    avant la première barre forment une levée, numérotée pour finir sur N.
    """
    if len(times) < 2 or not bars:
        raise ValueError("il faut au moins deux temps et une barre")
    times = _extend(times, start, end)
    at = sorted({min(range(len(times)), key=lambda i, b=b: abs(times[i] - b)) for b in bars})
    gaps = [b - a for a, b in pairwise(at)]
    n = Counter(gaps).most_common(1)[0][0] if gaps else size
    starts = list(range(at[0] - n, -1, -n))[::-1] + at
    starts += range(at[-1] + n, len(times), n)
    rows = []
    for i, t in enumerate(times):
        if i < starts[0]:
            rows.append([t, n - (starts[0] - i) + 1, n, 4])
            continue
        k = bisect_left(starts, i + 1) - 1
        bar = starts[k + 1] - starts[k] if k + 1 < len(starts) else n
        rows.append([t, i - starts[k] + 1, bar, 4])
    return rows


def _grid(beats: list[float], division: int) -> list[float]:
    """La grille de SheetSage2 : chaque temps coupé en `division` subdivisions, et le dernier temps."""
    return [a + (b - a) * k / division for a, b in pairwise(beats) for k in range(division)] + [beats[-1]]


def _slotter(grid: list[float]):
    """La subdivision où SheetSage2 range un instant, comme lui : la plus proche, bornée à la grille."""
    bounds = [(a + b) / 2 for a, b in pairwise(grid)]
    return lambda t: max(0, min(bisect_left(bounds, t), len(bounds)))


def merge_slivers(rows: list[list], beats: list[float], division: int = 4) -> list[list]:
    """Les intervalles (début, fin, valeur) coupés à la grille, sans aucun plus court qu'une subdivision.

    Un intervalle qui tombe dans une seule subdivision se fond dans celui d'avant ; le premier,
    dans celui d'après.
    """
    slot = _slotter(_grid(beats, division))
    clipped = [[max(beats[0], a), min(beats[-1], b), v] for a, b, v in rows if b > beats[0] and a < beats[-1]]
    out: list[list] = []
    for a, b, v in clipped:
        if slot(b) > slot(a):
            out.append([a, b, v])
        elif out:
            out[-1][1] = b
    if out:
        out[0][0] = clipped[0][0]
    return out


def fit_notes(notes: list[tuple[float, float, int]], beats: list[float], division: int = 4) -> list[tuple]:
    """Les notes d'une voix (début, fin, hauteur) posées sur la grille : une subdivision au moins, sans chevauchement.

    Chaque note commence et finit sur une subdivision ; une note trop courte en prend une, une
    note qui en chevaucherait une autre commence après elle, ou disparaît s'il ne lui reste rien.
    """
    grid = _grid(beats, division)
    slot = _slotter(grid)
    out, free = [], 0
    for start, end, pitch in sorted(notes):
        s = max(slot(start), free)
        e = min(max(slot(end), s + 1), len(grid) - 1)
        if e > s:
            out.append((grid[s], grid[e], pitch))
            free = e
    return out
