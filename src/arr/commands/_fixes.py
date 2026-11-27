"""Les écrans de correction d'`arr review` : taper les barres d'un passage, récrire ses accords dans l'éditeur."""

from __future__ import annotations

from typing import Optional

import typer

from arr import audio, chordfix, grid, truth
from arr import review as layer
from arr.commands._common import confirm, detected_grid, lead_in, open_editor, song_bars
from arr.commands._playback import playing
from arr.commands._screen import chord_block, clock, position, song_chart
from arr.project import Project

KEPT = {"enter": "keep", "redo": "redo", "escape": "drop", "quit": "drop"}
USUAL = 4  # temps posés dans une mesure où le détecteur en a manqué un, ou entendu un deux fois


def cut(whole, start: float, end: float):
    return whole[int(round(start * audio.SR)) : int(round(end * audio.SR))]


def within(chart: list[tuple], start: float, end: float) -> list[tuple]:
    return [m for m in chart if start - 0.05 <= m[0] < end - 0.05]


def clicks(period: float) -> list[tuple[float, bool]]:
    """Les quatre clics du décompte, au tempo du passage, juste avant son début."""
    return [(-k * period, False) for k in range(4, 0, -1)]


def looped(body, lines, answers: dict[str, str], lead: int = 0) -> str:
    """Joue `body` en boucle sous l'écran `lines(instant, en pause)` jusqu'à une touche d'`answers` ; rend sa réponse.

    `lead` : la longueur, en échantillons, d'un décompte au début de `body`, rejoué à chaque tour ;
    l'instant est alors négatif pendant les clics.
    """
    from rich.console import Group

    length, paused, answer = (len(body) - lead) / audio.SR, False, "quit"

    def screen(seconds: float):
        t = (int(seconds * audio.SR) % len(body) - lead) / audio.SR
        return Group(*lines(min(t, length - 1e-3), paused))

    def steer(keys: list[str], seconds: float):
        nonlocal paused, answer
        for key in keys:
            if key == "pause":
                paused = not paused
            elif key in answers:
                answer = answers[key]
                return paused, None, True
        return paused, None

    playing(body, body, screen, steer, transient=True)
    return answer


def tap_bars(whole, chart: list[tuple], start: float, end: float, period: float, name: str) -> tuple[str, list[float]]:
    """Quatre clics au tempo, puis le passage joue une fois : rend les instants du morceau où Espace a été tapé.

    La grille du moment défile sous les yeux. Rend aussi la touche qui a arrêté la passe avant
    sa fin : « redo » (r, à refaire), « escape » ou « quit » (abandon) ; vide si elle est allée au bout.
    """
    from rich.console import Group
    from rich.progress_bar import ProgressBar

    body = cut(whole, start, end)
    playback, lead = lead_in(body, clicks(period))
    taps, length, stopped = truth.Taps(), len(body) / audio.SR, ""
    bars, marks = within(chart, start, end), [(0.0, len(body) / audio.SR, name, start)]

    def screen(seconds: float):
        t = position(seconds, lead)
        clicks = " · ".join(["clic"] * min(4, int((t + 4 * period) / period) + 1))
        now = f"décompte : {clicks}" if t < 0 else f"[green]▶[/] {clock(t)} / {clock(length)}"
        n = len(taps.times)
        return Group(
            f"[bold]Corriger les barres · {name}[/] · le passage joue une fois",
            "Espace sur le 1 de chaque mesure, et sur le 1 qui suit la dernière",
            "",
            now,
            ProgressBar(total=max(length, 1e-9), completed=max(t, 0.0), width=30),
            f"{n} frappe{'s' if n > 1 else ''}",
            *chord_block(bars, marks, min(t, length - 1e-3))[1:3],
            "",
            "[dim]r : recommencer · Échap : abandonner[/]",
        )

    def steer(keys: list[str], seconds: float):
        nonlocal stopped
        stopped = next((key for key in keys if key in ("redo", "escape", "quit")), "")
        return (False, None, True) if stopped else (False, None)

    playing(playback, None, screen, steer, taps.tap, taps.heard, transient=True)
    # Une frappe date une position du flux, décompte compris : elle devient un instant du morceau.
    return stopped, truth.bar_marks([start + position(t, lead) for t in taps.positions()], start, end + period)


