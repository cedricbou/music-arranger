"""Temps, mesures, tempo et tonalité."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from arr import audio
from arr.engines import device
from arr.project import ProjectError

# Miroir d'un tiers du fichier publié par les auteurs (cloud de la JKU) : la révision fige son contenu.
BEAT_THIS_REPO = "oulianov/beat_this"
BEAT_THIS_REVISION = "fea475438eb3b8e509c7661a44f1ca97ffbe9829"

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Profils de Krumhansl-Kessler
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def checkpoint() -> Path:
    """Poids de beat_this dans le cache Hugging Face ; seul `arr models pull` les télécharge."""
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        return Path(hf_hub_download(BEAT_THIS_REPO, "final0.ckpt", revision=BEAT_THIS_REVISION))
    except LocalEntryNotFoundError:
        raise ProjectError("poids de beat_this absents (arr models pull)") from None


@lru_cache(maxsize=1)
def _heard(path: Path) -> tuple:
    """Les temps et barres de beat_this pour ce fichier, et ses activations brutes : un seul passage du modèle."""
    import torch
    from beat_this.inference import File2Beats
    from beat_this.preprocessing import load_audio

    model = File2Beats(checkpoint_path=str(checkpoint()), device=device(), dbn=False)
    with torch.no_grad():
        logits = model.spect2frames(model.signal2spect(*load_audio(str(path))))
        b, d = model.frames2beats(*logits)
    frames = torch.sigmoid(torch.stack(logits, dim=1)).float().cpu().numpy()
    return [float(x) for x in b], [float(x) for x in d], frames


def beats(path: Path) -> tuple[list[float], list[float]]:
    return _heard(path)[:2]


def activations(path: Path) -> np.ndarray:
    """Ce que beat_this entend à chaque trame (50 par seconde) : colonnes temps et premier temps, de 0 à 1.

    Il ne pose un temps qu'au-dessus de 0,5 : un temps manqué laisse ici sa trace (`grid.fill_beats`).
    """
    return _heard(path)[2]


def tempo(beat_times: list[float]) -> float:
    return round(60.0 / audio.period(beat_times), 1)


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
