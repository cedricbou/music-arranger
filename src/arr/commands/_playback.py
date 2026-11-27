"""La lecture pilotée au clavier, commune à `play` et à `review` : touches, arrêts sur les mesures, écran en direct."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import Optional

KEYS = {
    b" ": "pause",
    b"D": "back",
    b"C": "forward",
    b"d": "doubt",
    b"\n": "enter",
    b"\r": "enter",
    b"q": "quit",
    b"m": "bars",
    b"r": "redo",
    b"\x1b": "escape",
}
STEP = 5.0  # secondes entre deux arrêts quand le morceau n'a pas de mesures connues


def parse_keys(data: bytes) -> list[str]:
    """Les touches reconnues dans ce que le terminal a envoyé : espace, flèches gauche et droite, Entrée, Échap, d, q, m, r."""
    found = re.findall(rb"\x1b[\[O].|\x1b|[ dqmr\r\n]", data)  # une séquence de flèche entière, sinon Échap seul
    return [KEYS[k[-1:]] for k in found if k[-1:] in KEYS]


@contextmanager
def keyboard(tap=None):
    """Le temps de la lecture, lit les touches sans attendre Entrée ; donne une fonction qui rend celles tapées.

    Avec `tap`, Espace ne pilote plus la lecture : un fil appelle `tap(heure)` à chaque
    Espace, l'heure (`time.monotonic`) lue dès que la touche arrive, là où l'écran ne passe
    que vingt fois par seconde ; la fonction donnée rend les autres touches.
    Hors d'un terminal (tests, sortie redirigée), aucune touche n'est lue.
    """
    import select
    import sys

    if not sys.stdin.isatty():
        yield lambda: []
        return
    import termios
    import threading
    import time
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setcbreak(fd)  # Ctrl+C reste un signal : il arrête toujours la lecture
    done = threading.Event()

    def pressed() -> list[str]:
        data = b""
        while select.select([fd], [], [], 0)[0]:
            data += os.read(fd, 64)
        return parse_keys(data)

    others: list[str] = []

    def listen() -> None:
        while not done.is_set():
            if select.select([fd], [], [], 0.05)[0]:
                at = time.monotonic()
                for key in parse_keys(os.read(fd, 64)):
                    tap(at) if key == "pause" else others.append(key)

    def beside() -> list[str]:
        """Les touches autres qu'Espace reçues par le fil depuis le dernier appel."""
        return [others.pop(0) for _ in range(len(others))]

    thread = threading.Thread(target=listen, daemon=True) if tap else None
    try:
        if thread:
            thread.start()
        yield beside if tap else pressed
    finally:
        done.set()
        if thread:
            thread.join()
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def bar_stops(starts: list[float], ranges: list[tuple[float, float]], length: float) -> list[float]:
    """Où mènent ← et → : les débuts de mesure, en secondes de lecture, et le début de chaque section jouée.

    `starts` sont les débuts de mesure dans le morceau ; sans eux, un arrêt toutes les `STEP` secondes.
    """
    starts = starts or [STEP * i for i in range(int(length / STEP) + 1)]
    stops, t = [], 0.0
    for start, end in ranges or [(0.0, length)]:
        stops += [t] + [t + b - start for b in starts if start < b < end]
        t += end - start
    # Une barre de mesure à quelques centièmes d'un début de section n'est pas un arrêt de plus.
    return [s for i, s in enumerate(stops) if s < length and (i == 0 or s - stops[i - 1] > 0.2)]


def next_after(stops: list[float], t: float, loop: bool = False) -> Optional[float]:
    """Le premier arrêt après `t` ; après le dernier : None, ou le premier si la lecture est en boucle."""
    ahead = [s for s in stops if s > t + 0.05]
    return ahead[0] if ahead else stops[0] if loop and stops else None


def neighbour(stops: list[float], t: float, step: int, loop: bool = False) -> Optional[float]:
    """Le début de la mesure d'avant (`step` -1) ou d'après (+1) celle où l'on est.

    Après la dernière : None, ou la première si la lecture est en boucle.
    """
    here = max((i for i, s in enumerate(stops) if s <= t + 0.05), default=0)
    if loop and here + step >= len(stops):
        return stops[0]
    return stops[max(here + step, 0)] if here + step < len(stops) else None


def playing(data, loop, screen, steer, tap=None, follow=None, transient: bool = False) -> None:
    """Joue `data`, puis `loop` sans fin s'il est donné, l'écran `screen(secondes)` tenu à jour.

    `steer(touches, secondes)` reçoit vingt fois par seconde les touches tapées et la position du
    flux ; il rend `(en pause, position où sauter ou None)`, suivi de True pour arrêter la lecture.
    `tap` et `follow` : voir `keyboard` et `studio.play`. `transient` : l'écran s'efface à la fin.
    """
    from arr import studio
    from arr.commands._screen import live

    with live(screen, transient) as shown, keyboard(tap) if tap else keyboard() as pressed:

        def watch(seconds: float):
            order = steer(pressed(), seconds)
            shown.update(screen(seconds if order[1] is None else order[1]))
            return order

        studio.play(data, loop=loop, watch=watch, follow=follow)
