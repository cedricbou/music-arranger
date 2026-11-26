"""arr review : les passages à relire, les réponses du musicien, et ce qu'elles deviennent après une nouvelle analyse."""

from contextlib import contextmanager

import numpy as np

from arr import audio, review
from arr.cli import app
from arr.commands import _playback as playback
from arr.commands._common import save_analysis, song_doubts, song_passages
from tests.helpers import WEAK, doubtful_song, fake_studio, runner

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
