"""Pistes et mix : séparer, fusionner, lister, retirer, régler, écouter."""

from __future__ import annotations

import json
from typing import Optional

import numpy as np
import typer

from arr import audio
from arr.app import ANALYSIS, MAX_STRETCH, ORIGINAL, app
from arr.commands._common import (
    add_track,
    confirm,
    created,
    describe,
    lead_in,
    original_beats,
    render_mix,
)
from arr.project import Project, ProjectError


def align_to_original(p: Project, take: str, stems: dict) -> tuple[dict, dict]:
    """Met les stems d'une prise au tempo exact de l'original et les cale sur ses temps.

    Un écart de tempo de 0,1 % suffit à décaler la fin du morceau : on étire toujours.
    """
    from arr import measure
    from arr.engines import analysis

    ref = original_beats(p)
    original = p.root / ORIGINAL
    if ref is None or not original.exists():
        return stems, {}
    fit = measure.beat_fit(analysis.beats(p.take_path(take))[0], ref)
    speed, offset, on_beat = fit["speed"], fit["offset"], fit["on_beat"]
    if abs(speed - 1) > MAX_STRETCH:
        typer.secho(
            f"attention : {take} est à un autre tempo que l'original ({1 / speed:.2f} fois) ; "
            "ses stems ne sont pas superposables",
            fg="yellow",
            err=True,
        )
        return stems, {"superposable": False}
    n = len(audio.load(original))
    aligned = {k: audio.fit(audio.shift(audio.stretch(v, speed), -offset), n) for k, v in stems.items()}
    if on_beat < 0.6:
        typer.secho(
            f"attention : {take} ne suit pas la grille de l'original ({on_beat:.0%} des temps calés) ; "
            "la greffe sonnera décalée",
            fg="yellow",
            err=True,
        )
    return aligned, {
        "superposable": on_beat >= 0.6,
        "on_beat": round(on_beat, 2),
        "offset_ms": round(offset * 1000),
        "speed": round(speed, 5),
    }


@app.command()
def split(
    take: Optional[str] = typer.Argument(None, help="Prise à séparer (ex. t001) ; sinon l'original."),
    model: str = typer.Option("htdemucs_6s", help="htdemucs_6s : 6 stems ; htdemucs_ft : 4 stems, plus précis."),
    shifts: int = typer.Option(1, help="Passes moyennées : 2 ou plus réduit les fuites, temps multiplié d'autant."),
) -> None:
    """Sépare l'original ou une prise en stems.

    Les stems de l'original deviennent les pistes drums, bass... Ceux d'une prise deviennent
    t001.drums, t001.bass..., muets et calés sur l'original : `arr graft` les fait entendre.
    """
    from arr.engines.separation import MODELS, separate

    p = Project.find()
    if model not in MODELS:
        raise ProjectError(f"modèle inconnu : {model} (connus : {', '.join(MODELS)})")
    source = p.take_path(take) if take else p.root / ORIGINAL
    if not source.exists():
        raise ProjectError(f"{source} introuvable (arr import <fichier>)")
    meta = {"op": "split", "model": model, "source": str(source.relative_to(p.root))}
    stems = separate(source, model, shifts)
    if take:
        stems, alignment = align_to_original(p, take, stems)
        for name, data in stems.items():
            track = f"{take}.{name}"
            version = add_track(p, track, data, {**meta, **alignment})
            p.tracks[track].setdefault("mute", True)
            typer.echo(f"{track} {version}")
        p.save()
        return
    for name, data in stems.items():
        version = add_track(p, name, data, meta)
        typer.echo(f"{name} {version}")
    # Cette séparation remplace la précédente : ses stems et leurs fusions doubleraient le mix.
    for name, t in p.tracks.items():
        if name in stems:
            t["mute"] = False
        elif "." not in name and not t.get("mute") and p.meta(name, t["active"])["op"] in ("split", "merge"):
            t["mute"] = True
            typer.echo(f"{name} rendue muette (séparation précédente)")
    p.save()


@app.command()
def merge(
    tracks: list[str] = typer.Argument(..., help="Pistes à fusionner."),
    as_: str = typer.Option(..., "--as", help="Nom de la piste résultante."),
) -> None:
    """Fusionne des pistes en une seule, pour corriger une séparation qui a mal réparti un instrument."""
    p = Project.find()
    if len(tracks) < 2:
        raise ProjectError("il faut au moins deux pistes à fusionner")
    parts = [audio.load(p.version_path(t)) for t in tracks]
    parents = [f"{t}/{p.tracks[t]['active']}" for t in tracks]
    version = add_track(p, as_, np.sum(parts, axis=0), {"op": "merge", "source": " + ".join(parents)})
    typer.echo(f"{as_} {version}")
    for t in tracks:
        if t != as_:
            p.tracks[t]["mute"] = True
            typer.echo(f"{t} rendue muette")
    p.tracks[as_]["mute"] = False
    p.save()