def stamp(t: float) -> str:
    return f"{int(t) // 60}:{t % 60:04.1f}".replace(".", ",")


def odd_bars(bars: list[float], beats: list[float]) -> set[int]:
    """Demande, pour les mesures tapées qui ne tiennent pas quatre temps, si elles sont vraies ; rend celles à recompter."""
    found = layer.counts(bars, beats)
    spread: set[int] = set()
    for n in sorted({n for n in found if n != USUAL}):
        where = [i for i, k in enumerate(found) if k == n]
        some = f"{len(where)} mesure{'s' if len(where) > 1 else ''} à {n} temps entre vos frappes"
        wrong = "temps manqué" if n < USUAL else "temps entendu en trop"
        typer.echo(f"{some} ({', '.join(stamp(bars[i]) for i in where)})")
        answer = ""
        while answer not in ("v", "t"):
            answer = (
                typer.prompt(f"  vraie mesure à {n} temps (v), ou {wrong} : {USUAL} temps égaux (t) ?").strip().lower()
            )
        if answer == "t":
            spread.update(where)
    return spread


def beat_counts(read: tuple[list[float], list[float]], start: float, end: float) -> str:
    """Le compte des mesures du passage, pour un morceau sans accords : « 4 · 3 · 5 · 4 temps »."""
    inside = [bar for bar in layer.measures(*read) if start - 0.05 <= bar[0] < end - 0.05]
    return " · ".join(str(len(bar)) for bar in inside) + " temps"


def replay(whole, start: float, end: float, name: str, what: str, old: list, new) -> str:
    """Rejoue le passage en boucle, la nouvelle grille sous l'ancienne ; rend « keep », « redo » ou « drop ».

    `old` : les lignes de la grille d'avant ; `new(instant)` : celles de la nouvelle, l'accord qui sonne en surbrillance.
    """
    body = cut(whole, start, end)

    def lines(t: float, paused: bool) -> list:
        state = "[yellow]⏸ en pause ·[/]" if paused else "[green]▶[/]"
        return [
            f"[bold]Corriger les {what} · {name}[/] · le passage rejoue avec la nouvelle grille",
            f"{state} en boucle · {clock(t)} / {clock(len(body) / audio.SR)}",
            "",
            "[dim]Avant[/]",
            *old,
            "[bold]Après[/]",
            *new(t),
            "",
            "[dim]Entrée : garder · r : refaire · Échap : abandonner · Espace : pause[/]",
        ]

    return looped(body, lines, KEPT)


def grid_rows(chart: list[tuple], start: float, end: float, name: str, t: float = -1.0) -> list:
    """Les rangées de la grille du passage, sans titre ; l'accord qui sonne à `t` en surbrillance."""
    marks = [(0.0, end - start, name, start)]
    return chord_block(within(chart, start, end), marks, t, t >= 0)[2:3]


