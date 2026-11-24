"""Fichier ChordPro : structure de l'original, grilles, paroles en repère, transposition, commande."""

import json
import re

from arr import chordpro, structure
from arr.cli import app
from arr.project import Project, Section
from tests.helpers import fake_transcription, runner

BEAT = 60 / 124

REFERENCE = """\
# written by arr — le-phare
{title: Le Phare}
{artist: Les Balises}
{key: Em}
{tempo: 124}
{time: 4/4}
{duration: 1:36}

{comment: basse seule les 4 premières}
{start_of_grid label="Intro" shape="4x4"}
| Em . . . | Em . . . | G . . . | D . . . |
| Em . . . | Em . . . | G . . . | D . . . |
{end_of_grid}

{start_of_grid label="Couplet 1" shape="4x4"}
| Em . . . | Em . . . | G . . . | D . . . | La lampe tourne et rien ne bouge / Sur le quai les filets sèchent
| Em . . . | Em . . . | G . . . | D . . . | On compte les bateaux qui rentrent / Il en manque un depuis hier
| C . . . | C . . . | G . . . | D . . . | Ta veste est restée sur la chaise / Le café refroidit tout seul
| C . . . | D . . . | Em . . . | Em . . . | Je garde un œil sur la passe / Et l'autre sur le téléphone
{end_of_grid}

{start_of_grid label="Refrain" shape="4x4"}
| C . . . | G . . . | D . . . | Em . . . | Allume, allume encore / Que la nuit sache où tu es
| C . . . | G . . . | D . C . | B7 . . . | Allume, allume encore / Je reste en haut, je veille
{end_of_grid}

{comment: regarde le batteur}
{start_of_grid label="Pont" shape="3x4"}
| Am . . . | F . . . | C . . . |
{end_of_grid}
{time: 2/4}
{start_of_grid label="Pont" shape="1x2"}
| G . |
{end_of_grid}
{time: 4/4}
{start_of_grid label="Pont" shape="4x4"}
| Am . . . | F . . . | C . . . | G . . . |
{end_of_grid}

{start_of_grid label="Refrain" shape="4x4"}
| C . . . | G . . . | D . . . | Em . . . | Allume, allume encore / Que la nuit sache où tu es
| C . . . | G . . . | D . C . | B7 . . . | Allume, allume encore / Je reste en haut, je veille
{end_of_grid}

{comment: fin sèche sur le 1}
{start_of_grid label="Fin" shape="2x4"}
| Em . . . | Em . . . |
{end_of_grid}
"""


class Clock:
    """Des mesures de grille d'accords à la suite : « Em », ou « D C » (deux accords, sur les temps 1 et 3)."""

    def __init__(self):
        self.t = 0.0

    def bars(self, cells: str, beats: int = 4) -> list[tuple]:
        out = []
        for cell in cells.split("|"):
            start, labels = self.t, cell.split()
            self.t += beats * BEAT
            step = beats // len(labels)
            out.append(
                (start, self.t, beats, [(j * step, step, label, start, self.t) for j, label in enumerate(labels)])
            )
        return out


def reference_passages() -> tuple[list[structure.Passage], dict]:
    c = Clock()
    loop = "E:min | E:min | G:maj | D:maj"
    chorus = "C:maj | G:maj | D:maj | E:min | C:maj | G:maj | D:maj C:maj | B:7"
    passages = [
        structure.Passage("Intro", c.bars(f"{loop} | {loop}"), "intro", "basse seule les 4 premières"),
        structure.Passage(
            "Couplet 1",
            c.bars(f"{loop} | {loop} | C:maj | C:maj | G:maj | D:maj | C:maj | D:maj | E:min | E:min"),
            "verse",
        ),
        structure.Passage("Refrain", c.bars(chorus), "chorus"),
        structure.Passage(
            "Pont",
            c.bars("A:min | F:maj | C:maj") + c.bars("G:maj", beats=2) + c.bars("A:min | F:maj | C:maj | G:maj"),
            "bridge",
            "regarde le batteur",
        ),
        structure.Passage("Refrain", c.bars(chorus), "chorus2"),
        structure.Passage("Fin", c.bars("E:min | E:min"), "outro", "fin sèche sur le 1"),
    ]
    verse = [
        "La lampe tourne et rien ne bouge",
        "Sur le quai les filets sèchent",
        "On compte les bateaux qui rentrent",
        "Il en manque un depuis hier",
        "Ta veste est restée sur la chaise",
        "Le café refroidit tout seul",
        "Je garde un œil sur la passe",
        "Et l'autre sur le téléphone",
    ]
    chorus_words = [
        "Allume, allume encore",
        "Que la nuit sache où tu es",
        "Allume, allume encore",
        "Je reste en haut, je veille",
    ]
    lyrics = {"verse": [(line, None) for line in verse]}
    lyrics |= {name: [(line, None) for line in chorus_words] for name in ("chorus", "chorus2")}
    return passages, lyrics


