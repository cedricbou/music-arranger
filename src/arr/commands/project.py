"""Créer un projet et y importer de l'audio."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from arr import audio
from arr.app import ORIGINAL, app
from arr.commands._common import (
    add_track,
    convert,
)
from arr.project import Project


@app.command()
def init(name: str, source: Optional[Path] = typer.Option(None, "--from", help="Morceau à importer.")) -> None:
    """Crée un projet dans le dossier NAME."""
    p = Project.create(Path(name), name)
    typer.echo(f"projet créé : {p.root}")
    if source:
        convert(source, p.root / ORIGINAL)
        typer.echo(f"importé : {ORIGINAL} ({audio.duration(p.root / ORIGINAL):.1f} s)")


@app.command("import")
def import_(
    source: Path,
    track: Optional[str] = typer.Option(None, "--as", help="Importer comme piste (stem ou idée), ex. bass."),
) -> None:
    """Ajoute un morceau complet, ou une piste avec --as."""
    p = Project.find()
    if track is None:
        convert(source, p.root / ORIGINAL)
        typer.echo(f"importé : {ORIGINAL}")
        return
    tmp = p.root / "source" / f"{track}-{source.stem}.flac"
    convert(source, tmp)
    version = add_track(p, track, audio.load(tmp), {"op": "import", "source": str(tmp.relative_to(p.root))})
    typer.echo(f"{track} {version}")
