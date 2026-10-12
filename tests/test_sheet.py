"""Antisèche d'un morceau : proposition, fichier, transposition."""

import json

import pytest

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


def transcribed(tmp_path, monkeypatch, folder: str = "song", title: str = "Freed From Desire") -> Project:
    p = Project.create(tmp_path / folder, folder)
    p.song.update(title=title, artist="Gala", key="D minor", bpm=121.0, duration=200.0)
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


def test_pdf_blocks_wrap_and_flow_without_cutting_a_song():
    from arr import pdf

    song = {
        "key": "Dm",
        "bpm": 121,
        "structure": "Intro 4 · C 16 · R 8",
        "parts": [{"name": "Couplet", "chords": " | ".join(["Dm | Fmaj7 C | Bb | C"] * 6), "repeat": 2}],
        "notes": ["départ batterie seule"],
    }
    entry = lambda n: {"number": n, "title": "Freed From Desire", "artist": "Gala", "sheet": song, "note": "enchaîner"}
    doc = pdf.Sheet()
    lines = pdf.block(doc, entry(3), 90.0)
    text = [[segment[1] for segment in segments] for _, segments in lines]
    assert text[0][:2] == ["3", "Freed From Desire"] and "Dm" in text[0] and " 121" in text[0]
    assert text[1] == ["Intro 4 · C 16 · R 8"]
    chords = [row for row in text if row[-1].startswith(("Dm", "Fmaj7", "Bb", "C"))]
    assert len(chords) > 1 and chords[0][0] == "Couplet" and chords[-1][-1].endswith("×2")  # la ligne est repliée
    assert all(doc.width(row[-1], pdf.CHORDS, "B") <= 90.0 for row in chords)
    assert text[-2:] == [["-", "départ batterie seule"], ["-", "enchaîner"]]
    # un titre trop long est écrit plus petit, puis coupé
    long = pdf.block(doc, {**entry(1), "title": "Un titre vraiment beaucoup trop long pour une colonne"}, 90.0)[0][1]
    assert long[1][2] < pdf.TITLE and long[1][1].endswith("...")

    pages = pdf.layout(doc, [entry(n) for n in range(1, 25)], columns=2)
    assert len(pages) > 1 and sum(len(page) for page in pages) == 24
    for page in pages:
        for _, y, _, block, gap in page:
            assert y + sum(height for height, _ in block) + 2 * gap <= pdf.PAGE[1] - pdf.MARGIN + 1e-6
    assert pdf.plain("Maldòn – « F♯ » … ×2") == "Maldòn - « F# » ... ×2"


def test_pdf_takes_the_largest_text_that_fits_the_pages(tmp_path):
    from arr import pdf

    song = {
        "key": "F",
        "bpm": 125,
        "structure": "C 16 · R 8",
        "parts": [{"name": "Refrain", "chords": "F | Dm | Bb | C"}],
    }
    entries = [{"number": n, "title": f"Morceau {n}", "sheet": song} for n in range(1, 25)]
    free = pdf.render(entries, "Essai", tmp_path / "libre.pdf")
    assert free["scale"] == 1.0 and (tmp_path / "libre.pdf").read_bytes().startswith(b"%PDF")
    three = pdf.render(entries, "Essai", tmp_path / "trois.pdf", pages=3)
    assert three["pages"] <= 3 and three["scale"] > 1.0 and three["fits"] and three["readable"]
    tight = pdf.render(entries, "Essai", tmp_path / "serre.pdf", pages=1)
    assert tight["pages"] == 1 and tight["fits"] and tight["scale"] < three["scale"]
    one = pdf.render(entries * 6, "Essai", tmp_path / "une.pdf", pages=1)
    assert one["scale"] == 0.5 and not one["fits"] and not one["readable"]


def test_setlist_orders_songs_and_prints_their_sheets(tmp_path, monkeypatch):
    transcribed(tmp_path, monkeypatch, "gala", "Freed From Desire")
    transcribed(tmp_path, monkeypatch, "whats-up", "What's Up?")
    Project.create(tmp_path / "brouillon", "brouillon")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["set", "new", "bar", "gala/", "--title", "Bar du Port"]).exit_code == 0
    assert runner.invoke(app, ["set", "new", "bar"]).exit_code != 0  # elle existe déjà
    assert runner.invoke(app, ["set", "add", "bar", "nope"]).exit_code != 0  # pas un projet
    assert runner.invoke(app, ["set", "add", "bar", "whats-up", "--at", "1"]).exit_code == 0
    assert runner.invoke(app, ["set", "add", "bar", "--break", "brouillon"]).exit_code == 0
    file = tmp_path / "setlists/bar.toml"
    assert sheet.setlist_entries(sheet.tomllib.loads(file.read_text())) == [
        {"song": "whats-up"},
        {"song": "gala"},
        {"break": True},
        {"song": "brouillon"},
    ]

    # un morceau non transcrit se voit dans la liste, et empêche l'impression
    shown = runner.invoke(app, ["set", "show", "bar"])
    assert "Bar du Port" in shown.output and "incomplet" in shown.output and "entracte" in shown.output
    assert "3 morceaux" in shown.output
    refused = runner.invoke(app, ["set", "print", "bar"])
    assert (
        refused.exit_code != 0 and "brouillon" in str(refused.exception) and "arr transcribe" in str(refused.exception)
    )

    # réglages du concert : une transposition et une note, sans toucher à l'antisèche du morceau
    file.write_text(
        'title = "Bar du Port"\nsongs = ["whats-up", { song = "gala", transpose = -2, note = "enchaîner" }]\n'
    )
    shown = runner.invoke(app, ["set", "show", "bar"]).output
    line = next(row for row in shown.splitlines() if "Freed From Desire" in row)
    assert line.startswith("2") and "Cm" in line and "transposé de -2 · enchaîner" in line and "3:20" in line
    assert "2 morceaux, 6 min 40 s" in shown
    printed = runner.invoke(app, ["set", "print", "bar", "--pages", "1"])
    assert printed.exit_code == 0 and "1 feuille(s)" in printed.output
    assert (tmp_path / "setlists/bar.pdf").read_bytes().startswith(b"%PDF")
    assert not (tmp_path / "gala/sheet.toml").exists()

    # depuis le dossier d'un morceau, la setlist se trouve aussi ; une inconnue cite celles qui existent
    monkeypatch.chdir(tmp_path / "gala")
    assert runner.invoke(app, ["set", "show", "bar"]).exit_code == 0
    unknown = runner.invoke(app, ["set", "show", "nope"])
    assert unknown.exit_code != 0 and "connues : bar" in str(unknown.exception)
    assert runner.invoke(app, ["sheet", "--pdf"]).exit_code == 0 and (tmp_path / "gala/export/sheet.pdf").exists()


