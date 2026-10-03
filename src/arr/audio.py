"""Audio en 48 kHz stéréo float32, forme (échantillons, 2)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000


def convert(src: Path, dst: Path) -> None:
    """Convertit n'importe quel fichier lisible par ffmpeg en FLAC 48 kHz stéréo."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ar", str(SR), "-ac", "2", str(dst)],
        check=True,
    )


def load(path: Path) -> np.ndarray:
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if sr != SR:
        raise ValueError(f"{path} est en {sr} Hz, attendu {SR}")
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    return audio


def save(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, SR, subtype="PCM_24")


def duration(path: Path) -> float:
    return sf.info(path).duration


def fit(audio: np.ndarray, n: int) -> np.ndarray:
    """Coupe ou complète par du silence pour faire exactement n échantillons."""
    if len(audio) >= n:
        return audio[:n]
    return np.concatenate([audio, np.zeros((n - len(audio), audio.shape[1]), audio.dtype)])


def scale_to(x: np.ndarray, ref: np.ndarray, where: np.ndarray | None = None) -> np.ndarray:
    """Met x à l'échelle pour que x[where] (tout x par défaut) ait le niveau RMS moyen de ref."""
    rms = float(np.sqrt(((x if where is None else x[where]) ** 2).mean()))
    return x if rms < 1e-6 else x * float(np.sqrt((ref ** 2).mean())) / rms


def db(gain_db: float) -> float:
    return 10 ** (gain_db / 20)


def mix(parts: list[tuple[np.ndarray, float]]) -> np.ndarray:
    """Somme des pistes (audio, gain en dB) ; baisse le tout si la somme sature."""
    n = max(len(a) for a, _ in parts)
    out = np.zeros((n, 2), np.float32)
    for audio, gain_db in parts:
        out[: len(audio)] += audio * db(gain_db)
    peak = float(np.abs(out).max())
    if peak > 1.0:
        out /= peak
    return out


def splice(base: np.ndarray, patch: np.ndarray, start: float, end: float, fade: float = 0.02) -> np.ndarray:
    """Remplace base[start:end] par la même plage de patch, avec fondus enchaînés."""
    a, b = int(start * SR), min(int(end * SR), len(base))
    patch = fit(patch, len(base))
    f = min(int(fade * SR), (b - a) // 2)
    env = np.zeros(len(base), np.float32)
    env[a:b] = 1.0
    if f:
        ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)
        env[a : a + f] = ramp
        env[b - f : b] = ramp[::-1]
    env = env[:, None]
    return base * (1 - env) + patch * env
