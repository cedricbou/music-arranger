"""Antisèche d'un morceau : sa proposition déduite du projet, son fichier sheet.toml, la transposition."""

from __future__ import annotations

import re
import tomllib
from collections import Counter
from pathlib import Path

SHEET_FILE = "sheet.toml"
HEADER = """# Antisèche du morceau. Ce fichier fait foi dès qu'il existe : modifie-le librement.
# Tout est écrit dans la tonalité de l'original ; `transpose` (en demi-tons) décale la
# tonalité et les accords à l'affichage et à l'impression.
# Un passage : [[parts]] avec name, chords (mesures séparées par |) et repeat. Pour en
# montrer moins, supprime le bloc ; `arr sheet --reset` revient à la proposition.

"""
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
# Nom complet pour les passages clés, abrégé pour la ligne de structure.
KINDS = {
    "intro": ("Intro", "Intro"),
    "verse": ("Couplet", "C"),
    "pre-chorus": ("Pré-refrain", "Pré"),
    "chorus": ("Refrain", "R"),
    "bridge": ("Pont", "Pont"),
    "interlude": ("Interlude", "Int"),
    "solo": ("Solo", "Solo"),
    "outro": ("Fin", "Fin"),
}
KEY_PARTS = ("verse", "pre-chorus", "chorus", "bridge", "solo")
SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
# L'écriture habituelle de chaque tonalité : celle qui a le moins d'altérations.
MAJOR = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MINOR = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]
FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Dm", "Gm", "Cm", "Fm", "Bbm", "Ebm"}
NOTE = r"[A-G][#b]?"


def chord_name(label: str) -> str:
    """« D:min » devient « Dm », « C:maj » devient « C » ; « N » (pas d'accord) devient un tiret."""
    if label == "N":
        return "–"
    root, _, quality = label.partition(":")
    quality, slash, bass = quality.partition("/")
    return root + QUALITIES.get(quality, quality) + slash + bass


def key_name(key: str) -> str:
    """« F major » devient « F », « D minor » devient « Dm » ; une tonalité déjà courte est gardée."""
    root, _, mode = key.strip().partition(" ")
    return root + ("m" if mode.lower().startswith("min") else "")


def _pitch(note: str) -> int:
    return (SHARPS.index(note[0]) + note.count("#") - note.count("b")) % 12


def transpose_key(key: str, semitones: int) -> str:
    minor = key.endswith("m")
    root = key[:-1] if minor else key
    if not re.fullmatch(NOTE, root):
        return key
    return (MINOR if minor else MAJOR)[(_pitch(root) + semitones) % 12] + ("m" if minor else "")


def transpose(chords: str, semitones: int, key: str) -> str:
    """Décale d'autant de demi-tons chaque accord d'une ligne (« F | Gm A/C# ») ; `key` est la tonalité d'arrivée.

    Elle décide de l'écriture : bémols dans une tonalité à bémols, dièses sinon.
    """
    if not semitones:
        return chords
    names = FLATS if key in FLAT_KEYS else SHARPS
    move = lambda m: names[(_pitch(m.group(0)) + semitones) % 12]
    return re.sub(rf"(?<![A-Za-z#]){NOTE}", move, chords)


def kind(section: str) -> str:
    """Le type d'une section : « chorus2 » est un « chorus »."""
    return re.sub(r"\d+$", "", section)


def groups(sections: list, chart: list[tuple]) -> list[tuple[str, list[tuple]]]:
    """Les passages du morceau dans l'ordre : (type, mesures), les sections voisines de même type réunies."""
    out: list[tuple[str, list[tuple]]] = []
    for s in sections:
        bars = [b for b in chart if s.start <= (b[0] + b[1]) / 2 < s.end]
        if out and out[-1][0] == kind(s.name):
            out[-1][1].extend(bars)
        elif bars:
            out.append((kind(s.name), bars))
    return out


