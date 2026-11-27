"""Écoute : le mix, une piste ou une prise, avec un écran qui dit ce qui joue."""

from __future__ import annotations

from typing import Optional

import typer

from arr import audio, midi
from arr.app import app
from arr.commands._common import (
    doubtful_passages,
    lead_in,
    load_track,
    mix_tracks,
    render_mix,
    song_doubts,
    song_grid,
)
from arr.commands._playback import bar_stops, neighbour, next_after, playing
from arr.commands._screen import mix_notes, position, song_chart, timeline, view
from arr.project import Project, ProjectError


def doubt_stops(doubts: dict, starts: list[float], ranges: list[tuple[float, float]], length: float) -> list[float]:
    """Où mène d : le début de chaque passage douteux, en secondes de lecture, parmi les mesures jouées."""
    stops, t = [], 0.0
    for start, end in ranges or [(0.0, length)]:
        played = [b for b in starts if start - 0.05 <= b < end]
        stops += [t + max(first - start, 0.0) for first, _, _ in doubtful_passages(doubts, played)]
        t += end - start
    return stops


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
) -> None:
    """Écoute le mix (complet ou partiel), une piste ou une prise, en entier ou par sections.

    Pendant la lecture, l'écran montre ce qui joue (pistes, versions, gains), la section en
    cours, le calage qui s'y applique et sa grille d'accords, l'accord du moment surligné.

    Espace met en pause et reprend ; flèche gauche revient à la mesure d'avant, flèche droite
    passe à la suivante. Ctrl+C arrête.

    Une mesure marquée « ? » sur la grille est une mesure dont `arr` n'est pas sûr du compte :
    d saute au prochain passage douteux. La marque ne change ni la grille ni le fichier du
    prompteur ; elle part quand `arr review` a jugé le passage bon.

    Avec --clock, un prompteur de scène sur le même ordinateur (namfoop) suit la lecture :
    l'horloge donne le tempo dès le décompte, Start part sur la mesure 1 du fichier ChordPro,
    la position suit les sections, les flèches et la boucle, la pause envoie Stop.
    """
    p = Project.find()
    sections = [name.strip() for given in sections for name in given.split(",") if name.strip()]
    ranges = [(s.start, s.end) for s in map(p.section, sections)]
    if name is None:
        path = render_mix(p, tuple(without), tuple(only))
    elif name in p.takes():
        if sections or bars or clock:
            raise ProjectError(
                f"une prise brute n'est pas calée sur l'original : ni section, ni décompte, ni horloge "
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
    doubts = (song_doubts(p, mine=True) or {}) if measures else {}
    # d mène au début de chaque passage douteux, parmi les mesures jouées.
    unsure = doubt_stops(doubts, [m[0] for m in measures], ranges, len(body) / audio.SR)
    keys = "Espace : pause · ← → : mesure" + (" · d : doute suivant" if unsure else "")
    hint = f"{'en boucle · ' if loop else ''}{'horloge MIDI → arr:transport · ' if clock else ''}{keys} · Ctrl+C arrête"
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
            notes=notes,
            solo=bool(name),
            version=version,
            paused=paused,
            doubts=doubts,
        )

    def steer(keys: list[str], seconds: float):
        nonlocal paused
        t = position(seconds, lead, len(playback) if loop else 0)
        base, jump = seconds - t, None  # le flux compte depuis le décompte ; les mesures, depuis le morceau joué
        for key in keys:
            if key == "pause":
                paused = not paused
            elif key == "doubt":
                if (target := next_after(unsure, max(t, 0.0), loop)) is not None:
                    t = jump = target
            elif key in ("back", "forward"):
                if (target := neighbour(stops, max(t, 0.0), -1 if key == "back" else 1, loop)) is not None:
                    t = jump = target
        return paused, None if jump is None else base + jump

    again = body if loop else None
    if not clock:
        playing(playback, again, screen, steer)
    else:
        where = lambda seconds: position(seconds, lead, len(playback) if loop else 0)
        with midi.Transport(plan, where) as transport:
            playing(playback, again, screen, steer, follow=transport.heard)
