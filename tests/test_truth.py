"""Passages de référence : frappes datées, rangement par versions, note de la grille."""

import json
import os
import time
from contextlib import contextmanager

import numpy as np
import pytest

from arr import truth
from arr.cli import add_track, app
from arr.project import Project, Section
from tests.helpers import runner, tone


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


def test_a_new_pass_keeps_the_earlier_marks(tmp_path):
    p = Project.create(tmp_path / "song", "song")
    assert truth.passages(p) == []
    first = truth.save(p, "chorus", 10.0, 20.0, [10.0, 12.0, 14.0])
    assert (first.version, first.beats_per_bar, first.bars) == ("v001", 4, [10.0, 12.0, 14.0])
    # le musicien dit que ce passage est à trois temps : la passe suivante le garde
    f = p.root / "truth/chorus.v001.toml"
    f.write_text(f.read_text().replace("beats_per_bar = 4", "beats_per_bar = 3"))
    truth.save(p, "chorus", 10.0, 20.0, [10.1, 12.1])
    truth.save(p, "intro+verse", 0.0, 10.0, [0.5, 2.5])
    assert sorted(x.name for x in (p.root / "truth").iterdir()) == [
        "chorus.v001.toml",
        "chorus.v002.toml",
        "intro+verse.v001.toml",
    ]
    assert [(x.name, x.version, x.beats_per_bar, x.bars) for x in truth.passages(p)] == [
        ("chorus", "v002", 3, [10.1, 12.1]),
        ("intro+verse", "v001", 4, [0.5, 2.5]),
    ]
    f.write_text("bars = oops")
    assert truth.passages(p)[0].version == "v002"  # une ancienne version illisible ne gêne pas


def marking_project(tmp_path, monkeypatch):
    """Un projet à 120 à la noire, et un faux studio où chaque bloc sort 30 ms après l'heure du flux."""
    from arr import studio
    from arr.commands import _playback as command

    p = Project.create(tmp_path / "song", "song")
    add_track(p, "guitar", tone(330, 8.0, amp=0.1), {"op": "split"})
    p.set_sections([Section("verse", 0.0, 4.0), Section("chorus", 4.0, 6.0), Section("outro", 6.0, 8.0)])
    p.save()
    grid = {"beats": [0.5 * i for i in range(16)], "downbeats": [2.0 * i for i in range(4)]}
    (p.root / "analysis.json").write_text(json.dumps(grid))
    monkeypatch.chdir(p.root)
    monkeypatch.setattr(studio, "config", lambda: {"output": {"device": "", "channels": [1, 2]}})
    session = {"taps": [], "played": []}

    @contextmanager
    def keyboard(tap=None):
        session["tap"] = tap
        yield lambda: []

    def play(data, loop=None, watch=None, follow=None):
        session["played"].append(data)
        for i in range(int(len(data) / 48000 / 0.02)):
            follow(0.02 * i, 100.03 + 0.02 * i, False)
        for at in session["taps"]:  # heures d'horloge : la position entendue est l'heure moins 100,03
            session["tap"](100.03 + at)
        watch(len(data) / 48000)

    monkeypatch.setattr(command, "keyboard", keyboard)
    monkeypatch.setattr(studio, "play", play)
    return p, session


