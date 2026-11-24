"""Structure d'un morceau tel qu'il se joue : une suite de passages nommés, chacun avec ses mesures."""

from __future__ import annotations

from dataclasses import dataclass

from arr.project import Section
from arr.sheet import KINDS, kind


@dataclass
class Passage:
    """Un passage joué : son nom, ses mesures (celles de `_screen.chart`), la section d'où il vient, un rappel."""

    name: str
    bars: list[tuple]
    section: str = ""
    cue: str = ""


def default(sections: list[Section], chart: list[tuple]) -> list[Passage]:
    """La structure de l'original : un passage par section qui porte au moins une mesure.

    Les mesures d'une section sont celles dont le milieu tombe dedans. Les noms sont ceux
    d'un musicien : les couplets numérotés dans l'ordre joué (« Couplet 1 », « Couplet 2 »),
    les autres passages d'un même type sous un seul nom, pour qu'un prompteur relie un son
    à tous les refrains. Les sections voisines de même type restent séparées.
    """
    out, verses = [], 0
    for s in sections:
        bars = [b for b in chart if s.start <= (b[0] + b[1]) / 2 < s.end]
        if not bars:
            continue
        name = kind(s.name)
        if name == "verse":
            verses += 1
            label = f"{KINDS[name][0]} {verses}"
        else:
            label = KINDS.get(name, (name.capitalize(),))[0]
        out.append(Passage(label, bars, s.name))
    return out
