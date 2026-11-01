"""Antisèche d'un morceau : proposition, fichier, transposition."""

import json

from arr import sheet
from arr.cli import app
from arr.project import Project, Section
from tests.helpers import fake_transcription, runner


def bars(*cells: str, beats: int = 4, start: float = 0.0) -> list[tuple]:
    """Des mesures de grille d'accords : « F:maj » ou « G:min A:maj » (deux accords dans la mesure)."""
    out = []
    for i, cell in enumerate(cells):
        a, b = start + 2.0 * i, start + 2.0 * i + 2.0
        labels = cell.split()
        out.append((a, b, beats, [(j, beats // len(labels), label, a, b) for j, label in enumerate(labels)]))
    return out


def test_chord_lines_are_reduced_to_what_repeats():
    phrase = ["F:maj", "G:min A:maj", "D:min", "Bb:maj C:maj"]
    assert sheet.motif(bars(*phrase * 2)) == ("F | Gm A | Dm | Bb C", 2)
    assert sheet.motif(bars(*phrase)) == ("F | Gm A | Dm | Bb C", 1)
    # un motif suivi d'autre chose, et une mesure tenue : notés dans la ligne
    assert sheet.motif(bars(*phrase * 2, "G:min", "N", "N", "N")) == ("[F | Gm A | Dm | Bb C] ×2 | Gm | – ×3", 1)
    assert sheet.motif(bars("F:maj", "F:maj")) == ("F | F", 1)  # deux mesures égales ne valent pas un signe
    # un long passage sans répétition est coupé
    names = [f"{n}:maj" for n in "CDEFGAB"] + [f"{n}:min" for n in "CDEFGAB"] + ["C:maj7", "D:maj7", "E:maj7"]
    chords, times = sheet.brief(bars(*names))
    assert chords.endswith("| …") and chords.count("|") == 16 and times == 1


def test_structure_counts_bars_and_extra_beats():
    sections = [Section("intro", 0.0, 4.0), Section("verse", 4.0, 8.0), Section("verse2", 8.0, 12.0)]
    sections += [Section("chorus", 12.0, 18.0), Section("outro", 18.0, 18.5)]
    chart = bars(*["C:maj"] * 8) + bars("F:maj", beats=2, start=16.0)
    passages = sheet.groups(sections, chart)
    # les deux couplets voisins n'en font qu'un ; la fin, sans mesure, disparaît
    assert [(name, len(b)) for name, b in passages] == [("intro", 2), ("verse", 4), ("chorus", 3)]
    assert sheet.structure(passages) == "Intro 2 · C 4 · R 2+2t"


def test_proposal_keeps_the_most_common_pattern_of_each_passage():
    sections = [Section("verse", 0.0, 4.0), Section("chorus", 4.0, 12.0)]
    sections += [Section("verse2", 12.0, 20.0), Section("interlude", 20.0, 28.0), Section("verse3", 28.0, 36.0)]
    chart = bars("A:maj", "A:maj") + bars("D:min", "G:maj", "D:min", "G:maj", start=4.0)
    chart += bars("A:min", "E:maj", "A:min", "E:maj", start=12.0) + bars(*["C:maj"] * 4, start=20.0)
    chart += bars("A:min", "E:maj", "A:min", "E:maj", start=28.0)
    got = sheet.propose({"key": "A minor", "bpm": 120.4}, sections, chart)
    assert (got["key"], got["bpm"], got["transpose"], got["notes"]) == ("Am", 120, 0, [])
    assert got["parts"] == [
        {"name": "Couplet", "chords": "Am | E", "repeat": 2},  # le premier couplet, différent, ne l'emporte pas
        {"name": "Refrain", "chords": "Dm | G", "repeat": 2},
    ]


def test_transposition_moves_key_and_chords_with_the_right_spelling():
    assert sheet.key_name("F major") == "F" and sheet.key_name("D minor") == "Dm" and sheet.key_name("Dm") == "Dm"
    assert sheet.transpose_key("F", -2) == "Eb" and sheet.transpose_key("Dm", -2) == "Cm"
    assert sheet.transpose_key("F", 2) == "G" and sheet.transpose_key("Am", 3) == "Cm"
    assert sheet.transpose("F | Gm A | Dm | Bb C", -2, "Eb") == "Eb | Fm G | Cm | Ab Bb"
    assert sheet.transpose("[F | Fmaj7 C/E] ×2 | – ×3", 2, "G") == "[G | Gmaj7 D/F#] ×2 | – ×3"
    assert sheet.transpose("Em7 A", 1, "Bb") == "Fm7 Bb"
    assert sheet.transpose("F | Gm", 0, "F") == "F | Gm"

    played = sheet.played({"key": "F", "transpose": -2, "parts": [{"name": "Couplet", "chords": "F | Bb"}]})
    assert played["key"] == "Eb" and played["parts"][0]["chords"] == "Eb | Ab"
    # une setlist peut imposer une autre transposition que celle du fichier
    assert sheet.played({"key": "F", "transpose": -2, "parts": []}, 0)["key"] == "F"


def transcribed(tmp_path, monkeypatch) -> Project:
    p = Project.create(tmp_path / "song", "song")
    p.song.update(title="Freed From Desire", artist="Gala", key="D minor", bpm=121.0)
    p.set_sections([Section("verse", 0.0, 2.0), Section("chorus", 2.0, 4.0)])
    p.save()
    fake_transcription(None, p.root / "score")
    grid = {"beats": [0.5 * i for i in range(8)], "downbeats": [0.0, 2.0]}
    (p.root / "analysis.json").write_text(json.dumps(grid))
    monkeypatch.chdir(p.root)
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    return p


def test_sheet_is_proposed_then_owned_by_its_file(tmp_path, monkeypatch):
    p = transcribed(tmp_path, monkeypatch)
    out = runner.invoke(app, ["sheet"]).output
    assert "Freed From Desire – Gala" in out and "Dm · 121 BPM" in out and "C 1 · R 1" in out
    assert "proposition déduite du projet" in out and not (p.root / "sheet.toml").exists()

    # un rappel écrit le fichier, qui fait foi ensuite
    out = runner.invoke(app, ["sheet", "--note", "départ batterie seule"]).output
    assert "• départ batterie seule" in out and "(sheet.toml)" in out
    written = sheet.load(p.root)
    assert written["notes"] == ["départ batterie seule"] and written["key"] == "Dm"
    assert (p.root / "sheet.toml").read_text().startswith("# Antisèche du morceau")

    written["parts"] = [{"name": "Riff", "chords": "Dm | F C", "repeat": 4}]
    sheet.save(p.root, written)
    out = runner.invoke(app, ["sheet", "--transpose=-2"]).output
    assert "Cm · 121 BPM" in out and "transposé de -2" in out and "Cm | Eb Bb" in out and "×4" in out
    assert sheet.load(p.root)["parts"][0]["chords"] == "Dm | F C"  # le fichier reste dans la tonalité d'origine

    # retour à la proposition : le fichier part à la corbeille
    out = runner.invoke(app, ["sheet", "--reset"]).output
    assert "proposition déduite du projet" in out and "Riff" not in out
    assert not (p.root / "sheet.toml").exists() and list((p.root / "trash").rglob("sheet.toml"))


def test_sheet_edit_writes_the_proposal_and_points_to_it(tmp_path, monkeypatch):
    p = transcribed(tmp_path, monkeypatch)
    out = runner.invoke(app, ["sheet", "--edit"]).output
    assert "à modifier" in out and "sheet.toml" in out
    assert sheet.load(p.root)["structure"] == "C 1 · R 1"

    (p.root / "sheet.toml").write_text("key = [")
    result = runner.invoke(app, ["sheet"])
    assert result.exit_code != 0 and "mal écrit" in str(result.exception)


def test_sheet_needs_a_transcribed_song(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    monkeypatch.chdir(p.root)
    result = runner.invoke(app, ["sheet"])
    assert result.exit_code != 0 and "arr transcribe" in str(result.exception)
