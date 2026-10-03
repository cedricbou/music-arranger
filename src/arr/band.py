"""Profil du groupe : ~/.config/arr/band.toml

    [trompette]
    track = "brass"                       # famille ACE-Step
    sound = "bright trumpet, tight stabs" # description réutilisée dans les prompts
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from arr.engines.acestep import TRACKS
from arr.project import ProjectError

PATH = Path(os.environ.get("ARR_BAND", Path.home() / ".config/arr/band.toml"))


@dataclass
class Instrument:
    name: str
    track: str
    sound: str


def instrument(name: str) -> Instrument:
    band = tomllib.loads(PATH.read_text()) if PATH.exists() else {}
    if name in band:
        entry = band[name]
        return Instrument(name, entry["track"], entry.get("sound", name))
    if name in TRACKS:
        return Instrument(name, name, name.replace("_", " "))
    raise ProjectError(
        f"instrument inconnu : {name}. Ajoute-le dans {PATH} ou utilise une famille : {', '.join(TRACKS)}"
    )
