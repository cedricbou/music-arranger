"""Faux moteurs et projets d'essai partagés par les tests : aucun test ne charge de modèle ni n'ouvre de carte son."""

import sys
import types

import numpy as np
from typer.testing import CliRunner

from arr import audio
from arr.cli import add_track
from arr.project import Project

# Importer le vrai sounddevice initialise déjà PortAudio, qui échoue sans serveur de son.
sounddevice = types.ModuleType("sounddevice")
sounddevice.PortAudioError = type("PortAudioError", (Exception,), {})
sounddevice.query_devices = lambda device=None: []
sounddevice.query_hostapis = lambda index=None: []
sys.modules["sounddevice"] = sounddevice

# Une couleur forcée par le terminal de celui qui lance les tests fausserait les sorties comparées.
runner = CliRunner(env={"FORCE_COLOR": "", "NO_COLOR": "1"})


def tone(freq: float, seconds: float, amp: float = 0.5) -> np.ndarray:
    t = np.arange(int(seconds * audio.SR)) / audio.SR
    mono = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return np.stack([mono, mono], axis=1)


def mixed_project(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    a = tone(220, 0.2)
    add_track(p, "guitar", a, {"op": "split", "model": "htdemucs_6s", "source": "source/original.flac"})
    add_track(p, "bass", a, {"op": "split", "model": "htdemucs_6s", "source": "source/original.flac"})
    add_track(p, "bass", a, {"op": "merge", "source": "takes/t001.flac"})
    p.tracks["guitar"]["mute"] = True
    p.tracks["bass"]["gain"] = -3.0
    p.save()
    monkeypatch.chdir(p.root)


ABC = """X:1
M:4/4
L:1/32
Q:1/4=121
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
K:Dm
% verse
V: Vocal
"Dm"a4f4z4a4|"C"g4z8c4|
"""


def fake_transcription(src, out_dir, beats=None, bars=None, score=True):
    """Les fichiers d'une transcription réussie ; score=False : SheetSage2 a refusé la partition."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if score:
        (out_dir / "score.abc").write_text(ABC)
    (out_dir / "beat.lab").write_text("".join(f"{0.5 * i:.2f}\t{i % 4 + 1}\t4\t4\n" for i in range(8)))
    (out_dir / "downbeat.lab").write_text("0.00\n2.00\n")
    (out_dir / "chord.lab").write_text("0.0\t1.0\tN\n1.0\t2.0\tD:min\n2.0\t3.0\tF:maj7\n3.0\t4.0\tC:maj\n")
    (out_dir / "key.lab").write_text("0.0\t4.0\tD:minor\n")
    (out_dir / "structure.lab").write_text("0.0\t1.0\tintro\n1.0\t2.0\tchorus\n2.0\t4.0\tchorus\n")
    return {}


def fake_render(abc, lyrics, style, out, *, free=False, seed=-1):
    import soundfile as sf

    fake_render.calls.append({"abc": abc, "lyrics": lyrics, "style": style, "free": free, "seed": seed})
    sf.write(out, tone(220, 4.0, amp=0.3), audio.SR)
    return {"model": "fake", "mode": "free" if free else "close", "style": style, "seed": 7 if seed < 0 else seed}


def song_project(tmp_path, monkeypatch):
    from arr.engines import analysis, separation, transcription, yue2

    fake_render.calls = []
    monkeypatch.setattr(transcription, "transcribe", fake_transcription)
    monkeypatch.setattr(yue2, "render", fake_render)
    stems = {n: tone(f, 4.0, amp=0.1) for n, f in (("drums", 110), ("bass", 55), ("guitar", 330), ("vocals", 440))}
    monkeypatch.setattr(separation, "separate", lambda path, model, shifts: dict(stems))
    # l'original bat à 120 ; les prises sont en retard de 100 ms
    late = lambda path: 0.0 if path.name == "original.flac" else 0.1
    monkeypatch.setattr(
        analysis, "beats", lambda path: ([0.5 * i + late(path) for i in range(8)], [i + late(path) for i in range(4)])
    )
    # beat_this a entendu nettement chaque temps : aucune mesure douteuse
    monkeypatch.setattr(analysis, "activations", lambda path: np.ones((200, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    audio.save(p.root / "source/original.flac", tone(220, 4.0))
    monkeypatch.chdir(p.root)
    return p


def chunks_of(data, seconds=0.05):
    n = int(seconds * audio.SR)
    return [data[i : i + n] for i in range(0, len(data), n)]


def fake_studio(monkeypatch, heard):
    from arr import player, studio

    track = {"id": "/t/1", "title": "Night Drive", "artist": "Paper Lanterns", "length": 2.0, "seek": True}
    # un lecteur ouvert, qui joue ; un test en change la liste par calls["players"] et calls["playing"]
    vlc = "org.mpris.MediaPlayer2.vlc"
    calls = {"played": [], "restart": [], "pause": [], "players": [vlc], "playing": {vlc}, "track": track}
    monkeypatch.setattr(
        studio,
        "config",
        lambda: {
            "output": {"device": "", "channels": [1, 2]},
            "input": {"device": "", "channels": [1], "latency_ms": 0},
            "capture": {"source": "", "channels": [], "loudness": -16.0, "player": calls.get("player", "")},
        },
    )
    monkeypatch.setattr(studio, "capture_source", lambda: ("fake.monitor", heard.shape[1]))
    monkeypatch.setattr(studio, "sources", lambda: [("fake.monitor", heard.shape[1]), ("other", 2)])
    monkeypatch.setattr(studio, "listen", lambda source, channels: iter(chunks_of(heard)))
    calls["looped"] = []

    calls["orders"] = []

    def play(data, loop=None, watch=None, follow=None):
        calls["played"].append(data)
        calls["looped"].append(loop)
        calls["followed"] = follow
        # la lecture « avance » : la position du flux à chaque appel, et ce que l'écran demande en retour
        calls["orders"] += [watch(seconds) for seconds in calls.get("positions", [])]

    monkeypatch.setattr(studio, "play", play)
    monkeypatch.setattr(player, "players", lambda: calls["players"])
    monkeypatch.setattr(player, "playing", lambda name: name in calls["playing"])
    monkeypatch.setattr(
        player,
        "now_playing",
        lambda name, playing_only=False: (
            calls["track"] if name in calls["players"] and (name in calls["playing"] or not playing_only) else None
        ),
    )
    monkeypatch.setattr(
        player, "restart", lambda name, tid: (calls["restart"].append((name, tid)), calls["playing"].add(name))
    )
    monkeypatch.setattr(player, "pause", lambda name: calls["pause"].append(name))
    return calls


def chord_song(bars: int = 24, bpm: float = 120.0) -> np.ndarray:
    """Un « morceau » dont l'harmonie change à chaque mesure et ne se répète jamais.

    Un accord par mesure, réattaqué à chaque temps : l'harmonie situe un passage à la mesure
    près, les attaques au centième de seconde. C'est ce qu'il faut pour tester un calage.
    """
    beat = 60 / bpm
    n = int(beat * audio.SR)
    t = np.arange(n) / audio.SR
    decay = np.exp(-t / 0.15).astype(np.float32)
    out = []
    for bar in range(bars):
        root = 110.0 * 2 ** (((bar * 7) % 12 + (bar // 12)) / 12)  # quintes successives, décalées à chaque tour
        third = 5 / 4 if bar % 3 else 6 / 5
        chord = sum(np.sin(2 * np.pi * root * r * t) for r in (1, third, 3 / 2, 2))
        out += [(0.1 * chord * decay).astype(np.float32)] * 4
    mono = np.concatenate(out)
    return np.stack([mono, mono], axis=1)


def short_bar_song() -> tuple[np.ndarray, list[float], list[float], list[tuple]]:
    """Un morceau à 120 à la noire dont la cinquième mesure n'a que deux temps.

    Renvoie l'audio, ses temps, ses débuts de mesure et ses accords (début, fin, étiquette).
    """
    names = ["A", "Bb", "B", "C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab"]
    whole = chord_song(bars=12)
    bar = 2 * audio.SR
    song = np.concatenate([whole[: 4 * bar + bar // 2], whole[5 * bar :]])
    starts = [2.0 * i for i in range(5)] + [9.0 + 2.0 * i for i in range(7)]
    ends = starts[1:] + [len(song) / audio.SR]
    chords = [
        (start, end, f"{names[(i * 7) % 12]}:{'maj' if i % 3 else 'min'}")
        for i, (start, end) in enumerate(zip(starts, ends, strict=True))
    ]
    return song, [0.5 * i for i in range(int(ends[-1] * 2))], starts, chords
