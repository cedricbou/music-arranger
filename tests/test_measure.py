"""measure.py : les chiffres qui remplacent l'écoute."""

import numpy as np

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
