"""Machine et modèles : périphériques audio, installation des moteurs, diagnostic."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

import typer

from arr import audio, engines
from arr.app import ORIGINAL, app, models_app
from arr.project import SONG_FILE, Project, ProjectError


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
        # Les stems d'avant le calage par sections portent `on_beat` : leur verdict ne vaut plus.
        if meta and meta.get("superposable") is False and "on_beat" not in meta:
            notes.append("autre tempo que l'original : non superposable")
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
    if length is None:
        return
    from arr.commands.align import TOLERANCE, take_mix

    reference = audio.load(original)
    for name in p.takes():
        if any(t.startswith(f"{name}.") for t in p.tracks):
            placed = measure.within(measure.time_map(reference, take_mix(p, name, nudged=True)), TOLERANCE)
            typer.echo(
                f"{name} : {placed:.0%} du morceau à moins de {TOLERANCE * 1000:.0f} ms de l'original (arr nudge {name})"
            )


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

    Sort en erreur si un passage va moins bien : un changement de la grille ne se livre pas ainsi.
    """
    from rich.console import Console
    from rich.table import Table

    from arr import measure
    from arr import truth as marks
    from arr.commands._common import song_grid

    folder = library_of(library)
    table = Table(box=None, pad_edge=False, header_style="bold")
    for column in ("Morceau", "Passage", "Barres justes", "En trop", "Mesures au compte", "Écart", "Depuis"):
        table.add_column(
            column, no_wrap=True, justify="left" if column in ("Morceau", "Passage", "Depuis") else "right"
        )
    total = dict.fromkeys(("marks", "matched", "shown", "counted", "right"), 0)
    moved: dict[str, list[str]] = {"mieux": [], "moins bien": []}
    for f in sorted(folder.glob(f"*/{SONG_FILE}")):
        p = Project(f.parent)
        found = marks.passages(p)
        if not found:
            continue
        grid = song_grid(p)
        if not grid:
            table.add_row(p.root.name, "", "[yellow]pas d'analyse (arr analyze)[/]")
            continue
        beats, bars = grid[0], measure.regular_bars(grid[1], grid[0])
        before, run = marks.last_run(p), {}
        for passage in found:
            s = marks.score(passage.bars, passage.beats_per_bar, beats, bars) | {"version": passage.version}
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
    )
    Console().print(table)
    for word, names in moved.items():
        if names:
            typer.echo(f"{word} : {', '.join(names)}")
    if moved["moins bien"]:
        raise typer.Exit(1)


@app.command()
def devices() -> None:
    """Montre les réglages audio effectifs et les périphériques disponibles."""
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
    for d in studio.jack_devices():
        typer.echo(f"  {d['name']}  ({d['max_input_channels']} entrées, {d['max_output_channels']} sorties)")


AUDIOCPP_RELEASES = "https://api.github.com/repos/0xShug0/audio.cpp/releases"
# La variante non portable vise AVX-512 et plante (SIGILL) sur les processeurs qui ne l'ont pas.
AUDIOCPP_ASSET = "-bin-ubuntu-x64-vulkan-portable.tar.gz"


def audiocpp_release(version: str) -> tuple[str, str, str]:
    """Nom, adresse et empreinte sha256 de l'archive d'une release (la dernière si `version` est vide)."""
    import json
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"{AUDIOCPP_RELEASES}/{f'tags/{version}' if version else 'latest'}") as reply:
            release = json.load(reply)
    except urllib.error.HTTPError as e:
        raise ProjectError(f"release d'audio.cpp introuvable : {version or 'la dernière'} (HTTP {e.code})") from None
    asset = next((a for a in release["assets"] if a["name"].endswith(AUDIOCPP_ASSET)), None)
    if asset is None or not asset.get("digest"):
        raise ProjectError(f"audio.cpp {release['tag_name']} : pas d'archive {AUDIOCPP_ASSET} avec son empreinte")
    return release["tag_name"], asset["browser_download_url"], asset["digest"].removeprefix("sha256:")


def install_audiocpp(version: str = "") -> str:
    """Met en service une version d'audio.cpp (la dernière si `version` est vide) et renvoie son nom.

    Chaque version a son dossier ; le lien `current` désigne celle qui sert. Les autres restent en place.
    """
    import hashlib
    import shutil
    import tarfile
    import urllib.request

    root, binary = engines.AUDIOCPP.parents[1], engines.AUDIOCPP.name
    if not (version and (root / version / binary).exists()):
        version, url, digest = audiocpp_release(version)
        if not (root / version / binary).exists():
            archive, _ = urllib.request.urlretrieve(url)
            found = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
            if found != digest:
                raise ProjectError(f"audio.cpp {version} : empreinte inattendue ({found[:12]}, attendu {digest[:12]})")
            partial = root / f"{version}.partiel"
            shutil.rmtree(partial, ignore_errors=True)
            partial.mkdir(parents=True)
            with tarfile.open(archive) as tar:
                tar.extractall(partial, filter="data")
            (partial / binary).chmod(0o755)
            partial.rename(root / version)
            Path(archive).unlink()
    link = root / engines.AUDIOCPP.parent.name
    link.unlink(missing_ok=True)
    link.symlink_to(version)
    return version


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
def models_pull(
    audiocpp: str = typer.Option(
        "",
        "--audiocpp",
        envvar="ARR_AUDIOCPP_VERSION",
        help="Version d'audio.cpp à mettre en service (ex. v0.9.0) ; par défaut la dernière release.",
    ),
) -> None:
    """Installe les modèles et leurs moteurs, et les met à jour (seule commande qui télécharge des modèles).

    Les poids viennent de Hugging Face. Le moteur audio.cpp vient de sa release GitHub : la
    dernière à chaque appel, ou celle de `--audiocpp` pour rester sur une version ou y revenir.
    """
    from demucs.pretrained import get_model
    from huggingface_hub import snapshot_download

    from arr.engines import analysis
    from arr.engines.separation import MODELS

    snapshot_download(
        "audio-cpp/Yue2-3B-GGUF",
        local_dir=engines.YUE2,
        allow_patterns=["yue2-3b-q8_0.gguf", "yue2-vae-f16.gguf", "sidecars/*"],
    )
    typer.echo(f"YuE2 dans {engines.YUE2}")

    typer.echo(f"audio.cpp {install_audiocpp(audiocpp)} dans {engines.AUDIOCPP.parents[1]}")

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
    analysis.checkpoint()
    typer.echo("Demucs et beat_this dans le cache Hugging Face")


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
    from arr.engines import analysis, yue2

    try:
        beat_this = bool(analysis.checkpoint())
    except ProjectError:
        beat_this = False
    for label, state in (
        ("audio.cpp", engines.AUDIOCPP.exists() and f"présent ({yue2.version()})"),
        ("YuE2", (engines.YUE2 / "yue2-3b-q8_0.gguf").exists() and "présent"),
        ("SheetSage2", engines.SS2_PYTHON.exists() and "présent"),
        ("beat_this", beat_this and "présent"),
    ):
        typer.echo(f"{label}: {state or 'absent (arr models pull)'}")
