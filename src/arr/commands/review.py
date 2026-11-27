"""review : écouter un par un les passages dont arr n'est pas sûr, dire lesquels sont bons, corriger leurs barres."""

from __future__ import annotations

from typing import Optional

import typer

from arr import audio
from arr import review as layer
from arr.app import app
from arr.commands._common import (
    detected_grid,
    lead_in,
    reference,
    song_bars,
    song_doubts,
    song_fixes,
    song_passages,
    tempo_question,
)
from arr.commands._fixes import ask_shift, ask_tempo, clicks, cut, fix_bars, fix_chords, looped, stamp, within
from arr.commands._screen import chord_block, clock, song_chart
from arr.project import Project, ProjectError

ANSWERS = {"enter": "right", "back": "back", "forward": "forward", "quit": "quit", "bars": "bars", "chords": "chords"}
KEYS = (
    "Entrée : c'est bon · m : les barres sont mal placées · a : un accord est faux\n"
    "← → : autre passage · Espace : pause · q : quitter (reprise plus tard)"
)


def section_of(p: Project, t: float) -> str:
    return next((s.name for s in p.sections if s.start - 0.05 <= t < s.end), "")


def label(p: Project, passage: layer.Passage) -> str:
    """Où est le passage, en quelques mots : la section de sa première mesure douteuse, et ses mesures."""
    name = section_of(p, min(passage.doubts, default=passage.start))
    return f"{name} · {passage.where}" if name else passage.where


def verified(found: list[layer.Passage]) -> str:
    done = sum(x.right for x in found)
    return f"vérifié : {done}/{len(found)} passage{'s' if len(found) > 1 else ''}"


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
        raise ProjectError(f"aucune correction à reprendre{f' dans {section}' if section else ''}")
    kind, start, end = taken
    name = section_of(p, start)
    where = "tout le morceau" if end == float("inf") else f"{name + ' · ' if name else ''}{stamp(start)} à {stamp(end)}"
    typer.echo(
        f"correction {layer.KINDS[kind]} reprise : {where} ; elle reste lisible dans les versions précédentes de review/"
    )


