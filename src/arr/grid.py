"""La grille telle qu'elle est lue : ce que beat_this a détecté, remis d'aplomb à chaque lecture.

`analysis.json` garde les temps et les barres de beat_this tels quels. Avant de servir, les
temps entendus deux fois sont retirés (`clean_beats`), les temps manqués dont il reste une
trace sont comblés (`fill_beats`), et les barres sont posées tous les N temps (`regular_bars`).
`doubtful_bars` dit où beat_this hésitait : ces mesures sont montrées, jamais corrigées.
"""

from __future__ import annotations

import numpy as np

HEARD = 0.07  # une trace de temps compte à moins de 70 ms de l'endroit attendu
WEAK = 0.9  # sous cette activation, beat_this a entendu le temps faiblement


def steady_bars(bars: list[float], reach: int = 8) -> list[float]:
    """Les barres de mesure sans le pas de 20 ms de beat_this, pour couper des boucles de la bonne durée.

    Chaque barre est replacée sur la droite ajustée à ses voisines. Une mesure de durée
    inhabituelle (à deux temps, par exemple) borne l'ajustement : elle reste où elle est.
    """
    t = np.asarray(bars, dtype=float)
    if len(t) < 3:
        return [float(b) for b in t]
    gaps = np.diff(t)
    regular = np.abs(gaps - np.median(gaps)) < 0.1 * np.median(gaps)
    out = t.copy()
    for i in range(len(t)):
        lo, hi = i, i
        while lo > max(0, i - reach) and regular[lo - 1]:
            lo -= 1
        while hi < min(len(t) - 1, i + reach) and regular[hi]:
            hi += 1
        if hi - lo >= 2:
            out[i] = np.polyval(np.polyfit(np.arange(lo, hi + 1), t[lo : hi + 1], 1), i)
    return [float(b) for b in out]


def clean_beats(beats: list[float], downbeats: list[float]) -> tuple[list[float], list[float]]:
    """Les temps et barres de beat_this, sans les temps entendus deux fois.

    beat_this pose parfois deux temps à 80–120 ms l'un de l'autre pour un seul temps joué ; chaque
    temps en trop avance d'un temps toutes les barres qui suivent. Une paire : un écart de moins
    d'une demi-période, nettement plus court que ses voisins, et une fois un des deux retiré, le
    temps gardé à une période de ses deux voisins. On garde le second : beat_this l'entend plus
    fort, et la batterie seule tombe dessus ; la barre du premier passe au second. Une suite de
    temps serrés (passage compté au double) n'est pas touchée. Sans paire, rend ses arguments.
    """
    if len(beats) < 4:
        return beats, downbeats
    t = np.asarray(beats, dtype=float)
    gaps = np.diff(t)

    def local(i: int, reach: int = 12) -> float:
        """La période autour du temps i. Une paire tirerait la médiane vers le bas : ses écarts sont
        remplacés par l'écart minuscule ajouté au suivant, à peu près une période."""
        near = gaps[max(0, i - reach) : i + reach + 1]
        step = float(np.percentile(near, 75))  # la médiane serait un écart minuscule dans une suite de paires
        for _ in range(3):
            tiny = near < 0.5 * step
            clean = ~(tiny | np.roll(tiny, 1) | np.roll(tiny, -1))
            pairs = (near[:-1] + near[1:])[tiny[:-1]]
            step = float(np.median(np.concatenate([near[clean], pairs]) if clean.any() or len(pairs) else near))
        return step

    kept: list[float] = []
    moved: dict[float, float] = {}  # temps retiré → temps gardé à sa place
    i = 0
    while i < len(t):
        beside = [gaps[j] for j in (i - 1, i + 1) if 0 <= j < len(gaps)]
        if i + 1 < len(t) and gaps[i] < 0.5 * (step := local(i)) and all(gaps[i] < 0.6 * g for g in beside):
            drop, keep = float(t[i]), float(t[i + 1])
            after = float(t[i + 2]) if i + 2 < len(t) else None
            sides = ([keep - kept[-1]] if kept else []) + ([after - keep] if after is not None else [])
            if sides and all(abs(s - step) < 0.25 * step for s in sides):
                kept.append(keep)
                moved[drop] = keep
                i += 2
                continue
        kept.append(float(t[i]))
        i += 1
    if not moved:
        return beats, downbeats
    return kept, sorted({moved.get(float(d), float(d)) for d in downbeats})


