"""Aides partagées par plusieurs modules de commandes."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from arr import audio
from arr.app import ANALYSIS, ORIGINAL
from arr.project import Project, ProjectError


def reference(p: Project) -> Path:
    """Audio de référence du projet : l'original s'il existe, sinon le mix courant."""
    original = p.root / ORIGINAL
    return original if original.exists() else render_mix(p)


def render_mix(p: Project, without: tuple[str, ...] = (), only: tuple[str, ...] = ()) -> Path:
    names = [t for t in p.tracks if t not in without and (t in only if only else not p.tracks[t].get("mute"))]
    if not names:
        raise ProjectError("aucune piste à mixer")
    parts = [(audio.load(p.version_path(t)), p.tracks[t].get("gain", 0.0)) for t in names]
    out = p.root / "mix" / "mix.flac"
    audio.save(out, audio.mix(parts))
    return out


def add_track(p: Project, track: str, data, meta: dict) -> str:
    version, path = p.new_version(track, meta)
    audio.save(path, data)
    p.activate(track, version)
    return version


def convert(source: Path, dst: Path) -> None:
    """Importe un fichier audio et prévient s'il ne contient que du silence."""
    audio.convert(source, dst)
    if float(np.abs(audio.load(dst)).max()) < audio.db(-60):
        typer.secho(f"attention : {source.name} est silencieux (niveau max sous -60 dB)", fg="yellow", err=True)


def original_beats(p: Project) -> Optional[list[float]]:
    f = p.root / ANALYSIS
    return json.loads(f.read_text())["beats"] if f.exists() else None


def describe(meta: dict) -> str:
    """Origine d'une version, en quelques mots."""
    op = meta["op"]
    detail = meta.get("model", "") if op == "split" else meta.get("source", "")
    return f"{op:<7} {detail}".rstrip()


def created(meta: dict) -> str:
    return datetime.fromisoformat(meta["created"]).strftime("%d/%m %H:%M")


def confirm(question: str) -> bool:
    return typer.prompt(f"{question} [o/N]", default="n", show_default=False).strip().lower() in (
        "o",
        "oui",
        "y",
        "yes",
    )


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def downbeats(p: Project) -> list[float]:
    f = p.root / ANALYSIS
    if not f.exists():
        raise ProjectError("pas d'analyse (lance `arr analyze`)")
    return json.loads(f.read_text())["downbeats"]
