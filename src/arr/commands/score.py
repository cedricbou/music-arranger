"""Partition, paroles, sections et analyse du morceau."""

from __future__ import annotations

import json
from typing import Optional

import typer

from arr import audio
from arr.app import ANALYSIS, LYRICS, LYRICS_TIMES, ORIGINAL, SCORE, app, lyrics_app, sections_app
from arr.commands._common import (
    downbeats,
    reference,
)
from arr.project import Project, ProjectError, Section


@app.command()
def analyze() -> None:
    """Détecte temps, mesures, tempo et tonalité."""
    from arr.engines import analysis

    p = Project.find()
    ref = reference(p)
    beats, downbeats = analysis.beats(ref)
    (p.root / ANALYSIS).write_text(json.dumps({"beats": beats, "downbeats": downbeats}))
    p.song["bpm"] = analysis.tempo(beats)
    p.song["key"] = analysis.key(ref)
    p.song["duration"] = round(audio.duration(ref), 3)
    p.save()
    typer.echo(f"bpm {p.song['bpm']}  tonalité {p.song['key']}  {len(downbeats)} mesures")


@app.command()
def transcribe() -> None:
    """Transcrit l'original en partition : mélodie, accords, tempo, tonalité, sections."""
    from arr import measure
    from arr.engines import analysis, transcription

    p = Project.find()
    original = p.root / ORIGINAL
    if not original.exists():
        raise ProjectError("pas de morceau original (arr import <fichier>)")
    typer.echo("transcription en cours (quelques minutes pour un morceau entier)...")
    out = p.root / "score"
    transcription.transcribe(original, out)
    info = transcription.read(out)
    # Le tempo de la partition fixe celui des prises : on le mesure sur l'audio, au BPM près,
    # car SheetSage2 peut se tromper d'une unité et les prises dériveraient.
    beats, downbeats = analysis.beats(original)
    bpm = round(60 / measure.period(beats))
    transcription.set_tempo(out, bpm)
    (p.root / ANALYSIS).write_text(json.dumps({"beats": beats, "downbeats": downbeats}))
    p.song.update(bpm=bpm, key=info["key"], duration=round(audio.duration(original), 3))
    p.set_sections([Section(*s) for s in measure.snap_sections(info["sections"], downbeats)])
    p.save()
    typer.echo(f"bpm {bpm}  tonalité {info['key']}  {len(downbeats)} mesures  -> {SCORE}")
    sections_list()


@lyrics_app.command("fetch")
def lyrics_fetch(
    artist: Optional[str] = typer.Argument(None, help="Par défaut, l'artiste du projet."),
    title: Optional[str] = typer.Argument(None, help="Par défaut, le titre du projet."),
    force: bool = typer.Option(False, "--force", help="Remplace un lyrics.txt existant."),
    times: bool = typer.Option(
        False, "--times", help="N'écrit que lyrics.lrc, les instants de chaque ligne : lyrics.txt reste tel quel."
    ),
) -> None:
    """Télécharge les paroles depuis LRCLIB et les range par section dans lyrics.txt.

    Les paroles horodatées sont gardées telles quelles dans lyrics.lrc : elles disent sur
    quelle mesure chaque ligne est chantée (`arr lyrics show`).
    """
    from arr import lyrics
    from arr.engines.transcription import first_sung

    p = Project.find()
    target, stamps = p.root / LYRICS, p.root / LYRICS_TIMES
    if target.exists() and not force and not times:
        raise ProjectError(f"{LYRICS} existe déjà (--force pour le remplacer, --times pour n'ajouter que les instants)")
    artist, title = artist or p.song.get("artist"), title or p.song.get("title")
    if not artist or not title:
        raise ProjectError("donne l'artiste et le titre : arr lyrics fetch ARTISTE TITRE")
    found = lyrics.fetch(artist, title)
    synced = found.get("syncedLyrics")
    if synced:
        stamps.write_text(synced.strip() + "\n")
    if times:
        if not synced:
            raise ProjectError(
                f"LRCLIB n'a pas d'horodatage pour {artist} - {title} : les lignes resteront sans mesure"
            )
        typer.echo(f"{LYRICS_TIMES} : {len(lyrics.timed(synced))} lignes horodatées ; {LYRICS} inchangé")
    elif synced and p.sections:
        target.write_text(lyrics.tagged(synced, p.sections, first_sung(p.root / "score")))
        typer.echo(f"{LYRICS} : paroles rangées dans {len(p.sections)} sections ; relis et corrige le découpage")
    else:
        target.write_text(found["plainLyrics"].strip() + "\n")
        why = "pas de sections (arr transcribe d'abord)" if not p.sections else "paroles non horodatées"
        typer.secho(
            f"{LYRICS} : paroles brutes, {why} ; ajoute les balises [Verse], [Chorus]... à la main", fg="yellow"
        )


