"""review : écouter un par un les passages dont arr n'est pas sûr, et dire lesquels sont bons."""

from __future__ import annotations

from typing import Optional

import typer

from arr import audio
from arr import review as layer
from arr.app import app
from arr.commands._common import reference, song_bars, song_doubts, song_passages
from arr.commands._playback import playing
from arr.commands._screen import chord_block, clock, position, song_chart
from arr.project import Project, ProjectError

ANSWERS = {"enter": "right", "back": "back", "forward": "forward", "quit": "quit"}
KEYS = "Entrée : c'est bon · ← → : autre passage · Espace : pause · q : quitter (reprise plus tard)"


def section_of(p: Project, t: float) -> str:
    return next((s.name for s in p.sections if s.start - 0.05 <= t < s.end), "")


def label(p: Project, passage: layer.Passage) -> str:
    """Où est le passage, en quelques mots : la section de sa première mesure douteuse, et ses mesures."""
    name = section_of(p, min(passage.doubts, default=passage.start))
    return f"{name} · {passage.where}" if name else passage.where


def verified(found: list[layer.Passage]) -> str:
    done = sum(x.right for x in found)
    return f"vérifié : {done}/{len(found)} passage{'s' if len(found) > 1 else ''}"


def listen(p: Project, whole, chart: list[tuple], passage: layer.Passage, head: str, foot: str) -> str:
    """Joue le passage en boucle jusqu'à une réponse : « right », « back », « forward » ou « quit »."""
    from rich.console import Group

    body = whole[int(round(passage.start * audio.SR)) : int(round(passage.end * audio.SR))]
    if not len(body):
        raise ProjectError(f"rien à jouer : {passage.where} est hors du morceau")
    length, name = len(body) / audio.SR, label(p, passage)
    bars = [m for m in chart if passage.start - 0.05 <= m[0] < passage.end - 0.05]
    doubts = {} if passage.right else passage.doubts
    marks = [(0.0, length, name, passage.start)]
    paused, answer = False, "quit"

    def screen(seconds: float):
        t = min(position(seconds, 0, len(body)), length - 1e-3)
        state = "[yellow]⏸ en pause ·[/]" if paused else "[green]▶[/]"
        judged = " · [green]✔ jugé bon[/]" if passage.right else ""
        where = f"{state} [bold cyan]{name}[/] · en boucle · {clock(t)} / {clock(length)}{judged}"
        grid = chord_block(bars, marks, t, True, doubts) or ["", "[dim]pas d'accords (arr transcribe)[/]"]
        return Group(f"[bold]{head}[/]", "", where, *grid, "", f"[dim]{KEYS}[/]", foot)

    def steer(keys: list[str], seconds: float):
        nonlocal paused, answer
        for key in keys:
            if key == "pause":
                paused = not paused
            elif key in ANSWERS:
                answer = ANSWERS[key]
                return paused, None, True
        return paused, None

    playing(body, body, screen, steer, transient=True)
    return answer


@app.command()
def review(
    section: Optional[str] = typer.Option(
        None, "--section", "-s", help="Relit cette section, douteuse ou non, au lieu des passages douteux."
    ),
    listing: bool = typer.Option(False, "--list", help="Liste les passages à relire et leur état, sans rien jouer."),
) -> None:
    """Fait écouter un par un les passages où `arr` n'est pas sûr du compte des mesures, pour dire lesquels sont bons.

    Un passage, ce sont des mesures douteuses voisines (un de leurs temps a été entendu faiblement),
    avec une mesure avant et une après. Il joue en boucle, sur l'original, avec sa grille d'accords
    et la raison du doute. Entrée dit qu'il est bon et passe au suivant ; flèche gauche et flèche
    droite mènent à un autre passage sans répondre ; Espace met en pause ; q quitte.

    Un passage jugé bon perd son « ? » dans `arr play`, et le garde perdu après un nouvel
    `arr analyze` tant que ses mesures ne changent pas. La relecture reprend au premier passage
    qui reste ; quand il n'en reste aucun, le morceau est vérifié. Les réponses sont rangées dans
    `review/` du morceau, une version par réponse ; rien de ce qu'`arr` a détecté n'est modifié.
    """
    p = Project.find()
    found, read = song_passages(p), song_bars(p)
    if not read:
        raise ProjectError("pas d'analyse (lance `arr analyze`)")
    if found is None:
        raise ProjectError(
            "ce morceau ne garde pas encore ce que le détecteur entendait : lance arr analyze "
            "(sur un morceau déjà transcrit, arr analyze remplace la tonalité par son estimation)"
        )
    if listing:
        for x in found:
            why = list(x.doubts.values())
            more = f" ; {len(why) - 1} de plus" if len(why) > 1 else ""
            state = "jugé bon" if x.right else "à relire"
            name = section_of(p, min(x.doubts))
            typer.echo(f"{clock(x.start):>5}  {x.where:<16} {name:<10} {why[0]}{more}  ·  {state}")
        typer.echo(verified(found) if found else "aucun passage douteux")
        return
    title = p.song.get("title") or p.root.name
    if section:
        s = p.section(section)
        bars, right = layer.measures(*read), layer.right_bars(p)
        one = layer.between(bars, s.start, s.end, song_doubts(p) or {}, right)
        if one is None:
            raise ProjectError(f"aucune mesure ne commence dans {section}")
        todo, at = [one], 0
    else:
        todo, at = found, next((i for i, x in enumerate(found) if not x.right), None)
        if at is None:
            typer.echo(f"{title} · {verified(found) if found else 'aucun passage douteux'} · morceau vérifié")
            return
    whole, chart = audio.load(reference(p)), song_chart(p)
    while True:
        head = f"{title} · section {section}" if section else f"{title} · relecture {at + 1}/{len(todo)}"
        answer = listen(p, whole, chart, todo[at], head, "" if section else verified(todo))
        if answer == "right":
            layer.judge_right(p, todo[at])
            todo[at].right = True
            typer.echo(f"✔ {label(p, todo[at])} : c'est bon")
            left = [i for i in [*range(at + 1, len(todo)), *range(at)] if not todo[i].right]
            if section or not left:
                break
            at = left[0]
        elif answer == "quit":
            break
        else:
            at = (at + (1 if answer == "forward" else -1)) % len(todo)
    if section:
        return
    left = sum(not x.right for x in todo)
    rest = f"il reste {left} passage{'s' if left > 1 else ''} : arr review" if left else "morceau vérifié"
    typer.echo(f"{title} · {verified(todo)} · {rest}")