def test_play_mark_stores_the_bars_where_they_were_heard(tmp_path, monkeypatch):
    p, session = marking_project(tmp_path, monkeypatch)
    # une mesure de décompte (2 s), puis refrain et outro (4 à 8 s du morceau) : frappe pendant le
    # décompte, deux barres à 10 et 20 ms près, un rebond
    session["taps"] = [1.0, 2.01, 2.09, 3.98]
    result = runner.invoke(app, ["play", "-s", "chorus,outro", "--count-in", "1", "--mark"], input="o\n")
    assert result.exit_code == 0, result.output
    assert "Espace : le 1 de chaque mesure" in result.output and "repérage" in result.output
    assert "2 barres repérées dans chorus+outro, de 0:04 à 0:05" in result.output
    assert "2 tombent sur une barre d'arr" in result.output
    kept = truth.passages(p)
    assert [(k.name, k.version, k.start, k.end, k.beats_per_bar) for k in kept] == [
        ("chorus+outro", "v001", 4.0, 8.0, 4)
    ]
    assert kept[0].bars == pytest.approx([4.01, 5.98], abs=0.002)

    # refuser le repérage n'écrit rien ; une seule frappe non plus
    assert "abandonné" in runner.invoke(app, ["play", "-s", "chorus,outro", "--mark"], input="n\n").output
    session["taps"] = [0.5]
    assert "rien n'est gardé" in runner.invoke(app, ["play", "-s", "chorus", "--mark"]).output
    assert len(list((p.root / "truth").iterdir())) == 1

    # le morceau entier, sans section ; une deuxième passe du même passage
    session["taps"] = [0.0, 2.0, 4.0]
    assert runner.invoke(app, ["play", "--mark"], input="o\n").exit_code == 0
    assert runner.invoke(app, ["play", "guitar", "--mark"], input="o\n").exit_code == 0
    assert [(k.name, k.version, k.bars) for k in truth.passages(p)][1] == ("song", "v002", [0.0, 2.0, 4.0])


def test_play_mark_refuses_what_cannot_be_read_as_one_passage(tmp_path, monkeypatch):
    from arr import audio

    p, session = marking_project(tmp_path, monkeypatch)
    audio.save(p.new_take({"style": "x"})[1], tone(220, 1.0))
    for args, why in (
        (["-s", "chorus", "--loop"], "sans --loop"),
        (["-s", "verse,outro"], "doivent se suivre"),
        (["-s", "outro,chorus"], "doivent se suivre"),
        (["t001"], "ni repérage"),
    ):
        result = runner.invoke(app, ["play", *args, "--mark"])
        assert result.exit_code != 0 and why in str(result.exception), args
    assert not session["played"] and not (p.root / "truth").exists()


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


