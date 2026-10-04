"""YuE2 : rend une prise complète (voix et groupe) à partir d'une partition ABC, de paroles et d'un style.

Le modèle tourne dans le binaire audio.cpp, sur le GPU via Vulkan.
"""
from __future__ import annotations

import random
import re
import subprocess
import tempfile
from pathlib import Path

from arr.engines import AUDIOCPP, YUE2

HEADER = re.compile(r"^(X:|T:|M:|L:|Q:|V:|K:|%)")


def melody_only(abc: str) -> str:
    """Retire les symboles d'accords : YuE2 invente alors l'accompagnement (mode libre)."""
    return "\n".join(
        line if HEADER.match(line) else re.sub(r'"[^"]*"', "", line) for line in abc.splitlines()
    ) + "\n"


def render(abc: str, lyrics: str, style: str, out: Path, *, free: bool = False, seed: int = -1) -> dict:
    """Écrit la prise dans `out` (WAV 48 kHz stéréo) et renvoie les réglages utilisés.

    Mode fidèle : mélodie et accords imposés, la prise garde tempo, mesures et tonalité.
    Mode libre : mélodie seule, l'accompagnement et parfois le tempo sont réinterprétés.
    """
    if not AUDIOCPP.exists():
        raise RuntimeError("audio.cpp absent (arr models pull)")
    seed = seed if seed >= 0 else random.randrange(2**31)
    with tempfile.TemporaryDirectory() as tmp:
        score = Path(tmp) / "score.abc"
        score.write_text(melody_only(abc) if free else abc)
        cmd = [
            str(AUDIOCPP), "--task", "gen", "--family", "yue2", "--model", str(YUE2),
            "--backend", "vulkan", "--threads", "8", "--lyrics", lyrics,
            "--request-option", f"style={style}",
            "--request-option", f"cot={'melody' if free else 'full'}",
            "--request-option", f"abc_file={score}",
            "--seed", str(seed), "--out", str(out),
        ]
        done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0 or not out.exists():
        raise RuntimeError(f"YuE2 a échoué (code {done.returncode}) : {(done.stderr or done.stdout)[-400:]}")
    return {"model": "yue2-3b-q8", "mode": "free" if free else "close", "style": style, "seed": seed}
