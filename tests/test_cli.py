import json

import numpy as np
import pytest
from typer.testing import CliRunner

from arr import audio
from arr.cli import add_track, app
from arr.project import Project, ProjectError, Section
from tests.test_core import tone

runner = CliRunner()


def test_merge_sums_tracks_and_mutes_sources(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    piano, guitar = tone(220, 0.5, amp=0.2), tone(330, 0.5, amp=0.3)
    add_track(p, "piano", piano, {"op": "split"})
    add_track(p, "guitar", guitar, {"op": "split"})
    monkeypatch.chdir(p.root)

    result = runner.invoke(app, ["merge", "piano", "guitar", "--as", "synth"])
    assert result.exit_code == 0, result.output

    p = Project.find()
    assert np.allclose(audio.load(p.version_path("synth")), piano + guitar, atol=1e-4)
    assert p.tracks["piano"]["mute"] and p.tracks["guitar"]["mute"]
    assert p.meta("synth", "v001")["source"] == "piano/v001 + guitar/v001"
    assert p.versions("piano") == ["v001"]


def test_merge_into_one_of_the_sources_keeps_it_audible(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "other", tone(220, 0.5, amp=0.2), {"op": "split"})
    add_track(p, "piano", tone(330, 0.5, amp=0.2), {"op": "split"})
    monkeypatch.chdir(p.root)

    assert runner.invoke(app, ["merge", "other", "piano", "--as", "other"]).exit_code == 0

    p = Project.find()
    assert p.tracks["other"]["active"] == "v002" and not p.tracks["other"]["mute"]
    assert p.tracks["piano"]["mute"]


def test_new_split_replaces_previous_stems_and_merges(tmp_path, monkeypatch):
    from arr.engines import separation

    a = tone(220, 0.5, amp=0.2)
    six = {n: a for n in ("drums", "bass", "other", "vocals", "guitar", "piano")}
    four = {n: a for n in ("drums", "bass", "other", "vocals")}
    monkeypatch.setattr(separation, "separate", lambda path, model, shifts: six if model == "htdemucs_6s" else four)

    p = Project.create(tmp_path / "song", "song")
    audio.save(p.root / "source/original.flac", a)
    monkeypatch.chdir(p.root)
    assert runner.invoke(app, ["split"]).exit_code == 0
    assert runner.invoke(app, ["merge", "guitar", "piano", "other", "--as", "synth"]).exit_code == 0
    result = runner.invoke(app, ["split", "--model", "htdemucs_ft"])
    assert result.exit_code == 0, result.output

    p = Project.find()
    audible = {n for n, t in p.tracks.items() if not t.get("mute")}
    assert audible == {"drums", "bass", "other", "vocals"}
    assert p.tracks["other"]["active"] == "v002"
    assert runner.invoke(app, ["split", "--model", "nope"]).exit_code != 0


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


def test_tracks_shows_mix_first_then_muted(tmp_path, monkeypatch):
    mixed_project(tmp_path, monkeypatch)
    out = runner.invoke(app, ["tracks"]).output
    lines = out.splitlines()
    bass = next(l for l in lines if "bass" in l and "v002" in l)
    guitar = next(l for l in lines if "guitar" in l and "v001" in l)
    assert lines.index(bass) < lines.index(guitar)
    assert "sur 2" in bass and "-3.0 dB" in bass and "takes/t001.flac" in bass
    assert "muette" in guitar and "htdemucs_6s" in guitar
    assert "v001" not in bass  # l'historique n'apparaît pas par défaut
    assert "Dans le mix : bass" in out and "1 muette" in out


def test_tracks_history_marks_the_active_version(tmp_path, monkeypatch):
    mixed_project(tmp_path, monkeypatch)
    for args in (["tracks", "-v"], ["tracks", "bass"]):
        out = runner.invoke(app, args).output
        assert "▸ v002" in out and "  v001" in out and "▸ v001" not in out.split("guitar")[0]
    assert "guitar" not in runner.invoke(app, ["tracks", "bass"]).output
    assert runner.invoke(app, ["tracks", "nope"]).exit_code != 0


# --- partition, paroles, prises

ABC = '''X:1
M:4/4
L:1/32
Q:1/4=121
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
K:Dm
% verse
V: Vocal
"Dm"f4d4z4d4|"C"A4z8e4|
'''


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
    monkeypatch.setattr(analysis, "beats", lambda path: ([0.5 * i + late(path) for i in range(8)], [late(path), 2.0 + late(path)]))
    p = Project.create(tmp_path / "song", "song")
    audio.save(p.root / "source/original.flac", tone(220, 4.0))
    monkeypatch.chdir(p.root)
    return p


def test_transcribe_fills_song_sections_and_beats(tmp_path, monkeypatch):
    song_project(tmp_path, monkeypatch)
    result = runner.invoke(app, ["transcribe"])
    assert result.exit_code == 0, result.output
    p = Project.find()
    assert p.song["bpm"] == 120 and p.song["key"] == "D minor" and p.song["duration"] == 4.0
    assert [(s.name, s.start, s.end) for s in p.sections] == [("intro", 0.0, 1.0), ("chorus", 1.0, 2.0), ("chorus2", 2.0, 4.0)]
    assert "Q:1/4=120\n" in (p.root / "score/score.abc").read_text()  # tempo mesuré, pas celui de SheetSage2
    assert runner.invoke(app, ["sections", "set", "a:1-1 b:2-2"]).exit_code == 0  # les mesures viennent de la transcription


def test_render_creates_versioned_takes(tmp_path, monkeypatch):
    p = song_project(tmp_path, monkeypatch)
    assert runner.invoke(app, ["render", "-s", "funk"]).exit_code != 0  # pas encore de partition
    runner.invoke(app, ["transcribe"])
    (p.root / "lyrics.txt").write_text("[Verse]\nla la\n")
    result = runner.invoke(app, ["render", "-s", "funk band", "--seed", "3", "-n", "2"])
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["render", "-s", "jazz trio", "--free"]).exit_code == 0

    p = Project.find()
    assert p.takes() == ["t001", "t002", "t003"]
    assert [c["seed"] for c in fake_render.calls] == [3, 4, -1]
    assert fake_render.calls[0]["lyrics"] == "[Verse]\nla la\n" and fake_render.calls[0]["abc"] == ABC.replace("=121", "=120")
    assert p.take_meta("t003") | {"created": ""} == {"created": "", "model": "fake", "mode": "free", "style": "jazz trio",
                                                    "seed": 7, "score": "score/score.abc", "instrumental": False}
    assert audio.duration(p.take_path("t001")) == 4.0 and not (p.root / "takes/rendu.wav").exists()
    listing = runner.invoke(app, ["takes"]).output
    assert "t001" in listing and "fidèle" in listing and "libre" in listing and "jazz trio" in listing


