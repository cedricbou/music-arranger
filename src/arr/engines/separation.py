"""Séparation en stems avec Demucs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torchaudio.functional as F

from arr import audio
from arr.engines import device

MODELS = {
    "htdemucs_6s": "6 stems (drums bass guitar piano vocals other) ; guitare et piano peu fiables",
    "htdemucs_ft": "4 stems (drums bass vocals other) ; plus précis, environ 2,5 fois plus lent",
}


def separate(path: Path, model_name: str = "htdemucs_6s", shifts: int = 1) -> dict[str, np.ndarray]:
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    model = get_model(model_name)
    wav = torch.from_numpy(audio.load(path).T)
    n = wav.shape[1]
    wav = F.resample(wav, audio.SR, model.samplerate)
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()
    with torch.no_grad():
        out = apply_model(model, wav[None], device=device(), shifts=shifts, progress=True)[0]
    out = out.cpu() * ref.std() + ref.mean()
    out = F.resample(out, model.samplerate, audio.SR)
    return {name: audio.fit(stem.T.numpy(), n) for name, stem in zip(model.sources, out, strict=True)}
