#!/usr/bin/env python
"""Compare, projet par projet, la grille avec et sans les temps manqués comblés.

À lancer à la main, sur la bibliothèque de l'utilisateur, jamais en CI :

    uv run python scripts/beat_report.py [~/Musique] [--frames DOSSIER] [--keep DOSSIER]

Les projets sont lus sans être modifiés ; les fichiers ChordPro recalculés vont dans un dossier
temporaire (ou DOSSIER avec --keep), en deux versions : `avant` et `apres`. Un projet analysé
avant que `arr analyze` ne garde les activations de beat_this n'a rien à combler : --frames
donne un dossier où les lire (`<projet>.npz`, au format du projet), pour mesurer sans réanalyser.
Pour chaque projet où un temps est ajouté, l'instant de chaque ajout puis, avant → après :

- temps, barres affichées, barres dont le nombre de temps n'est pas le plus fréquent ;
- barres affichées à plus d'un demi-temps d'une barre détectée par beat_this ;
- période du décompte (ms) et tempo ; barres de l'horloge MIDI à plus de 10 % de leur tempo médian ;
- lignes `{time:}` du fichier ChordPro, et s'il est identique.

Règle d'acceptation : sans temps ajouté, tout est identique ; sinon les barres hors des temps
forts n'augmentent pas. Un projet où les barres irrégulières augmentent est signalé « À ÉCOUTER ».
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from arr import audio, grid
from arr import chordpro as cho
from arr.commands import _common, chordpro
from arr.project import Project, ProjectError

real_fill, real_activations = grid.fill_beats, _common.activations


@contextmanager
def filling(on: bool):
    grid.fill_beats = real_fill if on else (lambda beats, *args, **kwargs: beats)
    try:
        yield
    finally:
        grid.fill_beats = real_fill


def grid_facts(p: Project, on: bool) -> dict:
    with filling(on):
        beats, detected = _common.detected_grid(p, mine=False)
    shown = grid.regular_bars(detected, beats)
    step = audio.period(beats)
    t = np.asarray(beats)
    counts = [int(((t >= a - 0.05) & (t < b - 0.05)).sum()) for a, b in zip(shown, shown[1:], strict=False)]
    usual = Counter(counts).most_common(1)[0][0] if counts else 0
    ref = np.asarray(detected)
    off = sum(np.abs(ref - b).min() > step / 2 for b in shown) if len(ref) else 0
    return {
        "temps": len(beats),
        "barres": len(shown),
        "irrégulières": sum(c != usual for c in counts),
        "hors temps fort": int(off),
        "décompte ms": round(1000 * step),
        "bpm": round(60 / step, 1),
        "_beats": beats,
    }


def chordpro_facts(p: Project, on: bool, out: Path) -> dict:
    with filling(on):
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


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("library", nargs="?", default=str(Path.home() / "Musique"))
    args.add_argument("--frames", help="Dossier d'activations (<projet>.npz) pour les projets qui n'en ont pas.")
    args.add_argument("--keep", help="Dossier où garder les fichiers ChordPro recalculés.")
    a = args.parse_args()
    out = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="beat-report-"))

    def activations(p: Project):
        spare = Path(a.frames) / f"{p.root.name}.npz" if a.frames else None
        own = real_activations(p)
        return own if own is not None or not (spare and spare.exists()) else np.load(spare)["frames"]

    _common.activations = activations
    unchanged, listen, worse, deaf = [], [], [], []
    for f in sorted(Path(a.library).expanduser().glob("*/analysis.json")):
        p = Project(f.parent)
        if activations(p) is None:
            deaf.append(p.root.name)
        before = grid_facts(p, False) | chordpro_facts(p, False, out)
        after = grid_facts(p, True) | chordpro_facts(p, True, out)
        same_text = before.pop("_text", None) == after.pop("_text", None)
        added = sorted(set(after.pop("_beats")) - set(before.pop("_beats")))
        if not added:
            if before != after or not same_text:
                worse.append(p.root.name)
                print(f"✗ {p.root.name} : aucun temps ajouté, mais la sortie change")
            unchanged.append(p.root.name)
            continue
        where = ", ".join(f"{int(t) // 60}:{t % 60:05.2f}" for t in added)
        print(f"\n{p.root.name} — {len(added)} temps ajouté{'s' if len(added) > 1 else ''} : {where}")
        for key in before:
            mark = "" if before[key] == after.get(key) else "   ←"
            print(f"  {key:<16} {before[key]!s:>7} → {after.get(key)!s:<7}{mark}")
        print(f"  ChordPro         {'identique' if same_text else 'change'}")
        if after["hors temps fort"] > before["hors temps fort"]:
            worse.append(p.root.name)
        if after["irrégulières"] > before["irrégulières"]:
            listen.append(p.root.name)
    print(f"\n{len(unchanged)} projets sans temps ajouté, sortie identique : {len(unchanged) - len(worse)}")
    if deaf:
        print(f"{len(deaf)} projets sans activations (arr analyze, ou --frames) : rien à combler")
    print(f"À ÉCOUTER (barres irrégulières en hausse) : {', '.join(listen) or 'aucun'}")
    print(f"EN RECUL (barres hors des temps forts en hausse) : {', '.join(worse) or 'aucun'}")
    print(f"fichiers ChordPro recalculés : {out}")
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main())
