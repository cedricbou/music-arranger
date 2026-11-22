"""Entrées et sorties audio en direct : capturer ce que joue l'ordinateur, jouer, enregistrer.

Installation visée par défaut : l'ordinateur joue sur sa sortie habituelle (une PreSonus),
dont les sorties arrivent en analogique sur les voies 7/8 d'une Soundcraft Signature MTK ;
on enregistre donc ce que joue l'ordinateur sur les entrées 7/8 de la Soundcraft, où se
règle le gain.

Réglages dans ~/.config/arr/audio.toml (`ARR_AUDIO`), tous facultatifs : chacun est décrit dans
docs/manual/audio.md, qu'un test tient à jour. Le même fichier porte la section [midi], lue par
`arr.midi` : port et canal des pédales.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import tomllib
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from arr import audio, measure
from arr.project import ProjectError

CONFIG = Path(os.environ.get("ARR_AUDIO", Path.home() / ".config/arr/audio.toml"))
INTERFACE = "Soundcraft"  # table d'enregistrement : ses entrées 7/8 reçoivent le son de l'ordinateur
CHUNK = 0.05  # secondes
DEFAULT_LATENCY = 0.0213  # un cycle PipeWire de 1024 échantillons : le minimum, sans les convertisseurs


# --- réglages


def _device_names() -> list[str]:
    import sounddevice as sd

    return [d["name"] for d in sd.query_devices()]


def sources() -> list[tuple[str, int]]:
    """Sources PipeWire : (nom, nombre de canaux)."""
    listing = subprocess.run(["pactl", "-f", "json", "list", "sources"], capture_output=True, text=True, check=True)
    return [(s["name"], len(s["channel_map"].split(","))) for s in json.loads(listing.stdout)]


def user_settings() -> dict:
    """Le fichier audio.toml tel qu'il est écrit ; vide s'il n'existe pas.

    Seul lecteur du fichier : chaque module complète ensuite sa section par ses défauts.
    """
    return tomllib.loads(CONFIG.read_text()) if CONFIG.exists() else {}


def config() -> dict:
    """Réglages effectifs du son : le fichier, complété par des défauts selon le matériel branché."""
    user = user_settings()
    present = any(INTERFACE.lower() in n.lower() for n in _device_names())
    defaults = {
        "output": {"device": "", "channels": [1, 2]},
        "input": {"device": INTERFACE if present else "", "channels": [1], "latency_ms": None},
        "capture": {"source": "", "channels": [7, 8] if present else [], "loudness": -16.0, "player": ""},
    }
    return {k: {**v, **user.get(k, {})} for k, v in defaults.items()}


def capture_source() -> tuple[str, int]:
    """Source PipeWire à écouter pour `arr capture`, et son nombre de canaux."""
    wanted = config()["capture"]["source"]
    known = sources()
    if wanted == "monitor":
        return default_monitor()
    if wanted:
        for name, count in known:
            if name == wanted:
                return name, count
        raise ProjectError(f"source PipeWire introuvable : {wanted} (arr devices)")
    for name, count in known:
        if INTERFACE.lower() in name.lower() and not name.endswith(".monitor"):
            return name, count
    return default_monitor()


def find_device(fragment: str, kind: str, channels: list[int]) -> int | None:
    """Indice du périphérique dont le nom contient `fragment` ; None pour celui par défaut."""
    import sounddevice as sd

    if not fragment:
        return None
    need = max(channels)
    found = [
        (sd.query_hostapis(d["hostapi"])["name"].startswith("JACK"), i)
        for i, d in enumerate(sd.query_devices())
        if fragment.lower() in d["name"].lower() and d[f"max_{kind}_channels"] >= need
    ]
    if not found:
        raise ProjectError(
            f"périphérique introuvable : « {fragment} » avec {need} canaux en "
            f"{'entrée' if kind == 'input' else 'sortie'} (arr devices)"
        )
    return max(found)[1]  # de préférence par JACK : c'est le graphe PipeWire, synchronisé


def jack_devices() -> list[dict]:
    """Les périphériques vus par l'API JACK de PipeWire : ceux que `[output]` et `[input]` nomment."""
    import sounddevice as sd

    return [d for d in sd.query_devices() if sd.query_hostapis(d["hostapi"])["name"].startswith("JACK")]


def duplex_devices(inp: dict, out: dict, wanted: list[int]) -> tuple[int | None, int | None]:
    """Entrée et sortie d'un même flux : PortAudio exige qu'elles viennent du même pilote.

    Quand un seul des deux est nommé, l'autre devient le périphérique par défaut du pilote
    du premier (avec JACK, c'est la sortie ou l'entrée par défaut de PipeWire).
    """
    import sounddevice as sd

    i, o = find_device(inp["device"], "input", wanted), find_device(out["device"], "output", out["channels"])
    if (i is None) != (o is None):
        api = sd.query_hostapis(sd.query_devices(i if o is None else o)["hostapi"])
        if o is None:
            o = api["default_output_device"]
        else:
            i = api["default_input_device"]
        if min(i, o) < 0:
            raise ProjectError(
                "pas de périphérique par défaut compatible : nomme l'entrée et la sortie dans audio.toml (arr devices)"
            )
    return i, o


