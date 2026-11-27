"""review : écouter un par un les passages dont arr n'est pas sûr, dire lesquels sont bons, corriger leurs barres."""

from __future__ import annotations

from typing import Optional

import typer

from arr import audio, truth
from arr import review as layer
from arr.app import app
from arr.commands._common import (
    confirm,
    detected_grid,
    lead_in,
    reference,
    song_bars,
    song_doubts,
    song_fixes,
    song_passages,
)
from arr.commands._playback import playing
from arr.commands._screen import chord_block, clock, position, song_chart
from arr.project import Project, ProjectError

ANSWERS = {"enter": "right", "back": "back", "forward": "forward", "quit": "quit", "bars": "bars"}
KEYS = (
    "Entrée : c'est bon · m : les barres sont mal placées\n"
    "← → : autre passage · Espace : pause · q : quitter (reprise plus tard)"
)
KEPT = {"enter": "keep", "redo": "redo", "escape": "drop", "quit": "drop"}
USUAL = 4  # temps posés dans une mesure où le détecteur en a manqué un, ou entendu un deux fois


def section_of(p: Project, t: float) -> str:
    return next((s.name for s in p.sections if s.start - 0.05 <= t < s.end), "")


def label(p: Project, passage: layer.Passage) -> str:
    """Où est le passage, en quelques mots : la section de sa première mesure douteuse, et ses mesures."""
    name = section_of(p, min(passage.doubts, default=passage.start))
    return f"{name} · {passage.where}" if name else passage.where


def verified(found: list[layer.Passage]) -> str:
    done = sum(x.right for x in found)
    return f"vérifié : {done}/{len(found)} passage{'s' if len(found) > 1 else ''}"


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


def listen(
    p: Project, whole, chart: list[tuple], passage: layer.Passage, head: str, foot: str, count: bool = False
) -> str:
    """Joue le passage en boucle jusqu'à une réponse : « right », « bars », « back », « forward » ou « quit ».

    `count` : quatre clics au tempo du passage avant chaque tour de boucle.
    """
    body, lead = cut(whole, passage.start, passage.end), 0
    if not len(body):
        raise ProjectError(f"rien à jouer : {passage.where} est hors du morceau")
    length, name = len(body) / audio.SR, label(p, passage)
    if count:
        period = layer.local_period(detected_grid(p)[0], (passage.start + passage.end) / 2)
        body, lead = lead_in(body, clicks(period))
    bars, doubts = within(chart, passage.start, passage.end), {} if passage.right else passage.doubts
    marks = [(0.0, length, name, passage.start)]

    def lines(t: float, paused: bool) -> list:
        state = "[yellow]⏸ en pause ·[/]" if paused else "[yellow]décompte ·[/]" if t < 0 else "[green]▶[/]"
        judged = f" · [green]✔ {passage.state}[/]" if passage.right else ""
        where = f"{state} [bold cyan]{name}[/] · en boucle · {clock(max(t, 0.0))} / {clock(length)}{judged}"
        grid = chord_block(bars, marks, t, True, doubts) or ["", "[dim]pas d'accords (arr transcribe)[/]"]
        return [f"[bold]{head}[/]", "", where, *grid, "", f"[dim]{KEYS}[/]", foot]

    return looped(body, lines, ANSWERS, lead)


# --- corriger les barres


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


def replay(p: Project, whole, start: float, end: float, name: str, fix: layer.Fix, before: list[tuple]) -> str:
    """Rejoue le passage en boucle avec la nouvelle grille sous l'ancienne ; rend « keep », « redo » ou « drop »."""
    after = song_chart(p, (fix,))
    body = cut(whole, start, end)
    marks = [(0.0, len(body) / audio.SR, name, start)]
    old = chord_block(within(before, start, end), marks, -1.0)[2:3] or [beat_counts(song_bars(p), start, end)]

    def lines(t: float, paused: bool) -> list:
        new = chord_block(within(after, start, end), marks, t, True)[2:3]
        state = "[yellow]⏸ en pause ·[/]" if paused else "[green]▶[/]"
        return [
            f"[bold]Corriger les barres · {name}[/] · le passage rejoue avec la nouvelle grille",
            f"{state} en boucle · {clock(t)} / {clock(len(body) / audio.SR)}",
            "",
            "[dim]Avant[/]",
            *old,
            "[bold]Après[/]",
            *(new or [beat_counts(song_bars(p, (fix,)), start, end)]),
            "",
            "[dim]Entrée : garder · r : refaire · Échap : abandonner · Espace : pause[/]",
        ]

    return looped(body, lines, KEPT)


