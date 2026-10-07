"""Partition, paroles, sections et analyse du morceau."""

from __future__ import annotations

import json
from typing import Optional

import typer

from arr import audio
from arr.app import ANALYSIS, LYRICS, ORIGINAL, SCORE, app, lyrics_app, sections_app
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
    bpm = round(60 / analysis.period(beats))
    transcription.set_tempo(out, bpm)
    (p.root / ANALYSIS).write_text(json.dumps({"beats": beats, "downbeats": downbeats}))
    p.song.update(bpm=bpm, key=info["key"], duration=round(audio.duration(original), 3))
    p.set_sections([Section(name, start, end) for name, start, end in info["sections"]])
    p.save()
    typer.echo(f"bpm {bpm}  tonalité {info['key']}  {len(downbeats)} mesures  -> {SCORE}")
    sections_list()


@lyrics_app.command("fetch")
def lyrics_fetch(
    artist: Optional[str] = typer.Argument(None, help="Par défaut, l'artiste du projet."),
    title: Optional[str] = typer.Argument(None, help="Par défaut, le titre du projet."),
    force: bool = typer.Option(False, "--force", help="Remplace un lyrics.txt existant."),
) -> None:
    """Télécharge les paroles depuis LRCLIB et les range par section dans lyrics.txt."""
    from arr import lyrics
    from arr.engines.transcription import first_sung

    p = Project.find()
    target = p.root / LYRICS
    if target.exists() and not force:
        raise ProjectError(f"{LYRICS} existe déjà (--force pour le remplacer)")
    artist, title = artist or p.song.get("artist"), title or p.song.get("title")
    if not artist or not title:
        raise ProjectError("donne l'artiste et le titre : arr lyrics fetch ARTISTE TITRE")
    found = lyrics.fetch(artist, title)
    if found.get("syncedLyrics") and p.sections:
        target.write_text(lyrics.tagged(found["syncedLyrics"], p.sections, first_sung(p.root / "score")))
        typer.echo(f"{LYRICS} : paroles rangées dans {len(p.sections)} sections ; relis et corrige le découpage")
    else:
        target.write_text(found["plainLyrics"].strip() + "\n")
        why = "pas de sections (arr transcribe d'abord)" if not p.sections else "paroles non horodatées"
        typer.secho(
            f"{LYRICS} : paroles brutes, {why} ; ajoute les balises [Verse], [Chorus]... à la main", fg="yellow"
        )


@sections_app.command("set")
def sections_set(spec: str = typer.Argument(..., help='Ex. "intro:1-8 couplet:9-24 refrain:25-40".')) -> None:
    """Définit les sections en numéros de mesure (inclusifs, à partir de 1)."""
    p = Project.find()
    bars = downbeats(p)
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


@sections_app.command("list")
def sections_list() -> None:
    """Affiche les sections."""
    p = Project.find()
    for s in p.sections:
        typer.echo(f"{s.name:<12} {s.start:7.2f} s -> {s.end:7.2f} s")
