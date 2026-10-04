import numpy as np
from typer.testing import CliRunner

from arr import audio
from arr.cli import add_track, app
from arr.project import Project, Section
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
