"""La grille lue : temps entendus deux fois, temps manqués, barres régulières."""

import numpy as np

from arr import audio, grid


def _grid(period: float, n: int, start: float = 0.0, per_bar: int = 4) -> tuple[list[float], list[float]]:
    """Une grille régulière, avec le léger tremblé de beat_this (±10 ms)."""
    jitter = [0.01 * ((i * 7) % 3 - 1) for i in range(n)]
    beats = [round(start + period * i + jitter[i], 3) for i in range(n)]
    return beats, beats[::per_bar]


def test_steady_bars_removes_the_20_ms_steps_and_keeps_a_short_bar():
    true = [0.33 + 1.882 * i for i in range(20)]
    stepped = [round(t / 0.02) * 0.02 for t in true]
    steady = grid.steady_bars(stepped)
    assert max(abs(a - b) for a, b in zip(steady[2:-2], true[2:-2], strict=True)) < 0.008
    # la durée d'une boucle de 8 mesures est juste, à moins de 5 ms
    assert abs((steady[12] - steady[4]) - 8 * 1.882) < 0.005

    # une mesure à deux temps n'est pas lissée : les barres d'après restent décalées d'autant
    bars = [2.0 * i for i in range(6)] + [11.0 + 2.0 * i for i in range(6)]
    assert np.allclose(grid.steady_bars(bars), bars, atol=1e-6)
    assert grid.steady_bars([1.0, 3.0]) == [1.0, 3.0]


def test_regular_bars_ignores_two_beat_flips_but_keeps_a_real_half_bar_shift():
    beats = [0.5 * i for i in range(80)]  # 4/4 régulier, deux temps de levée
    steady = [beats[i] for i in range(2, 80, 4)]
    # beat_this voit des mesures de deux temps le temps d'un refrain : 2+2 au lieu de 4
    flipped = sorted(steady + [beats[i] for i in (24, 32, 40)])
    assert grid.regular_bars(flipped, beats) == steady

    # le morceau perd vraiment deux temps à 20 s : une seule mesure courte, là
    shifted = [beats[i] for i in range(2, 40, 4)] + [beats[i] for i in range(40, 80, 4)]
    noisy = sorted(shifted + [beats[i] for i in (46, 54)])
    assert grid.regular_bars(noisy, beats) == shifted

    # sans barre détectée au début, les mesures remontent jusqu'à ne laisser qu'une levée
    late = [beats[i] for i in range(18, 80, 4)]
    assert grid.regular_bars(late, beats) == steady

    # un mètre qui change trop souvent pour qu'une longueur domine : rien ne bouge
    mixed = [beats[i] for i in (0, 3, 7, 10, 14, 17, 21, 25, 28)]
    assert grid.regular_bars(mixed, beats) == mixed


def test_clean_beats_leaves_a_grid_without_pairs_untouched():
    beats, bars = _grid(0.5, 64)
    assert grid.clean_beats(beats, bars) == (beats, bars)
    got = grid.clean_beats(beats, bars)
    assert got[0] is beats and got[1] is bars
    # une mesure à deux temps isolée est une vraie mesure : rien ne bouge
    short = bars[:4] + [b - 1.0 for b in bars[5:]]
    assert grid.clean_beats(beats, short)[1] is short
    # un passage compté au double (introduction en demi-temps), puis au simple : rien ne bouge
    halves = [1.0 * i for i in range(8)] + [8.0 + 0.5 * i for i in range(32)]
    assert grid.clean_beats(halves, halves[::4])[0] is halves
    doubled = [0.5 * i for i in range(16)] + [8.0 + 0.25 * i for i in range(16)] + [12.0 + 0.5 * i for i in range(16)]
    assert grid.clean_beats(doubled, doubled[::4])[0] is doubled


def test_clean_beats_keeps_the_second_beat_of_a_pair():
    beats, bars = _grid(0.46, 64)
    early = sorted(beats + [round(beats[20] - 0.08, 3)])
    assert grid.clean_beats(early, bars) == (beats, bars)
    # le second est gardé même quand le premier tombe plus près de la grille : beat_this l'entend plus fort
    late = round(beats[30] + 0.09, 3)
    got = grid.clean_beats(sorted(beats + [late]), bars)[0]
    assert late in got and beats[30] not in got and len(got) == len(beats)
    # une barre posée sur le temps en trop passe au temps gardé
    spurious = round(beats[24] - 0.08, 3)
    moved = sorted(bars[:6] + [spurious] + bars[7:])
    assert grid.clean_beats(sorted(beats + [spurious]), moved) == (beats, bars)


