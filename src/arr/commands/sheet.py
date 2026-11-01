"""Antisèche de scène : la fiche d'un morceau, proposée depuis le projet puis modifiable."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from typing import Optional

import typer

from arr import sheet as sheets
from arr.app import app
from arr.commands._screen import song_chart
from arr.project import Project, ProjectError


def song_sheet(p: Project) -> tuple[dict, bool]:
    """L'antisèche du morceau et si elle vient de sheet.toml ; sinon c'est la proposition déduite du projet."""
    try:
        written = sheets.load(p.root)
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"{sheets.SHEET_FILE} est mal écrit : {e} (arr sheet --edit, ou --reset)")
    if written is not None:
        return written, True
    chart = song_chart(p)
    missing = [
        what
        for what, there in (
            ("la tonalité et le tempo", p.song.get("key") and p.song.get("bpm")),
            ("les sections", p.sections),
            ("les accords", chart),
        )
        if not there
    ]
    if missing:
        raise ProjectError(f"il manque {', '.join(missing)} pour l'antisèche : lance arr transcribe")
    return sheets.propose(p.song, p.sections, chart), False


def show(p: Project, sheet: dict, written: bool) -> None:
    from rich.console import Console
    from rich.table import Table

    seen = sheets.played(sheet)
    console = Console()
    shift = f"  [yellow]transposé de {seen['transpose']:+d}[/]" if seen["transpose"] else ""
    title = " – ".join(filter(None, (p.song.get("title"), p.song.get("artist"))))
    console.print(f"[bold]{title}[/]  [bold cyan]{seen['key']}[/] · {seen['bpm']} BPM{shift}", highlight=False)
    if seen.get("structure"):
        console.print(f"[dim]{seen['structure']}[/]", highlight=False)
    table = Table.grid(padding=(0, 2))
    for part in seen.get("parts", []):
        times = f"[dim]×{part['repeat']}[/]" if part.get("repeat", 1) > 1 else ""
        table.add_row(f"[bold]{part.get('name', '')}[/]", part.get("chords", ""), times)
    console.print(table, highlight=False)
    for note in seen.get("notes", []):
        console.print(f"• {note}", highlight=False)
    origin = sheets.SHEET_FILE if written else "proposition déduite du projet : arr sheet --edit pour la modifier"
    console.print(f"[dim]({origin})[/]", highlight=False)


@app.command()
def sheet(
    edit: bool = typer.Option(False, "--edit", help="Écrit la proposition dans sheet.toml s'il manque, et l'ouvre."),
    note: Optional[str] = typer.Option(None, "--note", help="Ajoute un rappel à l'antisèche."),
    transpose: Optional[int] = typer.Option(
        None,
        "--transpose",
        help="Demi-tons de transposition : --transpose=-2 joue un ton plus bas ; 0 pour l'original.",
    ),
    reset: bool = typer.Option(False, "--reset", help="Revient à la proposition ; sheet.toml part dans trash/."),
) -> None:
    """Montre l'antisèche du morceau : tonalité, tempo, structure, accords des passages clés, rappels.

    Tant que sheet.toml n'existe pas, elle est déduite du projet. Dès qu'il existe, lui seul
    fait foi : modifie-le pour montrer moins, plus, ou autre chose.
    """
    p = Project.find()
    path = p.root / sheets.SHEET_FILE
    if reset:
        p._discard([path], purge=False)
    current, written = song_sheet(p)
    if note is not None or transpose is not None or (edit and not written):
        if note is not None:
            current["notes"] = [*current.get("notes", []), note]
        if transpose is not None:
            current["transpose"] = transpose
        sheets.save(p.root, current)
        written = True
    if edit:
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if editor and sys.stdin.isatty():
            subprocess.run([*editor.split(), str(path)], check=False)
            current, written = song_sheet(p)
        else:
            typer.echo(f"à modifier : {path}")
    show(p, current, written)
