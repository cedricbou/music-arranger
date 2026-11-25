"""truth, doubts : la grille notée contre les passages comptés à l'oreille, et les mesures dont arr doute."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from arr.app import app
from arr.project import SONG_FILE, Project, ProjectError


def library_of(given: Optional[Path]) -> Path:
    """Le dossier des morceaux : celui donné, sinon celui qui contient le projet courant, sinon le dossier courant."""
    if given:
        return given.expanduser()
    try:
        return Project.find().root.parent
    except ProjectError:
        return Path.cwd()


@app.command("truth")
def truth_(
    library: Optional[Path] = typer.Argument(
        None, help="Dossier des morceaux ; sinon celui qui contient le projet courant, ou le dossier courant."
    ),
    dry: bool = typer.Option(
        False, "--dry-run", help="Note sans rien retenir : le prochain lancement se compare encore au précédent."
    ),
) -> None:
    """Note la grille de chaque morceau contre ses passages de référence, repérés par `arr play --mark`.

    Pour chaque passage : les barres repérées, celles où `arr` pose une barre à moins de 70 ms,
    les barres qu'`arr` pose en trop, les mesures où il compte le bon nombre de temps (4, ou le
    `beats_per_bar` écrit dans le fichier du passage), l'écart médian entre ses barres et les
    frappes, et si le passage va mieux ou moins bien qu'au lancement précédent. La grille notée
    est celle d'`arr play`. Les notes sont gardées dans `truth/runs.json` de chaque morceau.

    « Accords » note ceux d'`arr play` contre le fichier d'accords du passage, que tu corriges à
    l'oreille (`truth/<passage>.vNNN.chords.txt`, écrit ici s'il manque) : part du temps où la
    fondamentale est juste, puis fondamentale et majeur ou mineur, et le nombre de mesures corrigées.

    « Doute » dit ce que valent les mesures marquées « ? » (`arr doubts`) : parmi les mesures où
    la grille se trompe, combien sont marquées, et combien le sont parmi celles où elle est juste.

    Sort en erreur si un passage va moins bien : un changement de la grille ne se livre pas ainsi.
    """
    from rich.console import Console
    from rich.table import Table

    from arr import grid
    from arr import truth as marks
    from arr.commands._common import song_doubts, song_grid
    from arr.commands._screen import song_chart

    def accuracy(scores: list[dict]) -> str:
        """Fondamentale, puis majeur ou mineur, pondérés par la durée notée ; les mesures corrigées."""
        scores = [c for c in scores if c]
        if not scores:
            return "-"
        seconds = sum(c["seconds"] for c in scores)
        root = sum(c["root"] * c["seconds"] for c in scores) / seconds
        triads = [c for c in scores if c["majmin"] is not None]
        majmin = sum(c["majmin"] * c["seconds"] for c in triads) / max(sum(c["seconds"] for c in triads), 1e-9)
        fixed, filled = sum(c["corrected"] for c in scores), sum(c["filled"] for c in scores)
        return f"{root:.0%} fond. · {majmin:.0%} maj/min · {fixed}/{filled} corrigées"

    def doubt(s: dict) -> str:
        return f"{s['caught']}/{s['bad']} fausses · {s['alarms']}/{s['good']} justes"

    folder = library_of(library)
    table = Table(box=None, pad_edge=False, header_style="bold")
    columns = (
        "Morceau",
        "Passage",
        "Barres justes",
        "En trop",
        "Mesures au compte",
        "Écart",
        "Doute",
        "Accords",
        "Depuis",
    )
    for column in columns:
        table.add_column(
            column, no_wrap=True, justify="left" if column in ("Morceau", "Passage", "Depuis") else "right"
        )
    total = dict.fromkeys(("marks", "matched", "shown", "counted", "right", "caught", "alarms", "bad", "good"), 0)
    moved: dict[str, list[str]] = {"mieux": [], "moins bien": []}
    chords: list[dict] = []
    for f in sorted(folder.glob(f"*/{SONG_FILE}")):
        p = Project(f.parent)
        found = marks.passages(p)
        if not found:
            continue
        read = song_grid(p)
        if not read:
            table.add_row(p.root.name, "", "[yellow]pas d'analyse (arr analyze)[/]")
            continue
        beats, bars = read[0], grid.regular_bars(read[1], read[0])
        before, run, unsure = marks.last_run(p), {}, song_doubts(p)
        shown = marks.shown_chords(song_chart(p))
        for passage in found:
            if not dry:
                marks.write_chords(p, passage, shown)
            file = marks.chords_path(p, passage)
            heard = marks.chord_score(passage, marks.read_chords(file), shown) if file.exists() else {}
            chords.append(heard)
            s = marks.score(passage.bars, passage.beats_per_bar, beats, bars) | {"version": passage.version}
            s |= {k: heard.get(k) for k in ("root", "majmin")}
            flags = marks.doubted(passage.bars, passage.beats_per_bar, list(unsure or ()))
            # Sans activations gardées, aucune mesure n'est marquée : le passage ne compte pas dans le doute.
            wrong = s.pop("wrong") if unsure is not None else [s.pop("wrong")][:0]
            s["caught"] = sum(f and w for f, w in zip(flags, wrong, strict=False))
            s["alarms"] = sum(f and not w for f, w in zip(flags, wrong, strict=False))
            s["bad"], s["good"] = sum(wrong), len(wrong) - sum(wrong)
            run[passage.name] = s
            since = marks.verdict(s, before.get(passage.name))
            if since in moved:
                moved[since].append(f"{p.root.name} {passage.name}")
            for key in total:
                total[key] += s[key]
            table.add_row(
                p.root.name,
                f"{passage.name} [dim]{passage.version} · {passage.beats_per_bar} temps[/]",
                f"{s['matched']}/{s['marks']}",
                str(s["shown"] - s["matched"]),
                f"{s['right']}/{s['counted']}",
                "-" if s["offset"] is None else f"{1000 * s['offset']:+.0f} ms",
                doubt(s) if unsure is not None else "[dim]arr analyze[/]",
                accuracy([heard]),
                {"mieux": "[green]mieux[/]", "moins bien": "[red]moins bien[/]"}.get(since, f"[dim]{since}[/]"),
            )
        if not dry:
            marks.record_run(p, run)
    if not total["marks"]:
        raise ProjectError(f"aucun passage de référence sous {folder} (arr play -s <section> --mark)")
    table.add_row(
        "[bold]Total[/]",
        "",
        f"{total['matched']}/{total['marks']}",
        str(total["shown"] - total["matched"]),
        f"{total['right']}/{total['counted']}",
        "",
        doubt(total),
        accuracy(chords),
    )
    Console().print(table)
    for word, names in moved.items():
        if names:
            typer.echo(f"{word} : {', '.join(names)}")
    if moved["moins bien"]:
        raise typer.Exit(1)


@app.command()
def doubts() -> None:
    """Liste les passages où `arr` n'est pas sûr du compte des mesures, avec leur instant et la raison.

    Une mesure est douteuse quand le détecteur a entendu faiblement un de ses temps : là, une
    barre ou un temps peut être de travers. À vérifier à l'oreille d'abord (`arr play` les marque
    d'un « ? », d y saute). Rien n'est corrigé : la grille et le fichier du prompteur ne changent pas.
    """
    from arr import grid
    from arr.commands._common import doubtful_passages, song_doubts, song_grid
    from arr.commands._screen import clock

    p = Project.find()
    found = song_doubts(p)
    if found is None:
        raise ProjectError("ce morceau ne garde pas encore ce que le détecteur entendait : lance arr analyze")
    read = song_grid(p)
    bars = grid.regular_bars(read[1], read[0])
    first = [min((t for t in read[0] if t >= b - 0.05), default=b) for b in bars]
    name = lambda t: next((s.name for s in p.sections if s.start - 0.05 <= t < s.end), "")
    for start, count, why in doubtful_passages(found, first):
        number = first.index(start) + 1
        where = f"mes. {number}" if count == 1 else f"mes. {number} à {number + count - 1}"
        typer.echo(
            f"{clock(start):>5}  {where:<16} {name(start):<10} {why[0]}{f' ; {count - 1} de plus' if count > 1 else ''}"
        )
    share = len(found) / max(len(bars), 1)
    typer.echo(
        f"{len(found)} mesure{'s' if len(found) > 1 else ''} douteuse{'s' if len(found) > 1 else ''} sur {len(bars)} ({share:.0%})"
    )