def test_clean_beats_finds_pairs_at_any_tempo_and_by_the_hundred():
    # 200 bpm : 100 ms d'écart font un tiers de période
    beats, bars = _grid(0.3, 80)
    fast = sorted(beats + [round(beats[i] - 0.1, 3) for i in (10, 41, 70)])
    assert grid.clean_beats(fast, bars) == (beats, bars)
    # un temps sur trois en double : la médiane des écarts tombe à 0,63 s pour une période de 0,70 s
    beats, bars = _grid(0.70, 300)
    crowded = sorted(beats + [round(b - 0.08, 3) for b in sorted(set(beats[1::3] + beats[200:240]))])  # tous, 40 temps
    assert float(np.median(np.diff(crowded))) < 0.65
    cleaned = grid.clean_beats(crowded, bars)
    assert cleaned == (beats, bars)
    assert grid.clean_beats(*cleaned) == cleaned  # idempotent
    assert round(60 / audio.period(cleaned[0])) == 86


def test_clean_beats_puts_the_bars_back_on_the_one():
    """Un temps en trop avance toutes les barres d'un temps ; retiré, elles retombent sur le « un »."""
    beats, bars = _grid(0.5, 120)
    noisy = sorted(beats + [round(beats[i] - 0.08, 3) for i in (41, 77, 78, 101)])
    assert grid.regular_bars(bars, noisy) != bars
    assert grid.regular_bars(*reversed(grid.clean_beats(noisy, bars))) == bars


def holed(period: float = 0.5, count: int = 40, missing: tuple = (17,)) -> tuple[list[float], np.ndarray]:
    """Une grille régulière où beat_this a manqué des temps, et ses activations : 1 sur un temps posé, 0 ailleurs."""
    beats = [round(period * i, 3) for i in range(count) if i not in missing]
    heard = np.zeros(int(count * period * 50) + 1)
    heard[[int(round(t * 50)) for t in beats]] = 1.0
    return beats, heard


def test_fill_beats_counts_a_missed_beat_that_left_a_trace():
    beats, heard = holed()
    assert grid.fill_beats(beats, heard) is beats  # rien ne s'entend dans le trou : il reste
    heard[int(8.5 * 50) + 1] = 0.39  # la trace du temps manqué, 20 ms après le milieu
    assert grid.fill_beats(beats, heard) == sorted(beats + [8.52])
    heard[int(8.5 * 50) + 1] = 0.15  # trop faible pour compter
    assert grid.fill_beats(beats, heard) is beats
    heard[int(8.5 * 50) + 6] = 0.9  # forte, mais à 120 ms du milieu : ce n'est pas le temps attendu
    assert grid.fill_beats(beats, heard) is beats
    assert grid.fill_beats(beats, None) is beats and grid.fill_beats(beats[:3], heard) == beats[:3]


def test_fill_beats_leaves_half_time_passages_and_double_holes():
    # un passage compté à moitié : chaque écart y vaut la période locale, même avec une trace à mi-chemin
    beats = [0.5 * i for i in range(16)] + [8.0 + 1.0 * i for i in range(12)] + [20.0 + 0.5 * i for i in range(16)]
    heard = np.full(int(28 * 50) + 1, 0.45)
    assert grid.fill_beats(beats, heard) is beats
    # deux trous qui se suivent : aucun n'est isolé
    beats, heard = holed(missing=(17, 19))
    heard[[int(8.5 * 50), int(9.5 * 50)]] = 0.45
    assert grid.fill_beats(beats, heard) is beats


def test_fill_beats_fills_the_last_gap_and_comes_after_the_beats_heard_twice():
    beats, heard = holed(missing=(38,))
    heard[int(19.0 * 50)] = 0.47
    assert grid.fill_beats(beats, heard)[-3:] == [18.5, 19.0, 19.5]
    # un temps entendu deux fois collé au trou : ni l'un ni l'autre n'est sûr, rien ne bouge
    beats, heard = holed()
    heard[int(8.5 * 50)] = 0.4
    twice = sorted(beats + [7.92])
    cleaned, _ = grid.clean_beats(twice, beats[::4])
    assert cleaned is twice and grid.fill_beats(twice, heard) is twice
    # à une mesure de là, le doublon est retiré d'abord et le trou comblé ensuite
    apart = sorted(beats + [5.92])
    cleaned, _ = grid.clean_beats(apart, beats[::4])
    assert grid.fill_beats(cleaned, heard) == sorted(beats + [8.5])
