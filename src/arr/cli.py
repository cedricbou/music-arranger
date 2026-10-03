from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from arr import audio, engines
from arr.project import Project, ProjectError, Section

app = typer.Typer(help="Arrangement audio local, stem par stem.", no_args_is_help=True)
sections_app = typer.Typer(help="Parties du morceau (intro, couplet, refrain...).", no_args_is_help=True)
models_app = typer.Typer(help="Poids des modèles.", no_args_is_help=True)
app.add_typer(sections_app, name="sections")
app.add_typer(models_app, name="models")

ORIGINAL = "source/original.flac"
ANALYSIS = "analysis.json"


def run() -> None:
    try:
        app()
    except ProjectError as e:
        typer.secho(f"erreur : {e}", fg="red", err=True)
        raise SystemExit(1)


@app.callback()
def main(ctx: typer.Context) -> None:
    # Seul `models pull` a le droit de toucher le réseau.
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


@app.command()
def split(
    source: Optional[Path] = typer.Argument(None, help="Fichier à séparer (ex. un rendu) ; sinon l'original."),
    model: str = typer.Option("htdemucs_6s", help="htdemucs_6s : 6 stems ; htdemucs_ft : 4 stems, plus précis."),
    shifts: int = typer.Option(1, help="Passes moyennées : 2 ou plus réduit les fuites, temps multiplié d'autant."),
) -> None:
    """Sépare un mix en stems ; chaque stem devient une nouvelle version de sa piste."""
    from arr.engines.separation import MODELS, separate

    p = Project.find()
    if model not in MODELS:
        raise ProjectError(f"modèle inconnu : {model} (connus : {', '.join(MODELS)})")
    source = (source or p.root / ORIGINAL).resolve()
    if not source.exists():
        raise ProjectError(f"{source} introuvable (arr import <fichier>)")
    rel = str(source.relative_to(p.root)) if source.is_relative_to(p.root) else str(source)
    stems = separate(source, model, shifts)
    for name, data in stems.items():
        version = add_track(p, name, data, {"op": "split", "model": model, "source": rel})
        typer.echo(f"{name} {version}")
    # Cette séparation remplace la précédente : ses stems et leurs fusions doubleraient le mix.
    for name, t in p.tracks.items():
        if name in stems:
            t["mute"] = False
        elif not t.get("mute") and p.meta(name, t["active"])["op"] in ("split", "merge"):
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
    if op == "split":
        detail = meta.get("model", "")
    elif op in ("merge", "import"):
        detail = meta.get("source", "")
    else:
        detail = meta.get("prompt", "")
        if meta.get("section"):
            detail += f" [{meta['section']}]"
        elif "start" in meta:
            detail += f" [{meta['start']:.0f}-{meta['end']:.0f} s]"
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
def play(track: Optional[str] = typer.Argument(None, help="Piste seule ; sinon le mix.")) -> None:
    """Écoute une piste ou le mix."""
    p = Project.find()
    path = p.version_path(track) if track else render_mix(p)
    subprocess.run(["ffplay", "-v", "error", "-nodisp", "-autoexit", str(path)])


# --- génération


def span(p: Project, section: Optional[str], start: Optional[float], end: Optional[float]):
    """Plage de temps visée : une section nommée, ou --from/--to, ou rien (tout le morceau)."""
    if section:
        s = p.section(section)
        return s.start, s.end
    if start is not None or end is not None:
        return start or 0.0, end
    return None


def song_kw(p: Project) -> dict:
    return {"bpm": p.song.get("bpm"), "key": p.song.get("key", "")}


SECTION = typer.Option(None, "--section", "-s", help="Ne traiter que cette section.")
PROMPT = typer.Option(None, "--prompt", "-p", help="Description du son voulu (en anglais de préférence).")
SEED = typer.Option(-1, help="Graine ; -1 pour aléatoire.")
COUNT = typer.Option(1, "-n", help="Nombre de variantes à générer.")


