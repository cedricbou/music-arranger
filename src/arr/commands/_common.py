"""Aides partagées par plusieurs modules de commandes."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import typer

from arr import audio, grid, review, truth
from arr.app import ANALYSIS, FRAMES, ORIGINAL
from arr.project import Project, ProjectError


def reference(p: Project) -> Path:
    """Audio de référence du projet : l'original s'il existe, sinon le mix courant."""
    original = p.root / ORIGINAL
    return original if original.exists() else render_mix(p)


def load_track(p: Project, track: str, version: Optional[str] = None) -> np.ndarray:
    """Une piste telle qu'elle joue : sa version active (ou `version`), avec son calage (arr nudge)."""
    base, ranges = p.offsets(track)
    return audio.nudged(audio.load(p.version_path(track, version)), base, ranges)


def mix_tracks(p: Project, without: tuple[str, ...] = (), only: tuple[str, ...] = ()) -> list[str]:
    """Les pistes qui entrent dans le mix : `only` l'emporte sur les sourdines."""
    return [t for t in p.tracks if t not in without and (t in only if only else not p.tracks[t].get("mute"))]


def render_mix(p: Project, without: tuple[str, ...] = (), only: tuple[str, ...] = ()) -> Path:
    names = mix_tracks(p, without, only)
    if not names:
        raise ProjectError("aucune piste à mixer")
    parts = [(load_track(p, t), p.tracks[t].get("gain", 0.0)) for t in names]
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


def detected_grid(p: Project) -> Optional[tuple[list[float], list[float]]]:
    """Temps et barres d'`arr analyze`, sans les temps entendus deux fois, les temps manqués comblés ; None sans analyse.

    `analysis.json` garde ce que beat_this a détecté ; le nettoyage est refait à chaque lecture.
    Un temps manqué n'est comblé que si le projet garde ce que beat_this entendait (`activations`).
    """
    f = p.root / ANALYSIS
    if not f.exists():
        return None
    detected = json.loads(f.read_text())
    return read_grid(detected["beats"], detected["downbeats"], activations(p))


def song_fixes(p: Project, beats: list[float]) -> list[review.Fix]:
    """Les barres corrigées par le musicien : les passages de `truth/` du projet, puis ceux d'`arr review`."""
    old = (review.legacy_fix(x.bars, x.beats_per_bar, beats) for x in truth.passages(p))
    return [*(fix for fix in old if fix), *review.bar_fixes(p)]


def song_grid(p: Project, more: tuple = ()) -> Optional[tuple[list[float], list[float]]]:
    """Les temps et les barres détectées du morceau, avec les corrections du musicien ; None sans analyse.

    Décompte, clic, tempo et sections lisent la grille ici ; l'écran et le prompteur, dans
    `song_bars`. `more` : des corrections à essayer, pas encore gardées.
    """
    read = detected_grid(p)
    return review.fix_grid(*read, [*song_fixes(p, read[0]), *more]) if read else None


def read_grid(beats: list[float], downbeats: list[float], heard) -> tuple[list[float], list[float]]:
    """Les temps et barres détectés, remis d'aplomb : doublons retirés, puis trous comblés d'après `heard`."""
    beats, downbeats = grid.clean_beats(beats, downbeats)
    return grid.fill_beats(beats, None if heard is None else heard[:, 0]), downbeats


def activations(p: Project) -> Optional[np.ndarray]:
    """Ce que beat_this entendait trame par trame (colonnes : temps, premier temps) ; None avant `arr analyze`."""
    f = p.root / FRAMES
    return np.load(f)["frames"] if f.exists() else None


def song_bars(p: Project, more: tuple = ()) -> Optional[tuple[list[float], list[float]]]:
    """Les temps et les barres de la grille d'`arr play` ; None sans analyse.

    Les barres sont posées tous les N temps (`grid.regular_bars`) sur ce que le détecteur a lu,
    puis les passages corrigés par le musicien prennent ses temps et ses barres : une barre
    qu'il a fixée ne bouge pas, et rien ne bouge hors de ses passages.
    """
    read = detected_grid(p)
    if not read:
        return None
    return review.fix_grid(read[0], grid.regular_bars(read[1], read[0]), [*song_fixes(p, read[0]), *more])


