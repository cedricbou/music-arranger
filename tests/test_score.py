"""Partition, paroles et analyse : transcribe, lyrics, analyze."""

import json

from arr import audio
from arr.cli import app
from arr.project import Project, Section
from tests.helpers import runner, song_project, tone


def test_transcribe_fills_song_sections_and_beats(tmp_path, monkeypatch):
    song_project(tmp_path, monkeypatch)
    result = runner.invoke(app, ["transcribe"])
    assert result.exit_code == 0, result.output
    p = Project.find()
    assert p.song["bpm"] == 120 and p.song["key"] == "D minor" and p.song["duration"] == 4.0
    assert [(s.name, s.start, s.end) for s in p.sections] == [
        ("intro", 0.0, 1.0),
        ("chorus", 1.0, 2.0),
        ("chorus2", 2.0, 4.0),
    ]
    assert "Q:1/4=120\n" in (p.root / "score/score.abc").read_text()  # tempo mesuré, pas celui de SheetSage2
    assert (
        runner.invoke(app, ["sections", "set", "a:1-1 b:2-2"]).exit_code == 0
    )  # les mesures viennent de la transcription


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


def test_lyrics_keep_the_time_of_each_line(tmp_path, monkeypatch):
    from arr import lyrics

    p = song_project(tmp_path, monkeypatch)
    synced = "[00:00.20] one\n[00:01.10] two\n[00:01.60] three\n[00:02.50] four\n[00:09.00] five\n"
    found = {"plainLyrics": "one", "syncedLyrics": synced}
    monkeypatch.setattr(lyrics, "fetch", lambda artist, title: found)
    runner.invoke(app, ["transcribe"])
    assert runner.invoke(app, ["lyrics", "fetch", "Artist", "Title"]).exit_code == 0
    # lyrics.txt est celui d'avant, l'horodatage est gardé à côté, tel quel
    assert (p.root / "lyrics.txt").read_text() == "[Intro]\none\n\n[Chorus]\ntwo\nthree\n\n[Chorus]\nfour\nfive\n"
    assert (p.root / "lyrics.lrc").read_text() == synced

    # une ligne corrigée garde l'instant de celle qu'elle remplace ; une ligne ajoutée n'en a pas
    (p.root / "lyrics.txt").write_text(
        "[Intro]\none\n\n[Chorus]\nTwo, corrected!\nthree\n\n[Chorus]\nfour\nmine\nfive\n"
    )
    out = runner.invoke(app, ["lyrics", "show"]).output
    assert "mes. 1   one" in out and "mes. 2   Two, corrected!" in out and "mes. 2   three" in out
    assert "mes. 3   four" in out and "—    mine" in out and "mes. 4   five" in out
    assert "1 ligne(s) sur 6 sans instant" in out

    # un projet aux paroles déjà corrigées : seuls les instants s'ajoutent
    (p.root / "lyrics.lrc").unlink()
    before = (p.root / "lyrics.txt").read_text()
    assert "6 lignes sans instant : arr lyrics fetch --times" in runner.invoke(app, ["lyrics", "show"]).output
    out = runner.invoke(app, ["lyrics", "fetch", "--times", "Artist", "Title"]).output
    assert "lyrics.lrc : 5 lignes horodatées" in out
    assert (p.root / "lyrics.txt").read_text() == before and (p.root / "lyrics.lrc").read_text() == synced

    # une source sans horodatage ne donne pas d'instants
    found["syncedLyrics"] = None
    result = runner.invoke(app, ["lyrics", "fetch", "--times", "Artist", "Title"])
    assert result.exit_code != 0 and "pas d'horodatage" in str(result.exception)


def test_lyrics_show_needs_one_tag_per_section(tmp_path, monkeypatch):
    p = song_project(tmp_path, monkeypatch)
    runner.invoke(app, ["transcribe"])
    result = runner.invoke(app, ["lyrics", "show"])
    assert result.exit_code != 0 and "arr lyrics fetch" in str(result.exception)
    (p.root / "lyrics.txt").write_text("[Verse]\nla\n")
    result = runner.invoke(app, ["lyrics", "show"])
    assert result.exit_code != 0 and "1 balises pour 3 sections" in str(result.exception)


