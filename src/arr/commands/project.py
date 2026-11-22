"""Créer un projet, y importer de l'audio, nommer les dossiers des morceaux."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from arr import audio
from arr.app import ORIGINAL, app
from arr.commands._common import (
    add_track,
    confirm,
    convert,
    folder_name,
)
from arr.commands.sheet import library, read_setlist, write_setlist
from arr.project import SONG_FILE, Project


@app.command()
def init(
    name: str = typer.Argument(..., help="Nom du projet : un dossier de ce nom est créé ici."),
    source: Optional[Path] = typer.Option(None, "--from", help="Morceau à importer."),
) -> None:
    """Crée un projet dans le dossier NAME."""
    p = Project.create(Path(name), name)
    typer.echo(f"projet créé : {p.root}")
    if source:
        convert(source, p.root / ORIGINAL)
        typer.echo(f"importé : {ORIGINAL} ({audio.duration(p.root / ORIGINAL):.1f} s)")


@app.command("import")
def import_(
    source: Path = typer.Argument(..., help="Fichier audio à importer (tout format lu par ffmpeg)."),
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


@app.command()
def rename(yes: bool = typer.Option(False, "--yes", "-y", help="Renomme sans demander.")) -> None:
    """Nomme le dossier de chaque morceau d'après son artiste et son titre (avril-lavigne--complicated).

    À lancer depuis le dossier qui contient les projets. Les setlists suivent. Un morceau sans
    artiste, ou dont le nouveau nom est déjà pris, garde son dossier.
    """
    root = library()
    moves, kept = {}, []
    for folder in sorted(d for d in root.iterdir() if (d / SONG_FILE).is_file()):
        song = Project(folder).song
        target = folder_name(str(song.get("title", "")), str(song.get("artist", "")))
        if target == folder.name:
            continue
        if not song.get("artist"):
            kept.append(f"{folder.name} : pas d'artiste dans song.toml")
        elif (root / target).exists() or target in moves.values():
            kept.append(f"{folder.name} : {target} existe déjà")
        else:
            moves[folder.name] = target
    for old, new in moves.items():
        typer.echo(f"{old}  ->  {new}")
    for line in kept:
        typer.echo(f"gardé  {line}")
    if not moves:
        typer.echo("rien à renommer")
        return
    if not yes and not confirm(f"renommer {len(moves)} dossier(s) et mettre les setlists à jour ?"):
        return
    for old, new in moves.items():
        (root / old).rename(root / new)
    for path in sorted((root / "setlists").glob("*.toml")):
        data = read_setlist(path)
        songs = [_renamed(item, moves) for item in data.get("songs", [])]
        if songs != data.get("songs", []):
            write_setlist(path, {**data, "songs": songs})
            typer.echo(f"setlist mise à jour : {path.name}")
    typer.echo(f"{len(moves)} dossier(s) renommé(s)")


def _renamed(item: str | dict, moves: dict[str, str]) -> str | dict:
    """Une ligne de setlist après renommage : un dossier, ou une table {song, transpose, note}."""
    if isinstance(item, str):
        return moves.get(item, item)
    return {**item, "song": moves.get(item["song"], item["song"])} if "song" in item else item
