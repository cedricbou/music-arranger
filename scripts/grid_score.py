#!/usr/bin/env python
"""Note ce que les détecteurs ont lu contre ce que le musicien a corrigé, morceau par morceau.

Outil d'atelier, à lancer à la main sur la bibliothèque, jamais en CI :

    uv run python scripts/grid_score.py [~/Musique] [--runs FICHIER]

Les corrections du musicien font foi : les barres tapées dans `arr review` (`review/` du projet)
et les passages de `truth/` du projet. Ce qui est noté est la lecture brute : les temps
d'`arr analyze` remis d'aplomb et les barres posées tous les N temps, sans aucune correction.
Les projets sont lus sans être modifiés. Pour chaque passage corrigé :

- barres justes : celles du musicien où la lecture brute pose une barre à moins de 70 ms ;
- en trop : les barres qu'elle pose ailleurs dans le passage ;
- mesures au compte : celles où elle compte le nombre de temps du musicien ;
- écart : de ses barres à celles du musicien (médiane) ;
- accords : pour un passage de `truth/` dont le fichier d'accords a été corrigé à l'oreille, la
  part du temps où la fondamentale est juste, puis fondamentale et majeur ou mineur.

Avec --runs, les notes sont gardées dans FICHIER (hors des projets) et comparées au lancement
précédent : « mieux », « moins bien », « pareil ». Sort en erreur si un passage va moins bien :
un changement de la lecture de la grille ne se livre pas ainsi.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from arr import grid, review, truth
from arr.commands._common import detected_grid, song_fixes
from arr.commands._screen import song_chart
from arr.project import SONG_FILE, Project


def song_scores(p: Project) -> dict[str, dict]:
    """La note de chaque passage corrigé du morceau, par nom : « truth chorus v002 », « review 1:23,4 »."""
    read = detected_grid(p, mine=False)
    if not read:
        return {}
    beats, bars = read[0], grid.regular_bars(read[1], read[0])
    old = [x for x in truth.passages(p) if review.legacy_fix(x.bars, x.beats_per_bar, beats)]
    fixes = song_fixes(p, beats)
    names = [f"truth {x.name} {x.version}" for x in old]
    names += [f"review {int(f.bars[0]) // 60}:{f.bars[0] % 60:04.1f}" for f in fixes[len(old) :]]
    out, shown = {}, None
    for i, (name, fix) in enumerate(zip(names, fixes, strict=True)):
        mine = review.measures(fix.beats, fix.bars)[:-1]  # la dernière barre ferme le passage
        per_bar = Counter(len(bar) for bar in mine).most_common(1)[0][0] if mine else 4
        s = truth.score(fix.bars, per_bar, beats, bars)
        s.pop("wrong")
        s |= {"version": name, "root": None, "majmin": None}
        if i < len(old) and (file := truth.chords_path(p, old[i])).exists():
            shown = shown if shown is not None else truth.shown_chords(song_chart(p))
            heard = truth.chord_score(old[i], truth.read_chords(file), shown)
            s |= {k: heard.get(k) for k in ("root", "majmin")}
        out[name] = s
    return out


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("library", nargs="?", default=str(Path.home() / "Musique"))
    args.add_argument("--runs", help="Fichier JSON où garder les notes, pour comparer au lancement précédent.")
    a = args.parse_args()
    runs = json.loads(Path(a.runs).read_text()) if a.runs and Path(a.runs).exists() else []
    before, now, worse = (runs[-1]["songs"] if runs else {}), {}, []
    total = Counter()
    for f in sorted(Path(a.library).expanduser().glob(f"*/{SONG_FILE}")):
        scores = song_scores(Project(f.parent))
        if not scores:
            continue
        now[f.parent.name] = scores
        for name, s in scores.items():
            since = truth.verdict(s, before.get(f.parent.name, {}).get(name)) if a.runs else ""
            if since == "moins bien":
                worse.append(f"{f.parent.name} {name}")
            total.update({k: s[k] for k in ("marks", "matched", "shown", "counted", "right")})
            offset = "-" if s["offset"] is None else f"{1000 * s['offset']:+.0f} ms"
            chords = "-" if s["root"] is None else f"{s['root']:.0%} fond. · {(s['majmin'] or 0):.0%} maj/min"
            print(
                f"{f.parent.name:<32} {name:<26} barres {s['matched']}/{s['marks']}  en trop {s['shown'] - s['matched']}"
                f"  au compte {s['right']}/{s['counted']}  écart {offset}  accords {chords}  {since}"
            )
    if not now:
        print(f"aucun passage corrigé sous {a.library} (arr review, touche m)")
        return 0
    print(
        f"Total : barres {total['matched']}/{total['marks']}, en trop {total['shown'] - total['matched']},"
        f" mesures au compte {total['right']}/{total['counted']}"
    )
    if a.runs:
        runs.append({"at": datetime.now().isoformat(timespec="seconds"), "songs": now})
        Path(a.runs).write_text(json.dumps(runs, indent=1))
    if worse:
        print(f"moins bien : {', '.join(worse)}")
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main())
