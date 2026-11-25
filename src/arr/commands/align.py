"""Calage : décaler une piste par section, à la main (nudge) ou d'après une mesure (align)."""

from __future__ import annotations

from typing import Optional

import numpy as np
import typer

from arr import audio
from arr.app import ORIGINAL, app
from arr.commands._common import load_track, original_beats
from arr.project import Project, ProjectError

TOLERANCE = 0.03  # en dessous de 30 ms, un décalage ne s'entend plus comme tel
STEP = 0.01  # résolution de la mesure : en dessous, deux décalages sont le même
ORIGINS = {"align": "automatique", "manual": "manuel"}


def beat_period(p: Project) -> Optional[float]:
    """Durée d'un temps du morceau, en secondes, ou None si le tempo n'est pas connu."""
    from arr import measure

    beats = original_beats(p) or []
    return measure.period(beats) if len(beats) > 2 else None


def targets(p: Project, name: str) -> list[str]:
    """Les pistes désignées par `name` : une piste, ou tous les stems d'une prise."""
    stems = [t for t in p.tracks if t.startswith(f"{name}.")]
    if name in p.tracks:
        return [name]
    if not stems:
        p.version_path(name)  # lève l'erreur « piste inconnue »
    return stems


def amount(ms: float, period: Optional[float]) -> str:
    """Un décalage lisible : en temps quand le tempo est connu, et toujours en millisecondes."""
    if period:
        return f"{ms / 1000 / period:+.2f} temps ({ms:+.0f} ms)"
    return f"{ms:+.0f} ms"


def show(p: Project, names: list[str]) -> None:
    from rich.console import Console
    from rich.table import Table

    period = beat_period(p)
    table = Table(box=None, pad_edge=False, header_style="bold")
    for column in ("Piste", "Portée", "Décalage", "Origine"):
        table.add_column(column, no_wrap=True)
    order = {"track": -1.0, **{s.name: s.start for s in p.sections}}
    for name in names:
        rules = sorted(p.nudges(name), key=lambda n: order.get(n["scope"], 1e9))
        for i, rule in enumerate(rules):
            scope = "toute la piste" if rule["scope"] == "track" else rule["scope"]
            table.add_row(
                name if i == 0 else "", scope, amount(rule["ms"], period), ORIGINS.get(rule["by"], rule["by"])
            )
    if table.row_count:
        Console().print(table)
        typer.echo("\n+ joue plus tard, - plus tôt ; les réglages d'une section s'ajoutent à celui de la piste")
    else:
        typer.echo("aucun calage appliqué")


@app.command()
def nudge(
    name: Optional[str] = typer.Argument(
        None, help="Piste, ou prise (ex. t001) pour tous ses stems ; sinon tout afficher."
    ),
    section: Optional[str] = typer.Option(
        None, "--section", "-s", help="Ne décale que cette section ; sinon toute la piste."
    ),
    beats: Optional[float] = typer.Option(
        None, "--beats", help="Décalage en temps : --beats=+1 joue un temps plus tard, --beats=-0.5 plus tôt."
    ),
    ms: Optional[float] = typer.Option(None, "--ms", help="Décalage en millisecondes : --ms=-20 joue 20 ms plus tôt."),
    add: bool = typer.Option(False, "--add", help="Ajoute à la valeur existante au lieu de la remplacer."),
    reset: bool = typer.Option(
        False, "--reset", help="Annule le calage : de la section donnée, sinon de toute la piste."
    ),
) -> None:
    """Décale une piste dans le mix, en entier ou par section, sans toucher à ses fichiers.

    Sans valeur, affiche ce qui est appliqué. Une valeur remplace celle de la même portée
    (--add pour l'ajuster) ; --reset l'annule. Les réglages sont gardés dans song.toml.
    """
    p = Project.find()
    names = targets(p, name) if name else [t for t in p.tracks if p.nudges(t)]
    if reset:
        if not name:
            raise ProjectError("indique la piste ou la prise à remettre à zéro")
        removed = sum(p.clear_nudges(t, scope=section) for t in names)
        p.save()
        typer.echo(f"{removed} réglage(s) annulé(s)")
        return
    if beats is None and ms is None:
        show(p, names)
        return
    if not name:
        raise ProjectError("indique la piste ou la prise à décaler")
    if beats is not None and ms is not None:
        raise ProjectError("donne --beats ou --ms, pas les deux")
    period = beat_period(p)
    if beats is not None and not period:
        raise ProjectError("le tempo est inconnu : utilise --ms, ou lance arr transcribe ou arr analyze")
    value = beats * period * 1000 if beats is not None else ms
    scope = section or "track"
    for track in names:
        current = next((n["ms"] for n in p.nudges(track) if n["scope"] == scope), 0.0)
        p.set_nudge(track, scope, current + value if add else value, by="manual")
    p.save()
    show(p, names)


