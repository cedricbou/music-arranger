"""Fichier ChordPro d'un morceau : une grille d'accords standard par passage, les paroles en repère.

Le format suit ChordPro 6 sans directive propre à un lecteur : `{start_of_grid}` par passage,
quatre mesures par ligne, une case par temps, les paroles chantées sur ces mesures après la
dernière barre. Une mesure d'une autre longueur a sa propre grille, entre deux `{time}`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from arr.sheet import chord_name, transpose
from arr.structure import Passage

PER_LINE = 4
NO_CHORD = "N.C."  # le « pas d'accord » que reconnaît ChordPro


@dataclass
class Grid:
    """Une grille : son nombre de temps par mesure, et ses lignes (mesures écrites, paroles en repère)."""

    beats: int
    lines: list[tuple[list[str], str]]


@dataclass
class Block:
    """Un passage mis en grilles, avec ce qu'en dit le compte rendu."""

    name: str
    cue: str
    grids: list[Grid]
    bars: int
    sung: int  # lignes de paroles placées en repère
    chords: bool  # au moins un accord
    odd: list[tuple[float, int]] = field(default_factory=list)  # mesures d'une autre longueur : (début, temps)


def meter(passages: list[Passage]) -> int:
    """Le nombre de temps par mesure du morceau : le plus fréquent."""
    sizes = Counter(b[2] for p in passages for b in p.bars)
    return sizes.most_common(1)[0][0] if sizes else 4


def bar_text(bar: tuple, key: str, shift: int) -> str:
    """« Em . . . » : une case par temps, l'accord où il commence, un point tant qu'il tient."""
    at = {chord[0]: chord[2] for chord in bar[3]}

    def name(label: str) -> str:
        return NO_CHORD if label == "N" else transpose(chord_name(label), shift, key)

    return " ".join(name(at[i]) if i in at else "." for i in range(bar[2]))


def edges(passages: list[Passage], key: str, shift: int) -> list[Passage]:
    """Les passages sans la levée, et avec une dernière mesure entière.

    ChordPro n'a pas de levée ; une grille d'une mesure courte serait comptée comme une
    mesure sur le prompteur. Les temps avant la première barre deviennent un rappel du premier
    passage, qui dit leur nombre et leurs accords s'il y en a ; un passage qui n'était que la
    levée disparaît. La dernière mesure, coupée par la fin de l'enregistrement, est complétée :
    le groupe tient le dernier accord.
    """
    usual = meter(passages)
    out = [Passage(p.name, list(p.bars), p.section, p.cue) for p in passages if p.bars]
    if out and out[-1].bars[-1][2] < usual:
        start, end, _, chords = out[-1].bars[-1]
        out[-1].bars[-1] = (start, end, usual, chords)
    if not out or out[0].bars[0][2] >= usual or sum(len(p.bars) for p in out) < 2:
        return out
    played = bar_text(out[0].bars.pop(0), key, shift)
    beats = len(played.split())
    cue = f"levée de {beats} temps" + ("" if set(played.split()) <= {NO_CHORD, "."} else f" : {played}")
    out = [p for p in out if p.bars]
    out[0].cue = " · ".join(filter(None, [cue, out[0].cue]))
    return out


def rows(bars: list[tuple]) -> list[tuple[int, list[tuple]]]:
    """Les lignes de mesures d'un passage : (temps par mesure, mesures), quatre au plus.

    Une mesure d'une autre longueur que ses voisines commence une ligne à elle.
    """
    runs: list[list[tuple]] = []
    for bar in bars:
        if runs and runs[-1][-1][2] == bar[2]:
            runs[-1].append(bar)
        else:
            runs.append([bar])
    return [(run[0][2], run[i : i + PER_LINE]) for run in runs for i in range(0, len(run), PER_LINE)]


def landmarks(lines: list[tuple[str, float | None]], spans: list[tuple[float, float]]) -> list[list[str]]:
    """Les paroles de chaque ligne de mesures, d'après l'instant où chaque ligne est chantée.

    Une ligne chantée hors du passage va sur sa première ou sa dernière ligne de mesures ; une
    ligne sans instant suit celle d'avant. Si aucune n'a d'instant, elles sont réparties à
    parts égales, dans l'ordre.
    """
    out: list[list[str]] = [[] for _ in spans]
    if not spans or not lines:
        return out
    if all(t is None for _, t in lines):
        where: list[int | None] = [j * len(spans) // len(lines) for j in range(len(lines))]
    else:
        where = [None if t is None else _row(t, spans) for _, t in lines]
        first = next(i for i in where if i is not None)
        for j, i in enumerate(where):
            where[j] = (where[j - 1] if j else first) if i is None else i
    for (text, _), i in zip(lines, where, strict=True):
        out[i].append(text.replace("|", "/").strip())
    return out


def _row(t: float, spans: list[tuple[float, float]]) -> int:
    inside = next((i for i, (a, b) in enumerate(spans) if a <= t < b), None)
    return inside if inside is not None else 0 if t < spans[0][0] else len(spans) - 1


def layout(passages: list[Passage], lyrics: dict[str, list], key: str, shift: int) -> list[Block]:
    """Les passages mis en grilles, transposés de `shift` demi-tons vers `key`.

    `lyrics` donne, pour une section, ses lignes de paroles : (texte, instant chanté ou None).
    """
    blocks, usual = [], meter(passages)
    for p in passages:
        lines = rows(p.bars)
        sung = landmarks(lyrics.get(p.section, []), [(r[0][0], r[-1][1]) for _, r in lines])
        grids: list[Grid] = []
        for (beats, bars), words in zip(lines, sung, strict=True):
            written = ([bar_text(b, key, shift) for b in bars], " / ".join(words))
            if grids and grids[-1].beats == beats:
                grids[-1].lines.append(written)
            else:
                grids.append(Grid(beats, [written]))
        chords = any(c[2] != "N" for b in p.bars for c in b[3])
        odd = [(b[0], b[2]) for b in p.bars if b[2] != usual]
        blocks.append(Block(p.name, p.cue, grids, len(p.bars), sum(len(w) for w in sung), chords, odd))
    return blocks


def duration(passages: list[Passage]) -> str:
    seconds = round(sum(b[1] - b[0] for p in passages for b in p.bars))
    return f"{seconds // 60}:{seconds % 60:02d}"


def write(head: dict, blocks: list[Block], usual: int) -> str:
    """Le texte du fichier. `head` : project, title, artist, key, tempo, duration (vides omis)."""
    out = [f"# written by arr — {head['project']}"]
    for directive in ("title", "artist", "key", "tempo"):
        if head.get(directive):
            out.append(f"{{{directive}: {head[directive]}}}")
    out += [f"{{time: {usual}/4}}", f"{{duration: {head['duration']}}}"]
    for block in blocks:
        out.append("")
        label = block.name.replace('"', "'")
        for i, grid in enumerate(block.grids):
            odd = grid.beats != usual
            if odd:
                out.append(f"{{time: {grid.beats}/4}}")
            if i == 0 and block.cue:
                out.append(f"{{comment: {block.cue}}}")
            widest = max(len(bars) for bars, _ in grid.lines)
            out.append(f'{{start_of_grid label="{label}" shape="{widest}x{grid.beats}"}}')
            for bars, words in grid.lines:
                out.append("| " + " | ".join(bars) + " |" + (f" {words}" if words else ""))
            out.append("{end_of_grid}")
            if odd:
                out.append(f"{{time: {usual}/4}}")
    return "\n".join(out) + "\n"