def regular_bars(downbeats: list[float], beats: list[float], change: int = 3) -> list[float]:
    """Les barres de mesure posées tous les N temps, N la longueur de mesure la plus fréquente.

    beat_this hésite parfois, le temps d'un refrain, entre des mesures de quatre et de deux
    temps alors que le groupe joue en 4/4. La place des barres dans la mesure (leur phase) se
    lit sur l'ensemble des barres détectées : elle ne change que si au moins `change` barres
    le confirment, et une seule mesure courte marque alors le décalage. Avant la première
    barre, il ne reste qu'une levée de moins de N temps. Si les mesures détectées sont trop
    diverses pour qu'une longueur domine (morceau à mètre changeant), rien ne bouge.
    """
    if len(downbeats) < 3 or len(beats) < 2:
        return downbeats
    t = np.asarray(beats, dtype=float)
    at = sorted({int(np.abs(t - d).argmin()) for d in downbeats})
    gaps = np.diff(at)
    sizes, counts = np.unique(gaps, return_counts=True)
    size = int(sizes[counts.argmax()])
    if size < 2 or counts.max() < 0.6 * len(gaps):
        return downbeats
    # Programmation dynamique : une phase par barre détectée, un coût par barre hors phase,
    # `change` par changement de phase.
    cost, back = np.zeros(size), []
    for i in at:
        best = int(cost.argmin())
        moved = cost[best] + change
        keep = cost <= moved
        back.append(np.where(keep, np.arange(size), best))
        cost = np.minimum(cost, moved) + (np.arange(size) != i % size)
    phase, phases = int(cost.argmin()), []
    for step in reversed(back):
        phases.append(phase)
        phase = int(step[phase])
    phases.reverse()
    # Chaque phase vaut à partir de la première barre détectée qui la porte.
    starts: list[tuple[int, int]] = []
    for i, phase in zip(at, phases, strict=True):
        if (not starts or starts[-1][1] != phase) and i % size == phase:
            starts.append((i, phase))
    first = starts[0][0]
    out = list(range(first % size, first, size))
    for (start, _), (end, _) in zip(starts, starts[1:] + [(len(t), 0)], strict=True):
        out += range(start, end, size)
    return [float(t[i]) for i in out]


def fill_beats(beats: list[float], activation, fps: float = 50.0, floor: float = 0.2) -> list[float]:
    """Les temps, avec ceux que beat_this a manqués là où il en a gardé une trace.

    `activation` est ce que beat_this entend à chaque trame (de 0 à 1, `fps` trames par
    seconde) ; il ne pose un temps qu'au-dessus de 0,5. Un trou : un écart d'environ deux
    périodes locales (à 15 % près) dont les voisins font une période. Il est comblé si
    l'activation atteint `floor` à moins de 70 ms de son milieu, à l'instant de ce pic : loin
    d'un temps elle reste sous 0,03. Deux trous qui se suivent, ou un passage compté à moitié
    (chaque écart y vaut la période locale), ne sont pas touchés. Sans trou comblé, rend `beats`.
    """
    if len(beats) < 4 or activation is None or not len(activation):
        return beats
    t = np.asarray(beats, dtype=float)
    gaps = np.diff(t)
    out, added = [], False
    for i, gap in enumerate(gaps):
        out.append(float(t[i]))
        step = float(np.median(np.concatenate([gaps[max(0, i - 8) : i], gaps[i + 1 : i + 9]])))
        beside = [gaps[j] for j in (i - 1, i + 1) if 0 <= j < len(gaps)]
        if abs(gap / step - 2) > 0.3 or any(abs(g / step - 1) > 0.15 for g in beside):
            continue
        middle = (t[i] + t[i + 1]) / 2
        first = max(int(round((middle - HEARD) * fps)), 0)
        window = np.asarray(activation[first : int(round((middle + HEARD) * fps)) + 1], dtype=float)
        if len(window) and window.max() >= floor:
            out.append((first + int(window.argmax())) / fps)
            added = True
    return [*out, float(t[-1])] if added else beats


def doubtful_bars(beats: list[float], bars: list[float], activation, fps: float = 50.0) -> dict[float, str]:
    """Les mesures où beat_this hésitait : le premier temps de la mesure → pourquoi, en quelques mots.

    Une mesure est douteuse quand un de ses temps a été entendu faiblement : son activation
    (le plus fort de sa trame et des deux voisines) est sous `WEAK`. Un temps comblé par
    `fill_beats` l'est toujours. Les temps d'avant la première barre ne font pas une mesure.
    """
    if activation is None or not len(activation) or not len(beats) or not len(bars):
        return {}
    heard = np.asarray(activation, dtype=float)
    out: dict[float, str] = {}
    edges, bar, start, rank = [*sorted(bars), float("inf")], -1, None, 0
    for t in beats:
        if t < edges[0] - 0.05:
            continue
        while t >= edges[bar + 1] - 0.05:
            bar, start, rank = bar + 1, t, 0
        rank += 1
        k = min(max(int(round(t * fps)), 0), len(heard) - 1)
        peak = float(heard[max(k - 1, 0) : k + 2].max())
        if peak < WEAK and start not in out:
            out[start] = f"temps {rank} entendu faiblement ({peak:.2f})".replace(".", ",")
    return out


# --- ce qui se trompe sur tout un morceau