def take_mix(p: Project, take: str, nudged: bool) -> np.ndarray:
    stems = [t for t in p.tracks if t.startswith(f"{take}.")]
    if not stems:
        raise ProjectError(f"{take} n'est pas encore séparée (arr split {take})")
    return np.sum([load_track(p, t) if nudged else audio.load(p.version_path(t)) for t in stems], axis=0)


def align_take(p: Project, take: str, write: bool) -> dict:
    """Mesure le décalage d'une prise sur l'original, section par section, et le corrige si `write`.

    La correction est inscrite comme réglages de calage (origine « align ») sur chaque stem :
    un décalage de fond pour toute la piste, et un réglage par section qui s'en écarte.
    """
    from arr import measure

    original = p.root / ORIGINAL
    if not original.exists():
        raise ProjectError("pas de morceau original auquel se caler")
    reference = audio.load(original)
    stems = [t for t in p.tracks if t.startswith(f"{take}.")]
    before = measure.time_map(reference, take_mix(p, take, nudged=False))
    sections = [(s.name, s.start, s.end) for s in p.sections] or [("track", 0.0, len(reference) / audio.SR)]
    found = measure.by_section(before, sections)
    sure = [s for s in found if s["lag"] is not None and not s["ambiguous"]]
    base = float(np.median([-s["lag"] for s in sure])) if sure else 0.0
    report = {"sections": found, "before": measure.within(before, TOLERANCE), "base": base, "after": None}
    if not write:
        return report
    for track in stems:
        p.clear_nudges(track, by="align")
        # Un réglage posé à la main est une décision : on ne l'écrase pas, on se cale dessus.
        manual = {n["scope"]: n["ms"] / 1000 for n in p.nudges(track)}
        ground = manual.get("track", base)
        if "track" not in manual and abs(base) >= TOLERANCE / 2:
            p.set_nudge(track, "track", base * 1000, by="align")
        for s in sure:
            if s["name"] not in ("track", *manual) and abs(-s["lag"] - ground) >= STEP:
                p.set_nudge(track, s["name"], (-s["lag"] - ground) * 1000, by="align")
    p.save()
    after = measure.time_map(reference, take_mix(p, take, nudged=True))
    report["after"] = measure.within(after, TOLERANCE)
    report["after_sections"] = measure.by_section(after, sections)
    return report


def print_report(p: Project, take: str, report: dict) -> None:
    from rich.console import Console
    from rich.table import Table

    period = beat_period(p)
    table = Table(box=None, pad_edge=False, header_style="bold")
    columns = ["Section", "Décalage mesuré", "Mesure"] + (["Après calage"] if report["after"] is not None else [])
    for column in columns:
        table.add_column(column, no_wrap=True)
    after = {s["name"]: s for s in report.get("after_sections", [])}
    for s in report["sections"]:
        if s["lag"] is None:
            row = [s["name"], "-", "pas de mesure fiable"]
        elif s["guessed"]:
            row = [
                s["name"],
                amount(s["lag"] * 1000, period),
                "ambiguë : calée dans la continuité de la section précédente, à vérifier",
            ]
        elif s["ambiguous"]:
            row = [
                s["name"],
                amount(s["lag"] * 1000, period),
                f"ambiguë (écart de {s['spread'] * 1000:.0f} ms) : à régler avec arr nudge",
            ]
        else:
            row = [s["name"], amount(s["lag"] * 1000, period), f"{s['windows']} fenêtre(s)"]
        if report["after"] is not None:
            a = after.get(s["name"])
            row.append("-" if not a or a["lag"] is None else f"{a['lag'] * 1000:+.0f} ms")
        table.add_row(*row)
    Console().print(table)
    typer.echo(
        f"\n{take} : {report['before']:.0%} du morceau à moins de {TOLERANCE * 1000:.0f} ms de l'original avant calage"
        + (f", {report['after']:.0%} après" if report["after"] is not None else "")
    )
    typer.echo("+ : la prise est en retard sur l'original, - : en avance")


@app.command()
def align(
    take: str = typer.Argument(..., help="Prise à caler (ex. t001), déjà séparée par arr split."),
    report: bool = typer.Option(False, "--report", help="Mesure et affiche le décalage par section, sans rien régler."),
) -> None:
    """Cale les stems d'une prise sur l'original, section par section.

    Mesure le décalage de la prise (harmonie, puis attaques) et l'inscrit comme réglages de
    calage sur chacun de ses stems : arr nudge les montre, les ajuste ou les annule. Relancer
    remplace les réglages automatiques, jamais ceux posés à la main.
    """
    p = Project.find()
    p.take_path(take)
    print_report(p, take, align_take(p, take, write=not report))
    if not report:
        typer.echo(f"réglages inscrits sur les stems de {take} : arr nudge {take}")
