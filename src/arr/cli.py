from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from arr import audio, engines
from arr.project import Project, ProjectError, Section

app = typer.Typer(help="Réarranger un morceau : partition, prises complètes, greffe de stems.", no_args_is_help=True)
sections_app = typer.Typer(help="Parties du morceau (intro, couplet, refrain...).", no_args_is_help=True)
models_app = typer.Typer(help="Poids des modèles.", no_args_is_help=True)
lyrics_app = typer.Typer(help="Paroles du morceau.", no_args_is_help=True)
app.add_typer(sections_app, name="sections")
app.add_typer(lyrics_app, name="lyrics")
app.add_typer(models_app, name="models")

ORIGINAL = "source/original.flac"
ANALYSIS = "analysis.json"
SCORE = "score/score.abc"
LYRICS = "lyrics.txt"
ON_BEAT = 0.035     # un temps de la prise est « calé » s'il tombe à moins de 35 ms d'un temps de l'original
MAX_STRETCH = 0.03  # au-delà de 3 % d'écart de tempo, une prise n'est plus la même interprétation


def run() -> None:
    try:
        app()
    except ProjectError as e:
        typer.secho(f"erreur : {e}", fg="red", err=True)
        raise SystemExit(1)


@app.callback()
def main(ctx: typer.Context) -> None:
    # Les modèles ne touchent le réseau que dans `models pull` (`lyrics fetch` interroge LRCLIB).
    if ctx.invoked_subcommand != "models":
        engines.offline()


def reference(p: Project) -> Path:
    """Audio de référence du projet : l'original s'il existe, sinon le mix courant."""
    original = p.root / ORIGINAL
    return original if original.exists() else render_mix(p)


def render_mix(p: Project, without: tuple[str, ...] = (), only: tuple[str, ...] = ()) -> Path:
    names = [
        t for t in p.tracks
        if t not in without and (t in only if only else not p.tracks[t].get("mute"))
    ]
    if not names:
        raise ProjectError("aucune piste à mixer")
    parts = [(audio.load(p.version_path(t)), p.tracks[t].get("gain", 0.0)) for t in names]
    out = p.root / "mix" / "mix.flac"
    audio.save(out, audio.mix(parts))
    return out


def add_track(p: Project, track: str, data, meta: dict) -> str:
    version, path = p.new_version(track, meta)
    audio.save(path, data)
    p.activate(track, version)
    return version


def convert(source: Path, dst: Path) -> None:
    """Importe un fichier audio et prévient s'il ne contient que du silence."""
    audio.convert(source, dst)
    if float(np.abs(audio.load(dst)).max()) < audio.db(-60):
        typer.secho(f"attention : {source.name} est silencieux (niveau max sous -60 dB)", fg="yellow", err=True)


# --- projet


@app.command()
def init(name: str, source: Optional[Path] = typer.Option(None, "--from", help="Morceau à importer.")) -> None:
    """Crée un projet dans le dossier NAME."""
    p = Project.create(Path(name), name)
    typer.echo(f"projet créé : {p.root}")
    if source:
        convert(source, p.root / ORIGINAL)
        typer.echo(f"importé : {ORIGINAL} ({audio.duration(p.root / ORIGINAL):.1f} s)")


@app.command("import")
def import_(
    source: Path,
    track: Optional[str] = typer.Option(None, "--as", help="Importer comme piste (stem ou idée), ex. bass."),
) -> None:
    """Ajoute un morceau complet, ou une piste avec --as."""
    p = Project.find()
    if track is None:
        convert(source, p.root / ORIGINAL)
        typer.echo(f"importé : {ORIGINAL}")
        return
    tmp = p.root / "source" / f"{track}-{source.stem}.flac"
    convert(source, tmp)
    version = add_track(p, track, audio.load(tmp), {"op": "import", "source": str(tmp.relative_to(p.root))})
    typer.echo(f"{track} {version}")


def original_beats(p: Project) -> Optional[list[float]]:
    f = p.root / ANALYSIS
    return json.loads(f.read_text())["beats"] if f.exists() else None