def tempo_split(beats: list[float], parts: list[tuple[str, float, float]], near: float = 0.1) -> dict | None:
    """Un morceau compté à deux tempos, l'un double de l'autre : quelles parties à chacun ; None sinon.

    `parts` sont (nom, début, fin), les sections du morceau. La période d'une partie est la médiane
    de ses écarts entre temps ; « double » s'entend à `near` près (10 %). Il faut au moins quatre
    mesures à chaque tempo. Rend `period` (celle du tempo rapide), `fast` et `slow` (les noms).
    """
    periods: dict[str, tuple[float, int]] = {}
    for name, start, end in parts:
        inside = [t for t in beats if start - 0.05 <= t < end - 0.05]
        if len(inside) >= 5:
            periods[name] = (float(np.median(np.diff(inside))), len(inside))
    if len(periods) < 2:
        return None
    lowest = min(p for p, _ in periods.values())
    step = float(np.median([p for p, _ in periods.values() if p / lowest < 1 + near]))
    fast = [n for n, (p, _) in periods.items() if abs(p / step - 1) < near]
    slow = [n for n, (p, _) in periods.items() if abs(p / step - 2) < 2 * near]
    if sum(periods[n][1] for n in fast) < 16 or sum(periods[n][1] for n in slow) < 16:
        return None
    return {"period": step, "fast": fast, "slow": slow}


def halve_beats(
    beats: list[float], downbeats: list[float], start: float, end: float, anchor: float | None = None, size: int = 4
):
    """Un temps sur deux entre `start` et `end` : le passage y était compté au double.

    Sont gardés les temps du rang de celui qui est le plus près d'`anchor` ; sans `anchor`, du rang
    qui garde le plus de barres détectées. Les barres y étaient deux fois trop serrées : restent
    celles qui continuent le compte de `size` temps depuis la dernière barre d'avant la plage (à
    défaut, depuis la première de la plage). Rend les temps, les barres et le premier temps gardé,
    à redonner comme `anchor`.
    """
    inside = [t for t in beats if start - 0.05 <= t < end - 0.05]
    if len(inside) < 2:
        return beats, downbeats, anchor
    within = lambda d: start - 0.05 <= d < end - 0.05
    strong = lambda kept: sum(any(abs(d - t) < 0.05 for t in kept) for d in downbeats if within(d))
    if anchor is None:
        first = 0 if strong(inside[0::2]) >= strong(inside[1::2]) else 1
    else:
        first = min(range(len(inside)), key=lambda i: abs(inside[i] - anchor)) % 2
    dropped = set(inside[1 - first :: 2])
    kept = [t for t in beats if t not in dropped]
    rank = lambda d: min(range(len(kept)), key=lambda i: abs(kept[i] - d))
    here = [d for d in downbeats if within(d) and not any(abs(d - t) < 0.05 for t in dropped)]
    before = [d for d in downbeats if d < start - 0.05]
    origin = rank(before[-1]) if before else rank(here[0]) if here else 0
    on_count = [d for d in here if (rank(d) - origin) % size == 0]
    bars = [d for d in downbeats if not within(d)] + (on_count or here[::2])
    return kept, sorted(bars), inside[first]


def double_beats(beats: list[float], downbeats: list[float], start: float, end: float):
    """Un temps de plus au milieu de chaque écart entre `start` et `end` : le passage y était compté à moitié.

    Les barres y étaient deux fois trop espacées : une de plus au milieu de chaque mesure. Rend les temps et les barres.
    """
    inside = lambda t: start - 0.05 <= t < end - 0.05
    out: list[float] = []
    for t, after in zip(beats, [*beats[1:], None], strict=True):
        out.append(t)
        if after is not None and inside(t):
            out.append((t + after) / 2)
    bars = list(downbeats)
    for a, b in zip(downbeats, downbeats[1:], strict=False):
        if inside(a) and b <= end + 0.05:
            bars.append(min(out, key=lambda t: abs(t - (a + b) / 2)))
    return out, sorted(set(bars))


def shift_bars(beats: list[float], bars: list[float], start: float, end: float, by: int, size: int = 4) -> list[float]:
    """Les barres posées `by` temps plus tard, là où elles arrivent entre `start` et `end` : le 1 y était décalé d'autant.

    Une barre de la plage que le décalage ferait sortir par la fin est retirée ; si la première
    barre déplacée laisse une mesure entière de `size` temps au début de la plage, elle y est
    posée aussi. Hors de la plage, rien ne bouge.
    """
    t = np.asarray(beats, dtype=float)
    inside = lambda x: start - 0.05 <= x < end - 0.05
    moved, kept = [], []
    for bar in bars:
        i = int(np.abs(t - bar).argmin()) + by if len(t) else 0
        if len(t) and i < len(t) and inside(float(t[i])):
            moved.append(i)
        elif not inside(bar):
            kept.append(bar)
    first = min(moved, default=0) - size
    while moved and first >= 0 and inside(float(t[first])):
        moved.append(first)
        first -= size
    return sorted({*kept, *(float(t[i]) for i in moved)})


def bar_shift(marks: list[float], beats: list[float], bars: list[float], size: int = 4) -> int:
    """De combien de temps les barres `marks` du musicien suivent celles écrites (`bars`), si c'est partout pareil ; 0 sinon."""
    t, found = np.asarray(beats, dtype=float), set()
    for mark in marks:
        before = [b for b in bars if b <= mark + 0.05]
        if not before or not len(t):
            return 0
        found.add((int(np.abs(t - mark).argmin()) - int(np.abs(t - before[-1]).argmin())) % size)
    return found.pop() if len(found) == 1 else 0