# --- capture de ce que joue l'ordinateur


def default_monitor() -> tuple[str, int]:
    """Source PipeWire qui copie la sortie par défaut, et son nombre de canaux."""
    sink = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, check=True).stdout.strip()
    return f"{sink}.monitor", dict(sources())[f"{sink}.monitor"]


def listen(source: str, channels: int) -> Iterator[np.ndarray]:
    """Flux continu de blocs (échantillons, canaux) lus sur une source PipeWire."""
    block = int(CHUNK * audio.SR) * channels * 4
    cmd = [
        "parec",
        f"--device={source}",
        "--format=float32le",
        f"--rate={audio.SR}",
        f"--channels={channels}",
        "--raw",
        "--latency-msec=20",
    ]
    if channels > 2:
        cmd.append("--channel-map=" + ",".join(f"aux{i}" for i in range(channels)))
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
        try:
            while data := proc.stdout.read(block):
                yield np.frombuffer(data[: len(data) // (channels * 4) * channels * 4], np.float32).reshape(
                    -1, channels
                )
        finally:
            proc.terminate()


def gate(
    chunks: Iterable[np.ndarray],
    *,
    threshold_db: float = -50.0,
    preroll: float = 0.25,
    silence: float = 3.0,
    should_stop: Callable[[], bool] = lambda: False,
    on_start: Callable[[], None] = lambda: None,
) -> np.ndarray:
    """Garde l'audio entre le premier son et le silence final.

    Démarre au premier bloc au-dessus du seuil (en gardant `preroll` secondes avant), s'arrête
    après `silence` secondes sous le seuil, quand `should_stop()` devient vrai, ou sur Ctrl+C.
    """
    limit = audio.db(threshold_db)
    before: list[np.ndarray] = []
    kept: list[np.ndarray] = []
    quiet = 0.0
    try:
        for chunk in chunks:
            loud = float(np.abs(chunk).max(initial=0.0)) >= limit
            seconds = len(chunk) / audio.SR
            if not kept:
                if not loud:
                    before = (before + [chunk])[-max(1, round(preroll / seconds)) :]
                    continue
                kept = before + [chunk]
                on_start()
                continue
            kept.append(chunk)
            quiet = 0.0 if loud else quiet + seconds
            if quiet >= silence or should_stop():
                break
    except KeyboardInterrupt:
        pass
    if not kept:
        raise ProjectError("aucun son reçu")
    out = np.concatenate(kept)
    loud = np.flatnonzero(np.abs(out).max(axis=1) >= limit)
    return out[: min(len(out), loud[-1] + audio.SR // 2)]


def peaks(
    chunks: Iterable[np.ndarray],
    seconds: float | None = None,
    on_update: Callable[[np.ndarray, np.ndarray], None] = lambda now, held: None,
) -> np.ndarray:
    """Niveau de crête par canal, en dB, sur `seconds` (ou jusqu'à Ctrl+C).

    `on_update(now, held)` reçoit à chaque bloc la crête du bloc et la crête maximale tenue.
    """
    held, heard = None, 0.0
    try:
        for chunk in chunks:
            now = 20 * np.log10(np.abs(chunk).max(axis=0) + 1e-9)
            held = now if held is None else np.maximum(held, now)
            on_update(now, held)
            heard += len(chunk) / audio.SR
            if seconds is not None and heard >= seconds:
                break
    except KeyboardInterrupt:
        pass
    if held is None:
        raise ProjectError("aucun son reçu")
    return held


def stereo(captured: np.ndarray, channels: list[int]) -> np.ndarray:
    """Réduit une capture multicanal à deux canaux : ceux demandés, sinon la paire la plus forte."""
    if channels:
        picked = captured[:, [c - 1 for c in channels]]
    else:
        energy = (captured**2).sum(axis=0)
        pairs = energy[: len(energy) // 2 * 2].reshape(-1, 2).sum(axis=1)
        first = int(pairs.argmax()) * 2
        picked = captured[:, first : first + 2]
    return np.repeat(picked, 2, axis=1) if picked.shape[1] == 1 else np.ascontiguousarray(picked)


# --- lecture et enregistrement synchronisés


def loop_block(data: np.ndarray, position: int, frames: int, loop_from: int) -> tuple[np.ndarray, int]:
    """`frames` échantillons à partir de `position`, en reprenant à `loop_from` après la fin.

    Renvoie aussi la position suivante.
    """
    index = position + np.arange(frames)
    over = index >= len(data)
    index[over] = loop_from + (index[over] - len(data)) % (len(data) - loop_from)
    return data[index], int(index[-1]) + 1


def play(data: np.ndarray, loop: np.ndarray | None = None, watch=None) -> None:
    """Joue `data` sur la sortie configurée, puis `loop` sans fin s'il est donné ; Ctrl+C arrête.

    `watch(secondes)` est appelé vingt fois par seconde avec la position de lecture, comptée
    depuis le début de `data` ; en boucle elle revient à la fin de `data` à chaque tour.
    Il peut renvoyer `(en pause, position où sauter ou None)` pour piloter la lecture.
    """
    import threading

    import sounddevice as sd

    out = config()["output"]
    device = find_device(out["device"], "output", out["channels"])
    if loop is not None and not len(loop):
        raise ProjectError("rien à jouer en boucle")
    # Un seul flux pour le décompte et la boucle : deux lectures à la suite perdraient le tempo.
    whole = data if loop is None else np.concatenate([data, loop])
    columns = [c - 1 for c in out["channels"]]
    position, done = 0, threading.Event()
    paused, jump = False, None

    def callback(outdata, frames, time, status):
        nonlocal position, jump
        outdata.fill(0)
        if jump is not None:
            position, jump = int(np.clip(jump, 0, len(whole) - 1)), None
        if paused:
            return
        if loop is None:
            block = whole[position : position + frames]
            outdata[: len(block), columns] = block
            position += len(block)
            if len(block) < frames:
                raise sd.CallbackStop
        else:
            block, position = loop_block(whole, position, frames, len(data))
            outdata[:, columns] = block

    try:
        with sd.OutputStream(
            samplerate=audio.SR,
            device=device,
            channels=max(out["channels"]),
            dtype="float32",
            callback=callback,
            finished_callback=done.set,
        ):
            while not done.wait(0.05):
                order = watch(position / audio.SR) if watch else None
                if order:
                    paused = order[0]
                    if order[1] is not None:
                        jump = int(order[1] * audio.SR)
    except KeyboardInterrupt:
        pass


@contextmanager
def looping(data: np.ndarray) -> Iterator[None]:
    """Joue `data` en boucle sur la sortie réglée, le temps du bloc."""
    import sounddevice as sd

    out = config()["output"]
    device = find_device(out["device"], "output", out["channels"])
    sd.play(data, audio.SR, loop=True, mapping=out["channels"], device=device)
    try:
        yield
    finally:
        sd.stop()


def play_and_record(playback: np.ndarray, channel: int | None = None, watch=None) -> tuple[np.ndarray, float]:
    """Joue `playback` et enregistre l'instrument dans le même flux, donc à décalage constant.

    `watch(secondes)` est appelé dix fois par seconde avec le temps écoulé, lu sur l'horloge :
    assez juste pour un affichage, et le flux n'est pas touché.

    Renvoie l'enregistrement (stéréo) et son retard sur le playback, en secondes : la valeur
    mesurée par `arr calibrate`, sinon le minimum du système (la latence annoncée par
    PortAudio n'est pas fiable ici).
    """
    import sounddevice as sd

    cfg = config()
    out, inp = cfg["output"], cfg["input"]
    wanted = [channel] if channel else inp["channels"]
    try:
        recorded = sd.playrec(
            playback,
            audio.SR,
            device=duplex_devices(inp, out, wanted),
            input_mapping=wanted,
            output_mapping=out["channels"],
            dtype="float32",
        )
    except sd.PortAudioError as e:
        raise ProjectError(f"impossible d'ouvrir l'entrée et la sortie ensemble : {e} (arr devices)")
    started = time.monotonic()
    try:
        while watch and sd.get_stream().active:
            watch(time.monotonic() - started)
            time.sleep(0.1)
        sd.wait()
    except KeyboardInterrupt:
        sd.stop()
    latency = DEFAULT_LATENCY if inp["latency_ms"] is None else inp["latency_ms"] / 1000
    return (np.repeat(recorded, 2, axis=1) if recorded.shape[1] == 1 else recorded), latency


def measure_latency(played: np.ndarray, recorded: np.ndarray, longest: float = 0.5) -> float:
    """Retard de `recorded` sur `played`, en secondes, par corrélation (jusqu'à `longest`)."""
    if float(np.abs(recorded).max(initial=0.0)) < audio.db(-40):
        raise ProjectError(
            "rien n'est revenu sur l'entrée : relie la sortie à l'entrée de l'instrument "
            "(câble, ou retour de la table) et monte le gain"
        )
    return measure.delay(played, recorded, longest)


def save_latency(seconds: float) -> None:
    """Note la latence mesurée dans audio.toml, en gardant les autres réglages."""
    import tomli_w

    user = user_settings()
    user.setdefault("input", {})["latency_ms"] = round(seconds * 1000, 1)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(tomli_w.dumps(user))