def tempo_first(p: Project, whole, title: str) -> bool:
    """Pose la question des deux tempos si elle se pose, et recompte le morceau selon la réponse ; False si le musicien quitte."""
    split = tempo_question(p)
    if not split:
        return True
    keep, ranges = ask_tempo(p, whole, split, title)
    if keep == "quit":
        return False
    count = lambda: sum(
        any(a - 0.05 <= bar[0] < b - 0.05 for a, b, _ in ranges) for bar in layer.measures(*song_bars(p))
    )
    before = count()
    layer.save_tempo(p, keep, split["period"], ranges)
    if keep == "asis":
        typer.echo("tempo laissé tel quel ; la question ne sera plus posée (arr review --undo pour y revenir)")
        return True
    bpm, names = round((30 if keep == "slow" else 60) / split["period"]), split["fast" if keep == "slow" else "slow"]
    typer.echo(f"✔ {bpm} partout : {', '.join(names)} recompté{'s' if len(names) > 1 else ''}")
    typer.echo(f"  {before} mesures deviennent {count()} · les accords restent à leur instant")
    written = float(p.song.get("bpm") or 0)
    if written and abs(written / bpm - 1) > 0.25:
        typer.echo(
            f"  song.toml dit bpm = {written:g} : prompteur et antisèche l'affichent encore ; écrivez-y {bpm} si c'est votre compte"
        )
    return True


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
        False,
        "--undo",
        help="Reprend la dernière correction (tempo, barres, décalage ou accords) du morceau, ou de la section donnée par -s.",
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

    a corrige les accords : le passage s'ouvre dans l'éditeur ($VISUAL ou $EDITOR), une ligne par
    mesure, une case par temps, rempli de ce qu'`arr` montre ; « / » tient l'accord, « N.C. » dit
    qu'il n'y en a pas. À la fermeture, le passage rejoue avec les nouveaux accords sous les anciens :
    Entrée garde, r rouvre l'éditeur, Échap abandonne. Une ligne illisible (nom d'accord inconnu,
    cinq cases pour quatre temps) est dite avec son numéro, et l'éditeur se rouvre sur le texte.
    Barres et accords faux : m d'abord, puis a sur les barres corrigées.

    Une correction se voit partout où le morceau se lit : `arr play`, `arr chordpro`, `arr sheet`,
    le décompte, les numéros de mesure. Les accords restent à l'instant où ils sonnent. Rien ne
    bouge hors des mesures tapées. --undo reprend la dernière correction, de barres ou d'accords.

    Quand le morceau est compté à deux tempos, l'un double de l'autre, la relecture commence par
    une question : une section joue en boucle avec un clic sur chaque temps, 1 et 2 passent d'un
    tempo à l'autre, Entrée garde celui qui s'entend pour tout le morceau (les sections comptées
    à l'autre sont recomptées), s laisse tel quel. Après des barres tapées, si le 1 était décalé
    du même nombre de temps sur toutes les mesures, `arr` propose d'appliquer ce décalage à la
    section ou à tout le morceau. Rien n'est appliqué sans réponse, et --undo le reprend.

    Un passage jugé bon ou corrigé perd son « ? » dans `arr play`. Un jugement tient après un
    nouvel `arr analyze` tant que les mesures ne changent pas ; une correction tient toujours.
    La relecture reprend au premier passage qui reste ; quand il n'en reste aucun, le morceau est
    vérifié. Tout est rangé dans `review/` du morceau, une version par décision ; rien de ce
    qu'`arr` a détecté n'est modifié.
    """
    p = Project.find()
    if back:
        return undo(p, section)
    if not song_bars(p):
        raise ProjectError("pas d'analyse (lance `arr analyze`)")
    title = p.song.get("title") or p.root.name
    if listing and tempo_question(p):
        typer.echo("? arr ne compte pas partout au même tempo : arr review pose la question avant la relecture")
    whole = None if listing else audio.load(reference(p))
    if not listing and not tempo_first(p, whole, title):
        return
    found = song_passages(p)
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
    chart, fixed = song_chart(p), 0
    while True:
        head = f"{title} · section {section}" if section else f"{title} · relecture {at + 1}/{len(todo)}"
        answer = listen(p, whole, chart, todo[at], head, "" if section else verified(todo), count)
        if answer in ("bars", "chords"):
            name, bars = label(p, todo[at]), answer == "bars"
            fix = (fix_bars if bars else fix_chords)(p, whole, chart, todo[at], name)
            if fix is None:
                typer.echo(f"{name} : {'barres laissées telles quelles' if bars else 'accords laissés tels quels'}")
                continue
            written = song_bars(p)
            saved = layer.save_fix(p, fix) if bars else layer.save_chord_fix(p, fix)
            typer.echo(f"✔ {name} : {'barres corrigées' if bars else 'accords corrigés'} ({layer.FOLDER}/{saved.name})")
            if bars and (wide := ask_shift(p, fix, written)):
                layer.save_shift(p, *wide)
                where = "tout le morceau" if wide[1] == float("inf") else f"{stamp(wide[0])} à {stamp(wide[1])}"
                typer.echo(f"✔ le 1 décalé de {wide[2]} temps : {where}")
            # La grille a changé : les passages et leurs numéros de mesure se relisent, et le passage rejoue.
            start, chart, fixed = todo[at].start, song_chart(p), fixed + 1
            todo = chosen() if section else song_passages(p)
            at = min(range(len(todo)), key=lambda i: abs(todo[i].start - start), default=None)
            if at is None:
                break
            continue
        elif answer == "right":
            if not todo[at].right:  # un passage déjà corrigé n'a pas besoin d'un jugement de plus
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