def cover_track(p, source: str, target: str, caption: str, fidelity: float, section, seed: int, n: int, op: str):
    """Rejoue la piste SOURCE selon CAPTION.

    Avec une section, seule cette plage change : sur place si la cible est la source,
    sinon la cible ne joue que la section et la source s'y tait.
    """
    from arr.engines.acestep import Engine

    src = p.version_path(source)
    base = audio.load(src)
    rng = span(p, section, None, None)
    engine = Engine()
    for i in range(n):
        out, meta = engine.generate("cover", caption, src, fidelity=fidelity,
                                    seed=seed if seed < 0 else seed + i, **song_kw(p))
        out = audio.scale_to(audio.fit(out, len(base)), base)
        if rng:
            under = base if target == source else np.zeros_like(base)
            out = audio.splice(under, out, *rng)
            meta["section"] = section
        meta.update(op=op, parent=f"{source}/{src.stem}")
        typer.echo(f"{target} {add_track(p, target, out, meta)}")
    if rng and target != source:
        cut = audio.splice(base, np.zeros_like(base), *rng)
        meta = {"op": "cut", "section": section, "parent": f"{source}/{src.stem}"}
        typer.echo(f"{source} {add_track(p, source, cut, meta)}  (se tait pendant {section})")


@app.command()
def restem(
    track: str,
    as_: str = typer.Option(..., "--as", help="Instrument cible (profil du groupe ou famille ACE-Step)."),
    fidelity: float = typer.Option(0.35, help="0 : partie réinventée ; 0.3 : garde le rythme ; 0.7 : très proche de l'original."),
    prompt: Optional[str] = PROMPT, section: Optional[str] = SECTION, seed: int = SEED, n: int = COUNT,
) -> None:
    """Rejoue un stem avec un autre instrument en gardant sa ligne."""
    from arr import band

    p = Project.find()
    inst = band.instrument(as_)
    cover_track(p, track, inst.name, prompt or f"solo {inst.sound}, isolated instrument stem",
                fidelity, section, seed, n, "restem")
    if inst.name != track and not section:
        p.tracks[track]["mute"] = True
        p.save()
        typer.echo(f"{track} rendue muette (arr mute {track} --off pour la réactiver)")


@app.command()
def polish(
    track: str,
    fidelity: float = typer.Option(0.5, help="0.3 : rejoué librement ; 0.5 : même ligne, nettoyée ; 0.7 : retouche légère."),
    prompt: Optional[str] = PROMPT, section: Optional[str] = SECTION, seed: int = SEED, n: int = COUNT,
) -> None:
    """Rejoue proprement une idée mal jouée, même instrument, même ligne."""
    p = Project.find()
    caption = prompt or f"clean, tight, well played {track.replace('_', ' ')}, studio recording"
    cover_track(p, track, track, caption, fidelity, section, seed, n, "polish")


@app.command()
def fix(
    track: str,
    prompt: str = typer.Option(..., "--prompt", "-p", help="Ce qu'on veut entendre dans le passage."),
    section: Optional[str] = SECTION,
    start: Optional[float] = typer.Option(None, "--from", help="Début en secondes."),
    end: Optional[float] = typer.Option(None, "--to", help="Fin en secondes."),
    seed: int = SEED, n: int = COUNT,
) -> None:
    """Régénère un passage d'une piste ; le reste n'est pas touché."""
    from arr.engines.acestep import Engine

    p = Project.find()
    rng = span(p, section, start, end)
    if not rng:
        raise ProjectError("indique --section ou --from/--to")
    src = p.version_path(track)
    base = audio.load(src)
    start, end = rng[0], rng[1] if rng[1] is not None else len(base) / audio.SR
    inside = np.zeros(len(base), bool)
    inside[int(start * audio.SR) : int(end * audio.SR)] = True
    engine = Engine()
    for i in range(n):
        out, meta = engine.generate("repaint", prompt, src, start=start, end=end,
                                    seed=seed if seed < 0 else seed + i, **song_kw(p))
        # Le passage refait est ramené au niveau moyen de la piste ; hors plage, l'original reste au bit près.
        out = audio.fit(out, len(base))
        out = audio.scale_to(out, base, inside)
        meta.update(op="fix", parent=f"{track}/{src.stem}")
        typer.echo(f"{track} {add_track(p, track, audio.splice(base, out, start, end), meta)}")


