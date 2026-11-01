"""Antisèche de scène : la fiche d'un morceau, proposée depuis le projet puis modifiable."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Optional

import typer

from arr import sheet as sheets
from arr.app import app, set_app
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


def open_editor(path: Path) -> bool:
    """Ouvre `path` dans l'éditeur de l'utilisateur ; sans éditeur ni terminal, indique seulement le fichier."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor and sys.stdin.isatty():
        subprocess.run([*editor.split(), str(path)], check=False)
        return True
    typer.echo(f"à modifier : {path}")
    return False


def entry(p: Project, number: int | str = "", semitones: int | None = None, note: str = "") -> dict:
    """Un morceau prêt à imprimer : son antisèche telle qu'elle se joue, son titre, son rang."""
    current, _ = song_sheet(p)
    return {
        "number": number,
        "title": p.song.get("title", p.root.name),
        "artist": p.song.get("artist", ""),
        "sheet": sheets.played(current, semitones),
        "note": note,
        "duration": float(p.song.get("duration", 0.0)),
    }


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
    pdf: bool = typer.Option(False, "--pdf", help="Écrit aussi export/sheet.pdf, pour voir l'antisèche imprimée."),
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
    if edit and open_editor(path):
        current, written = song_sheet(p)
    show(p, current, written)
    if pdf:
        from arr import pdf as printer

        out = p.root / "export" / "sheet.pdf"
        printer.render([entry(p)], p.song.get("title", p.root.name), out, columns=2)
        typer.echo(out.relative_to(p.root))


# --- setlists : un fichier par concert, dans le dossier qui contient les projets


def library() -> Path:
    """Le dossier qui contient les projets : celui du projet courant, sinon le dossier courant."""
    try:
        return Project.find().root.parent
    except ProjectError:
        return Path.cwd()


def setlist_file(name: str, must_exist: bool = True) -> Path:
    folder = library() / "setlists"
    path = folder / f"{name.removesuffix('.toml')}.toml"
    if must_exist and not path.exists():
        known = ", ".join(sorted(f.stem for f in folder.glob("*.toml"))) or "aucune"
        raise ProjectError(f"setlist inconnue : {name} (connues : {known}) ; arr set new {name} MORCEAU...")
    return path


def song_folder(name: str) -> str:
    """Le dossier d'un morceau, tel qu'il s'écrit dans une setlist ; refuse ce qui n'est pas un projet."""
    folder = Path(name.rstrip("/")).name
    if not (library() / folder / "song.toml").exists():
        raise ProjectError(f"{folder} n'est pas un projet de {library()}")
    return folder


def read_setlist(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"{path.name} est mal écrit : {e} (arr set edit {path.stem})")


def write_setlist(path: Path, data: dict) -> None:
    import tomli_w

    path.parent.mkdir(exist_ok=True)
    path.write_text(tomli_w.dumps(data))


def setlist_songs(data: dict) -> tuple[list[dict], list[str]]:
    """Les morceaux d'une setlist prêts à imprimer, numérotés, et ce qui empêche d'en imprimer certains."""
    entries, problems, number = [], [], 0
    for item in sheets.setlist_entries(data):
        if item.get("break"):
            entries.append({"break": True, "sheet": {}})
            continue
        number += 1
        folder = library() / str(item.get("song", ""))
        try:
            if not (folder / "song.toml").exists():
                raise ProjectError("projet introuvable")
            entries.append(entry(Project(folder), number, item.get("transpose"), str(item.get("note", ""))))
        except ProjectError as e:
            problems.append(f"{item.get('song')} : {e}")
            entries.append({"number": number, "title": str(item.get("song")), "sheet": None})
    return entries, problems


@set_app.command("new")
def set_new(
    name: str = typer.Argument(..., help="Nom de la setlist : setlists/NOM.toml est créé."),
    songs: list[str] = typer.Argument(None, help="Dossiers des morceaux, dans l'ordre du concert."),
    title: Optional[str] = typer.Option(None, "--title", help="Titre imprimé en haut des feuilles ; sinon le nom."),
) -> None:
    """Crée une setlist, à lancer depuis le dossier qui contient les projets."""
    path = setlist_file(name, must_exist=False)
    if path.exists():
        raise ProjectError(f"la setlist {name} existe déjà (arr set add {name} MORCEAU..., ou arr set edit {name})")
    write_setlist(path, {"title": title or name, "songs": [song_folder(s) for s in songs or []]})
    typer.echo(f"{path.relative_to(library())} : {len(songs or [])} morceau(x)")