@lyrics_app.command("show")
def lyrics_show() -> None:
    """Montre les paroles section par section, chaque ligne avec la mesure où elle commence."""
    from arr import lyrics, measure
    from arr.engines.transcription import first_sung

    p = Project.find()
    target, stamps = p.root / LYRICS, p.root / LYRICS_TIMES
    if not target.exists():
        raise ProjectError(f"pas de {LYRICS} : lance arr lyrics fetch")
    synced = stamps.read_text() if stamps.exists() else None
    parts = lyrics.placed(target.read_text(), synced, p.sections, first_sung(p.root / "score"))
    if parts is None:
        found = len(lyrics.blocks(target.read_text()))
        raise ProjectError(
            f"{LYRICS} a {found} balises pour {len(p.sections)} sections : une balise par section, dans l'ordre"
        )
    bars = measure.steady_bars(downbeats(p))
    untimed = 0
    for s, part in zip(p.sections, parts, strict=True):
        typer.secho(s.name, bold=True)
        for text, t in part:
            if t is None:
                untimed += 1
            where = "   —   " if t is None else f"mes. {max(1, sum(b <= t for b in bars)):<3}"
            typer.echo(f"  {where} {text}")
    total = sum(len(part) for part in parts)
    if not synced:
        typer.secho(f"{total} lignes sans instant : arr lyrics fetch --times pour les placer", fg="yellow")
    elif untimed:
        typer.secho(
            f"{untimed} ligne(s) sur {total} sans instant (ajoutées à la main, ou absentes de {LYRICS_TIMES})",
            fg="yellow",
        )


@sections_app.command("set")
def sections_set(spec: str = typer.Argument(..., help='Ex. "intro:1-8 couplet:9-24 refrain:25-40".')) -> None:
    """Définit les sections en numéros de mesure (inclusifs, à partir de 1)."""
    from arr import measure

    p = Project.find()
    bars = measure.steady_bars(downbeats(p))
    ends = bars[1:] + [p.song["duration"]]
    out = []
    for item in spec.split():
        name, _, span = item.partition(":")
        first, _, last = span.partition("-")
        first, last = int(first), int(last or first)
        if not 1 <= first <= last <= len(bars):
            raise ProjectError(f"{item} : les mesures vont de 1 à {len(bars)}")
        out.append(Section(name, round(bars[first - 1], 3), round(ends[last - 1], 3)))
    p.set_sections(out)
    p.save()
    sections_list()


@sections_app.command("snap")
def sections_snap() -> None:
    """Pose les bornes des sections sur les barres de mesure, pour des boucles qui retombent juste.

    `arr transcribe` le fait déjà ; cette commande sert aux projets transcrits avant, ou après
    un nouvel `arr analyze`.
    """
    from arr import measure

    p = Project.find()
    before = [(s.name, s.start, s.end) for s in p.sections]
    if not before:
        raise ProjectError("pas de sections (arr transcribe ou arr sections set)")
    after = measure.snap_sections(before, downbeats(p))
    p.set_sections([Section(*s) for s in after])
    p.save()
    sections_list()
    kept = {s[0] for s in after}
    moved = max((abs(a[1] - b[1]) for a in after for b in before if a[0] == b[0]), default=0.0)
    typer.echo(f"bornes déplacées de {moved * 1000:.0f} ms au plus")
    if gone := [s[0] for s in before if s[0] not in kept]:
        typer.secho(f"plus courtes qu'une mesure, retirées : {', '.join(gone)}", fg="yellow", err=True)


@sections_app.command("list")
def sections_list() -> None:
    """Affiche les sections."""
    p = Project.find()
    for s in p.sections:
        typer.echo(f"{s.name:<12} {s.start:7.2f} s -> {s.end:7.2f} s")