def test_truth_scores_every_marked_passage_of_the_library(tmp_path, monkeypatch):
    def song(name: str, grid: dict, marked: dict) -> Project:
        p = Project.create(tmp_path / name, name)
        (p.root / "analysis.json").write_text(json.dumps(grid))
        for passage, bars in marked.items():
            truth.save(p, passage, bars[0], bars[-1] + 2.0, bars)
        return p

    beats, bars = steady(8)
    good = song("a--good", {"beats": beats, "downbeats": bars}, {"chorus": bars[2:6], "intro": bars[:2]})
    song("b--unmarked", {"beats": beats, "downbeats": bars}, {})
    # beat_this a manqué le temps de 5,5 s : la mesure repérée de 4 à 6 s n'en a que trois
    holed = [t for t in beats if t != 5.5]
    song("c--holed", {"beats": holed, "downbeats": bars}, {"verse": bars[1:5]})
    # ce que beat_this entendait : net partout dans le premier morceau, faible à 4,5 s dans le dernier
    heard = np.zeros((801, 2), np.float32)
    heard[[int(t * 50) for t in beats], 0] = 1.0
    np.savez_compressed(good.root / "analysis_frames.npz", frames=heard)
    heard[int(4.5 * 50), 0], heard[int(5.5 * 50), 0] = 0.6, 0.0  # et rien à 5,5 s : le trou reste
    np.savez_compressed(tmp_path / "c--holed/analysis_frames.npz", frames=heard)
    monkeypatch.chdir(good.root)

    result = runner.invoke(app, ["truth"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    rows = [" ".join(line.split()) for line in result.output.splitlines()]
    assert not any("b--unmarked" in row for row in rows)
    assert "a--good chorus v001 · 4 temps 4/4 0 3/3 +0 ms 0/0 fausses · 0/3 justes - nouveau" in rows
    assert "a--good intro v001 · 4 temps 2/2 0 1/1 +0 ms 0/0 fausses · 0/1 justes - nouveau" in rows
    # après le temps manqué, les barres posées tous les quatre temps tombent un temps plus tard
    # la mesure à trois temps est marquée douteuse (son temps de 4,5 s) ; la suivante, décalée, ne l'est pas
    assert "c--holed verse v001 · 4 temps 2/4 1 2/3 +0 ms 1/2 fausses · 0/1 justes - nouveau" in rows
    assert "Total 8/10 1 6/7 1/2 fausses · 0/5 justes -" in rows

    # rien n'a changé : pareil partout ; --dry-run ne retient pas le lancement
    assert "pareil" in runner.invoke(app, ["truth", str(tmp_path), "--dry-run"], env={"COLUMNS": "200"}).output
    assert len(json.loads((good.root / "truth/runs.json").read_text())) == 1

    # la grille se dégrade sur un morceau (barres un temps trop tôt), s'améliore sur l'autre
    (good.root / "analysis.json").write_text(json.dumps({"beats": beats, "downbeats": [b + 0.5 for b in bars]}))
    (tmp_path / "c--holed/analysis.json").write_text(json.dumps({"beats": beats, "downbeats": bars}))
    result = runner.invoke(app, ["truth"], env={"COLUMNS": "200"})
    assert result.exit_code == 1
    assert "mieux : c--holed verse" in result.output
    assert "moins bien : a--good chorus, a--good intro" in result.output
    # le lancement suivant se compare à celui-ci
    assert runner.invoke(app, ["truth"], env={"COLUMNS": "200"}).exit_code == 0

    # un morceau repéré mais jamais analysé est dit, sans arrêter les autres
    (tmp_path / "c--holed/analysis.json").rename(tmp_path / "c--holed/analysis.json.off")
    assert "pas d'analyse" in runner.invoke(app, ["truth", "--dry-run"], env={"COLUMNS": "200"}).output
    empty = tmp_path / "elsewhere"
    empty.mkdir()
    result = runner.invoke(app, ["truth", str(empty)])
    assert result.exit_code != 0 and "aucun passage de référence" in str(result.exception)


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


def test_the_chord_file_is_prefilled_then_scored_against_what_i_hear(tmp_path):
    p = Project.create(tmp_path / "song", "song")
    passage = truth.save(p, "chorus", 0.0, 10.0, [0.0, 2.0, 4.0, 6.0, 8.0])
    path = truth.write_chords(p, passage, CHORDS)
    assert path.name == "chorus.v001.chords.txt"
    lines = [line for line in path.read_text().splitlines() if not line.startswith("#")]
    assert [" ".join(line.split()) for line in lines] == [
        "1 0:00.00 Dm | Dm",
        "2 0:02.00 Fmaj7 C | Fmaj7 C",  # l'accord change au milieu de la mesure
        "3 0:04.00 N.C. | N.C.",
        "4 0:06.00 Emaj7/3 | Emaj7/3",
    ]
    rows = truth.read_chords(path)
    assert truth.chord_score(passage, rows, CHORDS) == {
        "root": 1.0,
        "majmin": 1.0,
        "seconds": 8.0,
        "filled": 4,
        "corrected": 0,
    }

    # j'entends D majeur à la première mesure, un seul accord à la deuxième, et je ne sais pas pour la quatrième
    text = path.read_text().replace("Dm               |", "D                |").replace("Fmaj7 C  ", "F        ")
    path.write_text(text.replace("Emaj7/3          |", "                 |"))
    rows = truth.read_chords(path)
    assert [heard for _, heard, _ in rows] == [["D"], ["F"], ["N.C."], []]
    s = truth.chord_score(passage, rows, CHORDS)
    # fondamentale : D juste (2 s), F juste une demi-mesure (1 s sur 2), N.C. juste (2 s) ; la mesure vidée ne compte pas
    assert s["root"] == pytest.approx(5 / 6) and s["majmin"] == pytest.approx(3 / 6)
    assert (s["seconds"], s["filled"], s["corrected"]) == (6.0, 3, 2)

    # le fichier corrigé n'est jamais récrit ; une nouvelle passe garde les corrections des mesures qui n'ont pas bougé
    assert truth.write_chords(p, passage, CHORDS) is None and path.read_text().count("D   ") == 1
    again = truth.save(p, "chorus", 0.0, 10.0, [0.05, 2.02, 4.9, 6.0, 8.0])
    lines = truth.write_chords(p, again, CHORDS).read_text().splitlines()[4:]
    assert [" ".join(line.split()) for line in lines] == [
        "1 0:00.05 D | Dm",
        "2 0:02.02 F | Fmaj7 N.C.",  # la mesure est plus longue, arr y lit autre chose ; ma correction reste
        "3 0:04.90 N.C. | N.C.",  # cette barre a bougé de presque un temps : l'accord d'arr, à réécouter
        "4 0:06.00 | Emaj7/3",
    ]
    # rien à écrire sans accords transcrits ; rien à noter sans mesure remplie, ni majeur ou mineur sur un sus4
    other = truth.save(p, "intro", 0.0, 4.0, [0.0, 2.0])
    assert truth.write_chords(p, other, []) is None and truth.chord_score(other, [], CHORDS) == {}
    assert truth.chord_score(other, [(0, ["Dsus4"], ["Dm"])], CHORDS)["majmin"] is None


def chord_project(tmp_path, monkeypatch):
    """Quatre mesures à 120 à la noire, transcrites : Dm, puis F et C, rien, puis E."""
    p = Project.create(tmp_path / "lib/night-drive", "Night Drive")
    beats = [0.5 * i for i in range(16)]
    (p.root / "analysis.json").write_text(json.dumps({"beats": beats, "downbeats": beats[::4]}))
    (p.root / "score/chord.lab").write_text("".join(f"{a}\t{b}\t{label}\n" for a, b, label in CHORDS))
    (p.root / "score/beat.lab").write_text("".join(f"{t:.2f}\t{i % 4 + 1}\t4\t4\n" for i, t in enumerate(beats)))
    monkeypatch.chdir(p.root)
    return p


def test_truth_writes_the_chord_file_and_scores_the_chords(tmp_path, monkeypatch):
    p = chord_project(tmp_path, monkeypatch)
    truth.save(p, "verse", 0.0, 8.0, [0.0, 2.0, 4.0, 6.0])
    path = p.root / "truth/verse.v001.chords.txt"
    # --dry-run n'écrit rien ; le premier vrai lancement écrit le fichier, rempli des accords d'arr
    assert runner.invoke(app, ["truth", "--dry-run"], env={"COLUMNS": "220"}).exit_code == 0 and not path.exists()
    result = runner.invoke(app, ["truth"], env={"COLUMNS": "220"})
    assert "100% fond. · 100% maj/min · 0/3 corrigées" in result.output and path.exists()

    # j'entends F tout le long de la deuxième mesure : arr avait C sur sa seconde moitié
    path.write_text(path.read_text().replace("Fmaj7 C  ", "F        "))
    result = runner.invoke(app, ["truth"], env={"COLUMNS": "220"})
    assert result.exit_code == 1 and "83% fond. · 83% maj/min · 1/3 corrigées" in result.output
    assert "moins bien : night-drive verse" in result.output  # les accords comptent dans le verdict
    assert result.output.count("83% fond.") == 2  # le passage, et le total


def test_play_mark_leaves_a_chord_file_to_correct(tmp_path, monkeypatch):
    p, session = marking_project(tmp_path, monkeypatch)
    (p.root / "score/chord.lab").write_text("0.0\t4.0\tA:min\n4.0\t6.0\tC:maj\n6.0\t8.0\tG:maj\n")
    (p.root / "score/beat.lab").write_text("".join(f"{0.5 * i:.2f}\t{i % 4 + 1}\t4\t4\n" for i in range(16)))
    session["taps"] = [0.0, 2.0, 3.9]
    result = runner.invoke(app, ["play", "-s", "chorus,outro", "--mark"], input="o\n")
    assert "accords à corriger à l'oreille, mesure par mesure : truth/chorus+outro.v001.chords.txt" in result.output
    rows = truth.read_chords(p.root / "truth/chorus+outro.v001.chords.txt")
    # trois barres font deux mesures : la dernière frappe ferme la précédente
    assert rows == [(0, ["C"], ["C"]), (1, ["G"], ["G"])]
