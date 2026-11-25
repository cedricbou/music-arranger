"""ChordPro : le morceau écrit pour un prompteur de scène, et son aperçu à l'écran."""

from __future__ import annotations

import tomllib

import typer

from arr import chordpro as cho
from arr import lyrics, structure
from arr import sheet as sheets
from arr.app import LYRICS, LYRICS_TIMES, app
from arr.commands._screen import song_chart
from arr.project import Project, ProjectError


def played_key(p: Project) -> tuple[str, int]:
    """La tonalité jouée et la transposition : celles de sheet.toml s'il existe, sinon l'original."""
    try:
        written = sheets.load(p.root)
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"{sheets.SHEET_FILE} est mal écrit : {e} (arr sheet --edit, ou --reset)")
    if written is None:
        return sheets.key_name(str(p.song.get("key", ""))), 0
    seen = sheets.played(written)
    return seen["key"], seen["transpose"]


def song_lyrics(p: Project, passages: list[structure.Passage]) -> tuple[dict, list[str], str]:
    """Les paroles de chaque section avec leur instant chanté, ce qui en est laissé de côté, et d'où elles viennent."""
    from arr.engines.transcription import first_sung

    f, times = p.root / LYRICS, p.root / LYRICS_TIMES
    if not f.exists():
        return {}, [], "sans paroles"
    synced = times.read_text() if times.exists() else None
    parts = lyrics.placed(f.read_text(), synced, p.sections, first_sung(p.root / "score"))
    if parts is None:
        why = f"{len(lyrics.blocks(f.read_text()))} balises pour {len(p.sections)} sections, paroles laissées de côté"
        return {}, [f"{LYRICS} : {why} — relis {LYRICS}"], "sans paroles"
    by = {s.name: part for s, part in zip(p.sections, parts, strict=True)}
    kept = {passage.section for passage in passages}
    warnings = [
        f"{name} : plus courte qu'une mesure, ses paroles sont laissées de côté — relis {LYRICS}"
        for name, lines in by.items()
        if lines and name not in kept
    ]
    source = f"paroles de {LYRICS}" + (f", placées par {LYRICS_TIMES}" if synced else ", réparties")
    return by, warnings, source


def prepare(p: Project) -> tuple[dict, list[cho.Block], int, list[str], str]:
    """Tout ce qu'il faut pour écrire le fichier : en-tête, passages en grilles, mesure, alertes, sources."""
    chart = song_chart(p)
    if not chart:
        raise ProjectError("pas d'accords : lance arr transcribe")
    if all(bar[2] == 1 for bar in chart):
        raise ProjectError("pas de grille de mesures : lance arr analyze")
    passages = structure.default(p.sections, chart)
    if not passages:
        raise ProjectError("aucune section ne couvre une mesure : vois arr sections list, puis arr sections set")
    key, shift = played_key(p)
    words, warnings, source = song_lyrics(p, passages)
    passages = cho.edges(passages, key, shift)
    blocks = cho.layout(passages, words, key, shift)
    warnings += [f"{b.name} : aucun accord — relis la transcription" for b in blocks if not b.chords]
    head = {
        "project": p.root.name,
        "title": p.song.get("title", p.root.name),
        "artist": p.song.get("artist", ""),
        "key": key,
        "tempo": round(float(p.song.get("bpm", 0))),
        "duration": cho.duration(passages),
    }
    sources = f"structure de l'original · accords de la transcription · {source}"
    return head, blocks, cho.meter(passages), warnings, sources


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n > 1 else ''}"


def clock(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def chords_of(block: cho.Block) -> list:
    return [(g.beats, [bars for bars, _ in g.lines]) for g in block.grids]


def report(head: dict, blocks: list[cho.Block], usual: int, warnings: list[str], sources: str, path: str) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console(highlight=False)
    total = sum(b.bars for b in blocks)
    facts = f"{head['key']} · ♩{head['tempo']} · {usual}/4 · {total} mesures · {head['duration']}"
    console.print(f"[bold]{head['title']}[/] → {path}   [dim]{facts}[/]")
    console.print(f"  [dim]{sources}[/]\n")
    table = Table.grid(padding=(0, 3))
    seen: dict[str, list] = {}
    for b in blocks:
        if seen.get(b.name) == chords_of(b):
            detail = "comme le premier"
        else:
            seen.setdefault(b.name, chords_of(b))
            lines = sum(len(g.lines) for g in b.grids)
            detail = plural(lines, "ligne") + " de mesures"
            if b.odd:
                at = ", ".join(f"{beats} temps à {clock(start)}" for start, beats in b.odd)
                detail += f", dont {'une mesure' if len(b.odd) == 1 else f'{len(b.odd)} mesures'} de {at}"
            if b.sung:
                detail += f" · {plural(b.sung, 'ligne')} de paroles en repère"
        table.add_row(f"  {b.name}", f"{b.bars:>3} mes.", detail, "1 rappel" if b.cue else "")
    console.print(table)
    if warnings:
        console.print()
    for warning in warnings:
        console.print(f"  [yellow]⚠ {warning}[/]")
    console.print("  [dim]arr chordpro --show : le lire ici, passage par passage[/]")


def show(head: dict, blocks: list[cho.Block], usual: int) -> None:
    from rich.console import Console
    from rich.markup import escape

    console = Console(highlight=False)
    console.print(
        f"[bold]{escape(head['title'])}[/] · {head['key']} · ♩{head['tempo']} · {usual}/4 · {head['duration']}"
    )
    width = max(len(bar) for b in blocks for g in b.grids for bars, _ in g.lines for bar in bars) + 2

    def cell(bar: str) -> str:
        marks = " ".join("[dim].[/]" if c == "." else f"[bold cyan]{escape(c)}[/]" for c in bar.split())
        return " " + marks + " " * (width - len(bar)) + "[dim]|[/]"

    for b in blocks:
        cue = f"     [yellow]{escape(b.cue)}[/]" if b.cue else ""
        console.print(f"\n  [bold]{escape(b.name.upper()):<12}[/]{b.bars:>3} mes.{cue}")
        current = usual
        for g in b.grids:
            for i, (bars, words) in enumerate(g.lines):
                lead = f"{g.beats}/4 " if i == 0 and g.beats != current else "    "
                tail = f"  {escape(words)}" if words else ""
                console.print(f"{lead}[dim]|[/]" + "".join(cell(bar) for bar in bars) + tail)
            current = g.beats


@app.command()
def chordpro(
    display: bool = typer.Option(False, "--show", help="Montre le morceau ici, passage par passage, sans l'écrire."),
) -> None:
    """Écrit le morceau en fichier ChordPro pour un prompteur de scène : export/<dossier>.cho.

    Une grille d'accords standard par passage, dans l'ordre joué : quatre mesures par ligne,
    une case par temps, les paroles chantées sur ces mesures en repère après la dernière
    barre. Le fichier est dans la tonalité jouée (`transpose` de sheet.toml) et se réécrit
    en entier à chaque appel : c'est le projet qu'on corrige, jamais le fichier.
    """
    p = Project.find()
    head, blocks, usual, warnings, sources = prepare(p)
    if display:
        show(head, blocks, usual)
        return
    out = p.root / "export" / f"{p.root.name}.cho"
    out.parent.mkdir(exist_ok=True)
    out.write_text(cho.write(head, blocks, usual))
    report(head, blocks, usual, warnings, sources, str(out.relative_to(p.root)))
