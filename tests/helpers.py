"""Faux moteurs et projets d'essai partagés par les tests : aucun test ne charge de modèle ni n'ouvre de carte son."""

import numpy as np
from typer.testing import CliRunner

from arr import audio
from arr.cli import add_track
from arr.project import Project

runner = CliRunner()


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
"Dm"f4d4z4d4|"C"A4z8e4|
"""


def fake_transcription(src, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "score.abc").write_text(ABC)
    (out_dir / "beat.lab").write_text("".join(f"{0.5 * i:.2f}\t{i % 4 + 1}\t4\t4\n" for i in range(8)))
    (out_dir / "downbeat.lab").write_text("0.00\n2.00\n")
    (out_dir / "key.lab").write_text("0.0\t4.0\tD:minor\n")
    (out_dir / "structure.lab").write_text("0.0\t1.0\tintro\n1.0\t2.0\tchorus\n2.0\t4.0\tchorus\n")


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
        analysis, "beats", lambda path: ([0.5 * i + late(path) for i in range(8)], [late(path), 2.0 + late(path)])
    )
    p = Project.create(tmp_path / "song", "song")
    audio.save(p.root / "source/original.flac", tone(220, 4.0))
    monkeypatch.chdir(p.root)
    return p


def chunks_of(data, seconds=0.05):
    n = int(seconds * audio.SR)
    return [data[i : i + n] for i in range(0, len(data), n)]


def fake_studio(monkeypatch, heard):
    from arr import spotify, studio

    track = {"id": "/t/1", "title": "Freed From Desire", "artist": "Gala", "length": 2.0}
    calls = {"played": [], "restart": [], "pause": 0}
    monkeypatch.setattr(
        studio,
        "config",
        lambda: {
            "output": {"device": "", "channels": [1, 2]},
            "input": {"device": "", "channels": [1], "latency_ms": 0},
            "capture": {"source": "", "channels": [], "loudness": -16.0},
        },
    )
    monkeypatch.setattr(studio, "capture_source", lambda: ("fake.monitor", heard.shape[1]))
    monkeypatch.setattr(studio, "sources", lambda: [("fake.monitor", heard.shape[1]), ("other", 2)])
    monkeypatch.setattr(studio, "listen", lambda source, channels: iter(chunks_of(heard)))
    calls["looped"] = []

    def play(data, loop=None):
        calls["played"].append(data)
        calls["looped"].append(loop)

    monkeypatch.setattr(studio, "play", play)
    monkeypatch.setattr(spotify, "now_playing", lambda playing_only=False: track)
    monkeypatch.setattr(spotify, "restart", lambda tid: calls["restart"].append(tid))
    monkeypatch.setattr(spotify, "pause", lambda: calls.__setitem__("pause", calls["pause"] + 1))
    return calls
