"""Enveloppe unique autour d'ACE-Step 1.5 : une tâche, un fichier source, un audio en sortie."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

from arr import audio
from arr.engines import CHECKPOINTS, device, offline

BASE = "acestep-v15-base"
TRACKS = ["woodwinds", "brass", "fx", "synth", "strings", "percussion",
          "keyboard", "guitar", "bass", "drums", "backing_vocals", "vocals"]


def _project(v0: torch.Tensor, v1: torch.Tensor, dims=[-1]):
    # L'original passe en float64 sur le GPU, ce que l'Arc ne sait pas faire :
    # on fait cette petite projection sur le CPU.
    dtype, dev = v0.dtype, v0.device
    v0, v1 = v0.cpu().double(), v1.cpu().double()
    v1 = torch.nn.functional.normalize(v1, dim=dims)
    parallel = (v0 * v1).sum(dim=dims, keepdim=True) * v1
    return parallel.to(dev, dtype), (v0 - parallel).to(dev, dtype)


def instruction(task: str, tracks: list[str]) -> str | None:
    """Consigne au format d'entraînement d'ACE-Step (noms de piste en majuscules)."""
    for t in tracks:
        if t not in TRACKS:
            raise ValueError(f"piste ACE-Step inconnue : {t} (connues : {', '.join(TRACKS)})")
    if task == "lego":
        return f"Generate the {tracks[0].upper()} track based on the audio context:"
    if task == "extract":
        return f"Extract the {tracks[0].upper()} track from the audio:"
    if task == "complete":
        return f"Complete the input track with {' | '.join(t.upper() for t in tracks)}:"
    return None


class Engine:
    def __init__(self, model: str = BASE):
        offline()
        from loguru import logger

        logger.remove()
        logger.add(sys.stderr, level="WARNING")
        from acestep.handler import AceStepHandler
        from acestep.models.common import apg_guidance

        apg_guidance.project = _project
        self.model = model
        self.handler = AceStepHandler()
        msg, ok = self.handler.initialize_service(
            project_root=str(CHECKPOINTS.parent), config_path=model, device=device()
        )
        if not ok:
            raise RuntimeError(msg)

    def generate(
        self,
        task: str,
        caption: str,
        src: Path | None = None,
        *,
        tracks: list[str] = (),
        start: float | None = None,
        end: float | None = None,
        strength: float | None = None,
        fidelity: float | None = None,
        bpm: float | None = None,
        key: str = "",
        duration: float | None = None,
        seed: int = -1,
        steps: int = 50,
        guidance: float = 7.0,
    ) -> tuple[np.ndarray, dict]:
        from acestep.inference import GenerationConfig, GenerationParams, generate_music

        kw: dict = dict(
            task_type=task, caption=caption, lyrics="[Instrumental]", instrumental=True,
            thinking=False, seed=seed, inference_steps=steps, guidance_scale=guidance, keyscale=key,
        )
        if src is not None:
            kw["src_audio"] = str(src)
        instr = instruction(task, list(tracks))
        if instr:
            kw["instruction"] = instr
        if bpm:
            kw["bpm"] = round(bpm)
        if duration:
            kw["duration"] = duration
        if start is not None:
            kw.update(repainting_start=start, repainting_end=end if end is not None else -1,
                      chunk_mask_mode="explicit")
        if strength is not None:
            # Part des pas conditionnés par le contenu de la source ; à 0, seul le texte guide.
            kw["audio_cover_strength"] = strength
        if fidelity is not None:
            # 0 : part d'un bruit pur ; 1 : part de l'audio source lui-même
            kw["cover_noise_strength"] = fidelity
        config = GenerationConfig(batch_size=1, use_random_seed=seed < 0, audio_format="flac")
        with tempfile.TemporaryDirectory() as tmp:
            res = generate_music(self.handler, None, GenerationParams(**kw), config, save_dir=tmp)
            if not res.success:
                raise RuntimeError(res.error)
            out = audio.load(Path(res.audios[0]["path"]))
        used = res.audios[0].get("params", {}).get("seed", seed)
        meta = {"model": self.model, "task": task, "prompt": caption, "seed": used, "steps": steps,
                "guidance": guidance}
        meta.update({k: v for k, v in (("instruction", instr), ("start", start), ("end", end),
                                       ("strength", strength), ("fidelity", fidelity)) if v is not None})
        return out, meta