def render(p: Project, task: str, name: str, caption: str, tracks: list[str], rng, seed: int, n: int) -> None:
    """Tâches qui rendent un mix complet (contexte + nouveaux instruments) dans renders/."""
    from arr.engines.acestep import Engine

    src = render_mix(p)
    total = audio.duration(src)
    engine = Engine()
    for i in range(n):
        kw = {}
        if task == "lego":
            kw = {"start": rng[0] if rng else 0.0, "end": (rng[1] if rng and rng[1] is not None else total)}
        out, meta = engine.generate(task, caption, src, tracks=tracks,
                                    seed=seed if seed < 0 else seed + i, **kw, **song_kw(p))
        d = p.root / "renders"
        d.mkdir(exist_ok=True)
        k = len(list(d.glob(f"{name}-*.flac"))) + 1
        path = d / f"{name}-{k:03d}.flac"
        audio.save(path, out)
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        typer.echo(f"{path.relative_to(p.root)}  (arr split {path.relative_to(p.root)} pour en tirer des stems)")


@app.command()
def add(
    instrument: str,
    prompt: Optional[str] = PROMPT, section: Optional[str] = SECTION, seed: int = SEED, n: int = COUNT,
) -> None:
    """Ajoute un instrument par-dessus le mix courant ; produit un rendu complet."""
    from arr import band

    p = Project.find()
    inst = band.instrument(instrument)
    render(p, "lego", f"add-{inst.name}", prompt or inst.sound, [inst.track], span(p, section, None, None), seed, n)


@app.command()
def complete(
    with_: str = typer.Option(..., "--with", help="Instruments à ajouter, séparés par des virgules."),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Style de l'arrangement voulu."),
    seed: int = SEED, n: int = COUNT,
) -> None:
    """Habille une idée (basse, piano...) avec d'autres instruments ; produit un rendu complet."""
    from arr import band

    p = Project.find()
    insts = [band.instrument(x.strip()) for x in with_.split(",")]
    render(p, "complete", "complete", prompt, [i.track for i in insts], None, seed, n)


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


@models_app.command("pull")
def models_pull() -> None:
    """Télécharge les poids depuis Hugging Face (seule commande qui utilise le réseau)."""
    from huggingface_hub import snapshot_download

    snapshot_download("ACE-Step/Ace-Step1.5", local_dir=engines.CHECKPOINTS)
    snapshot_download("ACE-Step/acestep-v15-base", local_dir=engines.CHECKPOINTS / "acestep-v15-base")
    typer.echo(f"ACE-Step dans {engines.CHECKPOINTS}")
    from beat_this.inference import load_model
    from demucs.pretrained import get_model

    from arr.engines.separation import MODELS

    for name in MODELS:
        get_model(name)
    load_model("final0", "cpu")
    typer.echo("Demucs et beat_this dans ~/.cache/torch/hub")


@app.command()
def doctor() -> None:
    """Vérifie que la carte Intel Arc est utilisable par PyTorch."""
    import torch

    typer.echo(f"torch {torch.__version__}")
    if not torch.xpu.is_available():
        typer.echo("xpu: indisponible")
        raise typer.Exit(1)
    typer.echo(f"xpu: disponible ({torch.xpu.get_device_name(0)})")
    x = torch.randn(2048, 2048, device="xpu")
    typer.echo(f"calcul de test: {float((x @ x).abs().mean()):.3f}")
    for name in ("acestep-v15-turbo", "acestep-v15-base", "vae"):
        state = "présent" if (engines.CHECKPOINTS / name).is_dir() else "absent (arr models pull)"
        typer.echo(f"{name}: {state}")
