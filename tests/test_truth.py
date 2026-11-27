"""Barres tapées à l'oreille : frappes datées, passages de truth/, note de la lecture brute."""

import os
import time

import numpy as np
import pytest

from arr import truth
from arr.project import Project, ProjectError
from tests.helpers import marked_passage


def steady(bars: int, beats_per_bar: int = 4, period: float = 0.5, start: float = 0.0):
    """Une grille régulière : ses temps et ses barres."""
    beats = [start + period * i for i in range(bars * beats_per_bar)]
    return beats, beats[::beats_per_bar]


def test_a_tap_is_placed_where_the_music_was_heard():
    # Un bloc toutes les 20 ms ; le son sort 30 ms après l'heure du flux, à 3 ms près d'un bloc à l'autre.
    rng = np.random.default_rng(1)
    blocks = [(50.0 + 0.02 * i + 0.03 + rng.uniform(-0.003, 0.003), 0.02 * i) for i in range(500)]
    heard = truth.heard_positions(blocks, [50.03 + 2.0, 50.03 + 2.011, 50.03 + 7.5])
    assert heard == pytest.approx([2.0, 2.011, 7.5], abs=0.002)
    # une frappe après le dernier bloc se lit sur le plus proche ; sans bloc, rien ne se lit
    assert truth.heard_positions(blocks[:3], [50.03 + 1.0]) == pytest.approx([1.0], abs=0.005)
    assert truth.heard_positions([], [1.0]) == []


def test_taps_become_bar_marks_inside_the_passage():
    taps = [9.0, 10.02, 10.1, 12.0, 14.01, 13.99, 16.5]
    # avant le passage, rebond à 80 ms, frappes dans le désordre, après la fin
    assert truth.bar_marks(taps, 10.0, 16.0) == [10.02, 12.0, 13.99]
    assert truth.bar_marks([9.95], 10.0, 16.0) == [9.95]  # un peu avant la borne : la première barre


def test_score_counts_bar_lines_and_beats_per_bar():
    beats, bars = steady(8)
    marks = [b + 0.03 for b in bars[1:6]]  # frappes 30 ms après la barre
    s = truth.score(marks, 4, beats, bars)
    assert (s["marks"], s["shown"], s["matched"], s["counted"], s["right"]) == (5, 5, 5, 4, 4)
    assert s["f"] == 1.0 and s["offset"] == pytest.approx(-0.03)

    # un temps manqué dans la troisième mesure repérée : la barre suivante reste, la mesure compte 3
    holed = [t for t in beats if t != 6.5 + 0.5]
    s = truth.score(marks, 4, holed, bars)
    assert (s["matched"], s["right"], s["counted"]) == (5, 3, 4)

    # barres posées un temps trop tôt : aucune ne tombe sur une frappe, les mesures gardent leur compte
    early = [b - 0.5 for b in bars]
    s = truth.score(marks, 4, beats, early)
    assert s["matched"] == 0 and s["f"] == 0.0 and s["offset"] is None and s["right"] == 4

    # une barre de trop au milieu d'une mesure (2 + 2) : justes, mais une en trop
    s = truth.score(marks, 4, beats, sorted(bars + [5.0]))
    assert (s["matched"], s["shown"]) == (5, 6) and s["f"] == pytest.approx(2 * 5 / 11)

    # mesures à trois temps, dites par le passage ; rien n'est écarté dans les cinq premières secondes
    beats, bars = steady(6, beats_per_bar=3)
    s = truth.score(bars[:4], 3, beats, bars)
    assert (s["matched"], s["right"], s["counted"]) == (4, 3, 3) and bars[3] < 5.0
    assert truth.score(bars[:4], 4, beats, bars)["right"] == 0
    assert truth.score([], 4, beats, bars)["marks"] == 0


def test_verdict_since_the_last_run():
    was = {"version": "v001", "f": 0.8, "right": 6}
    assert truth.verdict(was, None) == "nouveau"
    assert truth.verdict(was | {"version": "v002"}, was) == "nouveau"  # passage repéré de nouveau
    assert truth.verdict(dict(was), was) == "pareil"
    assert truth.verdict(was | {"f": 0.9}, was) == "mieux"
    assert truth.verdict(was | {"f": 0.9, "right": 5}, was) == "moins bien"  # un recul n'est pas racheté


def test_taps_are_dated_when_the_key_arrives(monkeypatch):
    """Sur un vrai terminal (ici un pseudo-terminal) : Espace est daté par le fil, les flèches sont ignorées."""
    import pty
    import sys
    import types

    from arr.commands._playback import keyboard

    master, slave = pty.openpty()
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: True, fileno=lambda: slave))
    taps = []
    with keyboard(taps.append) as pressed:
        time.sleep(0.1)
        sent = time.monotonic()
        os.write(master, b" \x1b[C")
        time.sleep(0.15)
        os.write(master, b" ")
        time.sleep(0.1)
        assert pressed() == []
    os.close(master), os.close(slave)
    assert len(taps) == 2 and 0 <= taps[0] - sent < 0.03 and taps[1] - taps[0] == pytest.approx(0.15, abs=0.03)


CHORDS = [(0.0, 2.0, "D:min"), (2.0, 3.0, "F:maj7"), (3.0, 4.0, "C:maj"), (4.0, 6.0, "N"), (6.0, 8.0, "E:maj7/3")]


