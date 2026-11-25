#!/usr/bin/env python
"""Compare, projet par projet, la grille avec et sans le retrait des temps entendus deux fois.

À lancer à la main, sur la bibliothèque de l'utilisateur, jamais en CI :

    uv run python scripts/beat_report.py [~/Musique] [--keep DOSSIER]

Les projets sont lus sans être modifiés ; les fichiers ChordPro recalculés vont dans un dossier
temporaire (ou DOSSIER avec --keep), en deux versions : `avant` et `apres`. Pour chaque projet
où quelque chose change, une ligne par grandeur, avant → après :

- temps, barres affichées, barres dont le nombre de temps n'est pas le plus fréquent ;
- barres affichées à plus d'un demi-temps d'une barre détectée par beat_this ;
- période du décompte (ms) et tempo ; barres de l'horloge MIDI à plus de 10 % de leur tempo médian ;
- lignes `{time:}` du fichier ChordPro, et s'il est identique ;
- le plus grand écart retiré et le plus petit écart gardé, en fraction de période.

Règle d'acceptation : sans temps retiré, tout est identique ; sinon les barres hors des temps
forts n'augmentent pas. Un projet où les barres irrégulières augmentent est signalé « À ÉCOUTER ».
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from arr import audio, measure
from arr import chordpro as cho
from arr.commands import chordpro
from arr.project import Project, ProjectError

real_clean = measure.clean_beats


@contextmanager
def cleaning(on: bool):
    measure.clean_beats = real_clean if on else (lambda beats, downbeats: (beats, downbeats))
    try:
        yield
    finally:
        measure.clean_beats = real_clean


def grid_facts(raw: dict, on: bool) -> dict:
    beats, detected = real_clean(raw["beats"], raw["downbeats"]) if on else (raw["beats"], raw["downbeats"])
    shown = measure.regular_bars(detected, beats)
    step = audio.period(real_clean(raw["beats"], raw["downbeats"])[0])
    t = np.asarray(beats)
    counts = [int(((t >= a - 0.05) & (t < b - 0.05)).sum()) for a, b in zip(shown, shown[1:], strict=False)]
    usual = Counter(counts).most_common(1)[0][0] if counts else 0
    ref = np.asarray(raw["downbeats"])
    off = sum(np.abs(ref - b).min() > step / 2 for b in shown) if len(ref) else 0
    return {
        "temps": len(beats),
        "barres": len(shown),
        "irrégulières": sum(c != usual for c in counts),
        "hors temps fort": int(off),
        "décompte ms": round(1000 * audio.period(beats)),
        "bpm": round(60 / audio.period(beats), 1),
    }


def chordpro_facts(p: Project, on: bool, out: Path) -> dict:
    with cleaning(on):
        try:
            head, blocks, usual, _, _ = chordpro.prepare(p)
            bars = chordpro.written_bars(p)
        except ProjectError:
            return {}
    text = cho.write(head, blocks, usual)
    (out / ("apres" if on else "avant")).mkdir(parents=True, exist_ok=True)
    (out / ("apres" if on else "avant") / f"{p.root.name}.cho").write_text(text)
    tempo = np.array([(end - start) / beats for start, end, beats in bars])
    return {
        "{time:}": sum(line.startswith("{time") for line in text.splitlines()),
        "horloge > 10 %": int((np.abs(tempo / np.median(tempo) - 1) > 0.1).sum()) if len(tempo) else 0,
        "_text": text,
    }


def ratios(raw: dict) -> str:
    beats, _ = real_clean(raw["beats"], raw["downbeats"])
    step = audio.period(beats)
    gone = sorted(set(raw["beats"]) - set(beats))
    t = np.asarray(raw["beats"])
    removed = [np.diff(t)[max(0, int(np.searchsorted(t, g)) - 1) : int(np.searchsorted(t, g)) + 1].min() for g in gone]
    kept = np.diff(beats).min() / step
    return f"retiré ≤ {max(removed) / step:.2f} · gardé ≥ {kept:.2f} période"


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("library", nargs="?", default=str(Path.home() / "Musique"))
    args.add_argument("--keep", help="Dossier où garder les fichiers ChordPro recalculés.")
    a = args.parse_args()
    out = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="beat-report-"))
    unchanged, listen, worse = [], [], []
    for f in sorted(Path(a.library).expanduser().glob("*/analysis.json")):
        raw, p = json.loads(f.read_text()), Project(f.parent)
        removed = len(raw["beats"]) - len(real_clean(raw["beats"], raw["downbeats"])[0])
        before = grid_facts(raw, False) | chordpro_facts(p, False, out)
        after = grid_facts(raw, True) | chordpro_facts(p, True, out)
        same_text = before.pop("_text", None) == after.pop("_text", None)
        if not removed:
            if before != after or not same_text:
                worse.append(p.root.name)
                print(f"✗ {p.root.name} : aucun temps retiré, mais la sortie change")
            unchanged.append(p.root.name)
            continue
        print(f"\n{p.root.name} — {removed} temps retiré{'s' if removed > 1 else ''} · {ratios(raw)}")
        for key in before:
            mark = "" if before[key] == after.get(key) else "   ←"
            print(f"  {key:<16} {before[key]!s:>7} → {after.get(key)!s:<7}{mark}")
        print(f"  ChordPro         {'identique' if same_text else 'change'}")
        if after["hors temps fort"] > before["hors temps fort"]:
            worse.append(p.root.name)
        if after["irrégulières"] > before["irrégulières"]:
            listen.append(p.root.name)
    print(f"\n{len(unchanged)} projets sans temps entendu deux fois, sortie identique : {len(unchanged) - len(worse)}")
    print(f"À ÉCOUTER (barres irrégulières en hausse) : {', '.join(listen) or 'aucun'}")
    print(f"EN RECUL (barres hors des temps forts en hausse) : {', '.join(worse) or 'aucun'}")
    print(f"fichiers ChordPro recalculés : {out}")
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main())