@set_app.command("add")
def set_add(
    name: str = typer.Argument(..., help="Setlist à compléter."),
    songs: list[str] = typer.Argument(None, help="Dossiers des morceaux à ajouter."),
    at: Optional[int] = typer.Option(None, "--at", help="Rang où les insérer (1 = en tête) ; sinon à la fin."),
    pause: bool = typer.Option(False, "--break", help="Ajoute un entracte (avant les morceaux donnés)."),
) -> None:
    """Ajoute des morceaux, ou un entracte, à une setlist."""
    path = setlist_file(name)
    data = read_setlist(path)
    items = data.setdefault("songs", [])
    new = (["---"] if pause else []) + [song_folder(s) for s in songs or []]
    if not new:
        raise ProjectError("rien à ajouter : donne des morceaux, ou --break pour un entracte")
    where = len(items) if at is None else max(at - 1, 0)
    items[where:where] = new
    write_setlist(path, data)
    typer.echo(f"{path.stem} : {sum(not e.get('break') for e in sheets.setlist_entries(data))} morceau(x)")


@set_app.command("edit")
def set_edit(name: str = typer.Argument(..., help="Setlist à ouvrir.")) -> None:
    """Ouvre le fichier de la setlist : réordonner, retirer, transposer un morceau pour ce concert.

    Un morceau s'écrit "dossier", ou { song = "dossier", transpose = -2, note = "enchaîner" } ;
    "---" marque un entracte.
    """
    open_editor(setlist_file(name))


@set_app.command("show")
def set_show(name: str = typer.Argument(..., help="Setlist à afficher.")) -> None:
    """Affiche l'ordre du concert : tonalité, tempo et durée de chaque morceau, et ce qui manque."""
    from rich.console import Console
    from rich.table import Table

    data = read_setlist(setlist_file(name))
    entries, problems = setlist_songs(data)
    table = Table(box=None, pad_edge=False, header_style="bold", title_justify="left")
    for column in ("N°", "Morceau", "Tonalité", "BPM", "Durée", "Pour ce concert"):
        table.add_column(column, no_wrap=True)
    total = 0.0
    for e in entries:
        if e.get("break"):
            table.add_row("", "[dim]— entracte —[/]", "", "", "", "")
        elif e["sheet"] is None:
            table.add_row(str(e["number"]), e["title"], "[red]?[/]", "", "", "[red]incomplet[/]")
        else:
            total += e["duration"]
            shift = f"transposé de {e['sheet']['transpose']:+d}" if e["sheet"]["transpose"] else ""
            song = " – ".join(filter(None, (e["title"], e["artist"])))
            length = f"{int(e['duration']) // 60}:{int(e['duration']) % 60:02d}"
            extra = " · ".join(filter(None, (shift, e["note"])))
            table.add_row(str(e["number"]), song, e["sheet"]["key"], str(e["sheet"]["bpm"]), length, extra)
    console = Console()
    console.print(f"[bold]{data.get('title', name)}[/]", highlight=False)
    console.print(table, highlight=False)
    typer.echo(
        f"\n{sum(not e.get('break') for e in entries)} morceaux, {int(total) // 60} min {int(total) % 60:02d} s de musique"
    )
    for problem in problems:
        typer.secho(problem, fg="yellow", err=True)


@set_app.command("print")
def set_print(
    name: str = typer.Argument(..., help="Setlist à imprimer."),
    pages: Optional[int] = typer.Option(
        None,
        "--pages",
        help="Nombre de feuilles A4 à ne pas dépasser : le texte prend la plus grande taille qui tient.",
    ),
    columns: int = typer.Option(2, "--columns", min=1, max=3, help="Colonnes par feuille."),
    out: Optional[Path] = typer.Option(None, "--out", help="Fichier PDF à écrire ; sinon setlists/NOM.pdf."),
) -> None:
    """Écrit le PDF des antisèches du concert : une feuille A4 en colonnes, un bloc par morceau.

    Chaque bloc porte le rang, le titre, la tonalité, le tempo, puis l'antisèche du morceau
    (arr sheet) et la note de la setlist. Un morceau sans antisèche possible est refusé.
    """
    from arr import pdf

    path = setlist_file(name)
    data = read_setlist(path)
    entries, problems = setlist_songs(data)
    if problems:
        raise ProjectError("antisèches impossibles à imprimer :\n  " + "\n  ".join(problems))
    if not entries:
        raise ProjectError(f"la setlist {name} est vide (arr set add {name} MORCEAU...)")
    target = out or path.with_suffix(".pdf")
    done = pdf.render(entries, str(data.get("title", name)), target, columns=columns, pages=pages)
    typer.echo(f"{target} : {done['pages']} feuille(s), texte à {done['scale']:.0%}")
    if not done["fits"]:
        typer.secho(
            f"ne tient pas en {pages} feuille(s), même au plus petit : allège des antisèches (arr sheet --edit)",
            fg="yellow",
            err=True,
        )
    elif not done["readable"]:
        typer.secho(
            "texte petit, difficile à lire debout : allège des antisèches (arr sheet --edit) ou ajoute une feuille",
            fg="yellow",
            err=True,
        )
