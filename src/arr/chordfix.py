"""Les accords corrigés par le musicien : le texte qu'il édite, sa lecture, et leur pose sur la transcription.

Une correction (`ChordFix`) porte les accords d'un passage, chacun à son instant : elle ne dépend
pas des barres, qui peuvent être corrigées avant ou après. Le musicien l'écrit dans un texte d'une
ligne par mesure, une case par temps (`chord_text`, `read_chord_text`) ; `lay_chords` la pose sur
les accords de la transcription, là où la grille se lit. Rangement : `review.save_chord_fix`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from arr.sheet import NOTE, chord_name

NO_CHORD = "N.C."
CHORD = re.compile(rf"{NOTE}(maj|min|dim|aug|sus|add|m|M|°|\+|b|#|\d|\(|\))*(/({NOTE}|[b#]?\d+))?")


@dataclass
class ChordFix:
    """Les accords que le musicien entend de `start` à `end` : (début, fin, nom), le nom tel qu'il l'a écrit (« N » : aucun)."""

    start: float
    end: float
    chords: list[tuple[float, float, str]]
    fixed: str = ""

    def covers(self, t: float) -> bool:
        return self.start - 0.05 <= t < self.end - 0.05


def chord_text(title: str, first: int, bars: list[tuple]) -> str:
    """Le texte à corriger : une ligne par mesure de la grille (`bars`, comme `chart` les rend), une case par temps."""
    width = 1 + max([4, *(len(chord_name(c[2])) for bar in bars for c in bar[3])])
    lines = [
        f"# {title} · une case par temps · « / » : l'accord continue · « {NO_CHORD} » : pas d'accord",
        "# Enregistrez et fermez pour revenir à la relecture ; sans changement, rien n'est corrigé.",
        "",
    ]
    for number, bar in enumerate(bars, start=first):
        slots = ["/"] * bar[2]
        for slot, _, name, _, _ in bar[3]:
            slots[slot] = NO_CHORD if name == "N" else chord_name(name)
        lines.append(f"{number:>3} │ " + "".join(slot.ljust(width) for slot in slots).rstrip())
    return "\n".join(lines) + "\n"


def read_chord_text(
    text: str, first: int, bars: list[tuple], beats: list[list[float]]
) -> tuple[list[tuple], list[str]]:
    """Les accords écrits dans `text`, à leur instant, et ce qui ne se lit pas (« ligne 5 : … »).

    `bars` sont les mesures montrées et `beats` les temps de chacune ; le dernier accord va
    jusqu'à la fin de la dernière mesure. Un nom qu'`arr` montrait garde son étiquette d'origine.
    """
    known = {chord_name(c[2]): c[2] for bar in bars for c in bar[3]} | {NO_CHORD: "N", "–": "N"}
    found: list[tuple[float, float, str]] = []
    errors, seen = [], set()
    for n, line in enumerate(text.splitlines(), start=1):
        number, bar, slots = line.replace("|", "│").partition("│")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not bar or not number.strip().isdigit() or not first <= int(number) < first + len(bars):
            errors.append(f"ligne {n} : attendu « numéro de mesure │ accords », de {first} à {first + len(bars) - 1}")
            continue
        i, slots = int(number) - first, slots.split()
        if i in seen or len(slots) != bars[i][2]:
            why = "écrite deux fois" if i in seen else f"{len(slots)} cases pour {bars[i][2]} temps"
            errors.append(f"ligne {n} : mesure {int(number)}, {why}")
            continue
        seen.add(i)
        ends = [*beats[i][1:], bars[i][1]]
        for slot, start, end in zip(slots, beats[i], ends, strict=True):
            if slot == "/" and found and abs(found[-1][1] - start) < 0.01:
                found[-1] = (found[-1][0], end, found[-1][2])
            elif slot == "/":
                errors.append(f"ligne {n} : « / » sans accord avant lui")
                found.append((start, end, "N"))  # une remarque par ligne, pas une par case
            elif slot not in known and not CHORD.fullmatch(slot):
                errors.append(f"ligne {n} : « {slot} » n'est pas un nom d'accord")
                found.append((start, end, slot))  # les « / » qui suivent ne sont pas des fautes de plus
            elif found and found[-1][2] == known.get(slot, slot) and abs(found[-1][1] - start) < 0.01:
                found[-1] = (found[-1][0], end, found[-1][2])
            else:
                found.append((start, end, known.get(slot, slot)))
    if not errors and len(seen) < len(bars):
        errors.append(f"il manque des mesures : {len(seen)} lignes pour {len(bars)} mesures")
    return found, errors


def lay_chords(chords: list[tuple], fixes: list[ChordFix]) -> list[tuple]:
    """Les accords de la transcription, ceux du musicien posés par-dessus dans leurs passages."""
    for fix in fixes:
        kept = []
        for start, end, name in chords:
            kept += [(start, min(end, fix.start), name)] if start < fix.start else []
            kept += [(max(start, fix.end), end, name)] if end > fix.end else []
        chords = sorted([*kept, *fix.chords])
    return chords