def test_melody_only_strips_chords_but_not_voice_names():
    from arr.engines.yue2 import melody_only

    out = melody_only(ABC)
    assert '"Dm"' not in out and '"C"' not in out and "f4d4z4d4|A4z8e4|" in out
    assert 'name="Vocal Melody"' in out


def test_split_take_then_graft(tmp_path, monkeypatch):
    p = song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    runner.invoke(app, ["split"])
    runner.invoke(app, ["render", "-s", "funk"])
    assert runner.invoke(app, ["graft", "t001", "guitar"]).exit_code != 0  # pas encore séparée
    result = runner.invoke(app, ["split", "t001"])
    assert result.exit_code == 0, result.output

    p = Project.find()
    audible = lambda: {n for n, t in Project.find().tracks.items() if not t.get("mute")}
    assert audible() == {"drums", "bass", "guitar", "vocals"}  # les stems de la prise arrivent muets
    meta = p.meta("t001.guitar", "v001")
    assert meta["superposable"] and meta["on_beat"] == 1.0 and meta["offset_ms"] == 100 and meta["speed"] == 1.0
    # la prise était en retard de 100 ms sur l'original : ses stems sont avancés d'autant
    got = audio.load(p.version_path("t001.guitar"))
    k = audio.SR // 10
    assert len(got) == 4 * audio.SR and not got[-k // 2 :].any() and got[: 3 * audio.SR].any()

    assert runner.invoke(app, ["graft", "t001", "guitar"]).exit_code == 0
    assert audible() == {"drums", "bass", "guitar", "vocals", "t001.guitar"}
    assert runner.invoke(app, ["graft", "t001", "drums", "bass", "--replace"]).exit_code == 0
    assert audible() == {"guitar", "vocals", "t001.guitar", "t001.drums", "t001.bass"}
    assert runner.invoke(app, ["graft", "t001", "kazoo"]).exit_code != 0
    assert runner.invoke(app, ["split"]).exit_code == 0  # re-séparer l'original ne touche pas aux greffes
    assert {"t001.guitar", "t001.drums"} <= audible()


def test_split_take_stretches_to_the_original_tempo(tmp_path, monkeypatch):
    from arr.engines import analysis

    song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    runner.invoke(app, ["render", "-s", "funk"])
    original = analysis.beats
    # la prise bat 1 % plus vite que l'original
    monkeypatch.setattr(analysis, "beats", lambda path: original(path) if path.name == "original.flac"
                        else ([0.495 * i for i in range(8)], [0.0, 1.98]))
    assert runner.invoke(app, ["split", "t001"]).exit_code == 0
    meta = Project.find().meta("t001.guitar", "v001")
    assert meta["superposable"] and meta["speed"] == 0.99 and meta["offset_ms"] == 0


def test_split_take_off_the_grid_is_flagged(tmp_path, monkeypatch):
    from arr.engines import analysis

    song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    runner.invoke(app, ["render", "-s", "funk"])
    original = analysis.beats
    # même tempo, mais la seconde moitié a glissé de 200 ms (une mesure en trop, par exemple)
    drifting = [0.5 * i + (0.2 if i >= 4 else 0.0) for i in range(8)]
    monkeypatch.setattr(analysis, "beats", lambda path: original(path) if path.name == "original.flac"
                        else (drifting, [0.0, 2.0]))
    result = runner.invoke(app, ["split", "t001"])
    assert result.exit_code == 0, result.output
    meta = Project.find().meta("t001.guitar", "v001")
    assert meta["superposable"] is False and meta["on_beat"] <= 0.5


def test_split_take_at_another_tempo_is_flagged(tmp_path, monkeypatch):
    from arr.engines import analysis

    song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    runner.invoke(app, ["render", "-s", "funk", "--free"])
    original = analysis.beats
    monkeypatch.setattr(analysis, "beats", lambda path: original(path) if path.name == "original.flac"
                        else ([0.45 * i for i in range(9)], [0.0, 1.8]))
    result = runner.invoke(app, ["split", "t001"])
    assert result.exit_code == 0, result.output
    assert Project.find().meta("t001.guitar", "v001")["superposable"] is False


def test_share_exports_part_mix_and_backing(tmp_path, monkeypatch):
    import shutil

    import pytest

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg absent")
    p = song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["split"])
    result = runner.invoke(app, ["share", "guitar"])
    assert result.exit_code == 0, result.output
    out = p.root / "export/guitar"
    assert {f.name for f in out.iterdir()} == {"partie.mp3", "mix.mp3", "sans.mp3"}
    assert abs(audio.duration(out / "sans.mp3") - 4.0) < 0.1


