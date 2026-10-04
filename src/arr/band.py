"""Profil du groupe : ~/.config/arr/band.toml

    [trompette]
    track = "brass"                       # famille ACE-Step
    sound = "bright trumpet, tight stabs" # description réutilisée dans les prompts

    [styles]                              # formules réutilisables avec --style
    funk = "light funk, syncopated 16th notes, clean tone, tight"
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


def _load() -> dict:
    return tomllib.loads(PATH.read_text()) if PATH.exists() else {}


def style(name: str) -> str:
    styles = _load().get("styles", {})
    if name not in styles:
        known = ", ".join(styles) or "aucun"
        raise ProjectError(f"style inconnu : {name} (connus : {known} ; à définir dans {PATH}, table [styles])")
    return styles[name]


def instrument(name: str) -> Instrument:
    band = _load()
    if name in band and name != "styles":
        entry = band[name]
        return Instrument(name, entry["track"], entry.get("sound", name))
    if name in TRACKS:
        return Instrument(name, name, name.replace("_", " "))
    raise ProjectError(
        f"instrument inconnu : {name}. Ajoute-le dans {PATH} ou utilise une famille : {', '.join(TRACKS)}"
    )
