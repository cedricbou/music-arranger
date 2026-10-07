"""Mesures pour vérifier un résultat sans l'écouter : calage, retard, niveaux, parts des stems.

Un agent ne peut pas juger un son. Ces fonctions donnent des chiffres à mettre dans une PR ;
elles disent si un résultat est cohérent (durée, niveau, calage), jamais s'il est beau.
"""

from __future__ import annotations

import numpy as np

from arr import audio

ON_BEAT = 0.035  # un temps est « calé » s'il tombe à moins de 35 ms d'un temps de référence


def period(beats: list[float]) -> float:
    """Durée moyenne d'un temps, assez précise pour comparer deux tempos.

    Les intervalles anormaux (temps manqué ou en trop) sont écartés avant de moyenner : une
    simple régression sur les temps serait faussée par un seul temps manqué.
    """
    gaps = np.diff(beats)
    median = np.median(gaps)
    return float(gaps[np.abs(gaps - median) < 0.1 * median].mean())


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
