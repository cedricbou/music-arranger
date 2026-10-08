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


def save_mp3(path: Path, audio: np.ndarray) -> None:
    """Pour partager avec les musiciens : MP3 lisible partout."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
         "-codec:a", "libmp3lame", "-q:a", "2", str(path)],
        input=np.ascontiguousarray(audio, dtype=np.float32).tobytes(), check=True,
    )


def stretch(audio: np.ndarray, speed: float) -> np.ndarray:
    """Change la durée sans changer la hauteur : speed 1.01 raccourcit de 1 %."""
    done = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
         "-filter:a", f"atempo={speed:.6f}", "-f", "f32le", "-"],
        input=np.ascontiguousarray(audio, dtype=np.float32).tobytes(), capture_output=True, check=True,
    )
    return np.frombuffer(done.stdout, dtype=np.float32).reshape(-1, 2).copy()


def loudness(audio: np.ndarray) -> float:
    """Volume perçu sur tout le morceau, en LUFS (EBU R128)."""
    done = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
         "-af", "ebur128", "-f", "null", "-"],
        input=np.ascontiguousarray(audio, dtype=np.float32).tobytes(), capture_output=True, check=True,
    )
    summary = done.stderr.decode(errors="replace").rsplit("Integrated loudness:", 1)[-1]
    return float(summary.split("I:")[1].split("LUFS")[0])


def normalize(audio: np.ndarray, target: float, ceiling_db: float = -1.0) -> tuple[np.ndarray, float]:
    """Amène l'audio à `target` LUFS par un seul gain global ; renvoie aussi ce gain, en dB.

    Le gain est réduit si les crêtes dépasseraient `ceiling_db` : la dynamique n'est pas touchée.
    """
    peak = float(np.abs(audio).max(initial=0.0))
    if peak < db(-60):
        return audio, 0.0
    gain = min(target - loudness(audio), ceiling_db - 20 * float(np.log10(peak)))
    return audio * db(gain), gain


def count_in(beats: list[float], downbeats: list[float], bars: int) -> list[tuple[float, bool]]:
    """Clics de décompte menant au premier temps fort : (instant, accentué).

    Les instants peuvent être négatifs quand le morceau commence trop tôt pour le décompte.
    """
    period = float(np.median(np.diff(beats)))
    per_bar = max(1, round(float(np.median(np.diff(downbeats))) / period)) if len(downbeats) > 1 else 4
    first = downbeats[0] if downbeats else beats[0]
    return [(first - k * period, k % per_bar == 0) for k in range(bars * per_bar, 0, -1)]


def add_clicks(audio: np.ndarray, ticks: list[tuple[float, bool]]) -> np.ndarray:
    """Ajoute un clic court à chaque instant (accentué : plus aigu)."""
    out = audio.copy()
    n = int(0.03 * SR)
    decay = np.exp(-np.arange(n) / (0.006 * SR))
    for time, accent in ticks:
        start = int(round(time * SR))
        if 0 <= start < len(out) - n:
            blip = 0.5 * decay * np.sin(2 * np.pi * (1600 if accent else 1000) * np.arange(n) / SR)
            out[start: start + n] += blip[:, None].astype(np.float32)
    return out


def shift(audio: np.ndarray, seconds: float) -> np.ndarray:
    """Retarde (seconds > 0) ou avance l'audio, à longueur constante."""
    k = int(round(seconds * SR))
    if k >= 0:
        return fit(np.concatenate([np.zeros((k, audio.shape[1]), audio.dtype), audio]), len(audio))
    return fit(audio[-k:], len(audio))


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
