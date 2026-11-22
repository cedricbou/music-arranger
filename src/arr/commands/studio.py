"""Audio en direct : capturer ce que joue l'ordinateur, s'enregistrer, régler les niveaux."""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from arr import audio
from arr.app import ANALYSIS, ORIGINAL, app
from arr.commands._common import (
    add_track,
    folder_name,
    lead_in,
    load_track,
)
from arr.commands._screen import live, song_chart, timeline, view
from arr.project import Project, ProjectError


@app.command()
def capture(
    name: Optional[str] = typer.Argument(
        None,
        help="Nom du projet à créer ; par défaut, l'artiste et le titre lus dans Spotify (paper-lanterns--night-drive).",
    ),
    play_: bool = typer.Option(
        False, "--play", help="Relance le morceau Spotify courant depuis le début, et met en pause à la fin."
    ),
    silence: float = typer.Option(3.0, help="Secondes de silence qui terminent l'enregistrement."),
    raw: bool = typer.Option(
        False, "--raw", help="Garde le niveau tel qu'enregistré, sans le ramener au volume cible."
    ),
) -> None:
    """Enregistre ce que joue l'ordinateur dans un nouveau projet.

    Le volume est ramené à une cible commune (-16 LUFS par défaut), pour que toutes les
    captures soient au même niveau quel que soit le gain réglé sur la table ce jour-là.

    L'enregistrement démarre tout seul au premier son et s'arrête à la fin du morceau
    (changement de titre dans Spotify, ou silence). Ctrl+C arrête aussi.
    """
    from arr import spotify, studio

    cfg = studio.config()["capture"]
    if name and (Path(name) / "song.toml").exists():
        raise ProjectError(f"{name} contient déjà un projet")
    source, count = studio.capture_source()
    state = {"track": None, "checked": 0.0}
    if play_:
        current = spotify.now_playing()
        if not current:
            raise ProjectError("Spotify ne répond pas : lance la lecture à la main, sans --play")
        spotify.restart(current["id"])

    def started() -> None:
        state["track"] = spotify.now_playing(playing_only=True)
        label = f" : {state['track']['artist']} - {state['track']['title']}" if state["track"] else ""
        typer.echo(f"enregistrement{label}")

    def track_changed() -> bool:
        if not state["track"] or time.monotonic() - state["checked"] < 0.5:
            return False
        state["checked"] = time.monotonic()
        now = spotify.now_playing()
        return now is not None and now["id"] != state["track"]["id"]

    picked = f"canaux {cfg['channels']}" if cfg["channels"] else "canaux automatiques"
    typer.echo(f"en attente du son sur {source}, {picked} (lance la lecture ; Ctrl+C pour arrêter)")
    typer.echo("si rien ne démarre : arr levels montre le niveau de chaque canal")
    captured = studio.gate(studio.listen(source, count), silence=silence, should_stop=track_changed, on_start=started)
    if play_:
        spotify.pause()
    data = studio.stereo(captured, cfg["channels"])
    track = state["track"]
    if track and track["length"]:
        data = data[: int((track["length"] + 1.0) * audio.SR)]  # coupe le début du morceau suivant
    name = name or (folder_name(track["title"], track["artist"]) if track else None)
    if not name:
        raise ProjectError("donne un nom de projet : arr capture <nom>")
    p = Project.create(Path(name), track["title"] if track else name)
    if track:
        p.song["artist"] = track["artist"]
    if not raw:
        data, applied = audio.normalize(data, cfg["loudness"])
        typer.echo(f"volume ramené à {cfg['loudness']:g} LUFS ({applied:+.1f} dB)")
    audio.save(p.root / ORIGINAL, data)
    p.song["duration"] = round(len(data) / audio.SR, 3)
    p.save()
    typer.echo(f"projet créé : {p.root}  ({len(data) / audio.SR:.1f} s)  ->  cd {p.root} && arr transcribe")