def test_lyrics_are_sorted_into_sections(tmp_path, monkeypatch):
    from arr import lyrics

    p = song_project(tmp_path, monkeypatch)
    synced = "[00:00.20] one\n[00:01.10] two\n[00:01.60] three\n[00:02.50] four\n[00:09.00] five\n"
    monkeypatch.setattr(lyrics, "fetch", lambda artist, title: {"plainLyrics": "one\ntwo", "syncedLyrics": synced})
    assert runner.invoke(app, ["lyrics", "fetch", "Artist", "Title"]).exit_code == 0
    assert (p.root / "lyrics.txt").read_text() == "one\ntwo\n"  # pas encore de sections : paroles brutes
    assert runner.invoke(app, ["lyrics", "fetch", "Artist", "Title"]).exit_code != 0  # n'écrase pas

    runner.invoke(app, ["transcribe"])
    assert runner.invoke(app, ["lyrics", "fetch", "Artist", "Title", "--force"]).exit_code == 0
    assert (p.root / "lyrics.txt").read_text() == "[Intro]\none\n\n[Chorus]\ntwo\nthree\n\n[Chorus]\nfour\nfive\n"


def test_lyrics_timestamps_are_shifted_to_the_recording():
    from arr import lyrics

    sections = [Section("intro", 0.0, 3.0), Section("verse", 3.0, 6.0)]
    synced = "[00:01.00] one\n[00:02.00] two\n"
    assert lyrics.tagged(synced, sections) == "[Intro]\none\ntwo\n\n[Verse]\n"
    # la voix entre à 3,5 s dans l'enregistrement : tout glisse de 2,5 s
    assert lyrics.tagged(synced, sections, first_sung=3.5) == "[Intro]\n\n[Verse]\none\ntwo\n"