def fix_bars(p: Project, whole, chart: list[tuple], passage: layer.Passage) -> Optional[layer.Fix]:
    """Fait taper le 1 de chaque mesure du passage, montre la grille qui en sort, et rend la correction gardée ou None.

    Le passage joue jusqu'à une mesure après sa fin : le 1 qui ferme la dernière mesure s'y entend.
    Chaque frappe va au temps détecté le plus proche ; à plus d'un demi-temps de tout temps, elle est refusée.
    """
    beats, name = detected_grid(p)[0], label(p, passage)
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
            answer = replay(p, whole, passage.start, end, name, fix, chart)
            if answer != "redo":
                return fix if answer == "keep" else None
            continue
        if not confirm("Refaire ?"):
            return None


def section_range(p: Project, given: str) -> tuple[float, float]:
    """Le début et la fin des sections données (« intro,intro2 »), qui doivent se suivre dans le morceau."""
    found = [p.section(name.strip()) for name in given.split(",") if name.strip()]
    if not found:
        raise ProjectError("-s : donne une section, ou plusieurs qui se suivent (ex. -s intro,intro2)")
    if any(abs(b.start - a.end) > 0.05 for a, b in zip(found, found[1:], strict=False)):
        raise ProjectError(f"-s {given} : les sections doivent se suivre dans le morceau (ex. -s chorus2,outro)")
    return found[0].start, found[-1].end


def undo(p: Project, section: Optional[str]) -> None:
    taken = layer.undo_fix(p, *section_range(p, section)) if section else layer.undo_fix(p)
    if taken is None:
        raise ProjectError(f"aucune correction de barres à reprendre{f' dans {section}' if section else ''}")
    name = section_of(p, taken.bars[0])
    typer.echo(
        f"correction reprise : {name + ' · ' if name else ''}{stamp(taken.bars[0])} à {stamp(taken.bars[-1])}"
        f" ({len(taken.bars) - 1} mesures) ; elle reste lisible dans les versions précédentes de review/"
    )


