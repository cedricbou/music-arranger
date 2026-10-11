"""SheetSage2 : transcrit un enregistrement en partition (mélodie, accords, temps, tonalité, structure).

Il a ses propres dépendances, incompatibles avec celles d'arr : il tourne dans un
environnement Python séparé, appelé en sous-processus.
"""

from __future__ import annotations

import os
import subprocess
from collections import Counter
from pathlib import Path

from arr.engines import SS2_PYTHON, device

SCRIPT = Path(__file__).with_name("_sheetsage2.py")
SCORE = "score.abc"


def transcribe(src: Path, out_dir: Path) -> None:
    """Écrit dans `out_dir` : score.abc, des MIDI, et des fichiers .lab horodatés."""
    if not SS2_PYTHON.exists():
        raise RuntimeError("environnement SheetSage2 absent (arr models pull)")
    out_dir.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        [str(SS2_PYTHON), str(SCRIPT), str(src), str(out_dir), device()],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    if done.returncode != 0 or not (out_dir / SCORE).exists():
        raise RuntimeError(f"SheetSage2 a échoué (code {done.returncode}) : {done.stderr[-400:]}")


def set_tempo(out_dir: Path, bpm: int) -> None:
    """Impose le tempo de la partition (ligne Q: de l'ABC)."""
    score = out_dir / SCORE
    score.write_text(
        "".join(
            f"Q:1/4={bpm}\n" if line.startswith("Q:") else line for line in score.read_text().splitlines(keepends=True)
        )
    )


def _rows(path: Path) -> list[list[str]]:
    return [line.split("\t") for line in path.read_text().splitlines() if line.strip()]


def chords(out_dir: Path) -> list[tuple[float, float, str]]:
    """Les accords du morceau : (début, fin, étiquette comme « D:min » ou « N »), vide sans transcription."""
    f = out_dir / "chord.lab"
    return [(float(start), float(end), label) for start, end, label in _rows(f)] if f.exists() else []


def beats(out_dir: Path) -> list[tuple[float, int]]:
    """Les temps de la transcription : (instant, rang dans la mesure). Les accords de `chords` tombent dessus."""
    f = out_dir / "beat.lab"
    return [(float(row[0]), int(row[1])) for row in _rows(f)] if f.exists() else []


def first_sung(out_dir: Path) -> float | None:
    """Instant de la première note de la mélodie vocale, ou None si elle manque."""
    f = out_dir / "melody_vocal.lab"
    rows = _rows(f) if f.exists() else []
    return float(rows[0][0]) if rows else None


def read(out_dir: Path) -> dict:
    """Résumé d'une transcription : tonalité et sections nommées."""
    keys = Counter()
    for start, end, label in _rows(out_dir / "key.lab"):
        keys[label.replace(":", " ")] += float(end) - float(start)
    # Deux sections voisines de même nom sont deux parties distinctes : on les numérote.
    seen, sections = Counter(), []
    for start, end, label in _rows(out_dir / "structure.lab"):
        seen[label] += 1
        name = label if seen[label] == 1 else f"{label}{seen[label]}"
        sections.append((name, float(start), float(end)))
    return {
        "key": keys.most_common(1)[0][0] if keys else "",
        "sections": sections,
    }