def align_to_original(p: Project, take: str, stems: dict) -> tuple[dict, dict]:
    """Met les stems d'une prise au tempo exact de l'original et les cale sur ses temps.

    Un écart de tempo de 0,1 % suffit à décaler la fin du morceau : on étire toujours.
    """
    from arr.engines import analysis

    ref = original_beats(p)
    original = p.root / ORIGINAL
    if ref is None or not original.exists():
        return stems, {}
    mine = analysis.beats(p.take_path(take))[0]
    speed = analysis.period(mine) / analysis.period(ref)
    if abs(speed - 1) > MAX_STRETCH:
        typer.secho(f"attention : {take} est à un autre tempo que l'original ({1 / speed:.2f} fois) ; "
                    "ses stems ne sont pas superposables", fg="yellow", err=True)
        return stems, {"superposable": False}
    ref, mine = np.array(ref), np.array(mine) / speed
    offset = float(np.median([t - ref[np.abs(ref - t).argmin()] for t in mine]))
    on_beat = float(np.mean([np.abs(ref - (t - offset)).min() < ON_BEAT for t in mine]))
    n = len(audio.load(original))
    aligned = {k: audio.fit(audio.shift(audio.stretch(v, speed), -offset), n) for k, v in stems.items()}
    if on_beat < 0.6:
        typer.secho(f"attention : {take} ne suit pas la grille de l'original ({on_beat:.0%} des temps calés) ; "
                    "la greffe sonnera décalée", fg="yellow", err=True)
    return aligned, {"superposable": on_beat >= 0.6, "on_beat": round(on_beat, 2),
                     "offset_ms": round(offset * 1000), "speed": round(speed, 5)}


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


def describe(meta: dict) -> str:
    """Origine d'une version, en quelques mots."""
    op = meta["op"]
    detail = meta.get("model", "") if op == "split" else meta.get("source", "")
    return f"{op:<7} {detail}".rstrip()


def created(meta: dict) -> str:
    return datetime.fromisoformat(meta["created"]).strftime("%d/%m %H:%M")


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
            table.add_row("", "", f"▸ {v}" if active else f"  {v}", "", describe(meta), created(meta),
                          style=style or (None if active else "dim"))
    Console().print(table)

    if not track:
        audible = [n for n in names if not p.tracks[n].get("mute")]
        summary = f"Dans le mix : {', '.join(audible) or 'rien'}"
        if len(audible) < len(names):
            n = len(names) - len(audible)
            summary += f"  ·  {n} muette{'s' if n > 1 else ''}"
        typer.echo(f"\n{summary}")


@app.command()
def pick(track: str, version: str) -> None:
    """Choisit la version active d'une piste."""
    p = Project.find()
    p.version_path(track, version)
    p.activate(track, version)
    typer.echo(f"{track} -> {version}")


@app.command()
def gain(track: str, db: float) -> None:
    """Règle le volume d'une piste dans le mix, en dB."""
    p = Project.find()
    p.version_path(track)
    p.tracks[track]["gain"] = db
    p.save()


@app.command()
def mute(track: str, off: bool = typer.Option(False, "--off", help="Réactive la piste.")) -> None:
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
) -> None:
    """Écoute le mix, une piste ou une prise."""
    p = Project.find()
    if name is None:
        path = render_mix(p)
    elif name in p.takes():
        path = p.take_path(name)
    else:
        path = p.version_path(name, version)
    subprocess.run(["ffplay", "-v", "error", "-nodisp", "-autoexit", str(path)])


# --- partition et paroles


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
    artist: str, title: str,
    force: bool = typer.Option(False, "--force", help="Remplace un lyrics.txt existant."),
) -> None:
    """Télécharge les paroles depuis LRCLIB et les range par section dans lyrics.txt."""
    from arr import lyrics
    from arr.engines.transcription import first_sung

    p = Project.find()
    target = p.root / LYRICS
    if target.exists() and not force:
        raise ProjectError(f"{LYRICS} existe déjà (--force pour le remplacer)")
    found = lyrics.fetch(artist, title)
    if found.get("syncedLyrics") and p.sections:
        target.write_text(lyrics.tagged(found["syncedLyrics"], p.sections, first_sung(p.root / "score")))
        typer.echo(f"{LYRICS} : paroles rangées dans {len(p.sections)} sections ; relis et corrige le découpage")
    else:
        target.write_text(found["plainLyrics"].strip() + "\n")
        why = "pas de sections (arr transcribe d'abord)" if not p.sections else "paroles non horodatées"
        typer.secho(f"{LYRICS} : paroles brutes, {why} ; ajoute les balises [Verse], [Chorus]... à la main",
                    fg="yellow")


# --- prises