@app.command()
def review(
    section: Optional[str] = typer.Option(
        None,
        "--section",
        "-s",
        help="Relit cette section, douteuse ou non, au lieu des passages douteux ; plusieurs qui se suivent : -s intro,intro2.",
    ),
    listing: bool = typer.Option(False, "--list", help="Liste les passages à relire et leur état, sans rien jouer."),
    back: bool = typer.Option(
        False, "--undo", help="Reprend la dernière correction de barres du morceau, ou de la section donnée par -s."
    ),
    count: bool = typer.Option(
        False,
        "--count-in",
        help="Quatre clics au tempo du passage avant chaque tour de boucle : pour s'entraîner à entrer.",
    ),
) -> None:
    """Fait écouter un par un les passages où `arr` n'est pas sûr du compte des mesures, pour les juger ou les corriger.

    Un passage, ce sont des mesures douteuses voisines (un de leurs temps a été entendu faiblement),
    avec une mesure avant et une après. Il joue en boucle, sur l'original, avec sa grille d'accords
    et la raison du doute. Entrée dit qu'il est bon et passe au suivant ; flèche gauche et flèche
    droite mènent à un autre passage sans répondre ; Espace met en pause ; q quitte.
    Avec --count-in, quatre clics au tempo du passage précèdent chaque tour de la boucle : les
    mêmes que ceux de m, pour se préparer à entrer sur le 1.

    m corrige les barres : après quatre clics au tempo, le passage joue une fois, et Espace se tape
    sur le 1 de chaque mesure, puis sur le 1 qui suit la dernière. Chaque frappe va au temps détecté
    le plus proche. Pendant les frappes, la grille du moment défile ; r recommence, Échap abandonne. Là où deux frappes ne tiennent pas quatre temps, `arr` demande si la mesure est
    vraiment plus courte ou plus longue, ou si un temps a été manqué ou entendu deux fois : il pose
    alors quatre temps égaux entre les deux frappes. Le passage rejoue avec la nouvelle grille sous
    l'ancienne : Entrée la garde, r refait les frappes, Échap abandonne.

    Une correction se voit partout où le morceau se lit : `arr play`, `arr chordpro`, `arr sheet`,
    le décompte, les numéros de mesure. Les accords restent à l'instant où ils sonnent. Rien ne
    bouge hors des mesures tapées. --undo reprend la dernière correction.

    Un passage jugé bon ou corrigé perd son « ? » dans `arr play`. Un jugement tient après un
    nouvel `arr analyze` tant que les mesures ne changent pas ; une correction tient toujours.
    La relecture reprend au premier passage qui reste ; quand il n'en reste aucun, le morceau est
    vérifié. Tout est rangé dans `review/` du morceau, une version par décision ; rien de ce
    qu'`arr` a détecté n'est modifié.
    """
    p = Project.find()
    if back:
        return undo(p, section)
    found, read = song_passages(p), song_bars(p)
    if not read:
        raise ProjectError("pas d'analyse (lance `arr analyze`)")
    if found is None and (listing or not section):
        raise ProjectError(
            "ce morceau ne garde pas encore ce que le détecteur entendait : lance arr analyze "
            "(sur un morceau déjà transcrit, arr analyze remplace la tonalité par son estimation)"
        )
    if listing:
        for x in found:
            why = list(x.doubts.values())
            more = f" ; {len(why) - 1} de plus" if len(why) > 1 else ""
            name = section_of(p, min(x.doubts))
            typer.echo(f"{clock(x.start):>5}  {x.where:<16} {name:<10} {why[0]}{more}  ·  {x.state}")
        typer.echo(verified(found) if found else "aucun passage douteux")
        return
    title = p.song.get("title") or p.root.name

    def chosen() -> list[layer.Passage]:
        """Le passage de la section demandée, sur la grille du moment."""
        (start, end), fixes = section_range(p, section), song_fixes(p, detected_grid(p)[0])
        bars = layer.measures(*song_bars(p))
        one = layer.between(bars, start, end, song_doubts(p) or {}, layer.right_bars(p), fixes)
        if one is None:
            raise ProjectError(f"aucune mesure ne commence dans {section}")
        one.start = min(one.start, start)  # dès le début de la section : ce qui précède sa première barre s'entend
        return [one]

    todo = chosen() if section else found
    at = 0 if section else next((i for i, x in enumerate(todo) if not x.right), None)
    if at is None:
        typer.echo(f"{title} · {verified(found) if found else 'aucun passage douteux'} · morceau vérifié")
        return
    whole, chart, fixed = audio.load(reference(p)), song_chart(p), 0
    while True:
        head = f"{title} · section {section}" if section else f"{title} · relecture {at + 1}/{len(todo)}"
        answer = listen(p, whole, chart, todo[at], head, "" if section else verified(todo), count)
        if answer == "bars":
            fix = fix_bars(p, whole, chart, todo[at])
            if fix is None:
                typer.echo(f"{label(p, todo[at])} : barres laissées telles quelles")
                continue
            saved = layer.save_fix(p, fix)
            typer.echo(f"✔ {label(p, todo[at])} : barres corrigées ({layer.FOLDER}/{saved.name})")
            # Les barres ont bougé : les passages et leurs numéros de mesure se relisent sur la nouvelle grille.
            start, chart, fixed = todo[at].start, song_chart(p), fixed + 1
            todo = chosen() if section else song_passages(p)
            at = min(range(len(todo)), key=lambda i: abs(todo[i].start - start), default=None)
            if at is None:
                break
        elif answer == "right":
            layer.judge_right(p, todo[at])
            todo[at].right = True
            typer.echo(f"✔ {label(p, todo[at])} : c'est bon")
        elif answer == "quit":
            break
        else:
            at = (at + (1 if answer == "forward" else -1)) % len(todo)
            continue
        left = [i for i in [*range(at + 1, len(todo)), *range(at + 1)] if not todo[i].right]
        if section or not left:
            break
        at = left[0]
    if fixed and (p.root / "export" / f"{p.root.name}.cho").exists():
        typer.echo("Le fichier du prompteur est plus ancien que vos corrections : arr chordpro")
    if section:
        return
    left = sum(not x.right for x in todo)
    rest = f"il reste {left} passage{'s' if left > 1 else ''} : arr review" if left else "morceau vérifié"
    typer.echo(f"{title} · {verified(todo)} · {rest}" if todo else f"{title} · aucun passage douteux · morceau vérifié")
