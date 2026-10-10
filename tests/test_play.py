"""Écoute : ce qui est joué, et ce que l'écran en dit."""

import json

import numpy as np

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

    from arr.commands.play import position, timeline, view

    p = Project.create(tmp_path / "song", "song")
    add_track(p, "guitar", tone(330, 6.0, amp=0.1), {"op": "split"})
    p.set_sections([Section("verse", 0.0, 2.0), Section("chorus", 2.0, 4.0), Section("outro", 4.0, 6.0)])
    p.set_nudge("guitar", "outro", 500.0)
    p.save()

    # sections jouées dans le désordre : l'horloge suit la lecture, pas le morceau
    marks = timeline(p, None, ["outro", "verse"], [(4.0, 6.0), (0.0, 2.0)])
    assert marks == [(0.0, 2.0, "outro"), (2.0, 4.0, "verse")]
    assert timeline(p, None, [], [])[1] == (2.0, 4.0, "chorus")

    def text(t):
        console = Console(width=200, record=True, file=open("/dev/null", "w"), color_system=None)
        console.print(view(p, None, None, (), (), marks, 4.0, False, t))
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
