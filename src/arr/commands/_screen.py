"""L'écran commun à `play` et `record` : ce qui joue, la grille d'accords de la section en cours, la position."""

from __future__ import annotations

from typing import Optional

from arr import audio
from arr.project import Project
from arr.sheet import chord_name

ORIGINS = {"align": "auto", "manual": "manuel"}
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


def chart(chords: list[tuple], beats: list[tuple]) -> list[tuple]:
    """La grille d'accords : une mesure par élément, comme sur une grille de jazz.

    Chaque mesure est (début, fin, nombre de temps, accords), et chaque accord
    (temps où il commence, durée en temps, étiquette, début, fin). Un accord tenu au-delà de
    la barre est réécrit au début de la mesure suivante. Sans grille de temps, chaque accord
    fait une mesure d'un temps.
    """
    if not beats:
        return [(start, end, 1, [(0, 1, label, start, end)]) for start, end, label in chords]
    last = max([beats[-1][0] + (beats[-1][0] - beats[-2][0] if len(beats) > 1 else 1.0)] + [c[1] for c in chords[-1:]])
    ends = [t for t, _ in beats[1:]] + [last]
    bars: list[list] = []
    for (t, number), end in zip(beats, ends, strict=True):
        if number == 1 or not bars:
            bars.append([t, end, 0, []])
        bar = bars[-1]
        # L'accord du temps est celui qui sonne en son milieu : les accords viennent d'une autre
        # analyse que les temps, et commencent quelques centièmes avant ou après eux.
        label = next((c[2] for c in chords if c[0] <= (t + end) / 2 < c[1]), "N")
        if bar[3] and bar[3][-1][2] == label:
            slot, held, _, start, _ = bar[3][-1]
            bar[3][-1] = (slot, held + 1, label, start, end)
        else:
            bar[3].append((bar[2], 1, label, t, end))
        bar[1], bar[2] = end, bar[2] + 1
    return [tuple(bar) for bar in bars]


def song_chart(p: Project) -> list[tuple]:
    """La grille d'accords du morceau, sur ses mesures de référence (`arr analyze`) ; vide sans transcription.

    Les barres sont posées tous les N temps (`grid.regular_bars`) : beat_this hésite parfois
    entre des mesures de quatre et de deux temps. Les accords viennent de la transcription, qui
    compte parfois les mesures autrement (une mesure à deux temps non vue) : `measure.seat_chords`
    les replace. Les temps entendus deux fois sont retirés d'abord, les temps manqués comblés (`song_grid`).
    Sans `analysis.json`, la grille suit les temps de la transcription.
    """
    from arr import grid, measure
    from arr.app import ORIGINAL, SCORE
    from arr.commands._common import song_grid
    from arr.engines import transcription

    score = (p.root / SCORE).parent
    chords, own = transcription.chords(score), transcription.beats(score)
    original, found = p.root / ORIGINAL, song_grid(p)
    if not chords or not found:
        return chart(chords, own)
    raw, detected = found
    downbeats = grid.regular_bars(detected, raw)
    if original.exists():
        own_bars = [t for t, number in own if number == 1]
        chords = measure.seat_chords(chords, own_bars, downbeats, raw, lambda: audio.load(original))
    beats, strong = [], iter(sorted(downbeats) + [float("inf")])
    bar = next(strong)
    for t in raw:
        if t >= bar - 0.05:
            beats.append((t, 1))
            bar = next(strong)
        else:
            beats.append((t, beats[-1][1] + 1 if beats else 1))
    return chart(chords, beats)