def song_doubts(p: Project, mine: bool = False) -> Optional[dict[float, str]]:
    """Les mesures douteuses de la grille d'`arr play` (`grid.doubtful_bars`) ; None si le projet ne garde pas ce que beat_this entendait.

    Avec `mine`, sans celles que le musicien a jugées bonnes ou corrigées dans `arr review` : ce qui garde un « ? ».
    """
    read, heard = song_bars(p), activations(p)
    if not read or heard is None:
        return None
    found = grid.doubtful_bars(*read, heard[:, 0])
    if not mine or not found:
        return found
    fixes = song_fixes(p, detected_grid(p)[0])
    return review.unjudged(found, review.measures(*read), review.right_bars(p), fixes)


def song_passages(p: Project) -> Optional[list[review.Passage]]:
    """Les passages à relire du morceau, jugés ou non (`review.passages`) ; None sans analyse ou sans activations."""
    read, found = song_bars(p), song_doubts(p)
    if not read or found is None:
        return None
    end = max(float(p.song.get("duration") or 0.0), read[0][-1] if read[0] else 0.0)
    fixes = song_fixes(p, detected_grid(p)[0])
    return review.passages(review.measures(*read), found, review.right_bars(p), end, fixes)


def review_line(p: Project) -> str:
    """Ce qu'il reste à relire, en une ligne : la dernière d'`arr analyze` et d'`arr transcribe`."""
    left = [x for x in song_passages(p) or [] if not x.right]
    if not left:
        return "aucun passage à relire"
    return f"{len(left)} passage{'s' if len(left) > 1 else ''} à relire : arr review"


def doubtful_passages(doubts: dict[float, str], starts: list[float]) -> list[tuple[float, int, list[str]]]:
    """Les mesures douteuses qui se suivent, réunies : (début, nombre de mesures, raisons), dans l'ordre du morceau.

    `starts` sont les débuts de toutes les mesures.
    """
    out: list[tuple[float, int, list[str]]] = []
    previous = False
    for start in starts:
        if start in doubts and previous:
            first, count, why = out[-1]
            out[-1] = (first, count + 1, [*why, doubts[start]])
        elif start in doubts:
            out.append((start, 1, [doubts[start]]))
        previous = start in doubts
    return out


def save_analysis(p: Project, beats: list[float], downbeats: list[float], heard: np.ndarray) -> None:
    """Range ce que beat_this a détecté, tel quel, et ce qu'il entendait."""
    (p.root / ANALYSIS).write_text(json.dumps({"beats": beats, "downbeats": downbeats}))
    np.savez_compressed(p.root / FRAMES, frames=heard.astype(np.float16), fps=np.float32(50.0))


def original_beats(p: Project) -> Optional[list[float]]:
    return grid[0] if (grid := song_grid(p)) else None


def lead_in(backing: np.ndarray, ticks: list[tuple[float, bool]]) -> tuple[np.ndarray, int]:
    """Ajoute les clics à `backing`, précédé du silence qu'il faut pour ceux d'avant son début.

    Renvoie le playback et la longueur de ce silence, en échantillons.
    """
    pad = max(0.0, -min((t for t, _ in ticks), default=0.0))
    lead = np.zeros((int(round(pad * audio.SR)), 2), np.float32)
    return audio.add_clicks(np.concatenate([lead, backing]), [(t + pad, accent) for t, accent in ticks]), len(lead)


def describe(meta: dict) -> str:
    """Origine d'une version, en quelques mots."""
    op = meta["op"]
    detail = meta.get("model", "") if op == "split" else meta.get("source", "")
    return f"{op:<7} {detail}".rstrip()


def created(meta: dict) -> str:
    return datetime.fromisoformat(meta["created"]).strftime("%d/%m %H:%M")


def confirm(question: str) -> bool:
    return typer.prompt(f"{question} [o/N]", default="n", show_default=False).strip().lower() in (
        "o",
        "oui",
        "y",
        "yes",
    )


def slug(text: str) -> str:
    """`L'été n'a pas duré` donne `l-ete-n-a-pas-dure` : les accents perdent leur signe, pas leur lettre."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def folder_name(title: str, artist: str = "") -> str:
    """Le dossier d'un morceau : `paper-lanterns--night-drive`, l'artiste d'abord pour trier ; le titre seul sans artiste."""
    return f"{slug(artist)}--{slug(title)}" if slug(artist) else slug(title)


def downbeats(p: Project) -> list[float]:
    if not (grid := song_grid(p)):
        raise ProjectError("pas d'analyse (lance `arr analyze`)")
    return grid[1]
