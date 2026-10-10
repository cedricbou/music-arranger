"""Écoute : le mix, une piste ou une prise, avec un écran qui dit ce qui joue."""

from __future__ import annotations

import json
from typing import Optional

import typer

from arr import audio
from arr.app import ANALYSIS, app
from arr.commands._common import lead_in, load_track, mix_tracks, render_mix
from arr.project import Project, ProjectError

ORIGINS = {"align": "auto", "manual": "manuel"}


def clock(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def timeline(p: Project, name: Optional[str], sections: list[str], ranges: list) -> list[tuple[float, float, str]]:
    """Les sections dans l'ordre où elles passent : (début, fin, nom), en secondes de lecture."""
    if name in p.takes():
        return []
    if not sections:
        return [(s.start, s.end, s.name) for s in p.sections]
    marks, t = [], 0.0
    for section, (start, end) in zip(sections, ranges, strict=True):
        marks.append((t, t + end - start, section))
        t += end - start
    return marks


def position(seconds: float, lead: int, first: int = 0) -> float:
    """Place dans le morceau joué, d'après la position du flux : négative pendant le décompte.

    `lead` est la longueur du décompte, en échantillons. En boucle, `first` est celle du
    premier passage, décompte compris : au-delà, la lecture a repris au début du morceau joué.
    """
    return seconds - (first if first and seconds * audio.SR >= first else lead) / audio.SR


def left_out(p: Project, track: str, without: tuple) -> str:
    """Une piste absente du mix, en un mot ; les stems d'une prise sont réunis sous un seul nom."""
    take = track.split(".")[0]
    if "." in track and take in p.takes():
        return f"stems de {take}"
    return f"{track} ({'écartée' if track in without else 'muette'})"


def view(p: Project, name, version, without, only, marks, length: float, loop: bool, t: float):
    """L'écran de lecture à l'instant `t` : ce qui joue, et ce qui s'applique à la section en cours."""
    from rich.console import Group
    from rich.progress_bar import ProgressBar
    from rich.table import Table

    from arr.commands.align import amount, beat_period

    period = beat_period(p)
    index = next((i for i, m in enumerate(marks) if m[0] <= t < m[1]), None)
    section = marks[index][2] if index is not None else None
    take = name in p.takes()
    names = mix_tracks(p, without, only) if name is None else [] if take else [name]

    table = Table(box=None, pad_edge=False, header_style="bold")
    for column in ("", "Piste", "Version", "Gain", "Calage piste", f"Calage {section or 'section'}", "Appliqué"):
        table.add_column(column, no_wrap=True)
    for track in names:
        rules = {n["scope"]: n for n in p.nudges(track)}
        whole, local = (
            (f"{amount(r['ms'], period)} [dim]{ORIGINS.get(r['by'], r['by'])}[/]" if r else "[dim]·[/]")
            for r in (rules.get("track"), rules.get(section))
        )
        total = sum(rules[k]["ms"] for k in ("track", section) if k in rules)
        gain = p.tracks[track].get("gain", 0.0)
        level = f"{gain:+.1f} dB" if gain else "[dim]·[/]"
        if gain and name:
            level = f"[dim]{gain:+.1f} dB dans le mix, non appliqué[/]"
        applied = (
            f"[bold yellow]{amount(total, period)}[/]" if rules.keys() & {"track", section} else "[dim]telle quelle[/]"
        )
        table.add_row("[green]●[/]", track, version or p.tracks[track]["active"], level, whole, local, applied)

    if take:
        mode = "libre" if p.take_meta(name).get("mode") == "free" else "fidèle"
        title = f"Prise {name}, telle que rendue ({mode})"
        parts = [f"[dim]ni calage ni gain ; ses stems calés se jouent un par un : arr play {name}.<stem>[/]"]
    elif name:
        title, parts = f"Piste {name}, seule", [table]
    else:
        title, parts = f"Mix · {len(names)} piste{'s' if len(names) > 1 else ''}", [table]
        out = list(dict.fromkeys(left_out(p, k, without) for k in p.tracks if k not in names))
        if out:
            parts.append(
                f"[dim]○ hors du mix : {f'{len(p.tracks) - len(names)} autres pistes' if only else ', '.join(out)}[/]"
            )

    if t < 0:
        where = "[yellow]décompte[/]"
    elif section:
        where = f"[bold cyan]{section}[/] [dim]({index + 1}/{len(marks)})[/]"
    else:
        where = "[dim]hors section[/]" if marks else "[bold cyan]morceau entier[/]"
    status = Table.grid(padding=(0, 2))
    after = f"[dim]puis {marks[index + 1][2]}[/]" if index is not None and index + 1 < len(marks) else ""
    status.add_row(
        f"[green]▶[/] {where}",
        f"{clock(max(t, 0.0))} / {clock(length)}",
        ProgressBar(total=max(length, 1e-9), completed=max(t, 0.0), width=30),
        after,
        "[dim]en boucle · Ctrl+C arrête[/]" if loop else "[dim]Ctrl+C arrête[/]",
    )
    return Group(f"[bold]{title}[/]", *parts, "", status)


@app.command()
def play(
    name: Optional[str] = typer.Argument(None, help="Piste ou prise (ex. t001) ; sinon le mix."),
    version: Optional[str] = typer.Argument(None, help="Version d'une piste ; sinon la version active."),
    without: list[str] = typer.Option(
        [], "--without", "-w", help="Mix sans cette piste (ex. -w bass pour jouer par-dessus)."
    ),
    only: list[str] = typer.Option([], "--only", "-o", help="Mix de ces seules pistes."),
    sections: list[str] = typer.Option(
        [],
        "--section",
        "-s",
        help="Sections à jouer, enchaînées dans l'ordre donné : -s verse,chorus ou -s verse -s chorus.",
    ),
    loop: bool = typer.Option(False, "--loop", "-l", help="Rejoue en boucle jusqu'à Ctrl+C."),
    bars: int = typer.Option(0, "--count-in", help="Mesures de décompte avant de commencer (pas à chaque boucle)."),
) -> None:
    """Écoute le mix (complet ou partiel), une piste ou une prise, en entier ou par sections.

    Pendant la lecture, l'écran montre ce qui joue (pistes, versions, gains), la section en
    cours et le calage qui s'y applique. Ctrl+C arrête.
    """
    from rich.console import Console
    from rich.live import Live

    from arr import studio

    p = Project.find()
    sections = [name.strip() for given in sections for name in given.split(",") if name.strip()]
    ranges = [(s.start, s.end) for s in map(p.section, sections)]
    if name is None:
        path = render_mix(p, tuple(without), tuple(only))
    elif name in p.takes():
        if sections or bars:
            raise ProjectError(
                f"une prise brute n'est pas calée sur l'original : ni section ni décompte "
                f"(arr split {name}, puis arr play {name}.<stem>)"
            )
        path = p.take_path(name)
    else:
        path = None
    body = audio.load(path) if path else load_track(p, name, version)
    if ranges:
        body = audio.cut(body, ranges)
        if not len(body):
            raise ProjectError("rien à jouer : ces sections sont hors du morceau")
    ticks: list[tuple[float, bool]] = []
    if bars:
        start = ranges[0][0] if ranges else 0.0
        grid = json.loads(f.read_text()) if (f := p.root / ANALYSIS).exists() else {"beats": [], "downbeats": []}
        beats, strong = ([t - start for t in grid[k] if t >= start - 0.05] for k in ("beats", "downbeats"))
        if len(beats) > 1:
            ticks = audio.count_in(beats, strong, bars)
        else:
            typer.secho("pas de décompte : le tempo est inconnu (arr transcribe ou arr analyze)", fg="yellow", err=True)
    playback, _ = lead_in(body, ticks)
    lead = len(playback) - len(body)
    marks = timeline(p, name, sections, ranges)

    def screen(seconds: float):
        t = position(seconds, lead, len(playback) if loop else 0)
        return view(p, name, version, tuple(without), tuple(only), marks, len(body) / audio.SR, loop, t)

    with Live(screen(0.0), console=Console(), refresh_per_second=8) as live:
        studio.play(playback, loop=body if loop else None, watch=lambda seconds: live.update(screen(seconds)))