@app.command()
def tracks(
    track: Optional[str] = typer.Argument(None, help="N'afficher que cette piste, avec son historique."),
    versions: bool = typer.Option(False, "--versions", "-v", help="Afficher l'historique de chaque piste."),
) -> None:
    """Montre ce qui joue dans le mix : pistes actives d'abord, muettes ensuite."""
    from rich.console import Console
    from rich.table import Table

    p = Project.find()
    if track:
        p.version_path(track)
    names = [track] if track else sorted(p.tracks, key=lambda n: bool(p.tracks[n].get("mute")))
    history = versions or bool(track)

    table = Table(box=None, pad_edge=False, header_style="bold")
    for column in ("", "Piste", "Version", "Gain", "Origine", "Créée"):
        table.add_column(column, no_wrap=column != "Origine")
    for name in names:
        t = p.tracks[name]
        muted = bool(t.get("mute"))
        all_versions = p.versions(name)
        mark = "[dim]○[/]" if muted else "[green]●[/]"
        level = "muette" if muted else f"{t.get('gain', 0.0):+.1f} dB"
        style = "dim" if muted else None
        if not history:
            meta = p.meta(name, t["active"])
            count = f" [dim]sur {len(all_versions)}[/]" if len(all_versions) > 1 else ""
            table.add_row(mark, name, t["active"] + count, level, describe(meta), created(meta), style=style)
            continue
        table.add_row(mark, f"[bold]{name}[/]", "", level, "", "", style=style)
        for v in all_versions:
            meta = p.meta(name, v)
            active = v == t["active"]
            table.add_row(
                "",
                "",
                f"▸ {v}" if active else f"  {v}",
                "",
                describe(meta),
                created(meta),
                style=style or (None if active else "dim"),
            )
    Console().print(table)

    if not track:
        audible = [n for n in names if not p.tracks[n].get("mute")]
        summary = f"Dans le mix : {', '.join(audible) or 'rien'}"
        if len(audible) < len(names):
            n = len(names) - len(audible)
            summary += f"  ·  {n} muette{'s' if n > 1 else ''}"
        typer.echo(f"\n{summary}")


