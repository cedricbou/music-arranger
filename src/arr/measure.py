"""Mesures pour vérifier un résultat sans l'écouter : calage, retard, niveaux, parts des stems.

Un agent ne peut pas juger un son. Ces fonctions donnent des chiffres à mettre dans une PR ;
elles disent si un résultat est cohérent (durée, niveau, calage), jamais s'il est beau.
"""

from __future__ import annotations

import numpy as np

from arr import audio
from arr.audio import period
from arr.grid import steady_bars

ON_BEAT = 0.035  # un temps est « calé » s'il tombe à moins de 35 ms d'un temps de référence


def snap_sections(sections: list[tuple[str, float, float]], bars: list[float]) -> list[tuple[str, float, float]]:
    """Pose les bornes des sections (nom, début, fin) sur les barres de mesure les plus proches.

    Le début du morceau et sa fin ne bougent pas : ils ne tombent pas sur une barre. Une borne
    d'avant la première barre ou d'après la dernière non plus : aucune barre n'y est proche.
    Une section plus courte qu'une mesure peut disparaître, ses deux bornes sur la même barre.
    """
    if len(bars) < 2 or not sections:
        return sections
    grid = np.asarray(steady_bars(bars))
    half = float(np.median(np.diff(grid))) / 2

    def near(t: float) -> float:
        return round(float(grid[np.abs(grid - t).argmin()]), 3) if grid[0] - half <= t <= grid[-1] + half else t

    out = []
    for i, (name, start, end) in enumerate(sections):
        start = start if i == 0 else near(start)
        end = end if i == len(sections) - 1 else near(end)
        if end > start:
            out.append((name, start, end))
    return out


def beat_fit(beats: list[float], reference: list[float]) -> dict:
    """Meilleur ajustement linéaire de `beats` sur `reference` : une vitesse, un décalage.

    Renvoie `speed` (rapport des périodes : < 1 si `beats` est plus rapide), `offset`
    (secondes à retirer après mise au tempo) et `on_beat` (part des temps qui tombent alors
    à moins de 35 ms d'un temps de référence).
    """
    ref = np.asarray(reference, dtype=float)
    speed = period(beats) / period(reference)
    mine = np.asarray(beats, dtype=float) / speed
    offset = float(np.median([t - ref[np.abs(ref - t).argmin()] for t in mine]))
    on_beat = float(np.mean([np.abs(ref - (t - offset)).min() < ON_BEAT for t in mine]))
    return {"speed": speed, "offset": offset, "on_beat": on_beat}


def delay(reference: np.ndarray, signal: np.ndarray, longest: float = 0.5) -> float:
    """Retard de `signal` sur `reference`, en secondes, par corrélation (de 0 à `longest`)."""
    a, b = reference[:, 0], signal[:, 0]
    lags = np.arange(int(longest * audio.SR))
    spectrum = np.fft.rfft(b, 2 * len(a)) * np.conj(np.fft.rfft(a, 2 * len(a)))
    return float(lags[np.argmax(np.fft.irfft(spectrum)[: len(lags)])]) / audio.SR


def level(data: np.ndarray) -> tuple[float, float]:
    """Niveau de crête et niveau moyen (RMS), en dB ; -120 pour du silence."""
    peak = float(np.abs(data).max(initial=0.0))
    rms = float(np.sqrt((data**2).mean())) if len(data) else 0.0
    return 20 * float(np.log10(max(peak, 1e-6))), 20 * float(np.log10(max(rms, 1e-6)))


def shares(stems: dict[str, np.ndarray]) -> dict[str, float]:
    """Part de l'énergie de chaque stem dans leur somme, de 0 à 1."""
    energy = {name: float((data**2).sum()) for name, data in stems.items()}
    total = sum(energy.values()) or 1.0
    return {name: value / total for name, value in energy.items()}


# --- carte de calage : où un signal se place-t-il par rapport à une référence ?

_RATE = 12000  # les mesures se font à 12 kHz : assez pour l'harmonie et les attaques
_ONSET_HOP = 0.01  # secondes
_CHROMA_HOP = 0.05


