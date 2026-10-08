"""Prises complètes : rendre, lister, greffer sur l'original, partager."""

from __future__ import annotations

import typer

from arr import audio
from arr.app import LYRICS, SCORE, app
from arr.commands._common import (
    created,
)
from arr.project import Project, ProjectError


@app.command()
def render(
    style: str = typer.Option(
        ..., "--style", "-s", help="Formation et couleur, en anglais : genre, instruments, voix."
    ),
    free: bool = typer.Option(False, "--free", help="Mélodie seule : accompagnement réinventé, tempo libre."),
    seed: int = typer.Option(-1, help="Graine ; -1 pour aléatoire."),
    n: int = typer.Option(1, "-n", help="Nombre de prises."),
) -> None:
    """Rend une prise complète du morceau (voix et groupe) à partir de la partition.

    Par défaut la prise est fidèle : mélodie et accords imposés, même tempo et mêmes mesures
    que l'original, donc ses stems peuvent y être greffés.
    """
    from arr.engines import yue2

    p = Project.find()
    score = p.root / SCORE
    if not score.exists():
        raise ProjectError("pas de partition (arr transcribe)")
    words = p.root / LYRICS
    if not words.exists():
        typer.secho(f"pas de {LYRICS} : la prise sera instrumentale", fg="yellow", err=True)
    text = words.read_text() if words.exists() else ""
    for i in range(n):
        tmp = p.root / "takes" / "rendu.wav"
        tmp.parent.mkdir(exist_ok=True)
        meta = yue2.render(score.read_text(), text, style, tmp, free=free, seed=seed if seed < 0 else seed + i)
        name, path = p.new_take({**meta, "score": SCORE, "instrumental": not text})
        audio.convert(tmp, path)
        tmp.unlink()
        typer.echo(f"{name}  ({'libre' if free else 'fidèle'}, graine {meta['seed']}, {audio.duration(path):.1f} s)")


@app.command()
def takes() -> None:
    """Liste les prises."""
    from rich.console import Console
    from rich.table import Table

    p = Project.find()
    table = Table(box=None, pad_edge=False, header_style="bold")
    for column in ("Prise", "Mode", "Graine", "Durée", "Créée", "Style"):
        table.add_column(column, no_wrap=column != "Style")
    for name in p.takes():
        m = p.take_meta(name)
        table.add_row(
            name,
            "libre" if m["mode"] == "free" else "fidèle",
            str(m["seed"]),
            f"{audio.duration(p.take_path(name)):.0f} s",
            created(m),
            m["style"],
        )
    Console().print(table)


@app.command()
def graft(
    take: str,
    stems: list[str] = typer.Argument(..., help="Stems de la prise à faire entendre : guitar, drums..."),
    replace: bool = typer.Option(False, "--replace", help="Coupe les mêmes stems de l'original."),
) -> None:
    """Greffe des stems d'une prise sur le mix : en plus de l'original, ou à sa place."""
    p = Project.find()
    p.take_path(take)
    if not any(t.startswith(f"{take}.") for t in p.tracks):
        raise ProjectError(f"{take} n'est pas encore séparée (arr split {take})")
    for stem in stems:
        track = f"{take}.{stem}"
        p.version_path(track)
        p.tracks[track]["mute"] = False
        typer.echo(f"{track} dans le mix")
        if replace and stem in p.tracks:
            p.tracks[stem]["mute"] = True
            typer.echo(f"{stem} (original) rendue muette")
    p.save()


@app.command()
def share(track: str) -> None:
    """Prépare un dossier pour le musicien : sa partie seule, le mix, et le mix sans lui."""
    p = Project.find()
    part = audio.load(p.version_path(track))
    others = [
        (audio.load(p.version_path(t)), p.tracks[t].get("gain", 0.0))
        for t in p.tracks
        if t != track and not p.tracks[t].get("mute")
    ]
    if not others:
        raise ProjectError("aucune autre piste dans le mix")
    out = p.root / "export" / track
    gain = p.tracks[track].get("gain", 0.0)
    audio.save_mp3(out / "partie.mp3", part)
    audio.save_mp3(out / "mix.mp3", audio.mix([*others, (part, gain)]))
    audio.save_mp3(out / "sans.mp3", audio.mix(others))
    typer.echo(f"{out.relative_to(p.root)}/ : partie.mp3, mix.mp3, sans.mp3")