def test_chord_names_are_read_back_as_root_and_triad():
    from arr.sheet import chord_label

    names = ["Dm7", "F", "F#maj7", "Bbm", "E/G#", "Csus4", "Asus2", "Bdim", "Am7b5", "Gaug", "N.C.", "–", ""]
    assert [chord_label(n) for n in names] == [
        "D:min",
        "F:maj",
        "F#:maj",
        "Bb:min",
        "E:maj",
        "C:sus4",
        "A:sus2",
        "B:dim",
        "A:dim",
        "G:aug",
        "N",
        "N",
        "N",
    ]


def test_marked_passages_are_read_in_their_latest_version(tmp_path):
    p = Project.create(tmp_path / "song", "song")
    assert truth.passages(p) == []
    marked_passage(p, "chorus", [10.0, 12.0, 14.0])
    f = marked_passage(p, "chorus", [10.1, 12.1], version=2, per_bar=3)
    marked_passage(p, "intro+verse", [0.5, 2.5])
    assert [(x.name, x.version, x.beats_per_bar, x.bars) for x in truth.passages(p)] == [
        ("chorus", "v002", 3, [10.1, 12.1]),
        ("intro+verse", "v001", 4, [0.5, 2.5]),
    ]
    (p.root / "truth/chorus.v001.toml").write_text("bars = oops")
    assert truth.passages(p)[0].version == "v002"  # une ancienne version illisible ne gêne pas
    f.write_text("bars = oops")
    with pytest.raises(ProjectError, match="illisible"):
        truth.passages(p)


def test_my_chords_score_the_transcribed_ones(tmp_path):
    p = Project.create(tmp_path / "song", "song")
    passage = truth.read(marked_passage(p, "chorus", [0.0, 2.0, 4.0, 6.0, 8.0]))
    path = truth.chords_path(p, passage)
    assert path.name == "chorus.v001.chords.txt"
    # à gauche de la barre ce que j'entends, à droite ce qu'arr avait écrit ; une mesure vidée ne compte pas
    path.write_text(
        "# en-tête\n  1  0:00.00  D  | Dm\n  2  0:02.00  F  | Fmaj7 C\n  3  0:04.00  N.C. | N.C.\n  4  0:06.00  | Emaj7/3\n"
    )
    rows = truth.read_chords(path)
    assert [heard for _, heard, _ in rows] == [["D"], ["F"], ["N.C."], []]
    s = truth.chord_score(passage, rows, CHORDS)
    # fondamentale : D juste (2 s), F juste une demi-mesure (1 s sur 2), N.C. juste (2 s)
    assert s["root"] == pytest.approx(5 / 6) and s["majmin"] == pytest.approx(3 / 6)
    assert (s["seconds"], s["filled"], s["corrected"]) == (6.0, 3, 2)
    assert truth.chord_score(passage, [], CHORDS) == {}
    assert truth.chord_score(passage, [(0, ["Dsus4"], ["Dm"])], CHORDS)["majmin"] is None


def test_the_workshop_script_scores_the_raw_reading_against_my_fixes(tmp_path, monkeypatch, capsys):
    import importlib.util
    import sys
    from pathlib import Path

    from arr import review
    from arr.commands._common import save_analysis

    spec = importlib.util.spec_from_file_location("grid_score", Path(__file__).parent.parent / "scripts/grid_score.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    def song(name: str, beats: list[float], bars: list[float]) -> Project:
        p = Project.create(tmp_path / name, name)
        save_analysis(p, beats, bars, np.ones((int(beats[-1] * 50) + 2, 2), np.float32))
        return p

    beats, bars = steady(8)
    good = song("a--good", beats, bars)
    marked_passage(good, "chorus", [4.03, 6.0, 8.02, 9.98])  # tapées à 30 ms près : la lecture brute est juste
    shifted = song("b--shifted", beats, [t + 1.0 for t in bars])  # le détecteur pose le 1 deux temps trop tard
    review.save_fix(shifted, review.make_fix([4.0, 6.0, 8.0, 10.0], beats, set()))
    song("c--untouched", beats, bars)
    assert script.song_scores(good)["truth chorus v001"] | {"f": 1.0} == {
        "marks": 4, "shown": 4, "matched": 4, "f": 1.0, "offset": 0.0, "counted": 3, "right": 3,
        "version": "truth chorus v001", "root": None, "majmin": None,
    }  # fmt: skip
    wrong = script.song_scores(shifted)["review 0:04.0"]
    assert (wrong["marks"], wrong["matched"], wrong["right"]) == (4, 0, 3)

    runs = tmp_path / "runs.json"
    monkeypatch.setattr(sys, "argv", ["grid_score.py", str(tmp_path), "--runs", str(runs)])
    assert script.main() == 0
    out = capsys.readouterr().out
    assert "a--good" in out and "barres 4/4" in out and "barres 0/4" in out and "c--untouched" not in out
    assert "Total : barres 4/8, en trop 3, mesures au compte 6/6" in out and "nouveau" in out
    assert script.main() == 0 and "pareil" in capsys.readouterr().out
    # la lecture brute se dégrade sur le premier morceau : le script sort en erreur et dit lequel
    save_analysis(good, beats, [t + 0.5 for t in bars], np.ones((802, 2), np.float32))
    assert script.main() == 1 and "moins bien : a--good truth chorus v001" in capsys.readouterr().out
    assert not (good.root / "truth/runs.json").exists()  # rien n'est écrit dans les projets