def structure(passages: list[tuple[str, list[tuple]]]) -> str:
    """« Intro 4 · C 16 · R 8+2t » : chaque passage et sa longueur en mesures, les temps en plus à part."""
    sizes = Counter(b[2] for _, bars in passages for b in bars)
    full = sizes.most_common(1)[0][0] if sizes else 4
    parts = []
    for name, bars in passages:
        # Les mesures d'une autre longueur comptent en temps : « 17+2t », ou une mesure de plus s'ils en font une.
        odd = sum(b[2] for b in bars if b[2] != full)
        whole, extra = sum(b[2] == full for b in bars) + odd // full, odd % full
        parts.append(f"{KINDS.get(name, (name, name))[1]} {whole}{f'+{extra}t' if extra else ''}")
    return " · ".join(parts)


def motif(bars: list[tuple]) -> tuple[str, int]:
    """La suite d'accords d'un passage, réduite à ce qui se répète : (accords, nombre de fois).

    Un passage fait d'un seul motif rend ce motif et son nombre de répétitions. Sinon les
    répétitions sont notées dans la ligne : « [F | Gm A] ×2 » pour un motif, « F ×4 » pour
    une mesure tenue, et le nombre de fois vaut 1.
    """
    cells = [" ".join(chord_name(chord[2]) for chord in bar[3]) for bar in bars]
    out, i = [], 0
    while i < len(cells):
        best = (1, 1)
        for size in range(1, (len(cells) - i) // 2 + 1):
            times = 1
            while cells[i + times * size : i + (times + 1) * size] == cells[i : i + size]:
                times += 1
            if times >= (3 if size == 1 else 2) and size * times > best[0] * best[1]:
                best = (size, times)
        size, times = best
        if times > 1 and size * times == len(cells) and size > 1:
            return " | ".join(cells[:size]), times
        phrase = " | ".join(cells[i : i + size])
        out.append(phrase if times == 1 else f"{phrase} ×{times}" if size == 1 else f"[{phrase}] ×{times}")
        i += size * times
    return " | ".join(out), 1


def brief(bars: list[tuple], longest: int = 16) -> tuple[str, int]:
    """Le motif d'un passage, borné : un passage long qui ne se répète pas est coupé après `longest` mesures."""
    chords, times = motif(bars)
    if times > 1 or len(bars) <= longest:
        return chords, times
    chords, times = motif(bars[:longest])
    return (f"[{chords}] ×{times}" if times > 1 else chords) + " | …", 1


def propose(song: dict, sections: list, chart: list[tuple]) -> dict:
    """L'antisèche déduite du projet : tonalité, tempo, structure, et les accords des passages clés.

    Pour chaque type de passage, le motif retenu est le plus fréquent parmi ses occurrences
    (le premier couplet est souvent écourté ou précédé d'une levée).
    """
    passages = groups(sections, chart)
    parts = []
    for name in dict.fromkeys(n for n, _ in passages if n in KEY_PARTS):
        motifs = [brief(bars) for n, bars in passages if n == name]
        chords, repeat = Counter(motifs).most_common(1)[0][0]
        parts.append({"name": KINDS[name][0], "chords": chords, "repeat": repeat})
    return {
        "key": key_name(str(song.get("key", ""))),
        "bpm": round(float(song.get("bpm", 0))),
        "transpose": 0,
        "structure": structure(passages),
        "notes": [],
        "parts": parts,
    }


def load(root: Path) -> dict | None:
    """Le contenu de sheet.toml, ou None s'il n'existe pas."""
    f = root / SHEET_FILE
    return tomllib.loads(f.read_text()) if f.exists() else None


def save(root: Path, sheet: dict) -> None:
    import tomli_w

    (root / SHEET_FILE).write_text(HEADER + tomli_w.dumps(sheet, multiline_strings=False))


def played(sheet: dict, semitones: int | None = None) -> dict:
    """L'antisèche telle qu'elle se joue : tonalité et accords transposés (de `semitones`, sinon du réglage du fichier)."""
    shift = int(sheet.get("transpose", 0)) if semitones is None else semitones
    key = transpose_key(str(sheet.get("key", "")), shift)
    parts = [{**part, "chords": transpose(str(part.get("chords", "")), shift, key)} for part in sheet.get("parts", [])]
    return {**sheet, "key": key, "transpose": shift, "parts": parts}