# --- studio : capture, lecture partielle, enregistrement


def chunks_of(data, seconds=0.05):
    n = int(seconds * audio.SR)
    return [data[i: i + n] for i in range(0, len(data), n)]


def test_gate_keeps_the_song_and_drops_the_silences():
    from arr import studio

    silence = lambda s: np.zeros((int(s * audio.SR), 2), np.float32)
    song = tone(220, 2.0, amp=0.3)
    started = []
    out = studio.gate(chunks_of(np.concatenate([silence(1.0), song, silence(5.0), tone(440, 1.0)])),
                      silence=3.0, on_start=lambda: started.append(True))
    assert started == [True]
    assert 2.2 <= len(out) / audio.SR <= 2.9  # un peu d'avance, un peu de queue, pas le son suivant
    assert not out[: int(0.1 * audio.SR)].any() and out[int(0.5 * audio.SR)].any()

    out = studio.gate(chunks_of(np.concatenate([song, song])), should_stop=lambda: True)
    assert len(out) / audio.SR < 0.2  # arrêt demandé (changement de titre)
    with pytest.raises(ProjectError):
        studio.gate(chunks_of(silence(1.0)))


def test_stereo_picks_requested_or_loudest_pair():
    from arr import studio

    captured = np.zeros((1000, 12), np.float32)
    captured[:, 6], captured[:, 7], captured[:, 0] = 0.3, 0.2, 0.05
    assert np.allclose(studio.stereo(captured, [])[0], [0.3, 0.2])       # paire 7/8, la plus forte
    assert np.allclose(studio.stereo(captured, [1, 2])[0], [0.05, 0.0])  # paire imposée
    assert studio.stereo(captured, [7]).shape == (1000, 2)               # mono dupliqué


def fake_studio(monkeypatch, heard):
    from arr import spotify, studio

    track = {"id": "/t/1", "title": "Freed From Desire", "artist": "Gala", "length": 2.0}
    calls = {"played": [], "restart": [], "pause": 0}
    monkeypatch.setattr(studio, "config", lambda: {
        "output": {"device": "", "channels": [1, 2]}, "input": {"device": "", "channels": [1], "latency_ms": 0},
        "capture": {"source": "", "channels": []}})
    monkeypatch.setattr(studio, "capture_source", lambda: ("fake.monitor", heard.shape[1]))
    monkeypatch.setattr(studio, "sources", lambda: [("fake.monitor", heard.shape[1]), ("other", 2)])
    monkeypatch.setattr(studio, "listen", lambda source, channels: iter(chunks_of(heard)))
    monkeypatch.setattr(studio, "play", lambda data: calls["played"].append(data))
    monkeypatch.setattr(spotify, "now_playing", lambda playing_only=False: track)
    monkeypatch.setattr(spotify, "restart", lambda tid: calls["restart"].append(tid))
    monkeypatch.setattr(spotify, "pause", lambda: calls.__setitem__("pause", calls["pause"] + 1))
    return calls


