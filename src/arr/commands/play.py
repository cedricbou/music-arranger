"""Écoute : le mix, une piste ou une prise, avec un écran qui dit ce qui joue."""

from __future__ import annotations

import json
from typing import Optional

import typer

from arr import audio
from arr.app import ANALYSIS, SCORE, app
from arr.commands._common import lead_in, load_track, mix_tracks, render_mix
from arr.commands._screen import live, mix_notes, position, timeline, view
from arr.project import Project, ProjectError


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
    cours, le calage qui s'y applique et ses accords, celui du moment surligné. Ctrl+C arrête.
    """
    from arr import studio
    from arr.engines import transcription

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
    take = name in p.takes()
    names, notes = [] if take else [name] if name else mix_tracks(p, tuple(without), tuple(only)), []
    if take:
        mode = "libre" if p.take_meta(name).get("mode") == "free" else "fidèle"
        title = f"Prise {name}, telle que rendue ({mode})"
        notes = [f"[dim]ni calage ni gain ; ses stems calés se jouent un par un : arr play {name}.<stem>[/]"]
    elif name:
        title = f"Piste {name}, seule"
    else:
        title = f"Mix · {len(names)} piste{'s' if len(names) > 1 else ''}"
        notes = mix_notes(p, names, tuple(without), tuple(only))
    # Une prise brute n'est pas calée sur l'original : ses accords ne tomberaient pas au bon moment.
    chords = [] if take else transcription.chords((p.root / SCORE).parent)
    hint = "en boucle · Ctrl+C arrête" if loop else "Ctrl+C arrête"

    def screen(seconds: float):
        t = position(seconds, lead, len(playback) if loop else 0)
        return view(
            p,
            title,
            names,
            marks,
            len(body) / audio.SR,
            hint,
            t,
            chords=chords,
            notes=notes,
            solo=bool(name),
            version=version,
        )

    with live(screen) as shown:
        studio.play(playback, loop=body if loop else None, watch=lambda seconds: shown.update(screen(seconds)))
