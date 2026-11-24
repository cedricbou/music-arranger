"""Paroles : téléchargement depuis LRCLIB et rangement dans les sections du morceau."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from arr.project import ProjectError, Section

API = "https://lrclib.net/api/search"
STAMP = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)$")


def fetch(artist: str, title: str) -> dict:
    """Meilleure correspondance LRCLIB : {'plainLyrics': ..., 'syncedLyrics': ... ou None, ...}."""
    query = urllib.parse.urlencode({"artist_name": artist, "track_name": title})
    request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": "arr (music-arranger)"})
    with urllib.request.urlopen(request, timeout=20) as response:
        results = json.load(response)
    results = [r for r in results if r.get("plainLyrics")]
    if not results:
        raise ProjectError(f"aucune parole trouvée pour {artist} - {title}")
    return next((r for r in results if r.get("syncedLyrics")), results[0])


def blocks(text: str) -> list[list[str]]:
    """Les lignes de chaque balise ([Verse], [Chorus]...) de lyrics.txt, dans l'ordre ; vide sans balise."""
    out: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if re.fullmatch(r"\[[^\]]*\]", line):
            out.append([])
        elif line and out:
            out[-1].append(line)
    return out


def timed(synced: str, first_sung: float | None = None) -> list[tuple[float, str]]:
    """Les lignes horodatées (`[mm:ss.xx] texte`) : (instant dans l'enregistrement, texte).

    `first_sung` est l'instant de la première note chantée dans l'enregistrement : il recale
    les horodatages, qui viennent d'une autre édition du morceau.
    """
    lines = []
    for raw in synced.splitlines():
        m = STAMP.match(raw.strip())
        if m and m.group(3):
            lines.append((int(m.group(1)) * 60 + float(m.group(2)), m.group(3)))
    if lines and first_sung is not None:
        offset = first_sung - lines[0][0]
        lines = [(t + offset, text) for t, text in lines]
    return lines


def within(lines: list[tuple[float, str]], sections: list[Section], i: int) -> list[tuple[float, str]]:
    """Les lignes chantées dans la section `i` ; la première prend aussi celles d'avant, la dernière celles d'après."""
    s, last = sections[i], i == len(sections) - 1
    return [(t, text) for t, text in lines if s.start <= t < s.end or (last and t >= s.end) or (i == 0 and t < s.start)]


def tagged(synced: str, sections: list[Section], first_sung: float | None = None) -> str:
    """Range des paroles horodatées sous des balises [Verse], [Chorus]... selon les sections."""
    lines = timed(synced, first_sung)
    out = []
    for i, s in enumerate(sections):
        tag = f"[{re.sub(r'[0-9]+$', '', s.name).capitalize()}]"
        out.append("\n".join([tag, *(text for _, text in within(lines, sections, i))]))
    return "\n\n".join(out) + "\n"


def _words(line: str) -> str:
    return " ".join(re.findall(r"\w+", line.lower()))


def placed(
    text: str, synced: str | None, sections: list[Section], first_sung: float | None = None
) -> list[list[tuple[str, float | None]]] | None:
    """Les lignes de lyrics.txt, section par section, chacune avec l'instant où elle est chantée, ou None.

    Les balises de lyrics.txt suivent les sections une à une (None sinon). Dans chaque section,
    ses lignes sont rapprochées dans l'ordre des lignes horodatées qui y tombent : une ligne
    corrigée prend l'instant de celle qu'elle remplace, une ligne ajoutée n'en a pas.
    """
    import difflib

    parts = blocks(text)
    if len(parts) != len(sections):
        return None
    lines = timed(synced, first_sung) if synced else []
    out = []
    for i, mine in enumerate(parts):
        source = within(lines, sections, i)
        times: list[float | None] = [None] * len(mine)
        match = difflib.SequenceMatcher(None, [_words(t) for _, t in source], [_words(m) for m in mine], autojunk=False)
        for tag, a, a_end, b, b_end in match.get_opcodes():
            if tag in ("equal", "replace"):
                for k in range(min(a_end - a, b_end - b)):
                    times[b + k] = source[a + k][0]
        out.append(list(zip(mine, times, strict=True)))
    return out
