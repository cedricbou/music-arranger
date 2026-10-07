"""Temps, mesures, tempo et tonalité."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from arr import audio
from arr.engines import device

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Profils de Krumhansl-Kessler
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def beats(path: Path) -> tuple[list[float], list[float]]:
    from beat_this.inference import File2Beats

    b, d = File2Beats(checkpoint_path="final0", device=device(), dbn=False)(str(path))
    return [float(x) for x in b], [float(x) for x in d]


def period(beat_times: list[float]) -> float:
    """Durée moyenne d'un temps, assez précise pour comparer deux tempos.

    Les intervalles anormaux (temps manqué ou en trop) sont écartés avant de moyenner.
    """
    gaps = np.diff(beat_times)
    median = np.median(gaps)
    return float(gaps[np.abs(gaps - median) < 0.1 * median].mean())


def tempo(beat_times: list[float]) -> float:
    return round(60.0 / float(np.median(np.diff(beat_times))), 1)


def key(path: Path) -> str:
    mono = audio.load(path).mean(1)[::4]  # 12 kHz suffit pour le chroma
    sr, n = audio.SR // 4, 8192
    frames = np.lib.stride_tricks.sliding_window_view(mono, n)[:: n // 2]
    spec = np.abs(np.fft.rfft(frames * np.hanning(n), axis=1)).sum(0)
    freqs = np.fft.rfftfreq(n, 1 / sr)
    keep = (freqs > 55) & (freqs < 2000)
    pitch = np.round(12 * np.log2(freqs[keep] / 440.0) + 69).astype(int) % 12
    chroma = np.bincount(pitch, weights=spec[keep], minlength=12)
    scores = {}
    for i, note in enumerate(NOTES):
        scores[f"{note} major"] = np.corrcoef(chroma, np.roll(MAJOR, i))[0, 1]
        scores[f"{note} minor"] = np.corrcoef(chroma, np.roll(MINOR, i))[0, 1]
    return max(scores, key=scores.get)
