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


def tagged(synced: str, sections: list[Section], first_sung: float | None = None) -> str:
    """Range des paroles horodatées sous des balises [Verse], [Chorus]... selon les sections.

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
    out = []
    for i, s in enumerate(sections):
        last = i == len(sections) - 1
        inside = [text for t, text in lines if s.start <= t < s.end or (last and t >= s.end)]
        if i == 0:
            inside = [text for t, text in lines if t < s.start] + inside
        tag = f"[{re.sub(r'[0-9]+$', '', s.name).capitalize()}]"
        out.append("\n".join([tag, *inside]))
    return "\n\n".join(out) + "\n"
