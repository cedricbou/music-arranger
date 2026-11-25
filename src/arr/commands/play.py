"""Écoute : le mix, une piste ou une prise, avec un écran qui dit ce qui joue."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import Optional

import typer

from arr import audio, midi, truth
from arr.app import app
from arr.commands._common import confirm, lead_in, load_track, mix_tracks, render_mix, song_grid
from arr.commands._screen import clock as mmss
from arr.commands._screen import live, mix_notes, position, song_chart, timeline, view
from arr.project import Project, ProjectError

KEYS = {b" ": "pause", b"D": "back", b"C": "forward"}
STEP = 5.0  # secondes entre deux arrêts quand le morceau n'a pas de mesures connues


def parse_keys(data: bytes) -> list[str]:
    """Les touches reconnues dans ce que le terminal a envoyé : espace, flèche gauche, flèche droite."""
    return [KEYS[k[-1:]] for k in re.findall(rb" |\x1b[\[O][CD]", data)]


@contextmanager
def keyboard(tap=None):
    """Le temps de la lecture, lit les touches sans attendre Entrée ; donne une fonction qui rend celles tapées.

    Avec `tap`, le clavier ne pilote plus la lecture : un fil appelle `tap(heure)` à chaque
    Espace, l'heure (`time.monotonic`) lue dès que la touche arrive, là où l'écran ne passe
    que vingt fois par seconde. Hors d'un terminal (tests, sortie redirigée), aucune touche n'est lue.
    """
    import select
    import sys

    if not sys.stdin.isatty():
        yield lambda: []
        return
    import termios
    import threading
    import time
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setcbreak(fd)  # Ctrl+C reste un signal : il arrête toujours la lecture
    done = threading.Event()

    def pressed() -> list[str]:
        data = b""
        while select.select([fd], [], [], 0)[0]:
            data += os.read(fd, 64)
        return parse_keys(data)

    def listen() -> None:
        while not done.is_set():
            if select.select([fd], [], [], 0.05)[0]:
                at = time.monotonic()
                for key in parse_keys(os.read(fd, 64)):
                    if key == "pause":
                        tap(at)

    thread = threading.Thread(target=listen, daemon=True) if tap else None
    try:
        if thread:
            thread.start()
        yield (lambda: []) if tap else pressed
    finally:
        done.set()
        if thread:
            thread.join()
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def marked_passage(sections: list[str], ranges: list[tuple[float, float]], length: float) -> tuple[str, float, float]:
    """Le passage que couvre un repérage : son nom, son début et sa fin dans le morceau.

    Les sections jouées doivent se suivre dans le morceau : une frappe se lit comme un instant du morceau.
    """
    if any(abs(b[0] - a[1]) > 0.05 for a, b in zip(ranges, ranges[1:], strict=False)):
        raise ProjectError("--mark : les sections doivent se suivre dans le morceau (ex. -s chorus2,outro)")
    return ("+".join(sections), ranges[0][0], ranges[-1][1]) if ranges else ("song", 0.0, length)


def keep_marks(p: Project, passage: tuple[str, float, float], times: list[float]) -> None:
    """Fin d'un repérage : dit ce que valent les frappes contre la grille, et les range si le musicien les garde."""
    from arr import measure

    name, start, end = passage
    bars = truth.bar_marks(times, start, end)
    if len(bars) < 2:
        typer.secho(f"{len(bars)} barre repérée dans {name} : rien n'est gardé (Espace sur le 1 de chaque mesure)")
        return
    typer.echo(f"{len(bars)} barres repérées dans {name}, de {mmss(bars[0])} à {mmss(bars[-1])}")
    if grid := song_grid(p):
        s = truth.score(bars, 4, grid[0], measure.regular_bars(grid[1], grid[0]))
        typer.echo(f"  {s['matched']} tombent sur une barre d'arr (à 70 ms près), qui en pose {s['shown']} ici")
    if not confirm("Garder ce repérage ?"):
        typer.echo("repérage abandonné, rien n'est écrit")
        return
    kept = truth.save(p, name, start, end, bars)
    typer.echo(
        f"gardé : truth/{name}.{kept.version}.toml ({kept.beats_per_bar} temps par mesure) · arr truth pour la note"
    )


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


