"""arr review : les passages à relire, les réponses du musicien, et ce qu'elles deviennent après une nouvelle analyse."""

from contextlib import contextmanager

import numpy as np
import pytest

from arr import audio, review
from arr.cli import app
from arr.commands import _playback as playback
from arr.commands._common import save_analysis, song_doubts, song_passages
from tests.helpers import WEAK, doubtful_song, fake_studio, fake_taps, gappy_song, marked_passage, runner

# Seize mesures : les mesures 3 et 4 douteuses, puis la 7 (leurs passages se touchent), puis la 13.
FAR = (*WEAK, (25.0, 0.6))


def typing(monkeypatch, *turns):
    """Les touches tapées, un lot par appel de l'écran ; la lecture « avance » d'autant de pas."""
    typed = iter(turns)

    @contextmanager
    def keyboard():
        yield lambda: next(typed, [])

    monkeypatch.setattr(playback, "keyboard", keyboard)


def lines(result) -> list[str]:
    assert result.exit_code == 0, result.output
    return [" ".join(line.split()) for line in result.output.splitlines() if line.strip()]


def test_measures_and_passages():
    beats = [0.5 * i for i in range(-2, 40)]  # une levée de deux temps, puis dix mesures
    bars = review.measures(beats, [2.0 * i for i in range(10)])
    assert len(bars) == 10 and bars[0] == [0.0, 0.5, 1.0, 1.5] and bars[-1][-1] == 19.5
    # une mesure douteuse : elle-même, une avant, une après
    (one,) = review.passages(bars, {8.0: "a"}, [], 20.0)
    assert (one.start, one.end, one.first, one.where) == (6.0, 12.0, 4, "mes. 4 à 6") and not one.right
    # deux passages qui se touchent n'en font qu'un ; au bord du morceau, pas de mesure de plus
    (one,) = review.passages(bars, {2.0: "a", 8.0: "b"}, [], 20.0)
    assert (one.start, one.end, one.where) == (0.0, 12.0, "mes. 1 à 6") and list(one.doubts) == [2.0, 8.0]
    first, last = review.passages(bars, {0.0: "a", 18.0: "b"}, [], 20.0)
    assert (first.where, last.where, last.end) == ("mes. 1 à 2", "mes. 9 à 10", 20.0)
    # une section, douteuse ou non
    part = review.between(bars, 4.0, 8.0, {}, [])
    assert (part.start, part.end, part.where, part.right) == (4.0, 8.0, "mes. 3 à 4", False)
    assert review.between(bars, 30.0, 40.0, {}, []) is None


def test_a_judgement_holds_for_the_same_bar_only():
    bar = [4.0, 4.5, 5.0, 5.5]
    assert review.same([4.03, 4.52, 5.04, 5.5], bar)  # le détecteur redit la même chose, au pas près
    assert review.same([t + 0.2 for t in bar], bar)  # tout le morceau a glissé de moins d'un demi-temps
    assert not review.same([t + 0.5 for t in bar], bar)  # un temps plus tard : une autre mesure
    assert not review.same([4.0, 4.5, 5.0], bar)  # un temps de moins
    assert not review.same([4.0, 4.5, 5.2, 5.5], bar)  # un temps déplacé
    assert review.unjudged({4.0: "a", 6.0: "b"}, [bar, [6.0, 6.5, 7.0, 7.5]], [bar]) == {6.0: "b"}


