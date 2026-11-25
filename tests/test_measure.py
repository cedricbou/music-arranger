"""measure.py : les chiffres qui remplacent l'écoute."""

import numpy as np
import pytest

from arr import audio, measure
from tests.helpers import tone


def test_period_ignores_a_missed_beat():
    beats = [0.5 * i for i in range(40)]
    del beats[17]  # un temps manqué fausserait une régression
    assert abs(measure.period(beats) - 0.5) < 1e-9


def test_beat_fit_recovers_speed_and_offset():
    reference = [1.0 + 0.5 * i for i in range(60)]
    faster_and_late = [(t + 0.12) * 0.99 for t in reference]  # 1 % plus rapide, 120 ms de retard
    fit = measure.beat_fit(faster_and_late, reference)
    assert abs(fit["speed"] - 0.99) < 1e-6 and abs(fit["offset"] - 0.12) < 1e-6 and fit["on_beat"] == 1.0

    # la seconde moitié glisse de 200 ms : aucun ajustement linéaire ne la rattrape
    drifting = [t + (0.2 if i >= 30 else 0.0) for i, t in enumerate(reference)]
    assert measure.beat_fit(drifting, reference)["on_beat"] <= 0.5


def test_delay_finds_the_shift_between_two_recordings():
    rng = np.random.default_rng(0)
    noise = (0.2 * rng.standard_normal((audio.SR, 2))).astype(np.float32)
    assert abs(measure.delay(noise, audio.shift(noise, 0.068)) - 0.068) < 1 / audio.SR
    assert measure.delay(noise, noise) == 0.0


def test_level_and_shares():
    peak, rms = measure.level(tone(440, 1.0, amp=0.5))
    assert abs(peak - -6.02) < 0.05 and abs(rms - -9.03) < 0.05
    assert measure.level(np.zeros((100, 2), np.float32)) == (-120.0, -120.0)

    shares = measure.shares(
        {"drums": tone(110, 1.0, amp=0.3), "guitar": tone(330, 1.0, amp=0.1), "none": tone(1, 1.0, amp=0.0)}
    )
    assert abs(shares["drums"] - 0.9) < 0.01 and abs(shares["guitar"] - 0.1) < 0.01 and shares["none"] == 0.0


def test_chords_are_seated_back_on_the_reference_bars():
    """Une transcription qui n'a pas vu une mesure à deux temps pose ses accords une demi-mesure à côté."""
    from tests.helpers import short_bar_song

    song, beats, bars, truth = short_bar_song()
    own_bars = [2.0 * i for i in range(12)]  # la transcription compte quatre temps partout
    starts = lambda chords: [start for start, _, _ in chords]
    labels = lambda chords: [label for _, _, label in chords]

    # ses accords d'après la mesure courte arrivent une demi-mesure trop tard
    late = [(s + 1.0, e + 1.0, label) if s >= 9.0 else (s, e, label) for s, e, label in truth]
    seated = measure.seat_chords(late, own_bars, bars, beats, lambda: song)
    assert labels(seated) == labels(truth) and starts(seated) == pytest.approx(starts(truth), abs=0.01)
    # ni trou ni chevauchement : chaque accord est tenu jusqu'au suivant
    assert [end for _, end, _ in seated[:-1]] == pytest.approx(starts(seated)[1:])

    # ou une demi-mesure trop tôt : l'accord de la mesure courte n'a alors pas été vu du tout
    early = [(s - 1.0, e - 1.0, label) if s >= 9.0 else (s, e, label) for s, e, label in truth if s != 8.0]
    seated = measure.seat_chords(early, own_bars, bars, beats, lambda: song)
    assert labels(seated) == labels(early)
    assert starts(seated)[5:] == pytest.approx(starts(truth)[6:], abs=0.01) and seated[4][0] == 8.0


def test_chords_stay_put_when_the_grids_agree():
    def never():
        raise AssertionError("l'audio n'a pas à être lu quand les deux grilles comptent pareil")

    chords = [(2.0 * i + 0.03, 2.0 * i + 2.03, "C:maj") for i in range(6)]
    bars = [2.0 * i for i in range(6)]
    assert measure.seat_chords(chords, [b + 0.03 for b in bars], bars, [0.5 * i for i in range(24)], never) == chords


def test_steady_bars_removes_the_20_ms_steps_and_keeps_a_short_bar():
    true = [0.33 + 1.882 * i for i in range(20)]
    stepped = [round(t / 0.02) * 0.02 for t in true]
    steady = measure.steady_bars(stepped)
    assert max(abs(a - b) for a, b in zip(steady[2:-2], true[2:-2], strict=True)) < 0.008
    # la durée d'une boucle de 8 mesures est juste, à moins de 5 ms
    assert abs((steady[12] - steady[4]) - 8 * 1.882) < 0.005

    # une mesure à deux temps n'est pas lissée : les barres d'après restent décalées d'autant
    bars = [2.0 * i for i in range(6)] + [11.0 + 2.0 * i for i in range(6)]
    assert np.allclose(measure.steady_bars(bars), bars, atol=1e-6)
    assert measure.steady_bars([1.0, 3.0]) == [1.0, 3.0]


