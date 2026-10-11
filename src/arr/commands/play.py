"""Écoute : le mix, une piste ou une prise, avec un écran qui dit ce qui joue."""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from typing import Optional

import typer

from arr import audio
from arr.app import ANALYSIS, SCORE, app
from arr.commands._common import lead_in, load_track, mix_tracks, render_mix
from arr.commands._screen import chart, live, mix_notes, position, timeline, view
from arr.project import Project, ProjectError

KEYS = {b" ": "pause", b"D": "back", b"C": "forward"}
STEP = 5.0  # secondes entre deux arrêts quand le morceau n'a pas de mesures connues


def parse_keys(data: bytes) -> list[str]:
    """Les touches reconnues dans ce que le terminal a envoyé : espace, flèche gauche, flèche droite."""
    return [KEYS[k[-1:]] for k in re.findall(rb" |\x1b[\[O][CD]", data)]


@contextmanager
def keyboard():
    """Le temps de la lecture, lit les touches sans attendre Entrée ; donne une fonction qui rend celles tapées.

    Hors d'un terminal (tests, sortie redirigée), aucune touche n'est lue.
    """
    import select
    import sys

    if not sys.stdin.isatty():
        yield lambda: []
        return
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setcbreak(fd)  # Ctrl+C reste un signal : il arrête toujours la lecture

    def pressed() -> list[str]:
        data = b""
        while select.select([fd], [], [], 0)[0]:
            data += os.read(fd, 64)
        return parse_keys(data)

    try:
        yield pressed
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def bar_stops(starts: list[float], ranges: list[tuple[float, float]], length: float) -> list[float]:
    """Où mènent ← et → : les débuts de mesure, en secondes de lecture, et le début de chaque section jouée.

    `starts` sont les débuts de mesure dans le morceau ; sans eux, un arrêt toutes les `STEP` secondes.
    """
    starts = starts or [STEP * i for i in range(int(length / STEP) + 1)]
    stops, t = [], 0.0
    for start, end in ranges or [(0.0, length)]:
        stops += [t] + [t + b - start for b in starts if start < b < end]
        t += end - start
    # Une barre de mesure à quelques centièmes d'un début de section n'est pas un arrêt de plus.
    return [s for i, s in enumerate(stops) if s < length and (i == 0 or s - stops[i - 1] > 0.2)]


def neighbour(stops: list[float], t: float, step: int) -> Optional[float]:
    """Le début de la mesure d'avant (`step` -1) ou d'après (+1) celle où l'on est ; None après la dernière."""
    here = max((i for i, s in enumerate(stops) if s <= t + 0.05), default=0)
    return stops[max(here + step, 0)] if here + step < len(stops) else None


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
    cours, le calage qui s'y applique et sa grille d'accords, l'accord du moment surligné.

    Espace met en pause et reprend ; flèche gauche revient à la mesure d'avant, flèche droite
    passe à la suivante. Ctrl+C arrête.
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
    score = (p.root / SCORE).parent
    measures = [] if take else chart(transcription.chords(score), transcription.beats(score))
    hint = f"{'en boucle · ' if loop else ''}Espace : pause · ← → : mesure · Ctrl+C arrête"
    grid = json.loads(f.read_text()) if (f := p.root / ANALYSIS).exists() and not take else {"downbeats": []}
    stops = bar_stops([m[0] for m in measures] or grid["downbeats"], ranges, len(body) / audio.SR)
    paused = False

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
            bars=measures,
            loop=loop,
            notes=notes,
            solo=bool(name),
            version=version,
            paused=paused,
        )

    with live(screen) as shown, keyboard() as pressed:

        def watch(seconds: float):
            nonlocal paused
            t = position(seconds, lead, len(playback) if loop else 0)
            base, jump = seconds - t, None  # le flux compte depuis le décompte ; les mesures, depuis le morceau joué
            for key in pressed():
                if key == "pause":
                    paused = not paused
                elif (target := neighbour(stops, max(t, 0.0), -1 if key == "back" else 1)) is not None:
                    t = jump = target
            shown.update(screen(seconds if jump is None else base + jump))
            return paused, None if jump is None else base + jump

        studio.play(playback, loop=body if loop else None, watch=watch)
