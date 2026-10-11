"""Écoute : ce qui est joué, et ce que l'écran en dit."""

import json

import numpy as np
import pytest

from arr import audio
from arr.cli import add_track, app
from arr.project import Project, Section
from tests.helpers import fake_studio, runner, tone


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


def test_play_shows_what_plays_and_what_is_applied(tmp_path, monkeypatch):
    fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    for name, f in (("drums", 110), ("bass", 55), ("guitar", 330), ("piano", 440)):
        add_track(p, name, tone(f, 4.0, amp=0.1), {"op": "split"})
    p.set_sections([Section("verse", 0.0, 2.0), Section("chorus", 2.0, 4.0)])
    p.tracks["bass"]["gain"] = -5.0
    p.tracks["piano"]["mute"] = True
    p.set_nudge("guitar", "track", 40.0)
    p.set_nudge("guitar", "chorus", -15.0, by="align")
    p.save()
    _, path = p.new_take({"model": "yue2", "mode": "close", "style": "funk", "seed": 1})
    audio.save(path, tone(220, 0.5, amp=0.1))
    monkeypatch.chdir(p.root)
    monkeypatch.setenv("COLUMNS", "200")
    line = lambda out, start: next(row for row in out.splitlines() if row.strip("●○ ").startswith(start))

    out = runner.invoke(app, ["play", "-w", "drums"]).output
    assert "Mix · 2 pistes" in out and "verse" in line(out, "▶")
    assert "v001" in line(out, "bass") and "-5.0 dB" in line(out, "bass")
    assert "+40 ms" in line(out, "guitar") and "dB" not in line(out, "guitar")
    assert "drums (écartée)" in line(out, "hors du mix") and "piano (muette)" in line(out, "hors du mix")

    # dans le refrain, le réglage de la section s'ajoute à celui de la piste
    out = runner.invoke(app, ["play", "-s", "chorus"]).output
    assert "chorus" in line(out, "▶") and "0:00 / 0:02" in line(out, "▶")
    guitar = line(out, "guitar")
    assert "+40 ms manuel" in guitar and "-15 ms auto" in guitar and "+25 ms" in guitar

    assert "stems de t001" not in out
    out = runner.invoke(app, ["play", "-o", "bass"]).output
    assert "hors du mix : 3 autres pistes" in out

    out = runner.invoke(app, ["play", "bass"]).output
    assert "Piste bass, seule" in out and "-5.0 dB dans le mix, non appliqué" in line(out, "bass")

    out = runner.invoke(app, ["play", "t001"]).output
    assert "Prise t001, telle que rendue (fidèle)" in out and "ni calage ni gain" in out


def test_play_view_follows_the_position(tmp_path):
    from rich.console import Console

    from arr.commands._screen import position, timeline, view

    p = Project.create(tmp_path / "song", "song")
    add_track(p, "guitar", tone(330, 6.0, amp=0.1), {"op": "split"})
    p.set_sections([Section("verse", 0.0, 2.0), Section("chorus", 2.0, 4.0), Section("outro", 4.0, 6.0)])
    p.set_nudge("guitar", "outro", 500.0)
    p.save()

    # sections jouées dans le désordre : l'horloge suit la lecture, pas le morceau
    marks = timeline(p, None, ["outro", "verse"], [(4.0, 6.0), (0.0, 2.0)])
    assert marks == [(0.0, 2.0, "outro", 4.0), (2.0, 4.0, "verse", 0.0)]
    assert timeline(p, None, [], [])[1] == (2.0, 4.0, "chorus", 2.0)

    def text(t):
        console = Console(width=200, record=True, file=open("/dev/null", "w"), color_system=None)
        console.print(view(p, "Mix · 1 piste", ["guitar"], marks, 4.0, "Ctrl+C arrête", t))
        return console.export_text()

    assert "outro (1/2)" in text(0.5) and "+500 ms" in text(0.5) and "puis verse" in text(0.5)
    assert "verse (2/2)" in text(3.0) and "+500 ms" not in text(3.0)
    assert "décompte" in text(-1.0)

    # décompte de 2 s, puis 4 s jouées ; en boucle, la position repart du début du corps
    sr = audio.SR
    assert position(1.0, lead=2 * sr, first=6 * sr) == -1.0
    assert position(5.0, lead=2 * sr, first=6 * sr) == 3.0
    assert position(7.0, lead=2 * sr, first=6 * sr) == 1.0
    assert position(6.0, lead=2 * sr) == 4.0  # sans boucle, la fin reste la fin


