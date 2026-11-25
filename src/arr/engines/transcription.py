"""SheetSage2 : transcrit un enregistrement en partition (mélodie, accords, temps, tonalité, structure).

Il a ses propres dépendances, incompatibles avec celles d'arr : il tourne dans un
environnement Python séparé, appelé en sous-processus.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from arr.engines import SS2_PYTHON, _notation, device

SCRIPT = Path(__file__).with_name("_sheetsage2.py")
SCORE = "score.abc"
REPAIR = "repair.json"


def transcribe(src: Path, out_dir: Path, beats: list[float] | None = None, bars: list[float] | None = None) -> dict:
    """Écrit dans `out_dir` : score.abc, des MIDI, et des fichiers .lab horodatés.

    Si SheetSage2 refuse la partition, elle est réécrite sur la grille donnée (`beats`, `bars` :
    celle d'`arr analyze`). Renvoie ce qui s'est passé : {"repaired": raison} si elle a été
    réécrite, {"missing": raison} si elle manque encore, {} si tout va bien. Une erreur si la
    transcription elle-même échoue (pas d'accords).
    """
    if not SS2_PYTHON.exists():
        raise RuntimeError("environnement SheetSage2 absent (arr models pull)")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        grid = Path(tmp) / "grid.json"
        grid.write_text(json.dumps({"beats": beats or [], "bars": bars or []}))
        done = subprocess.run(
            [str(SS2_PYTHON), str(SCRIPT), str(src), str(out_dir), device(), str(grid)],
            capture_output=True,
            text=True,
            env=os.environ,
        )
    if done.returncode != 0 or not (out_dir / "chord.lab").exists():
        why = done.stderr.strip()[-400:] or "aucun message, et pas d'accords écrits"
        raise RuntimeError(f"SheetSage2 a échoué (code {done.returncode}) : {why}")
    return outcome(out_dir)


def outcome(out_dir: Path) -> dict:
    """Ce que dit le compte rendu de reprise de la partition (voir `transcribe`)."""
    f = out_dir / REPAIR
    if not f.exists():
        return {} if (out_dir / SCORE).exists() else {"missing": "SheetSage2 n'a laissé ni partition ni raison"}
    report = json.loads(f.read_text())
    why = _notation.reason(report["error"])
    if report.get("repair_error") or not (out_dir / SCORE).exists():
        return {"missing": f"{why} ; la reprise a échoué aussi ({report.get('repair_error') or 'sans message'})"}
    return {"repaired": why}


def set_tempo(out_dir: Path, bpm: int) -> None:
    """Impose le tempo de la partition (ligne Q: de l'ABC), s'il y en a une."""
    score = out_dir / SCORE
    if not score.exists():
        return
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