def chord_page(
    bars: list[tuple], marks: list[tuple], t: float, loop: bool = False
) -> tuple[Optional[str], list, Optional[tuple], tuple]:
    """Les mesures à montrer à l'instant `t` de la lecture.

    Renvoie le nom de la section, ses mesures, la place de l'accord qui sonne (mesure, rang
    dans la mesure ; None pendant le décompte) et la section suivante avec sa première
    rangée de mesures (en boucle, après la dernière section vient la première). Hors de
    toute section, la page est une suite de huit mesures autour de la position.
    """

    def within(start: float, end: float) -> list:
        # Par le milieu : une section redéfinie à la main ne tombe plus sur les barres de mesure.
        # Une section plus courte qu'une mesure garde celle qu'elle traverse.
        inside = [b for b in bars if start <= (b[0] + b[1]) / 2 < end]
        return inside or [b for b in bars if b[0] < end and b[1] > start]

    index = next((i for i, m in enumerate(marks) if m[0] <= t < m[1]), 0 if t < 0 and marks else None)
    if index is None:
        now = max(t, 0.0)
        at = max((i for i, b in enumerate(bars) if b[0] <= now), default=0)
        name, page, upcoming = None, bars[at - at % (2 * PER_ROW) :][: 2 * PER_ROW], ()
    else:
        start, end, name, origin = marks[index]
        now, page = origin + t - start, within(origin, origin + end - start)
        after = marks[index + 1] if index + 1 < len(marks) else marks[0] if loop and len(marks) > 1 else None
        upcoming = (after[2], within(after[3], after[3] + after[1] - after[0])[:PER_ROW]) if after else ()
    started = [(i, j) for i, b in enumerate(page) for j, chord in enumerate(b[3]) if chord[3] <= now]
    current = (started[-1] if started else (0, 0)) if page and t >= 0 else None
    return name, page, current, upcoming


def chord_block(bars: list[tuple], marks: list[tuple], t: float, loop: bool = False) -> list:
    """La grille de la section : une case par mesure, un accord écrit sur son temps, « / » par temps tenu."""
    import shutil

    from rich.table import Table
    from rich.text import Text

    name, page, current, upcoming = chord_page(bars, marks, t, loop)
    if not page:
        return []
    ahead = upcoming[1] if upcoming else []
    # Une colonne par temps, assez large pour le plus long nom : les temps tombent les uns sous les autres.
    slot = max(4, 1 + max(len(chord_name(chord[2])) for b in page + ahead for chord in b[3]))
    fit = (shutil.get_terminal_size((80, 24)).columns - 1) // (slot * max(b[2] for b in page + ahead) + 2)
    per_row = PER_ROW if fit >= PER_ROW else 2 if fit >= 2 else 1

    def rows(shown: list, lit: Optional[tuple], style: str = "") -> Table:
        grid = Table.grid()
        for row in range(0, len(shown), per_row):
            cells = []
            for i, bar in enumerate(shown[row : row + per_row], start=row):
                cell = Text("│ ", style=style)
                for j, (_, held, label, _, _) in enumerate(bar[3]):
                    text = chord_name(label).ljust(slot) + "/".ljust(slot) * (held - 1)
                    # Vidéo inverse : les couleurs du terminal lui-même, donc toujours lisibles.
                    cell.append(text, style="bold reverse" if (i, j) == lit else style)
                cells.append(cell)
            grid.add_row(*cells, Text("│", style=style))
        return grid

    lines = ["", f"[bold]Accords[/]{f' · {name}' if name else ''}", rows(page, current)]
    if ahead:
        # La première rangée de la section suivante reste sous les yeux : l'enchaînement se lit d'avance.
        lines += [f"[dim]── puis {upcoming[0]} ──[/]", rows(ahead[:per_row], None, "dim")]
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
    bars: list[tuple] = (),
    notes: list[str] = (),
    solo: bool = False,
    version: Optional[str] = None,
    recording: bool = False,
    loop: bool = False,
    paused: bool = False,
):
    """L'écran à l'instant `t` : ce qui joue, ce qui s'applique à la section en cours, et ses accords.

    `names` sont les pistes jouées ; `solo` dit qu'une piste est écoutée seule, sans son gain de mix.
    """
    from rich.console import Group
    from rich.progress_bar import ProgressBar
    from rich.table import Table

    from arr.commands.align import amount, beat_period

    t = min(t, length - 1e-3)  # la dernière image reste dans la dernière section jouée
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
        f"{'[red]●[/]' if recording else '[yellow]⏸ en pause ·[/]' if paused else '[green]▶[/]'} {where}",
        f"{clock(max(t, 0.0))} / {clock(length)}",
        ProgressBar(total=max(length, 1e-9), completed=max(t, 0.0), width=30),
        after,
    )
    # La consigne va avec le titre : sur la ligne d'état, elle la ferait déborder d'un terminal de 80 colonnes.
    head = f"[bold]{title}[/]  [dim]{hint}[/]"
    return Group(head, *([table] if names else []), *notes, *chord_block(list(bars), marks, t, loop), "", status)


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

    return Live(screen(0.0), console=Console(), refresh_per_second=20)