@app.command()
def render(
    style: str = typer.Option(..., "--style", "-s", help="Formation et couleur, en anglais : genre, instruments, voix."),
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
        table.add_row(name, "libre" if m["mode"] == "free" else "fidèle", str(m["seed"]),
                      f"{audio.duration(p.take_path(name)):.0f} s", created(m), m["style"])
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
    others = [(audio.load(p.version_path(t)), p.tracks[t].get("gain", 0.0))
              for t in p.tracks if t != track and not p.tracks[t].get("mute")]
    if not others:
        raise ProjectError("aucune autre piste dans le mix")
    out = p.root / "export" / track
    gain = p.tracks[track].get("gain", 0.0)
    audio.save_mp3(out / "partie.mp3", part)
    audio.save_mp3(out / "mix.mp3", audio.mix([*others, (part, gain)]))
    audio.save_mp3(out / "sans.mp3", audio.mix(others))
    typer.echo(f"{out.relative_to(p.root)}/ : partie.mp3, mix.mp3, sans.mp3")


# --- sections


def downbeats(p: Project) -> list[float]:
    f = p.root / ANALYSIS
    if not f.exists():
        raise ProjectError("pas d'analyse (lance `arr analyze`)")
    return json.loads(f.read_text())["downbeats"]


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


# --- modèles et machine


AUDIOCPP_RELEASE = (
    "https://github.com/0xShug0/audio.cpp/releases/download/v0.9.0/"
    "audio-v0.9.0-bin-ubuntu-x64-vulkan-portable.tar.gz"
)
SS2_PACKAGES = [
    "transformers==4.45.2", "huggingface-hub==0.36.0", "safetensors==0.5.3", "numpy==1.26.4", "scipy==1.13.1",
    "mir_eval==0.8.2", "pretty_midi==0.2.10", "mido==1.3.3", "setuptools==78.1.1", "soundfile",
]


@models_app.command("pull")
def models_pull() -> None:
    """Installe les modèles et leurs moteurs (seule commande qui télécharge des modèles)."""
    import tarfile
    import urllib.request

    from beat_this.inference import load_model
    from demucs.pretrained import get_model
    from huggingface_hub import snapshot_download

    from arr.engines.separation import MODELS

    snapshot_download("audio-cpp/Yue2-3B-GGUF", local_dir=engines.YUE2,
                      allow_patterns=["yue2-3b-q8_0.gguf", "yue2-vae-f16.gguf", "sidecars/*"])
    typer.echo(f"YuE2 dans {engines.YUE2}")

    if not engines.AUDIOCPP.exists():
        engines.AUDIOCPP.parent.mkdir(parents=True, exist_ok=True)
        archive, _ = urllib.request.urlretrieve(AUDIOCPP_RELEASE)
        with tarfile.open(archive) as tar:
            tar.extractall(engines.AUDIOCPP.parent, filter="data")
        engines.AUDIOCPP.chmod(0o755)
    typer.echo(f"audio.cpp dans {engines.AUDIOCPP.parent}")

    if not engines.SS2_PYTHON.exists():
        env = {**os.environ, "VIRTUAL_ENV": str(engines.SS2_PYTHON.parents[1])}
        subprocess.run(["uv", "venv", "-q", "--python", "3.11", env["VIRTUAL_ENV"]], check=True)
        subprocess.run(["uv", "pip", "install", "-q", "torch==2.11.0", "torchaudio==2.11.0",
                        "--index-url", "https://download.pytorch.org/whl/xpu"], check=True, env=env)
        subprocess.run(["uv", "pip", "install", "-q", *SS2_PACKAGES], check=True, env=env)
    subprocess.run([str(engines.SS2_PYTHON), "-c",
                    "from transformers import AutoModel; "
                    "AutoModel.from_pretrained('m-a-p/SheetSage2', trust_remote_code=True)"], check=True)
    typer.echo(f"SheetSage2 dans {engines.SS2_PYTHON.parents[1]}")

    for name in MODELS:
        get_model(name)
    load_model("final0", "cpu")
    typer.echo("Demucs et beat_this dans ~/.cache")


@app.command()
def doctor() -> None:
    """Vérifie la carte Intel Arc et la présence des modèles."""
    import torch

    typer.echo(f"torch {torch.__version__}")
    if not torch.xpu.is_available():
        typer.echo("xpu: indisponible")
        raise typer.Exit(1)
    typer.echo(f"xpu: disponible ({torch.xpu.get_device_name(0)})")
    x = torch.randn(2048, 2048, device="xpu")
    typer.echo(f"calcul de test: {float((x @ x).abs().mean()):.3f}")
    for label, path in (("audio.cpp", engines.AUDIOCPP), ("YuE2", engines.YUE2 / "yue2-3b-q8_0.gguf"),
                        ("SheetSage2", engines.SS2_PYTHON)):
        typer.echo(f"{label}: {'présent' if path.exists() else 'absent (arr models pull)'}")