def test_lyrics_fetch_defaults_to_the_project_song(tmp_path, monkeypatch):
    from arr import lyrics

    p = Project.create(tmp_path / "song", "Night Drive")
    monkeypatch.chdir(p.root)
    asked = []
    monkeypatch.setattr(lyrics, "fetch", lambda artist, title: asked.append((artist, title)) or {"plainLyrics": "la"})
    assert runner.invoke(app, ["lyrics", "fetch"]).exit_code != 0  # pas d'artiste connu
    p.song["artist"] = "Paper Lanterns"
    p.save()
    assert runner.invoke(app, ["lyrics", "fetch"]).exit_code == 0
    assert asked == [("Paper Lanterns", "Night Drive")]


def test_analyze_writes_tempo_key_and_beat_grid(tmp_path, monkeypatch):
    from arr.engines import analysis

    p = Project.create(tmp_path / "song", "song")
    audio.save(p.root / "source/original.flac", tone(440, 4.0))
    monkeypatch.chdir(p.root)
    monkeypatch.setattr(analysis, "beats", lambda path: ([0.5 * i for i in range(8)], [0.0, 2.0]))
    result = runner.invoke(app, ["analyze"])
    assert result.exit_code == 0, result.output
    p = Project.find()
    assert p.song["bpm"] == 120.0 and p.song["duration"] == 4.0
    assert p.song["key"].split()[0] == "A"  # un la à 440 Hz
    assert json.loads((p.root / "analysis.json").read_text())["downbeats"] == [0.0, 2.0]


def test_beats_load_the_weights_from_the_hugging_face_cache(tmp_path, monkeypatch):
    import beat_this.inference
    import huggingface_hub

    from arr.engines import analysis

    asked, loaded = [], []

    def download(repo, filename, revision):
        asked.append((repo, filename, revision))
        return str(tmp_path / filename)

    class File2Beats:
        def __init__(self, checkpoint_path, device, dbn):
            loaded.append(checkpoint_path)

        def __call__(self, path):
            return [0.0, 0.5], [0.0]

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    monkeypatch.setattr(beat_this.inference, "File2Beats", File2Beats)
    monkeypatch.setattr(analysis, "device", lambda: "cpu")
    assert analysis.beats(tmp_path / "morceau.flac") == ([0.0, 0.5], [0.0])
    assert asked == [(analysis.BEAT_THIS_REPO, "final0.ckpt", analysis.BEAT_THIS_REVISION)]
    assert loaded == [str(tmp_path / "final0.ckpt")]  # un chemin local : beat_this ne va pas chercher ailleurs


def test_chords_are_read_from_the_transcription(tmp_path):
    from arr.engines import transcription

    assert transcription.chords(tmp_path) == []
    (tmp_path / "chord.lab").write_text("0.01\t1.11\tN\n1.11\t2.97\tD:min\n")
    assert transcription.chords(tmp_path) == [(0.01, 1.11, "N"), (1.11, 2.97, "D:min")]
    assert transcription.beats(tmp_path) == []
    (tmp_path / "beat.lab").write_text("0.01\t1\t5\t8\n0.22\t2\t5\t8\n1.11\t1\t4\t4\n")
    assert transcription.beats(tmp_path) == [(0.01, 1), (0.22, 2), (1.11, 1)]


def test_sections_snap_puts_an_existing_project_on_its_bars(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    p.song["duration"] = 20.0
    p.set_sections([Section("intro", 0.0, 4.3), Section("blip", 4.3, 4.5), Section("verse", 4.5, 20.0)])
    p.save()
    monkeypatch.chdir(p.root)
    assert runner.invoke(app, ["sections", "snap"]).exit_code != 0  # pas d'analyse

    (p.root / "analysis.json").write_text(json.dumps({"beats": [], "downbeats": [2.0 * i for i in range(10)]}))
    result = runner.invoke(app, ["sections", "snap"])
    assert result.exit_code == 0, result.output
    assert [vars(s) for s in Project.find().sections] == [
        {"name": "intro", "start": 0.0, "end": 4.0},
        {"name": "verse", "start": 4.0, "end": 20.0},
    ]
    assert "retirées : blip" in result.output