def fix_bars(p: Project, whole, chart: list[tuple], passage: layer.Passage, name: str) -> Optional[layer.Fix]:
    """Fait taper le 1 de chaque mesure du passage, montre la grille qui en sort, et rend la correction gardée ou None.

    Le passage joue jusqu'à une mesure après sa fin : le 1 qui ferme la dernière mesure s'y entend.
    Chaque frappe va au temps détecté le plus proche ; à plus d'un demi-temps de tout temps, elle est refusée.
    """
    beats = detected_grid(p)[0]
    period = layer.local_period(beats, (passage.start + passage.end) / 2)
    end = min(passage.end + USUAL * period, len(whole) / audio.SR)
    while True:
        stopped, marks = tap_bars(whole, chart, passage.start, end, period, name)
        if stopped == "redo":
            continue
        if stopped:
            return None
        bars, far = layer.snap(marks, beats)
        if far:
            typer.echo(f"frappe à {', '.join(map(stamp, far))} : aucun temps détecté à moins d'un demi-temps")
        elif len(bars) < 2:
            typer.echo(f"{len(bars)} frappe : il en faut deux au moins (le 1 d'une mesure, et le 1 qui la suit)")
        else:
            fix = layer.make_fix(bars, beats, odd_bars(bars, beats), USUAL)
            after = song_chart(p, (fix,))
            old = grid_rows(chart, passage.start, end, name) or [beat_counts(song_bars(p), passage.start, end)]
            counted = [beat_counts(song_bars(p, (fix,)), passage.start, end)]
            new = lambda t, after=after, counted=counted: grid_rows(after, passage.start, end, name, t) or counted
            answer = replay(whole, passage.start, end, name, "barres", old, new)
            if answer != "redo":
                return fix if answer == "keep" else None
            continue
        if not confirm("Refaire ?"):
            return None


def fix_chords(p: Project, whole, chart: list[tuple], passage: layer.Passage, name: str) -> Optional[chordfix.ChordFix]:
    """Ouvre les accords du passage dans l'éditeur, montre la grille qui en sort, et rend la correction gardée ou None.

    Le texte est un fichier temporaire : une ligne par mesure de la grille du moment, barres corrigées
    comprises. Ce qui ne se lit pas est dit en tête du texte, avec son numéro de ligne, et l'éditeur
    se rouvre ; le rendre sans y toucher abandonne.
    """
    import tempfile
    from pathlib import Path

    bars = within(chart, passage.start, passage.end)
    if not bars or not any(bar[3] for bar in bars):
        typer.echo("pas d'accords à corriger ici : lance arr transcribe")
        return None
    beats = {bar[0]: bar for bar in layer.measures(*song_bars(p))}
    times = [beats[bar[0]] for bar in bars]
    given = chordfix.chord_text(name, passage.first, bars)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "accords.txt"
        path.write_text(given)
        while True:
            shown = path.read_text()
            if not open_editor(path):
                typer.echo("pas d'éditeur : règle $VISUAL ou $EDITOR, dans un terminal")
                return None
            text = "\n".join(line for line in path.read_text().splitlines() if not line.startswith("# ✗")) + "\n"
            found, errors = chordfix.read_chord_text(text, passage.first, bars, times)
            if errors:
                if path.read_text() == shown and "# ✗" in shown:
                    typer.echo("texte rendu tel quel : accords laissés tels quels")
                    return None
                for error in errors:
                    typer.echo(error)
                # Les numéros de ligne sont ceux du texte du musicien : les remarques vont à la fin.
                path.write_text(text + "".join(f"# ✗ {error}\n" for error in errors))
                continue
            fix = chordfix.ChordFix(bars[0][0], bars[-1][1], found)
            after = song_chart(p, chords_too=(fix,))
            if within(after, passage.start, passage.end) == bars:
                typer.echo("aucun accord n'a changé")
                return None
            new = lambda t, after=after: grid_rows(after, passage.start, passage.end, name, t)
            answer = replay(
                whole,
                passage.start,
                passage.end,
                name,
                "accords",
                grid_rows(chart, passage.start, passage.end, name),
                new,
            )
            if answer != "redo":
                return fix if answer == "keep" else None
            path.write_text(text)


# --- ce qui se trompe sur tout le morceau