def test_rhythm_is_read_beat_by_beat():
    bar = sheet.rhythm("x..x ..x. x-x. ...x")[0]
    assert bar[0] == (4, [("note", 0, 1, False), ("rest", 1, 2, False), ("note", 3, 1, False)])
    assert bar[2] == (4, [("note", 0, 2, False), ("note", 2, 1, False), ("rest", 3, 1, False)])
    # une tenue en début de temps prolonge la note d'avant : une note liée
    second = sheet.rhythm("x--- | -x.. x-x xx")[1]
    assert second[0] == (4, [("note", 0, 1, True), ("note", 1, 1, False), ("rest", 2, 2, False)])
    assert second[1] == (3, [("note", 0, 2, False), ("note", 2, 1, False)]) and second[2][0] == 2
    assert sheet.rhythm(".-..")[0][0] == (4, [("rest", 0, 4, False)])  # une tenue après un silence reste un silence
    for wrong in ("x.y.", "x", "xxxxx"):
        with pytest.raises(ValueError, match="temps illisible"):
            sheet.rhythm(wrong)


def test_note_values_follow_the_beat():
    from arr import pdf

    assert pdf.pieces(4, "note", 0, 4) == [(0, 4)] and pdf.pieces(4, "rest", 0, 4) == [(0, 4)]  # noire, soupir
    assert pdf.pieces(4, "note", 0, 3) == [(0, 3)]  # croche pointée
    assert pdf.pieces(4, "note", 1, 2) == [(1, 2)]  # double, croche, double
    assert pdf.pieces(4, "note", 1, 3) == [(1, 2), (3, 1)]  # croche liée à une double
    assert pdf.pieces(4, "rest", 1, 3) == [(1, 1), (2, 2)] and pdf.pieces(4, "rest", 0, 3) == [(0, 2), (2, 1)]
    assert pdf.pieces(3, "note", 0, 2) == [(0, 2), (1, 2)] and pdf.pieces(3, "rest", 0, 3) == [(0, 4)]
    assert pdf.pieces(2, "note", 0, 2) == [(0, 4)] and pdf.pieces(2, "note", 1, 1) == [(1, 2)]


def test_grooves_are_shown_and_printed(tmp_path, monkeypatch):
    from arr import pdf

    p = transcribed(tmp_path, monkeypatch)
    runner.invoke(app, ["sheet", "--note", "x"])
    written = sheet.load(p.root)
    tab = ["A|3---3-5-|", "E|--------|"]
    written["grooves"] = [
        {
            "instrument": "basse",
            "part": "Couplet",
            "rhythm": "x..x ..x. x-x. ...x | x--- .... x-x- xxxx | x... x... x... x...",
        },
        {"instrument": "guitare", "tab": tab},
    ]
    sheet.save(p.root, written)
    out = runner.invoke(app, ["sheet", "--pdf"])
    assert out.exit_code == 0 and "basse · Couplet  x..x ..x." in out.output and "A|3---3-5-|" in out.output
    assert (p.root / "export/sheet.pdf").read_bytes().startswith(b"%PDF")

    doc = pdf.Sheet()
    lines = pdf.block(doc, {"number": 1, "title": "x", "sheet": written}, 90.0)
    drawn = [segments for _, segments in lines if callable(segments[0][1])]
    assert len(drawn) == 2  # trois mesures : deux tiennent sur la première ligne, la troisième passe dessous
    texts = [segment[1] for _, segments in lines for segment in segments if isinstance(segment[1], str)]
    assert "basse · Couplet" in texts and "guitare" in texts and all(row in texts for row in tab)

    written["grooves"] = [{"instrument": "basse", "rhythm": "x.y."}]
    sheet.save(p.root, written)
    refused = runner.invoke(app, ["sheet"])
    assert refused.exit_code != 0 and "groove de basse" in str(refused.exception)