def test_capture_creates_a_project_named_after_the_song(tmp_path, monkeypatch):
    quiet = np.zeros((audio.SR, 2), np.float32)
    # 1 s de silence, le morceau (2 s), puis le morceau suivant enchaîné sans silence
    heard = np.concatenate([quiet, tone(220, 2.0, amp=0.3), tone(880, 3.0, amp=0.3)])
    calls = fake_studio(monkeypatch, heard)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["capture", "--play"])
    assert result.exit_code == 0, result.output
    p = Project(tmp_path / "freed-from-desire")
    assert p.song["title"] == "Freed From Desire" and p.song["artist"] == "Gala"
    assert calls["restart"] == ["/t/1"] and calls["pause"] == 1
    # coupé à la durée annoncée par Spotify (+ marge) : le morceau suivant n'y est presque pas
    assert 2.0 <= p.song["duration"] <= 3.3
    assert runner.invoke(app, ["capture", "freed-from-desire"]).exit_code != 0  # n'écrase pas un projet


def test_lyrics_fetch_defaults_to_the_project_song(tmp_path, monkeypatch):
    from arr import lyrics

    p = Project.create(tmp_path / "song", "Freed From Desire")
    monkeypatch.chdir(p.root)
    asked = []
    monkeypatch.setattr(lyrics, "fetch", lambda artist, title: asked.append((artist, title)) or {"plainLyrics": "la"})
    assert runner.invoke(app, ["lyrics", "fetch"]).exit_code != 0  # pas d'artiste connu
    p.song["artist"] = "Gala"
    p.save()
    assert runner.invoke(app, ["lyrics", "fetch"]).exit_code == 0
    assert asked == [("Gala", "Freed From Desire")]


def test_play_partial_mix(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    for name, f in (("drums", 110), ("bass", 55), ("guitar", 330)):
        add_track(p, name, tone(f, 0.5, amp=0.1), {"op": "split"})
    monkeypatch.chdir(p.root)
    total = lambda *fs: sum(tone(f, 0.5, amp=0.1) for f in fs)

    assert runner.invoke(app, ["play", "--without", "bass"]).exit_code == 0
    assert runner.invoke(app, ["play", "-o", "bass", "-o", "drums"]).exit_code == 0
    assert runner.invoke(app, ["play", "guitar"]).exit_code == 0
    assert np.allclose(calls["played"][0], total(110, 330), atol=1e-3)
    assert np.allclose(calls["played"][1], total(110, 55), atol=1e-3)
    assert np.allclose(calls["played"][2], total(330), atol=1e-3)


def test_record_plays_backing_with_count_in_and_compensates_latency(tmp_path, monkeypatch):
    from arr import studio

    fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "drums", tone(110, 4.0, amp=0.1), {"op": "split"})
    add_track(p, "bass", tone(55, 4.0, amp=0.1), {"op": "split"})
    # temps toutes les 0,5 s à partir de 0,5 s : un décompte de 4 temps doit commencer à -1,5 s
    beats = [0.5 * i + 0.5 for i in range(7)]
    (p.root / "analysis.json").write_text(json.dumps({"beats": beats, "downbeats": [0.5, 2.5]}))
    monkeypatch.chdir(p.root)
    heard = {}

    def fake_duplex(playback, channel):
        heard["playback"], heard["channel"] = playback, channel
        # le musicien « joue » un son reconnaissable, que la carte restitue 100 ms en retard
        played = np.concatenate([np.zeros((int(1.5 * audio.SR), 2), np.float32), tone(880, 4.0, amp=0.2)])
        return audio.shift(audio.fit(played, len(playback)), 0.1), 0.1

    monkeypatch.setattr(studio, "play_and_record", fake_duplex)
    result = runner.invoke(app, ["record", "bass", "--channel", "3"])
    assert result.exit_code == 0, result.output

    playback = heard["playback"]
    assert heard["channel"] == 3 and len(playback) == int(5.5 * audio.SR)  # 1,5 s de décompte en plus
    lead = playback[: int(1.5 * audio.SR)]
    assert np.abs(lead).max() > 0.3 and not lead[int(0.1 * audio.SR): int(0.4 * audio.SR)].any()  # des clics, pas de musique
    body = playback[int(1.6 * audio.SR): int(1.9 * audio.SR)]
    assert np.allclose(body, tone(110, 4.0, amp=0.1)[int(0.1 * audio.SR): int(0.4 * audio.SR)], atol=1e-3)  # batterie seule, sans la basse

    p = Project.find()
    assert p.versions("bass") == ["v001", "v002"] and p.meta("bass", "v002")["latency_ms"] == 100
    take = audio.load(p.version_path("bass"))
    assert len(take) == 4 * audio.SR
    assert np.allclose(take[: 3 * audio.SR], tone(880, 4.0, amp=0.2)[: 3 * audio.SR], atol=1e-3)  # calé sur le début du morceau