@app.command()
def rm(
    names: list[str] = typer.Argument(..., help="Pistes ou prises à retirer (ex. guitar piano t002)."),
    version: Optional[str] = typer.Option(None, "--version", "-v", help="Ne retirer que cette version d'une piste."),
    purge: bool = typer.Option(False, "--purge", help="Efface définitivement au lieu de mettre à la corbeille."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Ne demande pas de confirmation pour --purge."),
) -> None:
    """Retire des pistes, une version ou des prises dont tu n'as plus besoin.

    Par défaut tout part dans la corbeille du projet (trash/), d'où on peut le reprendre à la
    main. --purge libère la place tout de suite ; `arr rm --purge trash` vide la corbeille.
    """
    import shutil

    p = Project.find()
    if names == ["trash"]:
        trash = p.root / "trash"
        if not purge:
            raise ProjectError("pour vider la corbeille : arr rm --purge trash")
        if trash.exists() and (yes or confirm(f"vider définitivement {trash} ?")):
            shutil.rmtree(trash)
            typer.echo("corbeille vidée")
        return
    if version and len(names) != 1:
        raise ProjectError("--version s'applique à une seule piste")
    for name in names:  # tout vérifier avant de toucher à quoi que ce soit
        p.take_path(name) if name in p.takes() else p.version_path(name, version)
    if purge and not yes:
        what = f"{names[0]} {version}" if version else ", ".join(names)
        if not confirm(f"effacer définitivement {what} ?"):
            raise typer.Exit(1)
    for name in names:
        if name in p.takes():
            stems = [t for t in p.tracks if t.startswith(f"{name}.")]
            p.remove_take(name, purge=purge)
            typer.echo(f"{name} retirée" + (f" avec ses stems ({len(stems)})" if stems else ""))
            continue
        p.remove(name, version, purge=purge)
        if name in p.tracks:
            typer.echo(f"{name} {version} retirée ; version active : {p.tracks[name]['active']}")
        else:
            typer.echo(f"{name} retirée")
    if not purge:
        typer.echo("dans la corbeille du projet (trash/) ; arr rm --purge trash pour la vider")


@app.command()
def pick(
    track: str = typer.Argument(..., help="Piste dont on change la version active."),
    version: str = typer.Argument(..., help="Version à rendre active (ex. v002) ; arr tracks PISTE les liste."),
) -> None:
    """Choisit la version active d'une piste."""
    p = Project.find()
    p.version_path(track, version)
    p.activate(track, version)
    typer.echo(f"{track} -> {version}")


# Sans ignore_unknown_options, « arr gain bass -5 » prend -5 pour une option.
@app.command(context_settings={"ignore_unknown_options": True})
def gain(
    track: str = typer.Argument(..., help="Piste à régler."),
    db: float = typer.Argument(..., help="Gain en dB, par rapport à la piste telle quelle : -5, 0, +3."),
) -> None:
    """Règle le volume d'une piste dans le mix, en dB."""
    p = Project.find()
    p.version_path(track)
    p.tracks[track]["gain"] = db
    p.save()
    typer.echo(f"{track} : {db:+.1f} dB")


@app.command()
def mute(
    track: str = typer.Argument(..., help="Piste à sortir du mix."),
    off: bool = typer.Option(False, "--off", help="Réactive la piste."),
) -> None:
    """Sort une piste du mix sans la supprimer."""
    p = Project.find()
    p.version_path(track)
    p.tracks[track]["mute"] = not off
    p.save()


@app.command()
def mix(
    without: list[str] = typer.Option([], "--without", "-w", help="Piste à exclure."),
    only: list[str] = typer.Option([], "--only", "-o", help="Ne garder que ces pistes."),
) -> None:
    """Mixe les versions actives dans mix/mix.flac."""
    p = Project.find()
    typer.echo(render_mix(p, tuple(without), tuple(only)))


@app.command()
def play(
    name: Optional[str] = typer.Argument(None, help="Piste ou prise (ex. t001) ; sinon le mix."),
    version: Optional[str] = typer.Argument(None, help="Version d'une piste ; sinon la version active."),
    without: list[str] = typer.Option(
        [], "--without", "-w", help="Mix sans cette piste (ex. -w bass pour jouer par-dessus)."
    ),
    only: list[str] = typer.Option([], "--only", "-o", help="Mix de ces seules pistes."),
    sections: list[str] = typer.Option(
        [],
        "--section",
        "-s",
        help="Sections à jouer, enchaînées dans l'ordre donné : -s verse,chorus ou -s verse -s chorus.",
    ),
    loop: bool = typer.Option(False, "--loop", "-l", help="Rejoue en boucle jusqu'à Ctrl+C."),
    bars: int = typer.Option(0, "--count-in", help="Mesures de décompte avant de commencer (pas à chaque boucle)."),
) -> None:
    """Écoute le mix (complet ou partiel), une piste ou une prise, en entier ou par sections.

    Ctrl+C arrête.
    """
    from arr import studio

    p = Project.find()
    sections = [name.strip() for given in sections for name in given.split(",") if name.strip()]
    ranges = [(s.start, s.end) for s in map(p.section, sections)]
    if name is None:
        path = render_mix(p, tuple(without), tuple(only))
    elif name in p.takes():
        if sections or bars:
            raise ProjectError(
                f"une prise brute n'est pas calée sur l'original : ni section ni décompte "
                f"(arr split {name}, puis arr play {name}.<stem>)"
            )
        path = p.take_path(name)
    else:
        path = p.version_path(name, version)
    body = audio.load(path)
    if ranges:
        body = audio.cut(body, ranges)
        if not len(body):
            raise ProjectError("rien à jouer : ces sections sont hors du morceau")
    ticks: list[tuple[float, bool]] = []
    if bars:
        start = ranges[0][0] if ranges else 0.0
        grid = json.loads(f.read_text()) if (f := p.root / ANALYSIS).exists() else {"beats": [], "downbeats": []}
        beats, strong = ([t - start for t in grid[k] if t >= start - 0.05] for k in ("beats", "downbeats"))
        if len(beats) > 1:
            ticks = audio.count_in(beats, strong, bars)
        else:
            typer.secho("pas de décompte : le tempo est inconnu (arr transcribe ou arr analyze)", fg="yellow", err=True)
    playback, _ = lead_in(body, ticks)
    what = " → ".join(sections) or "morceau entier"
    typer.echo(f"{what}  ({len(body) / audio.SR:.1f} s){', en boucle' if loop else ''} ; Ctrl+C arrête")
    studio.play(playback, loop=body if loop else None)