def _mono(data: np.ndarray) -> np.ndarray:
    return data.mean(axis=1)[:: audio.SR // _RATE]


def _onsets(x: np.ndarray) -> np.ndarray:
    """Force des attaques, une valeur toutes les 10 ms."""
    hop = int(_ONSET_HOP * _RATE)
    n = len(x) // hop * hop
    energy = np.log1p(50 * np.sqrt((x[:n].reshape(-1, hop) ** 2).mean(axis=1)))
    return np.maximum(np.diff(energy, prepend=energy[:1]), 0)


def _chroma(x: np.ndarray, size: int = 4096) -> np.ndarray:
    """Répartition de l'énergie sur les douze notes, une ligne toutes les 50 ms."""
    hop = int(_CHROMA_HOP * _RATE)
    frames = np.lib.stride_tricks.sliding_window_view(np.pad(x, (size // 2, size // 2)), size)[::hop]
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(size), axis=1))
    freqs = np.fft.rfftfreq(size, 1 / _RATE)
    keep = (freqs > 60) & (freqs < 2000)
    note = np.round(12 * np.log2(freqs[keep] / 440) + 69).astype(int) % 12
    chroma = np.log1p(10 * np.stack([spectrum[:, keep][:, note == i].sum(axis=1) for i in range(12)], axis=1))
    chroma -= chroma.mean(axis=1, keepdims=True)
    return chroma / (np.linalg.norm(chroma, axis=1, keepdims=True) + 1e-9)


def _scores(a: np.ndarray, b: np.ndarray, center: float, half: float, lags: np.ndarray, hop: float):
    """Ressemblance de `b` à `a` autour de `center`, pour chaque décalage de `lags` (en pas de `hop`)."""
    i0, i1 = int((center - half) / hop), int((center + half) / hop)
    if i0 < 0 or i1 > len(a):
        return None
    window, scores = a[i0:i1], []
    for lag in lags:
        j0, j1 = i0 + lag, i1 + lag
        if j0 < 0 or j1 > len(b):
            scores.append(-1.0)
        elif a.ndim == 2:  # chroma : lignes déjà normées
            scores.append(float((window * b[j0:j1]).sum() / len(window)))
        else:
            x, y = window - window.mean(), b[j0:j1] - b[j0:j1].mean()
            scores.append(float((x * y).sum() / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9)))
    return np.array(scores)


def time_map(reference: np.ndarray, signal: np.ndarray, step: float = 4.0, span: float = 3.0) -> list[dict]:
    """Décalage de `signal` par rapport à `reference`, fenêtre par fenêtre.

    Les attaques proposent des placements précis à 10 ms, mais elles se ressemblent d'un
    temps à l'autre ; l'harmonie, qui ne se répète pas d'un temps à l'autre, choisit entre
    eux. Une comparaison des seuls temps serait aveugle à un décalage d'un temps entier.

    Chaque entrée : `time` (centre de la fenêtre), `lag` (secondes, > 0 si le signal est en
    retard), `confidence` (corrélation des attaques) et `harmony` (corrélation de l'harmonie).
    """
    # Une marge de silence aux deux bouts : sans elle, la première fenêtre ne peut pas
    # essayer un décalage négatif (ni la dernière un positif), et sa mesure est fausse.
    margin = np.zeros(int(span * _RATE), dtype=np.float32)
    ref = np.concatenate([margin, _mono(reference), margin])
    sig = np.concatenate([margin, _mono(signal), margin])
    ref_chroma, sig_chroma = _chroma(ref), _chroma(sig)
    ref_onsets, sig_onsets = _onsets(ref), _onsets(sig)
    coarse = np.arange(-int(span / _CHROMA_HOP), int(span / _CHROMA_HOP) + 1)
    fine = np.arange(-int(span / _ONSET_HOP), int(span / _ONSET_HOP) + 1)
    out = []
    for center in np.arange(span + 8.0, len(ref) / _RATE - span - 8.0, step):
        harmony = _scores(ref_chroma, sig_chroma, center, 8.0, coarse, _CHROMA_HOP)
        attacks = _scores(ref_onsets, sig_onsets, center, 6.0, fine, _ONSET_HOP)
        if harmony is None or attacks is None:
            continue
        harmony = np.interp(fine * _ONSET_HOP, coarse * _CHROMA_HOP, harmony)
        peaks = np.flatnonzero((attacks[1:-1] >= attacks[:-2]) & (attacks[1:-1] >= attacks[2:])) + 1
        peaks = peaks[attacks[peaks] >= 0.5 * attacks.max()] if attacks.max() > 0 else peaks[:0]
        best = int(peaks[np.argmax(harmony[peaks] + 0.25 * attacks[peaks])]) if len(peaks) else int(np.argmax(harmony))
        out.append(
            {
                "time": float(center - span),
                "lag": float(fine[best] * _ONSET_HOP),
                "confidence": float(attacks[best]),
                "harmony": float(harmony[best]),
            }
        )
    return out


def by_section(windows: list[dict], sections: list[tuple[str, float, float]], minimum: float = 0.15) -> list[dict]:
    """Un décalage par section : la médiane de ses fenêtres fiables.

    Chaque entrée : `name`, `lag` (secondes, ou None sans fenêtre fiable), `windows` (leur
    nombre), `spread` (écart entre elles), `ambiguous` et `guessed`.

    Une fenêtre à cheval sur un changement de décalage donne une valeur mélangée : la section
    est sûre dès que 60 % de ses fenêtres s'accordent avec la médiane à 100 ms près. Sinon le
    passage se répète et plusieurs placements se valent : on retient les fenêtres qui
    prolongent la section précédente (`guessed`, une supposition à vérifier à l'oreille), et
    à défaut la section reste `ambiguous`.
    """
    out, previous = [], None
    for name, start, end in sections:
        lags = np.array([w["lag"] for w in windows if start <= w["time"] < end and w["confidence"] >= minimum])
        entry = {"name": name, "lag": None, "windows": len(lags), "spread": 0.0, "ambiguous": False, "guessed": False}
        if len(lags):
            median = float(np.median(lags))
            entry.update(lag=median, spread=float(lags.max() - lags.min()))
            if np.mean(np.abs(lags - median) <= 0.1) < 0.6:
                near = lags[np.abs(lags - previous) <= 0.1] if previous is not None else []
                if len(near) >= 2:
                    entry.update(lag=float(np.median(near)), guessed=True)
                else:
                    entry["ambiguous"] = True
            if not entry["ambiguous"]:
                previous = entry["lag"]
        out.append(entry)
    return out


def within(windows: list[dict], tolerance: float = 0.03, minimum: float = 0.15) -> float:
    """Part des fenêtres fiables où le signal est à moins de `tolerance` de la référence."""
    lags = [abs(w["lag"]) for w in windows if w["confidence"] >= minimum]
    return float(np.mean([lag < tolerance for lag in lags])) if lags else 0.0


_NOTES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_TRIADS = {
    "min": (0, 3, 7),
    "dim": (0, 3, 6),
    "hdim": (0, 3, 6),
    "aug": (0, 4, 8),
    "sus4": (0, 5, 7),
    "sus2": (0, 2, 7),
}


def _triad(label: str) -> np.ndarray | None:
    """Les trois notes d'un accord (« D:min », « F:maj7 »), comme une ligne de chroma ; None pour « N »."""
    root, _, quality = label.partition(":")
    if root[:1] not in _NOTES:
        return None
    steps = next((v for k, v in _TRIADS.items() if quality.startswith(k)), (0, 4, 7))
    notes = np.full(12, -0.25)
    notes[[(_NOTES[root[0]] + root.count("#") - root.count("b") + s) % 12 for s in steps]] = 0.75
    return notes / np.linalg.norm(notes)


def seat_chords(
    chords: list[tuple], own_bars: list[float], bars: list[float], beats: list[float], reference
) -> list[tuple]:
    """Replace les accords d'une transcription sur les mesures de référence du morceau.

    `chords` sont (début, fin, étiquette), posés sur les mesures `own_bars` de la transcription ;
    `bars` et `beats` sont la grille de référence. Là où les deux grilles ne comptent pas les
    mesures pareil (une mesure à deux temps que la transcription n'a pas vue), les accords
    sont décalés d'un nombre entier de temps pour retomber sur les barres de référence : vers
    l'avant ou vers l'arrière, selon ce qui colle le mieux à l'harmonie de `reference()`, qui
    rend l'audio du morceau et n'est appelé que s'il y a quelque chose à trancher.
    """
    if len(beats) < 3 or len(bars) < 2 or not own_bars or not chords:
        return chords
    beat, ref = period(beats), np.asarray(bars)
    size = int(round(float(np.median(np.diff(ref))) / beat))
    late = [int(round((d - ref[np.abs(ref - d).argmin()]) / beat)) for d in own_bars]
    zones, i = [], 0
    while i < len(late):
        j = i
        while j + 1 < len(late) and late[j + 1] == late[i]:
            j += 1
        if late[i]:
            zones.append((own_bars[i], own_bars[j + 1] if j + 1 < len(own_bars) else float("inf"), late[i]))
        i = j + 1
    if not zones:
        return chords
    chroma = _chroma(_mono(reference()))

    def fit(inside: list[tuple], shift: float) -> float:
        total = 0.0
        for start, end, label in inside:
            a, b = (max(int((t + shift) / _CHROMA_HOP), 0) for t in (start, end))
            if (triad := _triad(label)) is not None and len(chroma[a:b]):
                total += float((chroma[a:b] @ triad).sum())
        return total

    moved = []
    for start, end, label in chords:
        zone = next((z for z in zones if z[0] - 0.02 <= start < z[1] - 0.02), None)
        if zone:
            inside = [c for c in chords if zone[0] - 0.02 <= c[0] < zone[1] - 0.02]
            back = -zone[2]
            shift = max((back, back + size if back < 0 else back - size), key=lambda s: fit(inside, s * beat)) * beat
            start, end = start + shift, end + shift
        moved.append((start, end, label))
    moved.sort(key=lambda c: c[0])
    # Aux bords d'une zone, l'accord d'avant est tenu jusqu'au suivant : ni trou ni chevauchement.
    ends = [c[0] for c in moved[1:]] + [moved[-1][1]]
    return [(start, end, label) for (start, _, label), end in zip(moved, ends, strict=True) if end > start]