def ask_tempo(p: Project, whole, split: dict, title: str) -> tuple[str, list[tuple[float, float, float]]]:
    """La question des deux tempos : une section en boucle avec un clic par temps, à l'un ou l'autre tempo.

    Rend le tempo gardé (« slow », « fast »), « asis » (laisser tel quel) ou « quit », et les plages
    à recompter : (début, fin, premier temps gardé). La section jouée est une de celles lues au
    tempo rapide : son clic lent tombe un temps sur deux, du côté de ses barres détectées.
    """
    beats, downbeats = detected_grid(p)
    parts = {s.name: s for s in p.sections}
    played = parts[split["fast"][0]]
    inside = [t for t in beats if played.start - 0.05 <= t < played.end - 0.05]
    _, _, anchor = grid.halve_beats(beats, downbeats, played.start, played.end)
    body = cut(whole, played.start, played.end)
    ticks = {"fast": inside, "slow": inside[inside.index(anchor) % 2 :: 2]}
    clicked = {k: audio.add_clicks(body, [(t - played.start, False) for t in v]) for k, v in ticks.items()}
    bpm = {"fast": round(60 / split["period"]), "slow": round(30 / split["period"])}
    current = "slow"

    def lines(t: float, paused: bool) -> list:
        state = "[yellow]⏸ en pause ·[/]" if paused else "[green]▶[/]"
        return [
            f"[bold]{title} · avant la relecture[/]",
            "",
            "[yellow]?[/] arr ne compte pas partout au même tempo",
            f"  {bpm['slow']:<5}{', '.join(split['slow'])}",
            f"  {bpm['fast']:<5}{', '.join(split['fast'])}",
            "",
            f"{state} [bold cyan]{played.name}[/] · en boucle, avec un clic sur chaque temps à [bold]{bpm[current]}[/]",
            "",
            f"[dim]1 : écouter le clic à {bpm['slow']} · 2 : écouter le clic à {bpm['fast']}[/]",
            "[dim]Entrée : garder le clic en cours pour tout le morceau · s : laisser tel quel · q : quitter[/]",
        ]

    answers = {"one": "slow", "two": "fast", "enter": "keep", "skip": "asis", "quit": "quit"}
    while (answer := looped(clicked[current], lines, answers)) in ("slow", "fast"):
        current = answer
    if answer != "keep":
        return answer, []
    if current == "fast":
        return "fast", [(parts[n].start, parts[n].end, 0.0) for n in split["slow"]]
    kept = [grid.halve_beats(beats, downbeats, parts[n].start, parts[n].end)[2] for n in split["fast"]]
    return "slow", [(parts[n].start, parts[n].end, a) for n, a in zip(split["fast"], kept, strict=True)]


def ask_shift(
    p: Project, fix: layer.Fix, written: tuple[list[float], list[float]]
) -> Optional[tuple[float, float, int]]:
    """Après des barres tapées : si le 1 suit partout celui d'`arr` du même nombre de temps, propose d'étendre ce décalage.

    `written` : la grille d'avant la correction. Rend (début, fin, temps) pour la section ou le
    morceau, None pour « seulement ici ». Rien n'est proposé si une mesure tapée a été recomptée.
    """
    beats = detected_grid(p)[0]
    untouched = [t for t in beats if fix.bars[0] - 0.05 <= t <= fix.bars[-1] + 0.05]
    by = grid.bar_shift(fix.bars, beats, written[1], USUAL) if len(untouched) == len(fix.beats) else 0
    if not by:
        return None
    touched = [s for s in p.sections if s.start < fix.bars[-1] - 0.05 and s.end > fix.bars[0] + 0.05]
    names = ", ".join(s.name for s in touched)
    here = (
        f"à {'la section ' + names if len(touched) == 1 else 'ces sections (' + names + ')'} (s), " if touched else ""
    )
    typer.echo(f"le 1 est {by} temps plus tard qu'écrit, sur toutes vos mesures")
    answer = typer.prompt(
        f"  appliquer {here}à tout le morceau (m), ou seulement ici (Entrée) ?", default="", show_default=False
    )
    if answer.strip().lower() == "s" and touched:
        return touched[0].start, touched[-1].end, by
    return (0.0, float("inf"), by) if answer.strip().lower() == "m" else None