def test_calibrate_measures_and_saves_the_round_trip(tmp_path, monkeypatch):
    from arr import studio

    fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    monkeypatch.setattr(studio, "CONFIG", tmp_path / "audio.toml")
    (tmp_path / "audio.toml").write_text('[output]\ndevice = "X"\n')
    monkeypatch.setattr(studio, "play_and_record", lambda playback, channel: (audio.shift(playback, 0.0375) * 0.5, 0.0))
    result = runner.invoke(app, ["calibrate"])
    assert result.exit_code == 0, result.output
    saved = (tmp_path / "audio.toml").read_text()
    assert "latency_ms = 37.5" in saved and 'device = "X"' in saved  # les autres réglages restent

    monkeypatch.setattr(studio, "play_and_record", lambda playback, channel: (np.zeros_like(playback), 0.0))
    assert runner.invoke(app, ["calibrate"]).exit_code != 0  # rien n'est revenu : pas de valeur écrite
    assert "latency_ms = 37.5" in (tmp_path / "audio.toml").read_text()


def test_capture_source_follows_the_setup(monkeypatch):
    from arr import studio

    known = [("alsa_output.presonus.monitor", 2), ("alsa_output.Soundcraft.monitor", 12), ("alsa_input.Soundcraft.multi", 14)]
    monkeypatch.setattr(studio, "sources", lambda: known)
    monkeypatch.setattr(studio, "default_monitor", lambda: known[0])
    setting = {"source": ""}
    monkeypatch.setattr(studio, "config", lambda: {"capture": setting})
    assert studio.capture_source() == ("alsa_input.Soundcraft.multi", 14)  # les entrées de la table, pas son moniteur
    setting["source"] = "monitor"
    assert studio.capture_source() == ("alsa_output.presonus.monitor", 2)
    setting["source"] = "alsa_output.Soundcraft.monitor"
    assert studio.capture_source() == ("alsa_output.Soundcraft.monitor", 12)
    setting["source"] = "nope"
    with pytest.raises(ProjectError):
        studio.capture_source()
    monkeypatch.setattr(studio, "sources", lambda: known[:1])
    setting["source"] = ""
    assert studio.capture_source() == known[0]  # sans la table : copie numérique de la sortie


def test_levels_reports_each_channel(monkeypatch):
    heard = np.zeros((audio.SR, 4), np.float32)
    heard[:, 2] = audio.db(-12) * np.sign(np.sin(np.arange(audio.SR)))  # canal 3 : bon niveau
    heard[:, 3] = 1.0                                                   # canal 4 : sature
    fake_studio(monkeypatch, heard)
    result = runner.invoke(app, ["levels", "--seconds", "0.5"])
    assert result.exit_code == 0, result.output
    lines = [l for l in result.output.splitlines() if "canal" in l and "crête" in l]
    assert "rien" in lines[0] and "-12.0 dB  bon niveau" in lines[2] and "SATURE" in lines[3]
    assert runner.invoke(app, ["levels", "--seconds", "0.2", "--source", "nope"]).exit_code != 0


def test_record_refuses_a_silent_take(tmp_path, monkeypatch):
    from arr import studio

    fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "drums", tone(110, 1.0, amp=0.1), {"op": "split"})
    monkeypatch.chdir(p.root)
    monkeypatch.setattr(studio, "play_and_record", lambda playback, channel: (np.zeros_like(playback), 0.0))
    result = runner.invoke(app, ["record", "bass", "--count-in", "0"])
    assert result.exit_code != 0 and "bass" not in Project.find().tracks