def test_the_reference_file_is_written_byte_for_byte():
    passages, lyrics = reference_passages()
    blocks = chordpro.layout(passages, lyrics, "Em", 0)
    head = {"project": "le-phare", "title": "Le Phare", "artist": "Les Balises", "key": "Em", "tempo": 124}
    head["duration"] = chordpro.duration(passages)
    assert chordpro.write(head, blocks, chordpro.meter(passages)) == REFERENCE
    assert [b.bars for b in blocks] == [8, 16, 8, 8, 8, 2] and [b.sung for b in blocks] == [0, 8, 4, 0, 4, 0]


def test_every_bar_of_a_grid_has_the_cells_its_shape_announces():
    passages, lyrics = reference_passages()
    text = chordpro.write({"project": "x", "duration": "0:00"}, chordpro.layout(passages, lyrics, "Em", 0), 4)
    shape = None
    for line in text.splitlines():
        if m := re.match(r'\{start_of_grid label="[^"]+" shape="(\d+)x(\d+)"\}', line):
            shape = (int(m.group(1)), int(m.group(2)))
        elif line.startswith("|"):
            bars = line[: line.rindex("|")].strip("| ").split(" | ")
            assert len(bars) <= shape[0] and all(len(bar.split()) == shape[1] for bar in bars), line


def test_chords_are_transposed_and_no_chord_is_written_as_such():
    c = Clock()
    bar = c.bars("F:maj G:min")[0]
    assert chordpro.bar_text(bar, "Eb", -2) == "Eb . Fm ."
    assert chordpro.bar_text(c.bars("N C:maj")[0], "D", 2) == "N.C. . D ."
    silent = structure.Passage("Intro", c.bars("N | N"), "intro")
    assert not chordpro.layout([silent], {}, "C", 0)[0].chords


def test_lyric_lines_follow_their_time_or_are_spread_evenly():
    spans = [(0.0, 8.0), (8.0, 16.0), (16.0, 24.0)]
    timed = [("un", 1.0), ("deux", 17.0), ("trois | quatre", 18.0)]
    assert chordpro.landmarks(timed, spans) == [["un"], [], ["deux", "trois / quatre"]]
    # une ligne sans instant : toutes sont réparties dans l'ordre
    assert chordpro.landmarks([("un", 1.0), ("deux", None)], spans) == [["un"], ["deux"], []]
    assert chordpro.landmarks([], spans) == [[], [], []]


def test_the_original_structure_names_passages_as_a_musician_does():
    c = Clock()
    chart = c.bars(" | ".join(["C:maj"] * 10))
    bar = 4 * BEAT
    sections = [Section("intro", 0.0, 0.3)]  # plus courte qu'une mesure : pas de passage
    sections += [
        Section(n, i * 2 * bar, (i + 1) * 2 * bar) for i, n in enumerate(["verse", "chorus", "verse2", "chorus2"])
    ]
    sections += [Section("coda", 8 * bar, 10 * bar)]
    got = structure.default(sections, chart)
    assert [(p.name, p.section, len(p.bars)) for p in got] == [
        ("Couplet 1", "verse", 2),
        ("Refrain", "chorus", 2),
        ("Couplet 2", "verse2", 2),
        ("Refrain", "chorus2", 2),
        ("Coda", "coda", 2),
    ]


