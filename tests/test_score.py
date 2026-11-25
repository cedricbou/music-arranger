"""Partition, paroles et analyse : transcribe, lyrics, analyze."""

import json
from pathlib import Path

from arr import audio
from arr.cli import app
from arr.engines import _notation, transcription
from arr.project import Project, Section
from tests.helpers import fake_transcription, runner, song_project, tone

REAL_TRANSCRIBE = transcription.transcribe  # avant que song_project le remplace


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


def fake_sheetsage2(monkeypatch, tmp_path, *, error=None, repair_error=None, code=0, labs=True):
    """SheetSage2 en sous-processus, remplacé : il écrit ses fichiers, et repair.json s'il a refusé la partition."""
    import subprocess

    seen = {}

    def run(cmd, **kwargs):
        out = Path(cmd[3])
        seen["grid"] = json.loads(Path(cmd[5]).read_text())
        if labs:
            fake_transcription(None, out, score=not error or not repair_error)
        if error:
            (out / "repair.json").write_text(json.dumps({"error": error, "repair_error": repair_error}))
        return subprocess.CompletedProcess(cmd, code, "", "")

    python = tmp_path / "ss2-python"
    python.touch()
    monkeypatch.setattr(transcription, "transcribe", REAL_TRANSCRIBE)
    monkeypatch.setattr(transcription, "SS2_PYTHON", python)
    monkeypatch.setattr(transcription.subprocess, "run", run)
    return seen


FIVE_BEATS = "Measure 31 (beat rows 122-126): non-consecutive beat IDs [1, 2, 3, 4, 4]"


def test_a_refused_score_is_rewritten_on_the_analyzed_bars(tmp_path, monkeypatch):
    song_project(tmp_path, monkeypatch)
    seen = fake_sheetsage2(monkeypatch, tmp_path, error=FIVE_BEATS)
    result = runner.invoke(app, ["transcribe"])
    assert result.exit_code == 0, result.output
    assert seen["grid"]["beats"] == [0.5 * i for i in range(8)]  # la grille d'arr analyze, passée à SheetSage2
    assert seen["grid"]["bars"] == [0.0, 1.0, 2.0, 3.0]
    assert "une mesure comptée avec un temps de trop ou de moins" in result.output
    assert "réécrite sur les mesures d'arr analyze" in result.output
    assert "-> score/score.abc" in result.output


def test_without_a_score_transcribe_still_saves_tempo_and_sections(tmp_path, monkeypatch):
    p = song_project(tmp_path, monkeypatch)
    fake_sheetsage2(monkeypatch, tmp_path, error=FIVE_BEATS, repair_error="Vocal: overlapping notes")
    result = runner.invoke(app, ["transcribe"])
    assert result.exit_code == 0, result.output
    assert "SheetSage2 n'a pas pu écrire la partition : une mesure comptée" in result.output
    assert "Vocal: overlapping notes" in result.output and "code 0" not in result.output
    p = Project.find()
    assert p.song["bpm"] == 120 and len(p.sections) == 3
    assert (p.root / "analysis.json").exists() and not (p.root / "score/score.abc").exists()
    assert runner.invoke(app, ["chordpro"]).exit_code == 0
    refused = runner.invoke(app, ["render", "-s", "funk"])
    assert refused.exit_code != 0 and "relance-le" in str(refused.exception)


def test_a_transcription_without_chords_is_a_failure_with_a_reason(tmp_path, monkeypatch):
    song_project(tmp_path, monkeypatch)
    fake_sheetsage2(monkeypatch, tmp_path, labs=False)
    result = runner.invoke(app, ["transcribe"])
    assert result.exit_code != 0
    assert "pas d'accords écrits" in str(result.exception)


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


def test_a_five_beat_bar_is_renumbered_on_the_given_bars():
    # SheetSage2 comptait 1 2 3 4 4 ; la grille d'arr analyze dit une barre tous les quatre temps
    times = [0.5 * i for i in range(1, 13)]
    rows = _notation.beat_rows(times, [1.0, 3.0, 5.0], start=0.0, end=6.4)
    assert [r[0] for r in rows] == [0.5 * i for i in range(14)]  # prolongée d'un temps de chaque côté
    assert [r[1] for r in rows] == [3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4]  # levée de deux temps
    assert {(r[2], r[3]) for r in rows} == {(4, 4)}
    # une seule barre connue : la taille donnée
    assert [r[1] for r in _notation.beat_rows(times, [1.5], 0.5, 6.0, size=3)] == [2, 3] + [1, 2, 3] * 3 + [1]


def test_a_short_bar_kept_by_the_grid_stays_short():
    times = [0.5 * i for i in range(14)]
    rows = _notation.beat_rows(times, [0.0, 2.0, 4.0, 5.0], start=0.0, end=6.5)
    assert [r[1] for r in rows] == [1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 1, 2, 3, 4]
    assert [r[2] for r in rows][8:10] == [2, 2]


def test_a_sliver_chord_merges_into_the_one_before():
    beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    chords = [[0.0, 1.984, "A:maj"], [1.984, 2.0, "C#:sus4"]]
    assert _notation.merge_slivers(chords, beats) == [[0.0, 2.0, "A:maj"]]
    first = [[0.0, 0.01, "N"], [0.01, 2.5, "D:min"]]
    assert _notation.merge_slivers(first, beats) == [[0.0, 2.0, "D:min"]]  # coupé à la grille aussi


def test_melody_notes_land_on_the_grid_without_overlap():
    beats = [0.0, 0.5, 1.0]  # subdivisions de 0,125 s
    notes = [(0.0, 0.03, 60), (0.02, 0.3, 62), (0.31, 0.32, 64), (0.9, 2.0, 65)]
    assert _notation.fit_notes(notes, beats) == [
        (0.0, 0.125, 60),
        (0.125, 0.25, 62),
        (0.25, 0.375, 64),
        (0.875, 1.0, 65),
    ]


def test_sheetsage2_reasons_are_said_in_plain_words():
    assert _notation.reason("Interval 1-2 (C#:sus4) is shorter than the ABC subbeat grid").startswith("un accord")
    assert _notation.reason("something new") == "something new"
