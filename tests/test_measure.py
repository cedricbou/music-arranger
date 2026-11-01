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