def neighbour(stops: list[float], t: float, step: int, loop: bool = False) -> Optional[float]:
    """Le début de la mesure d'avant (`step` -1) ou d'après (+1) celle où l'on est.

    Après la dernière : None, ou la première si la lecture est en boucle.
    """
    here = max((i for i, s in enumerate(stops) if s <= t + 0.05), default=0)
    if loop and here + step >= len(stops):
        return stops[0]
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
    clock: bool = typer.Option(
        False,
        "--clock",
        help="Envoie l'horloge et le transport MIDI sur le port « arr:transport » : un prompteur de scène suit le morceau.",
    ),
    mark: bool = typer.Option(
        False,
        "--mark",
        help="Repère les barres de mesure à l'oreille : Espace sur le 1 de chaque mesure du passage joué.",
    ),
) -> None:
    """Écoute le mix (complet ou partiel), une piste ou une prise, en entier ou par sections.

    Pendant la lecture, l'écran montre ce qui joue (pistes, versions, gains), la section en
    cours, le calage qui s'y applique et sa grille d'accords, l'accord du moment surligné.

    Espace met en pause et reprend ; flèche gauche revient à la mesure d'avant, flèche droite
    passe à la suivante. Ctrl+C arrête.

    Avec --clock, un prompteur de scène sur le même ordinateur (namfoop) suit la lecture :
    l'horloge donne le tempo dès le décompte, Start part sur la mesure 1 du fichier ChordPro,
    la position suit les sections, les flèches et la boucle, la pause envoie Stop.

    Avec --mark, le passage joué devient un passage de référence : Espace se tape sur le premier
    temps de chaque mesure (ni pause ni flèches pendant ce temps), une passe suffit. À la fin,
    les barres repérées sont rangées dans `truth/` du morceau, à l'instant où elles s'entendaient ;
    refaire un passage garde le repérage précédent à côté. `arr truth` note la grille contre elles.
    """
    from arr import studio

    p = Project.find()
    sections = [name.strip() for given in sections for name in given.split(",") if name.strip()]
    ranges = [(s.start, s.end) for s in map(p.section, sections)]
    if name is None:
        path = render_mix(p, tuple(without), tuple(only))
    elif name in p.takes():
        if sections or bars or clock or mark:
            raise ProjectError(
                f"une prise brute n'est pas calée sur l'original : ni section, ni décompte, ni horloge, ni repérage "
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
    if mark and loop:
        raise ProjectError("--mark : une seule passe du passage, sans --loop")
    passage = marked_passage(sections, ranges, len(body) / audio.SR) if mark else None
    ticks: list[tuple[float, bool]] = []
    if bars:
        start = ranges[0][0] if ranges else 0.0
        grid = song_grid(p) or ([], [])
        beats, strong = ([t - start for t in times if t >= start - 0.05] for times in grid)
        if len(beats) > 1:
            ticks = audio.count_in(beats, strong, bars)
        else:
            typer.secho("pas de décompte : le tempo est inconnu (arr transcribe ou arr analyze)", fg="yellow", err=True)
    playback, _ = lead_in(body, ticks)
    lead = len(playback) - len(body)
    plan = []
    if clock:
        from arr.commands.chordpro import written_bars

        try:
            bars = written_bars(p)
        except ProjectError as e:
            raise ProjectError(f"pas d'horloge MIDI sans les mesures du fichier ChordPro : {e}")
        plan = midi.clock_plan(bars, ranges or [(0.0, len(body) / audio.SR)], ticks[0][0] if ticks else 0.0)
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
    measures = [] if take else song_chart(p)
    keys = "Espace : le 1 de chaque mesure" if mark else "Espace : pause · ← → : mesure"
    hint = f"{'en boucle · ' if loop else ''}{'horloge MIDI → arr:transport · ' if clock else ''}{keys} · Ctrl+C arrête"
    taps = truth.Taps() if mark else None
    grid = song_grid(p) if not take else None
    stops = bar_stops([m[0] for m in measures] or (grid[1] if grid else []), ranges, len(body) / audio.SR)
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
            notes=notes + ([f"[bold yellow]● repérage[/] · {len(taps.times)} barres"] if taps else []),
            solo=bool(name),
            version=version,
            paused=paused,
        )

    def run() -> None:
        with live(screen) as shown, keyboard(taps.tap) if taps else keyboard() as pressed:

            def watch(seconds: float):
                nonlocal paused
                t = position(seconds, lead, len(playback) if loop else 0)
                base, jump = (
                    seconds - t,
                    None,
                )  # le flux compte depuis le décompte ; les mesures, depuis le morceau joué
                for key in pressed():
                    if key == "pause":
                        paused = not paused
                    elif (target := neighbour(stops, max(t, 0.0), -1 if key == "back" else 1, loop)) is not None:
                        t = jump = target
                shown.update(screen(seconds if jump is None else base + jump))
                return paused, None if jump is None else base + jump

            if not clock:
                studio.play(playback, loop=body if loop else None, watch=watch, follow=taps.heard if taps else None)
                return
            where = lambda seconds: position(seconds, lead, len(playback) if loop else 0)
            with midi.Transport(plan, where) as transport:

                def follow(seconds: float, at: float, stopped: bool) -> None:
                    transport.heard(seconds, at, stopped)
                    taps.heard(seconds, at, stopped)

                studio.play(
                    playback, loop=body if loop else None, watch=watch, follow=follow if taps else transport.heard
                )

    run()
    if taps:
        # Une frappe date une position du flux, décompte compris : elle devient un instant du morceau.
        keep_marks(p, passage, [passage[1] + position(t, lead) for t in taps.positions()])
