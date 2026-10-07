"""Machine et modèles : périphériques audio, installation des moteurs, diagnostic."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import typer

from arr import audio, engines
from arr.app import ORIGINAL, app, models_app
from arr.project import Project


@app.command()
def check() -> None:
    """Mesure chaque fichier audio du projet : durée, niveaux, volume, anomalies.

    Sert à vérifier un résultat sans l'écouter (et à remplir une PR) : une piste silencieuse,
    saturée, de la mauvaise longueur ou mal calée se voit ici.
    """
    from rich.console import Console
    from rich.table import Table

    from arr import measure

    p = Project.find()
    original = p.root / ORIGINAL
    length = len(audio.load(original)) if original.exists() else None
    table = Table(box=None, pad_edge=False, header_style="bold")
    for column in ("Fichier", "Durée", "Crête", "Moyen", "Volume", "Remarques"):
        table.add_column(
            column, no_wrap=column != "Remarques", justify="left" if column in ("Fichier", "Remarques") else "right"
        )

    def row(label: str, path: Path, meta: dict | None = None, same_length: bool = False) -> None:
        data = audio.load(path)
        peak, rms = measure.level(data)
        notes = []
        if peak < -60:
            notes.append("silencieux")
        elif peak >= -0.1:
            notes.append("sature")
        if same_length and length is not None and len(data) != length:
            notes.append(f"longueur différente de l'original ({(len(data) - length) / audio.SR:+.2f} s)")
        if meta and "on_beat" in meta:
            notes.append(f"calage {meta['on_beat']:.0%}" + ("" if meta.get("superposable") else ", non superposable"))
        volume = f"{audio.loudness(data):.1f} LUFS" if peak >= -60 else "-"
        table.add_row(
            label, f"{len(data) / audio.SR:.1f} s", f"{peak:.1f} dB", f"{rms:.1f} dB", volume, " ; ".join(notes)
        )

    if original.exists():
        row("original", original)
    for name, t in p.tracks.items():
        row(f"{name} {t['active']}", p.version_path(name), p.meta(name, t["active"]), same_length=True)
    for name in p.takes():
        row(name, p.take_path(name))
    Console().print(table)


@app.command()
def devices() -> None:
    """Montre les réglages audio effectifs et les périphériques disponibles."""
    import sounddevice as sd

    from arr import studio

    cfg = studio.config()
    source = studio.capture_source()[0]
    typer.echo(f"réglages ({studio.CONFIG}{'' if studio.CONFIG.exists() else ', absent : valeurs par défaut'})")
    typer.echo(f"  sortie    {cfg['output']['device'] or 'par défaut'}  canaux {cfg['output']['channels']}")
    measured = cfg["input"]["latency_ms"]
    typer.echo(
        f"  entrée    {cfg['input']['device'] or 'par défaut'}  canaux {cfg['input']['channels']}  latence "
        + (f"{measured} ms (mesurée)" if measured is not None else "non mesurée (arr calibrate)")
    )
    typer.echo(
        f"  capture   {source}  canaux {cfg['capture']['channels'] or 'automatiques'}"
        f"  volume cible {cfg['capture']['loudness']:g} LUFS"
    )
    typer.echo("sources PipeWire (pour [capture] source)")
    for name, count in studio.sources():
        typer.echo(f"  {name}  ({count} canaux)")
    typer.echo("périphériques (pour [output] et [input] device)")
    for d in sd.query_devices():
        if sd.query_hostapis(d["hostapi"])["name"].startswith("JACK"):
            typer.echo(f"  {d['name']}  ({d['max_input_channels']} entrées, {d['max_output_channels']} sorties)")


AUDIOCPP_RELEASE = (
    "https://github.com/0xShug0/audio.cpp/releases/download/v0.9.0/audio-v0.9.0-bin-ubuntu-x64-vulkan-portable.tar.gz"
)


SS2_PACKAGES = [
    "transformers==4.45.2",
    "huggingface-hub==0.36.0",
    "safetensors==0.5.3",
    "numpy==1.26.4",
    "scipy==1.13.1",
    "mir_eval==0.8.2",
    "pretty_midi==0.2.10",
    "mido==1.3.3",
    "setuptools==78.1.1",
    "soundfile",
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

    snapshot_download(
        "audio-cpp/Yue2-3B-GGUF",
        local_dir=engines.YUE2,
        allow_patterns=["yue2-3b-q8_0.gguf", "yue2-vae-f16.gguf", "sidecars/*"],
    )
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
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "-q",
                "torch==2.11.0",
                "torchaudio==2.11.0",
                "--index-url",
                "https://download.pytorch.org/whl/xpu",
            ],
            check=True,
            env=env,
        )
        subprocess.run(["uv", "pip", "install", "-q", *SS2_PACKAGES], check=True, env=env)
    subprocess.run(
        [
            str(engines.SS2_PYTHON),
            "-c",
            "from transformers import AutoModel; AutoModel.from_pretrained('m-a-p/SheetSage2', trust_remote_code=True)",
        ],
        check=True,
    )
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
    for label, path in (
        ("audio.cpp", engines.AUDIOCPP),
        ("YuE2", engines.YUE2 / "yue2-3b-q8_0.gguf"),
        ("SheetSage2", engines.SS2_PYTHON),
    ):
        typer.echo(f"{label}: {'présent' if path.exists() else 'absent (arr models pull)'}")