def test_review_lists_the_passages_without_playing(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = doubtful_song(tmp_path, monkeypatch, FAR, bars=16)
    assert lines(runner.invoke(app, ["review", "--list"])) == [
        "0:02 mes. 2 à 8 verse temps 3 entendu faiblement (0,70) ; 2 de plus · à relire",
        "0:22 mes. 12 à 14 chorus temps 3 entendu faiblement (0,60) · à relire",
        "vérifié : 0/2 passages",
    ]
    assert not calls["played"] and not (p.root / "review").exists()
    assert runner.invoke(app, ["doubts"]).exit_code != 0  # la commande n'existe plus
    # un morceau analysé avant que les activations ne soient gardées
    (p.root / "analysis_frames.npz").rename(p.root / "ailleurs.npz")
    result = runner.invoke(app, ["review"])
    assert result.exit_code != 0 and "lance arr analyze" in str(result.exception)
    (p.root / "analysis.json").unlink()
    assert "pas d'analyse" in str(runner.invoke(app, ["review", "--list"]).exception)


def test_review_plays_each_passage_in_a_loop_and_resumes_where_i_left(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = doubtful_song(tmp_path, monkeypatch, FAR, bars=16)
    audio.save(p.root / "source/original.flac", np.zeros((32 * audio.SR, 2), np.float32))

    # rien n'est tapé : le premier passage joue en boucle, de barre à barre, et rien n'est noté
    calls["positions"] = [0.0]
    out = runner.invoke(app, ["review"]).output
    assert "song · relecture 1/2" in out and "verse · mes. 2 à 8" in out and "en boucle" in out
    assert "│ D   /   /   /   │?E   /   /   /   │?F   /   /   /   │ G   /   /   /   │" in out
    assert "? compte incertain · 0:04 : temps 3 entendu faiblement (0,70)" in out
    assert "Entrée : c'est bon" in out and "vérifié : 0/2 passages" in out
    assert len(calls["played"][0]) == 14 * audio.SR and calls["looped"][0] is calls["played"][0]
    assert "il reste 2 passages : arr review" in out and not (p.root / "review").exists()

    # Espace met en pause ; → mène à l'autre passage sans répondre ; Entrée le juge bon ; q quitte
    calls["played"].clear(), calls["orders"].clear()
    calls["positions"] = [0.0, 0.1]
    typing(monkeypatch, ["pause"], ["forward"], ["enter"], ["quit"])
    out = runner.invoke(app, ["review"]).output
    assert calls["orders"] == [(True, None), (True, None, True), (False, None, True), (False, None, True)]
    assert [len(x) // audio.SR for x in calls["played"]] == [14, 6, 14]
    assert "✔ chorus · mes. 12 à 14 : c'est bon" in out and "vérifié : 1/2 passages · il reste 1 passage" in out
    assert [f.name for f in sorted((p.root / "review").iterdir())] == ["v001.toml"]

    # la reprise : le premier passage qui reste ; ← revient au passage jugé, montré comme tel
    typing(monkeypatch, ["back"], [], ["forward"], ["enter"])
    calls["positions"] = [0.0, 0.1]
    out = runner.invoke(app, ["review"]).output
    assert "relecture 2/2" in out and "✔ jugé bon" in out
    assert "✔ verse · mes. 2 à 8 : c'est bon" in out and "vérifié : 2/2 passages · morceau vérifié" in out
    # une version par réponse, la dernière porte tout
    assert [f.name for f in sorted((p.root / "review").iterdir())] == ["v001.toml", "v002.toml"]
    assert len(review.right_bars(p)) == 3 + 7 and song_doubts(p, mine=True) == {}

    # il ne reste rien : la relecture le dit, sans jouer
    calls["played"].clear()
    out = runner.invoke(app, ["review"]).output
    assert "vérifié : 2/2 passages · morceau vérifié" in out and not calls["played"]
    assert lines(runner.invoke(app, ["review", "--list"]))[-1] == "vérifié : 2/2 passages"


def test_a_judgement_survives_a_new_analysis_unless_the_bars_changed(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = doubtful_song(tmp_path, monkeypatch, FAR, bars=16)
    calls["positions"] = [0.0]
    typing(monkeypatch, ["enter"], ["enter"])
    assert "morceau vérifié" in runner.invoke(app, ["review"]).output

    def analysed(beats):
        heard = np.zeros((1601, 2), np.float32)
        heard[[int(round(t * 50)) for t in beats], 0] = 1.0
        for t, level in FAR:
            heard[int(t * 50), 0] = level
        save_analysis(p, beats, beats[::4], heard)

    # le détecteur redit les mêmes temps, à 20 ms près : rien n'est redemandé
    beats = [0.5 * i for i in range(64)]
    analysed([t + 0.02 * (i % 2) for i, t in enumerate(beats)])
    assert song_doubts(p) and song_doubts(p, mine=True) == {}
    assert all(x.right for x in song_passages(p))
    # il lit autrement la mesure 13 (un temps déplacé de 120 ms) : ce passage-là revient, l'autre non
    analysed([t + 0.12 if t == 25.5 else t for t in beats])
    assert list(song_doubts(p, mine=True)) == [24.0]
    assert [x.right for x in song_passages(p)] == [True, False]
    out = runner.invoke(app, ["review", "--list"]).output
    assert "jugé bon" in out and "à relire" in out and "vérifié : 1/2 passages" in out


def test_review_a_section_of_my_choice(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = doubtful_song(tmp_path, monkeypatch)
    calls["positions"] = [0.0]
    typing(monkeypatch, ["enter"])
    out = runner.invoke(app, ["review", "-s", "chorus"]).output
    assert "song · section chorus" in out and "chorus · mes. 5 à 8" in out
    assert "│ G   /   /   /   │ A   /   /   /   │?B   /   /   /   │ C   /   /   /   │" in out
    assert len(calls["played"][0]) == 8 * audio.SR and "✔ chorus · mes. 5 à 8 : c'est bon" in out
    # la mesure 7 est jugée avec sa section ; les mesures 3 et 4 restent à relire
    assert list(song_doubts(p, mine=True)) == [4.0, 6.0]
    assert "inconnue" in str(runner.invoke(app, ["review", "-s", "bridge"]).exception)


def test_a_judged_passage_loses_its_mark_in_play(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    doubtful_song(tmp_path, monkeypatch)
    calls["positions"] = [0.0]
    typing(monkeypatch, ["enter"])
    assert "morceau vérifié" in runner.invoke(app, ["review"]).output
    out = runner.invoke(app, ["play"]).output
    assert "?" not in out and "doute suivant" not in out


def test_analyze_and_transcribe_end_with_what_is_left_to_review(tmp_path, monkeypatch):
    from arr.engines import analysis
    from tests.helpers import song_project

    song_project(tmp_path, monkeypatch)
    assert lines(runner.invoke(app, ["analyze"]))[-1] == "aucun passage à relire"
    heard = np.ones((200, 2), np.float32)
    heard[74:77, 0] = 0.5  # le temps de 1,5 s, entendu faiblement
    monkeypatch.setattr(analysis, "activations", lambda path: heard)
    assert lines(runner.invoke(app, ["analyze"]))[-1] == "1 passage à relire : arr review"
    assert lines(runner.invoke(app, ["transcribe"]))[-1] == "1 passage à relire : arr review"


# --- corriger les barres

EVERY = [0.5 * i for i in range(64)]  # seize mesures à 120 à la noire


def test_a_tap_goes_to_the_nearest_detected_beat():
    # 45 ms en avance, 40 ms en retard, pile entre deux temps : les mêmes barres
    assert review.snap([3.955, 6.04, 8.25], EVERY) == ([4.0, 6.0, 8.0], [])
    assert review.snap([4.02, 3.97, 6.0], EVERY) == ([4.0, 6.0], [])  # deux frappes sur le même temps
    # au milieu d'un trou de deux temps, aucun temps à moins d'un demi-temps : la frappe est signalée
    holed = [t for t in EVERY if t != 4.0]
    assert review.snap([2.0, 4.01, 6.0], holed) == ([2.0, 4.01, 6.0], [4.01])


def test_a_missed_beat_is_spread_and_a_real_short_bar_is_kept():
    beats = [t for t in EVERY if t != 9.5]  # la mesure de 8 s n'a que trois temps
    taps = [6.0, 8.0, 10.0, 12.0]
    assert review.counts(taps, beats) == [4, 3, 4]
    regular = [2.0 * i for i in range(16)]
    # un temps manqué : quatre temps égaux entre les deux frappes
    fix = review.make_fix(taps, beats, {1})
    fixed, bars = review.fix_grid(beats, regular, [fix])
    assert fixed == EVERY and bars == regular
    assert all(len(bar) == 4 for bar in review.measures(fixed, bars))
    # une vraie mesure à trois temps : ses temps restent ceux du détecteur
    real = review.make_fix(taps, beats, set())
    assert review.fix_grid(beats, regular, [real]) == (beats, regular)
    assert [len(bar) for bar in review.measures(beats, regular)][3:6] == [4, 3, 4]
    # deux temps manqués de suite, ou un temps entendu deux fois : quatre temps égaux aussi
    two = [t for t in EVERY if t not in (9.0, 9.5)]
    assert review.fix_grid(two, regular, [review.make_fix(taps, two, {1})])[0] == EVERY
    twice = sorted([*EVERY, 9.1])
    assert review.counts(taps, twice) == [4, 5, 4]
    assert review.fix_grid(twice, regular, [review.make_fix(taps, twice, {1})])[0] == EVERY


def test_my_bars_are_pinned_and_nothing_moves_outside_them():
    late = [t + 1.0 for t in EVERY[::4]]  # le détecteur pose le 1 deux temps trop tard, partout
    fix = review.make_fix([8.0, 10.0, 12.0, 14.0], EVERY, set())
    beats, bars = review.fix_grid(EVERY, late, [fix])
    assert beats == EVERY
    assert bars == [
        1.0,
        3.0,
        5.0,
        7.0,
        8.0,
        10.0,
        12.0,
        14.0,
        15.0,
        *late[8:],
    ]  # les miennes dedans, les siennes dehors
    assert fix.covers(8.0) and fix.covers(12.0) and not fix.covers(14.0) and not fix.covers(7.0)
    # une correction plus récente l'emporte là où elle recouvre l'ancienne
    again = review.make_fix([9.0, 11.0, 13.0], EVERY, set())
    assert review.fix_grid(EVERY, late, [fix, again])[1][3:9] == [7.0, 8.0, 9.0, 11.0, 13.0, 14.0]


def test_m_fixes_the_bars_by_tapping_and_the_fix_shows_everywhere(tmp_path, monkeypatch):
    from arr.commands._common import song_bars, song_grid

    p = gappy_song(tmp_path, monkeypatch)
    assert runner.invoke(app, ["chordpro"]).exit_code == 0
    assert "{time: 3/4}" in (p.root / "export/song.cho").read_text()
    # m, puis cinq frappes (une en avance de 40 ms, une en retard), « temps manqué », Entrée garde
    taps = [5.96, 8.04, 10.0, 12.0, 14.0]
    session = fake_taps(monkeypatch, [taps], [["bars"], ["pause"], ["enter"]], lead=2.0, start=6.0)
    out = runner.invoke(app, ["review"], input="t\n").output
    assert "m : les barres sont mal placées" in out and "│?G   /   /   │" in out
    assert "Espace sur le 1 de chaque mesure" in out and "5 frappes" in out
    assert "1 mesure à 3 temps entre vos frappes (0:08,0)" in out and "temps manqué : 4 temps égaux (t)" in out
    before, after = out.split("Avant\n")[1].split("Après\n")
    assert before.startswith("│ F   /   /   /   │ G   /   /   │ A   /   /   /   │")
    assert after.startswith("│ F   /   /   /   │ G   /   /   /   │ A   /   /   /   │")
    assert "✔ verse · mes. 4 à 6 : barres corrigées (review/v001.toml)" in out and "morceau vérifié" in out
    assert "Le fichier du prompteur est plus ancien que vos corrections : arr chordpro" in out
    # le passage (6 s), quatre clics (2 s) puis le passage et une mesure de plus, une fois ; la boucle
    # avec la nouvelle grille ; enfin le passage corrigé rejoue, pour corriger ses accords ou passer au suivant
    assert session["played"] == [(6.0, True), (10.0, False), (8.0, True), (6.0, True)]
    # la correction se lit partout : grille, doutes, prompteur, décompte
    assert song_bars(p)[0] == EVERY and song_grid(p)[0] == EVERY
    assert song_doubts(p, mine=True) == {} and [x.state for x in song_passages(p)] == ["corrigé"]
    assert "corrigé" in runner.invoke(app, ["review", "--list"]).output
    assert runner.invoke(app, ["chordpro"]).exit_code == 0
    assert "{time: 3/4}" not in (p.root / "export/song.cho").read_text()
    out = runner.invoke(app, ["play", "-s", "verse"]).output
    assert "│ G   /   /   /   │" in out and "?" not in out

    # elle tient après une nouvelle analyse, même si le détecteur lit le passage tout autrement
    heard = np.ones((1601, 2), np.float32)
    moved = [t + 0.02 for t in EVERY if not 8.0 < t < 10.0]
    save_analysis(p, moved, [t + 1.02 for t in EVERY[::4]], heard)
    beats, bars = song_bars(p)
    assert [t for t in beats if 6.0 <= t <= 14.0] == [t for t in EVERY if 6.0 <= t <= 14.0]
    assert [t for t in bars if 6.0 <= t <= 14.0] == taps_on_beats(taps)

    # --undo la reprend, dans une nouvelle version ; il n'y a alors plus rien à reprendre
    out = runner.invoke(app, ["review", "--undo"]).output
    assert "correction des barres reprise : verse · 0:06,0 à 0:14,0" in out
    assert [f.name for f in sorted((p.root / "review").iterdir())] == ["v001.toml", "v002.toml"]
    assert review.bar_fixes(p) == [] and song_bars(p)[0] == moved
    assert "aucune correction" in str(runner.invoke(app, ["review", "--undo"]).exception)


def taps_on_beats(taps: list[float]) -> list[float]:
    return review.snap(taps, EVERY)[0]


def test_taps_can_be_redone_dropped_or_refused(tmp_path, monkeypatch):
    p = gappy_song(tmp_path, monkeypatch)
    # une frappe au milieu du trou : refusée, on refait ; puis une vraie mesure à trois temps, r, et Échap
    passes = [[6.0, 8.0, 9.5, 12.0], [6.0, 8.0, 10.0, 12.0], [6.0, 8.0, 10.0, 12.0]]
    session = fake_taps(monkeypatch, passes, [["bars"], ["redo"], ["escape"], ["quit"]], lead=2.0, start=6.0)
    out = runner.invoke(app, ["review"], input="o\nv\nx\nv\n").output
    assert "frappe à 0:09,5 : aucun temps détecté à moins d'un demi-temps" in out and "Refaire ?" in out
    assert out.count("vraie mesure à 3 temps (v)") == 3  # deux passes, et une réponse à côté redemandée
    assert "barres laissées telles quelles" in out and not (p.root / "review").exists()
    assert [played for played, _ in session["played"]] == [6.0, 10.0, 10.0, 8.0, 10.0, 8.0, 6.0]
    # une seule frappe : il en faut deux ; « n » abandonne
    fake_taps(monkeypatch, [[8.0]], [["bars"], ["quit"]], lead=2.0, start=6.0)
    out = runner.invoke(app, ["review"], input="n\n").output
    assert "1 frappe : il en faut deux au moins" in out and not (p.root / "review").exists()


def test_a_shifted_one_is_fixed_in_a_section_and_chords_stay_where_they_sound(tmp_path, monkeypatch):
    from arr.commands._screen import song_chart

    # le détecteur pose toutes les barres deux temps trop tard ; aucun temps faible : rien n'est douteux
    p = gappy_song(tmp_path, monkeypatch, missing=(), late=1.0, weak=())
    # sans l'original, les accords transcrits ne sont pas replacés sur les barres du détecteur (`measure.seat_chords`)
    (p.root / "source/original.flac").unlink()
    wrong = song_chart(p)
    late = {m[0]: m for m in wrong}
    assert late[17.0][2] == 4 and late[19.0][2] == 4
    assert [(c[0], c[2]) for c in late[17.0][3]] == [
        (0, "D:maj"),
        (2, "E:maj"),
    ]  # l'accord change au milieu de la mesure
    session = fake_taps(monkeypatch, [[16.0, 18.0, 20.0, 22.0]], [["bars"], ["enter"]], lead=2.0, start=16.0)
    out = runner.invoke(app, ["review", "-s", "chorus"]).output
    assert "✔ chorus" in out and "barres corrigées" in out
    # deux secondes de clics, la section depuis son début (16 s, avant la première barre du détecteur), une mesure de plus
    assert session["played"][1] == (18.0, False)
    chart = {m[0]: m for m in song_chart(p)}
    # mes barres : l'accord écrit sur le temps 3 d'une mesure fausse est sur le 1 de la bonne, au même instant
    assert [(c[0], c[2], c[3]) for c in chart[18.0][3]] == [(0, "E:maj", 18.0)]
    assert [(c[2], c[3]) for c in late[17.0][3]][1] == ("E:maj", 18.0)
    # hors de mes frappes rien ne bouge : la mesure d'avant et celle d'après sont celles du détecteur
    assert 15.0 in chart and 23.0 in chart and chart[22.0][2] == 2
    assert [m for m in song_chart(p) if m[0] < 15.0] == [m for m in wrong if m[0] < 15.0]
    assert [m for m in song_chart(p) if m[0] >= 23.0] == [m for m in wrong if m[0] >= 23.0]


def test_passages_marked_with_the_old_command_are_read_as_fixes(tmp_path, monkeypatch):
    from arr.commands._common import song_bars

    p = gappy_song(tmp_path, monkeypatch)
    # tapé autrefois à 30 ms près, en comptant quatre temps par mesure
    marked_passage(p, "verse", [6.03, 7.98, 10.01, 12.0])
    assert song_bars(p)[0] == EVERY and [x.state for x in song_passages(p)] == ["corrigé"]
    assert "aucune correction" in str(runner.invoke(app, ["review", "--undo"]).exception)  # --undo n'y touche pas
    # un passage compté à trois temps : trois temps égaux là où le détecteur en lit quatre
    marked_passage(p, "verse", [6.0, 8.0, 10.0, 12.0], version=2, per_bar=3)
    assert len(song_bars(p)[0]) == 61 and [len(b) for b in review.measures(*song_bars(p))][3:6] == [3, 3, 3]


def test_sections_in_a_row_play_from_their_very_start_and_the_taps_can_be_stopped(tmp_path, monkeypatch):
    from arr.commands._common import song_bars
    from arr.project import Section

    # un morceau sans ce que le détecteur entendait, dont les barres sont posées un temps trop tard
    p = gappy_song(tmp_path, monkeypatch, missing=(), late=0.5, weak=())
    (p.root / "analysis_frames.npz").unlink()
    p.set_sections([Section("intro", 0.0, 4.0), Section("intro2", 4.0, 8.0), Section("verse", 8.0, 32.0)])
    p.save()
    assert "lance arr analyze" in str(
        runner.invoke(app, ["review"]).exception
    )  # les passages douteux, eux, en ont besoin
    assert "doivent se suivre" in str(runner.invoke(app, ["review", "-s", "intro,verse"]).exception)

    # r pendant les frappes : la passe repart des quatre clics ; puis Échap : rien n'est gardé
    session = fake_taps(monkeypatch, ["redo", "escape"], [["bars"], ["quit"]], lead=2.0, start=0.0)
    out = runner.invoke(app, ["review", "-s", "intro,intro2"]).output
    assert "song · section intro,intro2" in out and "r : recommencer · Échap : abandonner" in out
    assert "barres laissées telles quelles" in out and not (p.root / "review").exists()
    # la boucle part du début de la première section, pas de sa première barre (0,5 s) ; les frappes aussi
    assert session["played"] == [(8.5, True), (12.5, False), (12.5, False), (8.5, True)]
    # la grille du moment est sous les yeux pendant les frappes
    tapping = out.split("Corriger les barres")[1]
    assert "Accords · intro" in tapping and "│ C   /   /   /   │" in tapping

    # les frappes couvrent les deux sections, depuis le tout premier temps
    taps = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    fake_taps(monkeypatch, [taps], [["bars"], ["enter"]], lead=2.0, start=0.0)
    out = runner.invoke(app, ["review", "-s", "intro,intro2"], input="v\n").output
    assert "barres corrigées" in out and [t for t in song_bars(p)[1] if t <= 10.0] == taps
    assert "correction des barres reprise" in runner.invoke(app, ["review", "--undo", "-s", "intro,intro2"]).output


def test_count_in_gives_four_clicks_before_each_turn_of_the_loop(tmp_path, monkeypatch):
    from arr import studio

    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    p = gappy_song(tmp_path, monkeypatch)
    quiet = audio.load(p.root / "source/original.flac")
    audio.save(p.root / "source/original.flac", np.zeros_like(quiet))  # seuls les clics s'entendent
    # la position du flux : pendant les clics, dans le passage, puis au second tour (la boucle reprend aux clics)
    calls["positions"] = [1.0, 3.0, 8.0 + 1.0, 8.0 + 3.0]
    out_lines = []
    real = studio.play
    monkeypatch.setattr(
        studio,
        "play",
        lambda data, loop=None, watch=None, follow=None: real(
            data, loop, lambda s: out_lines.append(s) or watch(s), follow
        ),
    )
    out = runner.invoke(app, ["review", "--count-in"]).output
    played = calls["played"][0]
    assert len(played) == 8 * audio.SR and calls["looped"][0] is played  # 2 s de clics et 6 s de passage, à chaque tour
    loud = np.flatnonzero(np.abs(played[:, 0]) > 0.1) / audio.SR
    starts = [float(loud[0])] + [float(b) for a, b in zip(loud, loud[1:], strict=False) if b - a > 0.1]
    assert starts == pytest.approx([0.0, 0.5, 1.0, 1.5], abs=1e-3)  # le 1 du passage tombe un temps après le quatrième
    assert "décompte" not in out.split("relecture")[-1]  # la dernière image : dans le passage, au second tour
    assert out_lines == [1.0, 3.0, 9.0, 11.0]
    # sans l'option, le passage joue sec
    calls["played"].clear()
    runner.invoke(app, ["review"])
    assert len(calls["played"][0]) == 6 * audio.SR


def test_the_screen_says_count_in_during_the_clicks(tmp_path, monkeypatch):
    calls = fake_studio(monkeypatch, np.zeros((10, 2), np.float32))
    gappy_song(tmp_path, monkeypatch)
    calls["positions"] = [8.0 + 1.0]  # second tour, pendant les clics
    out = runner.invoke(app, ["review", "--count-in"]).output
    assert "décompte · verse · mes. 4 à 6" in out and "0:00 / 0:06" in out


# --- corriger les accords


def editing(monkeypatch, *edits):
    """Un éditeur d'essai : chaque ouverture applique la fonction suivante au texte ; rend les textes ouverts."""
    from arr.commands import _fixes

    todo, opened = iter(edits), []

    def open_editor(path) -> bool:
        opened.append(path.read_text())
        path.write_text(next(todo)(opened[-1]))
        return True

    monkeypatch.setattr(_fixes, "open_editor", open_editor)
    return opened


def test_the_chord_text_is_one_line_per_bar_and_one_slot_per_beat():
    from arr import chordfix

    bars = [
        (0.0, 2.0, 4, [(0, 4, "A:min", 0.0, 2.0)]),
        (2.0, 3.5, 3, [(0, 2, "F:maj7", 2.0, 3.0), (2, 1, "N", 3.0, 3.5)]),
    ]
    beats = [[0.0, 0.5, 1.0, 1.5], [2.0, 2.5, 3.0]]
    text = chordfix.chord_text("intro2 · mes. 9 à 10", 9, bars)
    assert text.splitlines()[0].startswith("# intro2 · mes. 9 à 10 · une case par temps")
    assert [" ".join(line.split()) for line in text.splitlines()[3:]] == ["9 │ Am / / /", "10 │ Fmaj7 / N.C."]
    # relu tel quel : les mêmes accords, aux mêmes instants, sous leur étiquette d'origine
    assert chordfix.read_chord_text(text, 9, bars, beats) == (
        [(0.0, 2.0, "A:min"), (2.0, 3.0, "F:maj7"), (3.0, 3.5, "N")],
        [],
    )
    # ce que j'écris reste écrit comme je l'écris ; « / » en tête de mesure tient l'accord d'avant ; « | » vaut « │ »
    mine = "9 | Am / F#m7 /\n10 | / C/E Bb"
    assert chordfix.read_chord_text(mine, 9, bars, beats)[0] == [
        (0.0, 1.0, "A:min"),
        (1.0, 2.5, "F#m7"),
        (2.5, 3.0, "C/E"),
        (3.0, 3.5, "Bb"),
    ]
    # refusé, avec le numéro de la ligne : nom inconnu, cases en trop, « / » sans accord, mesure inconnue ou oubliée
    wrong = "# titre\n9 │ Hm / / /\n10 │ F / C G\n12 │ C / /\nbla"
    assert chordfix.read_chord_text(wrong, 9, bars, beats)[1] == [
        "ligne 2 : « Hm » n'est pas un nom d'accord",
        "ligne 3 : mesure 10, 4 cases pour 3 temps",
        "ligne 4 : attendu « numéro de mesure │ accords », de 9 à 10",
        "ligne 5 : attendu « numéro de mesure │ accords », de 9 à 10",
    ]
    assert chordfix.read_chord_text("9 │ / / / /\n10 │ F / /", 9, bars, beats)[1] == [
        "ligne 1 : « / » sans accord avant lui"
    ]
    assert "il manque des mesures" in chordfix.read_chord_text("9 │ Am / / /", 9, bars, beats)[1][0]
    # posés sur la transcription : mes accords dans mon passage, les siens autour, coupés à ses bords
    fix = chordfix.ChordFix(2.0, 4.0, [(2.0, 4.0, "Dm")])
    assert chordfix.lay_chords([(0.0, 3.0, "A:min"), (3.0, 5.0, "C:maj")], [fix]) == [
        (0.0, 2.0, "A:min"),
        (2.0, 4.0, "Dm"),
        (4.0, 5.0, "C:maj"),
    ]


def test_a_fixes_the_chords_in_my_editor_and_the_fix_shows_everywhere(tmp_path, monkeypatch):
    from arr.commands._screen import song_chart

    p = gappy_song(tmp_path, monkeypatch)
    before = song_chart(p)
    assert runner.invoke(app, ["chordpro"]).exit_code == 0
    cho = (p.root / "export/song.cho").read_text()
    # la mesure 5 (trois temps) : Gm, puis D7 sur son dernier temps ; les autres ne changent pas
    opened = editing(monkeypatch, lambda text: text.replace("G    /    /", "Gm   /    D7"))
    session = fake_taps(monkeypatch, [], [["chords"], ["enter"], ["quit"]], lead=0.0, start=0.0)
    out = runner.invoke(app, ["review"]).output
    assert "a : un accord est faux" in out
    assert [" ".join(line.split()) for line in opened[0].splitlines()[3:]] == [
        "4 │ F / / /",
        "5 │ G / /",
        "6 │ A / / /",
    ]
    old, new = out.split("Avant\n")[1].split("Après\n")
    assert old.startswith("│ F   /   /   /   │ G   /   /   │ A   /   /   /   │")
    assert new.startswith("│ F   /   /   /   │ Gm  /   D7  │ A   /   /   /   │")
    assert "✔ verse · mes. 4 à 6 : accords corrigés (review/v001.toml)" in out
    assert "Le fichier du prompteur est plus ancien que vos corrections : arr chordpro" in out
    assert [played for played, _ in session["played"]] == [
        6.0,
        6.0,
        6.0,
    ]  # l'écoute, la nouvelle grille, puis le passage corrigé

    # la correction se lit partout : grille, relecture, prompteur, antisèche
    chart = song_chart(p)
    fixed = {m[0]: m for m in chart}[8.0]
    assert [(c[0], c[1], c[2], c[3]) for c in fixed[3]] == [(0, 2, "Gm", 8.0), (2, 1, "D7", 9.0)]
    assert [m for m in chart if m[0] != 8.0] == [m for m in before if m[0] != 8.0]  # rien d'autre ne bouge
    assert [x.state for x in song_passages(p)] == ["corrigé"] and song_doubts(p, mine=True) == {}
    assert "│ Gm  /   D7 " in runner.invoke(app, ["play", "-s", "verse"]).output
    assert runner.invoke(app, ["chordpro"]).exit_code == 0
    after = (p.root / "export/song.cho").read_text()
    changed = [(a, b) for a, b in zip(cho.splitlines(), after.splitlines(), strict=True) if a != b]
    assert changed == [("| G . . |", "| Gm . D7 |")]  # le fichier du prompteur ne diffère que sur la mesure corrigée
    assert "Gm D7" in runner.invoke(app, ["sheet"]).output

    # elle tient après une nouvelle transcription, qui relit tout autrement
    (p.root / "score/chord.lab").write_text("0.0\t32.0\tE:min\n")
    assert [c[2] for c in {m[0]: m for m in song_chart(p)}[8.0][3]] == ["Gm", "D7"]
    assert [c[2] for c in {m[0]: m for m in song_chart(p)}[10.0][3]] == ["A:maj"]  # écrit par moi dans le passage
    assert [c[2] for c in {m[0]: m for m in song_chart(p)}[12.0][3]] == ["E:min"]

    # --undo la reprend
    out = runner.invoke(app, ["review", "--undo"]).output
    assert "correction des accords reprise : verse · 0:06,0 à 0:12,0" in out
    assert [c[2] for c in {m[0]: m for m in song_chart(p)}[8.0][3]] == ["E:min"]
    assert "aucune correction" in str(runner.invoke(app, ["review", "--undo"]).exception)


def test_a_line_arr_cannot_read_reopens_the_editor_on_my_text(tmp_path, monkeypatch):
    p = gappy_song(tmp_path, monkeypatch)
    opened = editing(
        monkeypatch,
        lambda text: text.replace(
            "G    /    /", "Hm   /    /    /"
        ),  # un nom inconnu, et quatre cases pour trois temps
        lambda text: text.replace("Hm   /    /    /", "Hm   /    /"),
        lambda text: text,  # rendu sans y toucher : abandon
        lambda text: text,  # seconde fois : rien n'a changé
    )
    fake_taps(monkeypatch, [], [["chords"], ["chords"], ["quit"]], lead=0.0, start=0.0)
    out = runner.invoke(app, ["review"]).output
    assert "ligne 5 : mesure 5, 4 cases pour 3 temps" in out and "ligne 5 : « Hm » n'est pas un nom d'accord" in out
    # l'éditeur se rouvre sur mon texte, la remarque à la fin : les numéros de ligne restent les miens
    assert "Hm   /    /    /" in opened[1] and opened[1].rstrip().endswith(
        "# ✗ ligne 5 : mesure 5, 4 cases pour 3 temps"
    )
    assert opened[2].count("# ✗") == 1 and "n'est pas un nom d'accord" in opened[2]
    assert "texte rendu tel quel : accords laissés tels quels" in out
    assert "aucun accord n'a changé" in out and not (p.root / "review").exists()
    # sans éditeur, rien ne se passe
    from arr.commands import _fixes

    monkeypatch.setattr(_fixes, "open_editor", lambda path: False)
    fake_taps(monkeypatch, [], [["chords"], ["quit"]], lead=0.0, start=0.0)
    assert "pas d'éditeur : règle $VISUAL ou $EDITOR" in runner.invoke(app, ["review"]).output


def test_bars_first_then_chords_on_the_corrected_bars(tmp_path, monkeypatch):
    from arr.commands._common import song_bars
    from arr.commands._screen import song_chart

    p = gappy_song(tmp_path, monkeypatch)
    # m : le temps manqué est rétabli ; le passage rejoue ; a s'ouvre sur les barres corrigées
    opened = editing(monkeypatch, lambda text: text.replace("G    /    /    /", "G    /    /    D7"))
    taps = [6.0, 8.0, 10.0, 12.0, 14.0]
    fake_taps(monkeypatch, [taps], [["bars"], ["enter"], ["chords"], ["enter"], ["enter"]], lead=2.0, start=6.0)
    out = runner.invoke(app, ["review"], input="t\n").output
    assert "barres corrigées (review/v001.toml)" in out and "accords corrigés (review/v002.toml)" in out
    assert "5 │ G / / /" in [" ".join(line.split()) for line in opened[0].splitlines()]
    assert "morceau vérifié" in out and len(list((p.root / "review").iterdir())) == 2  # Entrée n'ajoute pas de jugement
    fixed = {m[0]: m for m in song_chart(p)}[8.0]
    assert [(c[0], c[2], c[3]) for c in fixed[3]] == [(0, "G:maj", 8.0), (3, "D7", 9.5)]
    # --undo reprend la dernière : les accords, puis les barres
    assert "des accords reprise" in runner.invoke(app, ["review", "--undo"]).output and len(song_bars(p)[0]) == 64
    assert "des barres reprise" in runner.invoke(app, ["review", "--undo"]).output and len(song_bars(p)[0]) == 63


def test_a_bar_fix_made_later_keeps_the_chords_i_fixed():
    from arr import chordfix

    # mes accords sont gardés par instant : des barres corrigées après coup les laissent où ils sonnent
    fix = chordfix.ChordFix(8.0, 10.0, [(8.0, 9.0, "Gm"), (9.0, 10.0, "D7")])
    chords = chordfix.lay_chords([(2.0 * i, 2.0 * i + 2, "C:maj") for i in range(8)], [fix])
    assert (8.0, 9.0, "Gm") in chords and (9.0, 10.0, "D7") in chords and len(chords) == 9
