"""L'écran commun à `play` et `record` : ce qui joue, les accords de la section en cours, la position."""

from __future__ import annotations

from typing import Optional

from arr import audio
from arr.project import Project

ORIGINS = {"align": "auto", "manual": "manuel"}
# Qualités de la notation de chord.lab (« D:min »), telles qu'un musicien les écrit.
QUALITIES = {
    "maj": "",
    "min": "m",
    "maj6": "6",
    "min6": "m6",
    "min7": "m7",
    "minmaj7": "m(maj7)",
    "min9": "m9",
    "hdim7": "m7b5",
}
PER_ROW = 4


def clock(seconds: float) -> str:
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def timeline(p: Project, name: Optional[str], sections: list[str], ranges: list) -> list[tuple]:
    """Les sections dans l'ordre où elles passent : (début, fin, nom, début dans le morceau).

    Début et fin sont en secondes de lecture ; le dernier champ situe la section dans le
    morceau, pour y retrouver ses accords quand les sections sont jouées dans le désordre.
    """
    if name in p.takes():
        return []
    if not sections:
        return [(s.start, s.end, s.name, s.start) for s in p.sections]
    marks, t = [], 0.0
    for section, (start, end) in zip(sections, ranges, strict=True):
        marks.append((t, t + end - start, section, start))
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


def chord_name(label: str) -> str:
    """« D:min » devient « Dm », « C:maj » devient « C » ; « N » (pas d'accord) devient un tiret."""
    if label == "N":
        return "–"
    root, _, quality = label.partition(":")
    quality, slash, bass = quality.partition("/")
    return root + QUALITIES.get(quality, quality) + slash + bass


def chord_page(chords: list[tuple], marks: list[tuple], t: float) -> tuple[Optional[str], list, Optional[int], tuple]:
    """Les accords à montrer à l'instant `t` de la lecture.

    Renvoie le nom de la section, ses accords, l'indice de celui qui sonne (None pendant le
    décompte) et la section suivante avec ses premiers accords. Hors de toute section, la
    page est une suite de huit accords autour de la position.
    """

    def within(start: float, end: float) -> list:
        # Par le milieu : une section redéfinie à la main ne tombe plus sur les bornes des accords.
        return [c for c in chords if start <= (c[0] + c[1]) / 2 < end]

    index = next((i for i, m in enumerate(marks) if m[0] <= t < m[1]), 0 if t < 0 and marks else None)
    if index is None:
        now = max(t, 0.0)
        at = max((i for i, c in enumerate(chords) if c[0] <= now), default=0)
        name, page, upcoming = None, chords[at - at % (2 * PER_ROW) :][: 2 * PER_ROW], ()
    else:
        start, end, name, origin = marks[index]
        now, page = origin + t - start, within(origin, origin + end - start)
        after = marks[index + 1] if index + 1 < len(marks) else None
        upcoming = (after[2], within(after[3], after[3] + after[1] - after[0])[:PER_ROW]) if after else ()
    current = max((i for i, c in enumerate(page) if c[0] <= now), default=0) if page and t >= 0 else None
    return name, page, current, upcoming


def chord_block(chords: list[tuple], marks: list[tuple], t: float) -> list:
    from rich.table import Table

    name, page, current, upcoming = chord_page(chords, marks, t)
    if not page:
        return []
    grid = Table.grid(padding=(0, 2))
    for start in range(0, len(page), PER_ROW):
        grid.add_row(
            *(
                f"[bold black on yellow] {chord_name(c[2])} [/]" if start + i == current else f" {chord_name(c[2])} "
                for i, c in enumerate(page[start : start + PER_ROW])
            )
        )
    lines = ["", f"[bold]Accords[/]{f' · {name}' if name else ''}", grid]
    if upcoming and upcoming[1]:
        lines.append(f"[dim]puis {upcoming[0]} : {'  '.join(chord_name(c[2]) for c in upcoming[1])}[/]")
    return lines


def view(
    p: Project,
    title: str,
    names: list[str],
    marks: list[tuple],
    length: float,
    hint: str,
    t: float,
    *,
    chords: list[tuple] = (),
    notes: list[str] = (),
    solo: bool = False,
    version: Optional[str] = None,
    recording: bool = False,
):
    """L'écran à l'instant `t` : ce qui joue, ce qui s'applique à la section en cours, et ses accords.

    `names` sont les pistes jouées ; `solo` dit qu'une piste est écoutée seule, sans son gain de mix.
    """
    from rich.console import Group
    from rich.progress_bar import ProgressBar
    from rich.table import Table

    from arr.commands.align import amount, beat_period

    period = beat_period(p)
    index = next((i for i, m in enumerate(marks) if m[0] <= t < m[1]), None)
    section = marks[index][2] if index is not None else None

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
        if gain and solo:
            level = f"[dim]{gain:+.1f} dB dans le mix, non appliqué[/]"
        applied = (
            f"[bold yellow]{amount(total, period)}[/]" if rules.keys() & {"track", section} else "[dim]telle quelle[/]"
        )
        table.add_row("[green]●[/]", track, version or p.tracks[track]["active"], level, whole, local, applied)

    if t < 0:
        where = "[yellow]décompte[/]"
    elif section:
        where = f"[bold cyan]{section}[/] [dim]({index + 1}/{len(marks)})[/]"
    else:
        where = "[dim]hors section[/]" if marks else "[bold cyan]morceau entier[/]"
    status = Table.grid(padding=(0, 2))
    after = f"[dim]puis {marks[index + 1][2]}[/]" if index is not None and index + 1 < len(marks) else ""
    status.add_row(
        f"{'[red]●[/]' if recording else '[green]▶[/]'} {where}",
        f"{clock(max(t, 0.0))} / {clock(length)}",
        ProgressBar(total=max(length, 1e-9), completed=max(t, 0.0), width=30),
        after,
    )
    # La consigne va avec le titre : sur la ligne d'état, elle la ferait déborder d'un terminal de 80 colonnes.
    head = f"[bold]{title}[/]  [dim]{hint}[/]"
    return Group(head, *([table] if names else []), *notes, *chord_block(list(chords), marks, t), "", status)


def mix_notes(p: Project, names: list[str], without: tuple, only: tuple) -> list[str]:
    """La ligne qui dit quelles pistes du projet ne sont pas dans le mix joué."""
    out = list(dict.fromkeys(left_out(p, k, without) for k in p.tracks if k not in names))
    if not out:
        return []
    return [f"[dim]○ hors du mix : {f'{len(p.tracks) - len(names)} autres pistes' if only else ', '.join(out)}[/]"]


def live(screen):
    """L'affichage en direct de `screen(secondes)` ; à mettre à jour depuis la boucle de lecture."""
    from rich.console import Console
    from rich.live import Live

    return Live(screen(0.0), console=Console(), refresh_per_second=8)