def test_regular_bars_ignores_two_beat_flips_but_keeps_a_real_half_bar_shift():
    beats = [0.5 * i for i in range(80)]  # 4/4 régulier, deux temps de levée
    steady = [beats[i] for i in range(2, 80, 4)]
    # beat_this voit des mesures de deux temps le temps d'un refrain : 2+2 au lieu de 4
    flipped = sorted(steady + [beats[i] for i in (24, 32, 40)])
    assert measure.regular_bars(flipped, beats) == steady

    # le morceau perd vraiment deux temps à 20 s : une seule mesure courte, là
    shifted = [beats[i] for i in range(2, 40, 4)] + [beats[i] for i in range(40, 80, 4)]
    noisy = sorted(shifted + [beats[i] for i in (46, 54)])
    assert measure.regular_bars(noisy, beats) == shifted

    # sans barre détectée au début, les mesures remontent jusqu'à ne laisser qu'une levée
    late = [beats[i] for i in range(18, 80, 4)]
    assert measure.regular_bars(late, beats) == steady

    # un mètre qui change trop souvent pour qu'une longueur domine : rien ne bouge
    mixed = [beats[i] for i in (0, 3, 7, 10, 14, 17, 21, 25, 28)]
    assert measure.regular_bars(mixed, beats) == mixed


def test_snap_sections_puts_boundaries_on_bars_but_not_the_ends_of_the_song():
    bars = [0.5 + 2.0 * i for i in range(10)]
    sections = [
        ("intro", 0.0, 4.2),
        ("verse", 4.2, 8.7),
        ("blip", 8.7, 9.0),
        ("chorus", 9.0, 19.5),
        ("outro", 19.5, 25.0),
    ]
    snapped = measure.snap_sections(sections, bars)
    assert snapped == [("intro", 0.0, 4.5), ("verse", 4.5, 8.5), ("chorus", 8.5, 18.5), ("outro", 18.5, 25.0)]
    assert measure.snap_sections(snapped, bars) == snapped  # sans effet la deuxième fois
    assert measure.snap_sections(sections, []) == sections
    # avant la première barre, aucune n'est proche : la borne reste
    assert measure.snap_sections([("a", 0.0, 0.2), ("b", 0.2, 30.0)], [5.0 + 2.0 * i for i in range(9)])[0][2] == 0.2


def _grid(period: float, n: int, start: float = 0.0, per_bar: int = 4) -> tuple[list[float], list[float]]:
    """Une grille régulière, avec le léger tremblé de beat_this (±10 ms)."""
    jitter = [0.01 * ((i * 7) % 3 - 1) for i in range(n)]
    beats = [round(start + period * i + jitter[i], 3) for i in range(n)]
    return beats, beats[::per_bar]


def test_clean_beats_leaves_a_grid_without_pairs_untouched():
    beats, bars = _grid(0.5, 64)
    assert measure.clean_beats(beats, bars) == (beats, bars)
    got = measure.clean_beats(beats, bars)
    assert got[0] is beats and got[1] is bars
    # une mesure à deux temps isolée est une vraie mesure : rien ne bouge
    short = bars[:4] + [b - 1.0 for b in bars[5:]]
    assert measure.clean_beats(beats, short)[1] is short
    # un passage compté au double (introduction en demi-temps), puis au simple : rien ne bouge
    halves = [1.0 * i for i in range(8)] + [8.0 + 0.5 * i for i in range(32)]
    assert measure.clean_beats(halves, halves[::4])[0] is halves
    doubled = [0.5 * i for i in range(16)] + [8.0 + 0.25 * i for i in range(16)] + [12.0 + 0.5 * i for i in range(16)]
    assert measure.clean_beats(doubled, doubled[::4])[0] is doubled


def test_clean_beats_keeps_the_second_beat_of_a_pair():
    beats, bars = _grid(0.46, 64)
    early = sorted(beats + [round(beats[20] - 0.08, 3)])
    assert measure.clean_beats(early, bars) == (beats, bars)
    # le second est gardé même quand le premier tombe plus près de la grille : beat_this l'entend plus fort
    late = round(beats[30] + 0.09, 3)
    got = measure.clean_beats(sorted(beats + [late]), bars)[0]
    assert late in got and beats[30] not in got and len(got) == len(beats)
    # une barre posée sur le temps en trop passe au temps gardé
    spurious = round(beats[24] - 0.08, 3)
    moved = sorted(bars[:6] + [spurious] + bars[7:])
    assert measure.clean_beats(sorted(beats + [spurious]), moved) == (beats, bars)


def test_clean_beats_finds_pairs_at_any_tempo_and_by_the_hundred():
    # 200 bpm : 100 ms d'écart font un tiers de période
    beats, bars = _grid(0.3, 80)
    fast = sorted(beats + [round(beats[i] - 0.1, 3) for i in (10, 41, 70)])
    assert measure.clean_beats(fast, bars) == (beats, bars)
    # un temps sur trois en double : la médiane des écarts tombe à 0,63 s pour une période de 0,70 s
    beats, bars = _grid(0.70, 300)
    crowded = sorted(beats + [round(b - 0.08, 3) for b in sorted(set(beats[1::3] + beats[200:240]))])  # tous, 40 temps
    assert float(np.median(np.diff(crowded))) < 0.65
    cleaned = measure.clean_beats(crowded, bars)
    assert cleaned == (beats, bars)
    assert measure.clean_beats(*cleaned) == cleaned  # idempotent
    assert round(60 / audio.period(cleaned[0])) == 86


def test_clean_beats_puts_the_bars_back_on_the_one():
    """Un temps en trop avance toutes les barres d'un temps ; retiré, elles retombent sur le « un »."""
    beats, bars = _grid(0.5, 120)
    noisy = sorted(beats + [round(beats[i] - 0.08, 3) for i in (41, 77, 78, 101)])
    assert measure.regular_bars(bars, noisy) != bars
    assert measure.regular_bars(*reversed(measure.clean_beats(noisy, bars))) == bars