def test_play_sections_in_series_looped_after_a_count_in(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    song = np.concatenate([tone(110, 2.0, amp=0.1), tone(220, 2.0, amp=0.1), tone(440, 2.0, amp=0.1)])
    add_track(p, "guitar", song, {"op": "split"})
    p.set_sections([Section("verse", 0.0, 2.0), Section("chorus", 2.0, 4.0), Section("outro", 4.0, 6.0)])
    p.save()
    # 120 à la noire, quatre temps par mesure
    grid = {"beats": [0.5 * i for i in range(12)], "downbeats": [0.0, 2.0, 4.0]}
    (p.root / "analysis.json").write_text(json.dumps(grid))
    audio.save(p.new_take({"style": "x"})[1], tone(220, 1.0))
    monkeypatch.chdir(p.root)
    sr, inside = audio.SR, slice(1000, -1000)

    # une section, une fois
    assert runner.invoke(app, ["play", "-s", "chorus"]).exit_code == 0
    assert len(calls["played"][0]) == 2 * sr and calls["looped"][0] is None
    assert np.allclose(calls["played"][0][inside], song[2 * sr : 4 * sr][inside], atol=1e-3)

    # deux sections dans l'ordre demandé, qui n'est pas celui du morceau
    result = runner.invoke(app, ["play", "guitar", "-s", "outro", "-s", "verse"])
    assert result.exit_code == 0 and "outro (1/2)" in result.output and "puis verse" in result.output
    first, second = calls["played"][1][: 2 * sr], calls["played"][1][2 * sr :]
    assert np.allclose(first[inside], song[4 * sr :][inside], atol=1e-3)
    assert np.allclose(second[inside], song[: 2 * sr][inside], atol=1e-3)

    # en boucle après une mesure de décompte : les clics précèdent la section et ne sont pas dans la boucle
    result = runner.invoke(app, ["play", "-s", "chorus", "--loop", "--count-in", "1"])
    assert result.exit_code == 0, result.output
    played, looped = calls["played"][2], calls["looped"][2]
    assert len(played) == 4 * sr and len(looped) == 2 * sr
    lead = played[: 2 * sr]
    for k in range(4):
        assert lead[int(0.5 * k * sr) + 10 : int(0.5 * k * sr) + 500].any()
        assert not lead[int((0.5 * k + 0.1) * sr) : int((0.5 * k + 0.45) * sr)].any()
    assert np.array_equal(played[2 * sr :], looped)
    assert np.allclose(looped[inside], song[2 * sr : 4 * sr][inside], atol=1e-3)

    # même enchaînement écrit avec des virgules
    assert runner.invoke(app, ["play", "guitar", "--section", "outro,verse"]).exit_code == 0
    assert np.array_equal(calls["played"][3], calls["played"][1])

    assert runner.invoke(app, ["play", "-s", "nope"]).exit_code != 0
    # une prise brute n'est pas calée sur l'original
    result = runner.invoke(app, ["play", "t001", "-s", "chorus"])
    assert result.exit_code != 0 and "arr split t001" in str(result.exception)
    assert runner.invoke(app, ["play", "t001", "--loop"]).exit_code == 0
    assert len(calls["played"]) == 5


def test_play_count_in_without_a_known_tempo_only_warns(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "guitar", tone(330, 0.5, amp=0.1), {"op": "split"})
    monkeypatch.chdir(p.root)

    result = runner.invoke(app, ["play", "--count-in", "1"])
    assert result.exit_code == 0 and "pas de décompte" in result.output
    assert len(calls["played"][0]) == audio.SR // 2


def test_chord_names_read_like_a_lead_sheet():
    from arr.commands._screen import chord_name

    given = ["D:min", "C:maj", "F:maj7", "E:min7", "A:sus4", "C:maj6", "C:7", "N", "G:min/b3", "Bb"]
    assert [chord_name(c) for c in given] == ["Dm", "C", "Fmaj7", "Em7", "Asus4", "C6", "C7", "–", "Gm/b3", "Bb"]


def test_chart_puts_each_chord_on_its_beat():
    from arr.commands._screen import chart

    # 4/4, un temps par seconde ; Dm sur quatre temps, puis F et C sur deux temps chacun, puis G tenu six temps
    beats = [(float(i), i % 4 + 1) for i in range(12)]
    chords = [(0.0, 4.0, "D:min"), (4.0, 6.0, "F:maj"), (6.0, 8.0, "C:maj"), (8.0, 14.0, "G:maj")]
    bars = chart(chords, beats)
    assert [(b[0], b[1], b[2]) for b in bars] == [(0.0, 4.0, 4), (4.0, 8.0, 4), (8.0, 14.0, 4)]
    assert bars[0][3] == [(0, 4, "D:min", 0.0, 4.0)]
    assert bars[1][3] == [(0, 2, "F:maj", 4.0, 6.0), (2, 2, "C:maj", 6.0, 8.0)]

    # un accord tenu au-delà de la barre est réécrit ; une levée de deux temps fait une mesure courte
    pickup = [(0.0, 3), (1.0, 4)] + [(2.0 + i, i % 4 + 1) for i in range(8)]
    bars = chart([(0.0, 4.0, "A:min"), (4.0, 10.0, "E:7")], pickup)
    assert [b[2] for b in bars] == [2, 4, 4]
    assert [c[:3] for c in bars[1][3]] == [(0, 2, "A:min"), (2, 2, "E:7")] and bars[2][3][0][:3] == (0, 4, "E:7")

    # sans accord à cet endroit : « N » ; sans grille de temps : un accord par mesure
    assert chart([(2.0, 4.0, "C:maj")], [(0.0, 1), (1.0, 2), (2.0, 3), (3.0, 4)])[0][3][0][:3] == (0, 2, "N")
    assert chart(chords[:2], []) == [
        (0.0, 4.0, 1, [(0, 1, "D:min", 0.0, 4.0)]),
        (4.0, 6.0, 1, [(0, 1, "F:maj", 4.0, 6.0)]),
    ]


def test_chord_page_follows_the_section_being_played():
    from arr.commands._screen import chart, chord_page

    # mesures de quatre secondes ; couplet de 0 à 8 s, refrain de 8 à 16 s, deux accords dans la mesure 2 du refrain
    beats = [(float(i), i % 4 + 1) for i in range(20)]
    chords = [
        (0.0, 8.0, "D:min"),
        (8.0, 12.0, "F:maj"),
        (12.0, 14.0, "G:maj"),
        (14.0, 16.0, "C:maj"),
        (16.0, 20.0, "A:min"),
    ]
    bars = chart(chords, beats)
    whole = [(0.0, 8.0, "verse", 0.0), (8.0, 16.0, "chorus", 8.0)]

    name, page, current, upcoming = chord_page(bars, whole, 5.0)
    assert name == "verse" and page == bars[:2] and current == (1, 0)
    assert upcoming == ("chorus", bars[2:4])
    assert chord_page(bars, whole, 13.0)[2] == (1, 0) and chord_page(bars, whole, 14.5)[2] == (1, 1)
    assert chord_page(bars, whole, 14.5)[3] == ()

    # refrain puis couplet : à 6,5 s de lecture on est à 14,5 s du morceau
    swapped = [(0.0, 8.0, "chorus", 8.0), (8.0, 16.0, "verse", 0.0)]
    name, page, current, upcoming = chord_page(bars, swapped, 6.5)
    assert name == "chorus" and page[current[0]][3][current[1]][2] == "C:maj" and upcoming[0] == "verse"

    # en boucle, la suite de la dernière section est la première ; une section seule n'annonce rien
    assert chord_page(bars, swapped, 9.0)[3] == () and chord_page(bars, swapped, 9.0, loop=True)[3][0] == "chorus"
    assert chord_page(bars, swapped[:1], 1.0, loop=True)[3] == ()

    # décompte : la première section, sans accord surligné
    name, page, current, _ = chord_page(bars, swapped, -1.0)
    assert name == "chorus" and page == bars[2:4] and current is None

    # hors section, ou projet sans sections : une page de huit mesures autour de la position
    name, page, current, upcoming = chord_page(bars, whole, 17.0)
    assert name is None and page == bars and current == (4, 0) and upcoming == ()
    assert chord_page(bars, [], 13.0)[1:3] == (bars, (3, 0))

    # une section redéfinie à la main, qui ne tombe pas sur les barres : chaque mesure va où est son milieu
    assert chord_page(bars, [(0.0, 9.5, "verse", 0.0)], 0.0)[1] == bars[:2]
    assert chord_page([], whole, 1.0)[1] == []


def test_chord_grid_shows_how_long_each_chord_lasts(tmp_path, monkeypatch):
    from rich.console import Console

    from arr.commands._screen import chart, view

    p = Project.create(tmp_path / "song", "song")
    p.set_sections([Section("verse", 0.0, 16.0), Section("chorus", 16.0, 20.0)])
    beats = [(float(i), i % 4 + 1) for i in range(20)]
    chords = [
        (0.0, 4.0, "D:min"),
        (4.0, 6.0, "F:maj7"),
        (6.0, 8.0, "C:maj"),
        (8.0, 11.0, "Bb:maj"),
        (11.0, 20.0, "A:7"),
    ]
    bars = chart(chords, beats)
    marks = [(0.0, 16.0, "verse", 0.0), (16.0, 20.0, "chorus", 16.0)]

    def lines(t, columns):
        monkeypatch.setenv("COLUMNS", str(columns))
        console = Console(width=columns, record=True, file=open("/dev/null", "w"), color_system=None)
        console.print(view(p, "Mix", [], marks, 20.0, "", t, bars=bars))
        return [line.rstrip() for line in console.export_text().splitlines()]

    out = lines(5.0, 120)
    row = out[out.index("Accords · verse") + 1]
    # six colonnes par temps (« Fmaj7 » et une espace) : chaque temps tenu est un « / » sous les autres temps
    assert row == (
        "│ Dm    /     /     /     │ Fmaj7 /     C     /     │ Bb    /     /     A7    │ A7    /     /     /     │"
    )
    # sous un séparateur, la première rangée de la section suivante, sur les mêmes colonnes
    at = out.index("── puis chorus ──")
    assert out[at + 1] == "│ A7    /     /     /     │" and at == out.index("Accords · verse") + 2
    # terminal étroit : deux mesures par rangée, sans rien couper
    narrow = lines(5.0, 80)
    at = narrow.index("Accords · verse")
    assert narrow[at + 1] == "│ Dm    /     /     /     │ Fmaj7 /     C     /     │"
    assert narrow[at + 2] == "│ Bb    /     /     A7    │ A7    /     /     /     │"
    assert narrow[at + 3 : at + 5] == ["── puis chorus ──", "│ A7    /     /     /     │"]

    # l'accord qui sonne, et lui seul, est surligné sur toute sa durée
    def highlighted(t):
        monkeypatch.setenv("COLUMNS", "120")
        console = Console(
            width=120, record=True, file=open("/dev/null", "w"), color_system="standard", force_terminal=True
        )
        console.print(view(p, "Mix", [], marks, 20.0, "", t, bars=bars))
        spans = [s for s in console.export_text(styles=True).split("\x1b[") if s.startswith("1;7m")]
        return [s.split("m", 1)[1].rstrip() for s in spans]

    assert highlighted(5.0) == ["Fmaj7 /"] and highlighted(7.5) == ["C     /"]
    assert highlighted(11.2) == ["A7"] and highlighted(-1.0) == []


def test_play_shows_the_chords_of_the_section(tmp_path, monkeypatch):
    from tests.helpers import song_project

    fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    song_project(tmp_path, monkeypatch)
    assert "Accords" not in runner.invoke(app, ["play", "-o", "x"]).output  # pas de piste : erreur, pas d'écran
    assert runner.invoke(app, ["split"]).exit_code == 0
    assert "Accords" not in runner.invoke(app, ["play"]).output  # pas encore de transcription
    assert runner.invoke(app, ["transcribe"]).exit_code == 0

    monkeypatch.setenv("COLUMNS", "120")
    out = runner.invoke(app, ["play", "-s", "chorus2"]).output  # de 2 à 4 s : une mesure, Fmaj7 puis C
    assert "Accords · chorus2" in out and "│ Fmaj7 /     C     /     │" in out and "Dm" not in out
    out = runner.invoke(app, ["play"]).output  # l'écran de départ : l'intro, puis le refrain
    assert "Accords · intro" in out and "── puis chorus ──" in out and out.count("│ –   /   Dm  /   │") == 2

    assert runner.invoke(app, ["render", "-s", "funk"]).exit_code == 0
    out = runner.invoke(app, ["play", "t001"]).output
    assert "Prise t001" in out and "Accords" not in out  # une prise brute n'est pas calée sur l'original


def test_keys_are_read_from_what_the_terminal_sends():
    from arr.commands.play import parse_keys

    assert parse_keys(b" ") == ["pause"]
    assert parse_keys(b"\x1b[D\x1b[D\x1b[C") == ["back", "back", "forward"]
    assert parse_keys(b"\x1bOD \x1bOC") == ["back", "pause", "forward"]  # flèches en mode « application »
    assert parse_keys(b"q\x1b[A\n") == []  # le reste est ignoré


def test_arrows_lead_to_bar_starts():
    from arr.commands.play import bar_stops, neighbour

    bars = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    assert bar_stops(bars, [], 12.0) == bars
    # sections jouées dans le désordre : les arrêts suivent la lecture, pas le morceau
    stops = bar_stops(bars, [(8.0, 12.0), (2.0, 6.0)], 8.0)
    assert stops == [0.0, 2.0, 4.0, 6.0]
    # une section qui commence au milieu d'une mesure : son début, puis les barres suivantes
    assert bar_stops(bars, [(3.0, 7.0)], 4.0) == [0.0, 1.0, 3.0]
    # une barre à deux centièmes du début de la section ne fait pas un arrêt de plus
    assert bar_stops([0.0, 2.02, 4.02], [(2.0, 6.0)], 4.0) == pytest.approx([0.0, 2.02])
    # sans mesures connues : un arrêt toutes les cinq secondes
    assert bar_stops([], [], 12.0) == [0.0, 5.0, 10.0]

    assert neighbour(bars, 5.0, -1) == 2.0 and neighbour(bars, 5.0, +1) == 6.0  # depuis la mesure qui commence à 4 s
    assert neighbour(bars, 4.0, -1) == 2.0  # pile sur la barre : la mesure d'avant, pas celle-ci
    assert neighbour(bars, 1.0, -1) == 0.0 and neighbour(bars, 11.0, +1) is None
    assert neighbour(bars, 11.0, +1, loop=True) == 0.0 and neighbour(bars, 5.0, +1, loop=True) == 6.0


def test_play_pauses_and_moves_bar_by_bar(tmp_path, monkeypatch):
    from contextlib import contextmanager

    from arr.commands import play as command

    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = Project.create(tmp_path / "song", "song")
    add_track(p, "guitar", tone(330, 8.0, amp=0.1), {"op": "split"})
    p.set_sections([Section("verse", 0.0, 4.0), Section("chorus", 4.0, 8.0)])
    p.save()
    # 120 à la noire : une mesure toutes les 2 s ; une mesure de décompte
    grid = {"beats": [0.5 * i for i in range(16)], "downbeats": [2.0 * i for i in range(4)]}
    (p.root / "analysis.json").write_text(json.dumps(grid))
    monkeypatch.chdir(p.root)
    monkeypatch.setenv("COLUMNS", "200")
    typed = iter([[], ["pause"], ["back"], ["pause"], ["back", "back"], ["forward"], ["forward"], []])

    @contextmanager
    def keyboard():
        yield lambda: next(typed)

    monkeypatch.setattr(command, "keyboard", keyboard)
    # refrain en boucle après 2 s de décompte ; le flux est à 3 s, donc à 1 s du refrain, puis au deuxième tour
    calls["positions"] = [3.0, 3.0, 3.0, 3.0, 5.5, 5.5, 7.0, 7.0]
    result = runner.invoke(app, ["play", "-s", "chorus", "--loop", "--count-in", "1"])
    assert result.exit_code == 0, result.output
    assert calls["orders"] == [
        (False, None),
        (True, None),  # espace : pause
        (True, 2.0),  # ← en pause : début de la mesure (0 s du refrain, après 2 s de décompte)
        (False, None),  # espace : reprise
        (False, 2.0),  # ← ← depuis 3,5 s (deuxième mesure) : la première, on ne remonte pas plus haut
        (False, 2.0),  # → depuis la dernière mesure, en boucle : retour à la première
        (False, 8.0),  # deuxième tour, à 1 s du refrain : → mène à sa deuxième mesure
        (False, None),
    ]
    assert "Espace : pause" in result.output and "en pause" not in result.output  # la dernière image joue


def test_play_shows_the_pause(tmp_path):
    from rich.console import Console

    from arr.commands._screen import view

    p = Project.create(tmp_path / "song", "song")
    console = Console(width=200, record=True, file=open("/dev/null", "w"), color_system=None)
    console.print(view(p, "Mix", [], [], 4.0, "", 1.0, paused=True))
    assert "⏸ en pause" in console.export_text()


def test_chord_chart_follows_the_reference_bars(tmp_path):
    """Les mesures de la grille sont celles d'arr analyze, y compris une mesure à deux temps."""
    from arr.commands._screen import song_chart
    from tests.helpers import short_bar_song

    song, beats, bars, truth = short_bar_song()
    p = Project.create(tmp_path / "song", "song")
    audio.save(p.root / "source/original.flac", song)
    (p.root / "analysis.json").write_text(json.dumps({"beats": beats, "downbeats": bars}))
    score = p.root / "score"
    score.mkdir(exist_ok=True)
    # la transcription compte quatre temps partout, et pose les accords d'après la mesure courte trop tard
    (score / "beat.lab").write_text("".join(f"{t:.2f}\t{i % 4 + 1}\t4\t4\n" for i, t in enumerate(beats)))
    heard = [(s + 1.0, e + 1.0, label) if s >= 9.0 else (s, e, label) for s, e, label in truth]
    (score / "chord.lab").write_text("".join(f"{s:.2f}\t{e:.2f}\t{label}\n" for s, e, label in heard))

    chart = song_chart(p)
    assert [round(bar[0], 2) for bar in chart] == bars
    assert [bar[2] for bar in chart] == [4, 4, 4, 4, 2, 4, 4, 4, 4, 4, 4, 4]
    assert [[chord[2] for chord in bar[3]] for bar in chart] == [[label] for _, _, label in truth]

    # sans analyse : la grille de la transcription, telle quelle
    (p.root / "analysis.json").unlink()
    assert [bar[2] for bar in song_chart(p)][:6] == [4, 4, 4, 4, 4, 4]