@app.command()
def record(
    track: str = typer.Argument(..., help="Piste à enregistrer (ex. bass) ; une nouvelle version est créée."),
    without: list[str] = typer.Option([], "--without", "-w", help="Piste à retirer du playback."),
    only: list[str] = typer.Option([], "--only", "-o", help="Playback réduit à ces pistes."),
    bars: int = typer.Option(1, "--count-in", help="Mesures de décompte avant le premier temps fort ; 0 pour aucun."),
    click: bool = typer.Option(False, "--click", help="Garde le métronome pendant tout le morceau."),
    channel: Optional[int] = typer.Option(None, help="Canal d'entrée de l'instrument ; sinon celui de audio.toml."),
) -> None:
    """Enregistre ton instrument pendant que le playback joue, avec un décompte au tempo.

    Le playback est le mix courant sans la piste enregistrée. L'écran est celui d'`arr play` :
    les pistes du playback, la section en cours et sa grille d'accords, l'accord du moment surligné.
    Ctrl+C arrête et garde la prise.
    """
    from arr import studio

    p = Project.find()
    names = [
        t for t in p.tracks if t != track and t not in without and (t in only if only else not p.tracks[t].get("mute"))
    ]
    if names:
        backing = audio.mix([(load_track(p, t), p.tracks[t].get("gain", 0.0)) for t in names])
    elif (p.root / ORIGINAL).exists():
        backing = audio.load(p.root / ORIGINAL)
    else:
        raise ProjectError("rien à jouer : ni piste ni morceau original")
    ticks: list[tuple[float, bool]] = []
    analysis = p.root / ANALYSIS
    if analysis.exists():
        grid = json.loads(analysis.read_text())
        ticks = audio.count_in(grid["beats"], grid["downbeats"], bars) if bars else []
        if click:
            ticks += [(b, b in grid["downbeats"]) for b in grid["beats"]]
    elif bars or click:
        typer.secho("pas de décompte : le tempo est inconnu (arr transcribe ou arr analyze)", fg="yellow", err=True)
    playback, lead = lead_in(backing, ticks)
    marks, measures = timeline(p, None, [], []), song_chart(p)
    notes = [] if names else ["[dim]playback : morceau original[/]"]

    def screen(seconds: float):
        return view(
            p,
            f"Enregistrement de {track}",
            names,
            marks,
            len(backing) / audio.SR,
            "Ctrl+C arrête et garde la prise",
            seconds - lead / audio.SR,
            bars=measures,
            notes=notes,
            recording=True,
        )

    with live(screen) as shown:
        recorded, latency = studio.play_and_record(playback, channel, lambda seconds: shown.update(screen(seconds)))
    take = audio.fit(recorded[lead + int(round(latency * audio.SR)) :], len(backing))
    if float(np.abs(take).max()) < audio.db(-60):
        raise ProjectError(
            "rien n'a été enregistré sur ce canal : la prise n'est pas gardée "
            "(arr levels montre le niveau de chaque canal)"
        )
    version = add_track(
        p, track, take, {"op": "record", "source": " + ".join(names) or ORIGINAL, "latency_ms": round(latency * 1000)}
    )
    p.tracks[track]["mute"] = False
    p.save()
    typer.echo(f"{track} {version}  (latence compensée : {latency * 1000:.0f} ms)")


@app.command()
def calibrate(
    channel: Optional[int] = typer.Option(None, help="Canal d'entrée relié à la sortie ; sinon celui de audio.toml."),
) -> None:
    """Mesure le retard entre ce qui est joué et ce qui est enregistré, pour caler tes prises.

    Joue quelques clics et les réenregistre sur le canal où revient le son de l'ordinateur
    (7 par défaut avec la Soundcraft), puis note la latence dans audio.toml.
    """
    from arr import studio

    ticks = [(0.5 + 0.4 * i, i == 0) for i in range(6)]
    playback = audio.add_clicks(np.zeros((3 * audio.SR, 2), np.float32), ticks)
    back = studio.config()["capture"]["channels"]
    if channel is None and back and not studio.capture_source()[0].endswith(".monitor"):
        channel = back[0]  # la sortie de l'ordinateur revient déjà sur ce canal : pas de câble à ajouter
    recorded, _ = studio.play_and_record(playback, channel)
    latency = studio.measure_latency(playback, recorded)
    studio.save_latency(latency)
    typer.echo(f"latence mesurée : {latency * 1000:.1f} ms, notée dans {studio.CONFIG}")


def bar(db: float, width: int = 30) -> str:
    filled = int(round(np.clip((db + 60) / 60, 0, 1) * width))
    return "█" * filled + "·" * (width - filled)


def verdict(db: float) -> str:
    if db >= -0.5:
        return "SATURE : baisse le gain"
    if db >= -3:
        return "très fort"
    if db >= -18:
        return "bon niveau"
    if db >= -40:
        return "faible : monte le gain"
    return "rien"


@app.command()
def levels(
    seconds: Optional[float] = typer.Option(None, help="Durée de la mesure ; sinon jusqu'à Ctrl+C."),
    tone: bool = typer.Option(
        False, "--tone", help="Joue un son de référence à -12 dB sur la sortie pendant la mesure."
    ),
    source: Optional[str] = typer.Option(None, help="Source PipeWire à mesurer ; sinon celle de arr capture."),
) -> None:
    """Vumètres par canal, pour vérifier le câblage et régler le gain sur la table.

    Lance Spotify (ou --tone), regarde quels canaux bougent et règle le gain pour que les
    crêtes arrivent entre -18 et -3 dB. Ctrl+C affiche le bilan.
    """
    from rich.live import Live
    from rich.text import Text

    from arr import studio

    cfg = studio.config()
    name, count = (source, dict(studio.sources()).get(source)) if source else studio.capture_source()
    if count is None:
        raise ProjectError(f"source PipeWire introuvable : {source} (arr devices)")
    used = set(cfg["capture"]["channels"]) if not source else set()
    typer.echo(f"source : {name}  ({count} canaux)")
    t = np.arange(audio.SR) / audio.SR
    wave = (audio.db(-12) * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    playing = studio.looping(np.stack([wave, wave], axis=1)) if tone else contextlib.nullcontext()

    def view(now, held) -> Text:
        return Text(
            "\n".join(
                f"{'▶' if i + 1 in used else ' '} {i + 1:2d} {bar(now[i])} {now[i]:6.1f} dB  crête {held[i]:6.1f}"
                for i in range(count)
            )
        )

    with playing, Live(Text("en attente..."), refresh_per_second=10, transient=True) as live:
        held = studio.peaks(studio.listen(name, count), seconds, lambda now, held: live.update(view(now, held)))
    for i in range(count):
        mark = "▶" if i + 1 in used else " "
        typer.echo(f"{mark} canal {i + 1:2d}  crête {held[i]:6.1f} dB  {verdict(held[i])}")
    if used:
        typer.echo(f"▶ canaux utilisés par arr capture : {sorted(used)}")