def transcribed(tmp_path, monkeypatch) -> Project:
    p = Project.create(tmp_path / "night-drive", "night-drive")
    p.song.update(title="Night Drive", artist="Paper Lanterns", key="D minor", bpm=121.0, duration=4.0)
    p.set_sections([Section("verse", 0.0, 2.0), Section("chorus", 2.0, 4.0)])
    p.save()
    fake_transcription(None, p.root / "score")
    grid = {"beats": [0.5 * i for i in range(8)], "downbeats": [0.0, 2.0]}
    (p.root / "analysis.json").write_text(json.dumps(grid))
    monkeypatch.chdir(p.root)
    monkeypatch.setenv("COLUMNS", "200")
    return p


def test_the_command_writes_the_file_and_reports_it(tmp_path, monkeypatch):
    p = transcribed(tmp_path, monkeypatch)
    (p.root / "lyrics.txt").write_text("[Verse]\nOn roule de nuit\n\n[Chorus]\nPhares | allumés\nJusqu'au matin\n")
    out = runner.invoke(app, ["chordpro"]).output
    written = (p.root / "export/night-drive.cho").read_text()
    assert written.startswith("# written by arr — night-drive\n{title: Night Drive}\n{artist: Paper Lanterns}\n")
    assert "{key: Dm}\n{tempo: 121}\n{time: 4/4}\n{duration: 0:04}\n" in written
    assert '{start_of_grid label="Couplet 1" shape="1x4"}\n| N.C. . Dm . | On roule de nuit\n' in written
    assert (
        '{start_of_grid label="Refrain" shape="1x4"}\n| Fmaj7 . C . | Phares / allumés / Jusqu\'au matin\n' in written
    )
    assert "x_" not in written
    assert "Night Drive → export/night-drive.cho" in out and "Dm · ♩121 · 4/4 · 2 mesures · 0:04" in out
    assert "structure de l'original · accords de la transcription · paroles de lyrics.txt" in out
    assert "Refrain" in out and "2 lignes de paroles en repère" in out and "arr chordpro --show" in out

    # le fichier appartient à arr : il se réécrit en entier, dans la tonalité jouée
    (p.root / "export/night-drive.cho").write_text("corrigé à la main")
    (p.root / "sheet.toml").write_text('key = "Dm"\ntranspose = -2\n')
    runner.invoke(app, ["chordpro"])
    written = (p.root / "export/night-drive.cho").read_text()
    assert "{key: Cm}" in written and "| N.C. . Cm . |" in written and "| Ebmaj7 . Bb . |" in written


def test_show_displays_without_writing(tmp_path, monkeypatch):
    p = transcribed(tmp_path, monkeypatch)
    out = runner.invoke(app, ["chordpro", "--show"]).output
    assert "Night Drive · Dm · ♩121 · 4/4 · 0:04" in out and "COUPLET 1" in out and "Fmaj7" in out
    assert not (p.root / "export/night-drive.cho").exists()


def test_lyrics_that_do_not_follow_the_sections_are_left_out_with_a_warning(tmp_path, monkeypatch):
    p = transcribed(tmp_path, monkeypatch)
    (p.root / "lyrics.txt").write_text("[Verse]\nOn roule de nuit\n")
    out = runner.invoke(app, ["chordpro"]).output
    assert "1 balises pour 2 sections" in out and "sans paroles" in out
    assert "On roule" not in (p.root / "export/night-drive.cho").read_text()


def test_a_song_without_chords_or_bars_is_refused(tmp_path, monkeypatch):
    p = Project.create(tmp_path / "song", "song")
    monkeypatch.chdir(p.root)
    result = runner.invoke(app, ["chordpro"])
    assert result.exit_code != 0 and "arr transcribe" in str(result.exception)

    p = transcribed(tmp_path / "other", monkeypatch)
    (p.root / "analysis.json").unlink()
    (p.root / "score/beat.lab").unlink()
    result = runner.invoke(app, ["chordpro"])
    assert result.exit_code != 0 and "arr analyze" in str(result.exception)
