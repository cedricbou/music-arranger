"""MIDI en direct : piloter les pédales de scène par la sortie MIDI de la carte son.

Installation visée : l'ordinateur joue sur une PreSonus AudioBox iTwo, dont la sortie MIDI
va à l'entrée MIDI d'un multi-effets (un Boss GT-6B pour la basse). La pédale change de son
sur un changement de programme ; ses pédales d'expression et ses assignations répondent à
des contrôleurs (CC).

Tout passe par le séquenceur ALSA, en sous-processus (`alsa-utils`) : `aplaymidi` pour
envoyer, `aseqdump` pour écouter. `aseqsend` dit envoyer mais n'atteint pas la carte, d'où
le fichier MIDI minimal que `send()` fabrique pour `aplaymidi` (fiche 011). Rien n'est
jamais écrit dans la pédale : ni SysEx, ni sauvegarde, ni restauration de patches.

Le transport d'une lecture (horloge, Start, position, Stop) part autrement : un top toutes les
vingt millisecondes, qui s'arrête et saute avec la lecture, demande un port tenu ouvert. C'est
un port virtuel « arr:transport » ouvert par `python-rtmidi`, qu'un prompteur de scène sur le
même ordinateur écoute sans réglage (fiche 014).

Réglages dans ~/.config/arr/audio.toml (tous facultatifs) :

    [midi]
    port = ""        # fragment du nom du port, ou son adresse ; "" = le premier port matériel
    channel = 1      # canal des messages envoyés
"""

from __future__ import annotations

import re
import struct
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

from arr import studio
from arr.project import ProjectError

# Ports qui existent sur toute machine sans mener à un instrument : jamais choisis par défaut,
# mais utilisables si on les nomme (« Midi Through » sert de bouclage pour les tests).
VIRTUAL = ("System ", "Midi Through", "PipeWire")
CHANNELS = 16
VALUES = 128  # un octet de données MIDI : 0 à 127


def settings() -> dict:
    """Réglages de la section [midi] d'audio.toml, complétés par leurs défauts."""
    return {"port": "", "channel": 1, **studio.user_settings().get("midi", {})}


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True, **kwargs)
    except FileNotFoundError:
        raise ProjectError(f"{args[0]} est absent : installe alsa-utils (pacman -S alsa-utils)")
    except subprocess.CalledProcessError as e:
        raise ProjectError(f"{args[0]} a échoué : {(e.stderr or e.stdout or '').strip()}")


def ports() -> list[tuple[str, str]]:
    """Ports du séquenceur ALSA où l'on peut envoyer : (adresse « 20:0 », nom)."""
    listing = _run(["aplaymidi", "-l"]).stdout
    found = []
    for line in listing.splitlines():
        if match := re.match(r"\s*(\d+:\d+)\s+(.+?)\s{2,}(.+?)\s*$", line):
            address, client, name = match.groups()
            found.append((address, name if name.startswith(client) else f"{client} {name}"))
    return found


def find_port(fragment: str = "") -> tuple[str, str]:
    """Adresse et nom du port à utiliser : celui dont le nom ou l'adresse correspond.

    Sans fragment, le premier port matériel (ni System, ni Midi Through, ni PipeWire).
    """
    known = ports()
    if fragment:
        for address, name in known:
            if address == fragment or fragment.lower() in name.lower():
                return address, name
        raise ProjectError(f"port MIDI introuvable : « {fragment} » (arr midi ports)")
    for address, name in known:
        if not name.startswith(VIRTUAL):
            return address, name
    raise ProjectError(
        "aucun port MIDI matériel : branche l'interface, ou nomme le port dans audio.toml (arr midi ports)"
    )


def _byte(value: int, limit: int, what: str) -> int:
    if not 0 <= value < limit:
        raise ProjectError(f"{what} hors plage : {value} (de 0 à {limit - 1})")
    return value


def _status(kind: int, channel: int) -> int:
    return kind | _byte(channel - 1, CHANNELS, "canal MIDI")


def program_change(program: int, channel: int = 1) -> bytes:
    """Changement de programme, numéroté de 1 à 128 comme l'affichent les pédales."""
    return bytes([_status(0xC0, channel), _byte(program - 1, VALUES, "numéro de programme")])


def control_change(controller: int, value: int, channel: int = 1) -> bytes:
    """Contrôleur (CC) et sa valeur, de 0 à 127 tous les deux."""
    return bytes(
        [_status(0xB0, channel), _byte(controller, VALUES, "numéro de contrôleur"), _byte(value, VALUES, "valeur")]
    )


def bank_select(bank: int, channel: int = 1) -> bytes:
    """Sélection de banque, numérotée à partir de 1 : les contrôleurs 0 (MSB) et 32 (LSB).

    Une pédale qui ignore la banque ne retient que le changement de programme qui suit.
    """
    index = _byte(bank - 1, VALUES * VALUES, "numéro de banque")
    return control_change(0, index // VALUES, channel) + control_change(32, index % VALUES, channel)


# Longueur de chaque message, par type de statut ; le reste part en un seul bloc.
LENGTHS = {0x80: 3, 0x90: 3, 0xA0: 3, 0xB0: 3, 0xC0: 2, 0xD0: 2, 0xE0: 3}
# Le transport : sans canal, chacun a son octet de statut.
CLOCK, START, CONTINUE, STOP, POSITION = 0xF8, 0xFA, 0xFB, 0xFC, 0xF2
TRANSPORT = {CLOCK: "horloge", START: "Start", CONTINUE: "Continue", STOP: "Stop"}
SYSTEM = {POSITION: 3, **dict.fromkeys(TRANSPORT, 1)}


def song_position(sixteenths: int) -> bytes:
    """Song Position Pointer : la position en doubles-croches depuis le début du morceau."""
    value = _byte(sixteenths, VALUES * VALUES, "position")
    return bytes([POSITION, value % VALUES, value // VALUES])


def split(data: bytes) -> list[bytes]:
    """Découpe une suite d'octets en messages MIDI."""
    found, i = [], 0
    while i < len(data):
        size = SYSTEM.get(data[i]) or LENGTHS.get(data[i] & 0xF0, len(data) - i)
        found.append(data[i : i + size])
        i += size
    return found


def describe(data: bytes) -> list[tuple[str, bytes]]:
    """Les messages d'une suite d'octets, chacun avec sa description en clair."""
    said = []
    for message in split(data):
        kind, channel = message[0] & 0xF0, (message[0] & 0x0F) + 1
        if kind == 0xC0 and len(message) == 2:
            said.append((f"changement de programme {message[1] + 1}, canal {channel}", message))
        elif kind == 0xB0 and len(message) == 3:
            said.append((f"contrôleur {message[1]} = {message[2]}, canal {channel}", message))
        elif message[0] in TRANSPORT:
            said.append((TRANSPORT[message[0]], message))
        elif message[0] == POSITION and len(message) == 3:
            said.append((f"position {message[1] + VALUES * message[2]} (doubles-croches)", message))
        else:
            said.append((f"message {hexa(message)}", message))
    return said


def hexa(data: bytes) -> str:
    """Les octets d'un message, comme les écrivent les manuels : « C0 04 »."""
    return " ".join(f"{b:02X}" for b in data)


def smf(messages: list[bytes]) -> bytes:
    """Un fichier MIDI standard minimal : les messages au temps zéro, dans l'ordre donné."""
    track = b"".join(b"\x00" + m for m in messages) + b"\x00\xff\x2f\x00"  # deltas nuls, puis fin de piste
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, 96) + b"MTrk" + struct.pack(">I", len(track)) + track


def send(data: bytes, port: str = "") -> tuple[str, str]:
    """Envoie des octets MIDI bruts, et renvoie l'adresse et le nom du port utilisé.

    `aplaymidi` ne joue qu'un fichier, d'où le fichier temporaire ; `-d 0` supprime les deux
    secondes d'attente qu'il ajoute après la fin.
    """
    address, name = find_port(port)
    with tempfile.TemporaryDirectory() as folder:
        song = Path(folder) / "message.mid"
        song.write_bytes(smf(split(data)))
        _run(["aplaymidi", "-d", "0", "-p", address, str(song)])
    return address, name


def events(port: str = "", seconds: float | None = None) -> Iterator[str]:
    """Messages reçus sur un port, tels que les décrit `aseqdump`, un par ligne.

    S'arrête après `seconds`, sinon quand le flux se ferme (Ctrl+C, ou générateur abandonné).
    """
    import threading

    address, _ = find_port(port)
    try:
        proc = subprocess.Popen(["aseqdump", "-p", address], stdout=subprocess.PIPE, text=True)
    except FileNotFoundError:
        raise ProjectError("aseqdump est absent : installe alsa-utils (pacman -S alsa-utils)")
    deadline = threading.Timer(seconds, proc.terminate) if seconds else None
    if deadline:
        deadline.start()
    try:
        for line in proc.stdout:
            if re.match(r"\s*\d+:\d+\s", line):  # les deux premières lignes sont un en-tête
                yield line.strip()
    finally:
        if deadline:
            deadline.cancel()
        proc.terminate()
        proc.wait()


# --- le transport d'une lecture : l'horloge et la position, que suit un prompteur de scène

PULSES = 24  # tops d'horloge par noire
CLIENT, PORT = "arr", "transport"  # le port virtuel, tel que le séquenceur ALSA le nomme
EDGE = 1e-3  # un top à moins d'une milliseconde du début d'une plage en fait partie
JUMP = 0.02  # écart entre la position annoncée et la position attendue au-delà duquel la lecture a sauté
IDLE = 0.005  # attente du fil d'envoi quand rien n'est dû


def clock_plan(
    bars: list[tuple[float, float, int]], ranges: list[tuple[float, float]], since: float = 0.0
) -> list[tuple[float, int | None]]:
    """Les tops d'horloge d'une lecture : (instant dans le morceau joué, numéro du top depuis la mesure 1).

    `bars` : début, fin et nombre de temps de chaque mesure, la première étant la mesure 1 ;
    `ranges` : les plages jouées, en secondes de l'original, dans l'ordre ; `since` : l'instant de
    lecture, négatif pendant le décompte, où l'horloge commence. Chaque mesure reçoit 24 tops par
    temps, répartis également : l'horloge suit le tempo de l'enregistrement. Avant la mesure 1
    (levée, intro, décompte), les tops gardent la période de leurs voisins et n'ont pas de numéro :
    ils ne donnent que le tempo.
    """
    song, pulse = [], 0
    for start, end, beats in bars:
        count = PULSES * beats
        song += [(start + (end - start) * k / count, pulse + k) for k in range(count)]
        pulse += count
    if len(song) < 2:
        return []
    first, period = song[0][0], song[1][0] - song[0][0]
    plan: list[tuple[float, int | None]] = []
    offset = 0.0
    for lo, hi in ranges:
        before = int((first - lo) / period + EDGE) if lo < first else 0
        ticks = [(first - k * period, None) for k in range(before, 0, -1)]
        ticks += [(t, n) for t, n in song if lo - EDGE <= t < hi - EDGE]
        plan += [(offset + t - lo, n) for t, n in ticks]
        offset += hi - lo
    if len(plan) > 1:
        start, step = plan[0][0], plan[1][0] - plan[0][0]
        lead = int((start - since) / step + EDGE)
        plan = [(start - k * step, None) for k in range(lead, 0, -1)] + plan
    return plan


def messages(last: int | None, pulse: int | None, running: bool) -> tuple[bytes, bool]:
    """Ce qui part pour un top, d'après le précédent : les octets, et si le morceau tourne ensuite.

    Le premier top de la mesure 1 est précédé de Start ; un autre premier top, de sa position et
    de Continue ; un top qui ne suit pas le précédent (saut, tour de boucle, section suivante), de
    sa position. Un top sans numéro (avant la mesure 1) arrête le morceau s'il tournait.
    """
    tick = bytes([CLOCK])
    if pulse is None:
        return (bytes([STOP]) if running else b"") + tick, False
    where = song_position(min(pulse // (PULSES // 4), VALUES * VALUES - 1))
    if not running:
        return (bytes([START]) if pulse == 0 else where + bytes([CONTINUE])) + tick, True
    return (where if last != pulse - 1 else b"") + tick, True


def open_port():
    """Le port virtuel « arr:transport » du séquenceur ALSA, que les logiciels de scène écoutent sans réglage."""
    import rtmidi

    try:
        out = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA, name=CLIENT)
        out.open_virtual_port(PORT)
    except rtmidi.RtMidiError as e:
        raise ProjectError(f"impossible d'ouvrir le port MIDI {CLIENT}:{PORT} : {e} (le séquenceur ALSA est-il là ?)")
    return out


class Transport:
    """Le transport MIDI d'une lecture : l'horloge, Start, la position et Stop, à l'heure du son.

    Le flux audio dit à chaque bloc où en est la lecture et à quelle heure ce bloc sortira
    (`heard`) ; un fil envoie chaque top du plan à l'heure où son instant sortira. Un écart entre
    la position annoncée et celle attendue est un saut : le plan reprend à la nouvelle position.
    """

    def __init__(self, plan: list[tuple[float, int | None]], where, port=None, clock=None):
        import time

        self.times, self.pulses = [t for t, _ in plan], [n for _, n in plan]
        self.where = where  # position du flux, en secondes → instant dans le morceau joué
        self.port, self.clock = port, clock or time.monotonic
        self.anchor: tuple[float, float] | None = None  # (instant joué, heure où il sort)
        self.paused, self.moved = False, True
        self.next, self.last, self.running = 0, None, False

    def heard(self, seconds: float, at: float, paused: bool) -> None:
        """Appelé par le flux : la position `seconds` sortira à l'heure `at` (horloge monotone)."""
        played = self.where(seconds)
        if self.anchor is not None:
            expected = self.anchor[0] + at - self.anchor[1]
            self.moved = self.moved or abs(played - expected) > JUMP
        self.anchor, self.paused = (played, at), paused

    def step(self, now: float) -> float:
        """Envoie ce qui est dû à l'heure `now` ; rend combien de secondes attendre avant de revenir."""
        from bisect import bisect_left

        if self.anchor is None:
            return IDLE
        if self.paused:
            if self.running:
                self.send(bytes([STOP]))
                self.running = False
            return IDLE
        played, at = self.anchor
        if self.moved:
            self.moved = False
            self.next = bisect_left(self.times, played + now - at - IDLE)
        if self.next >= len(self.times):
            return IDLE
        due = at + self.times[self.next] - played
        if due - now > EDGE:
            return min(due - now, IDLE)
        pulse = self.pulses[self.next]
        data, self.running = messages(self.last, pulse, self.running)
        self.last, self.next = pulse, self.next + 1
        self.send(data)
        return 0.0

    def send(self, data: bytes) -> None:
        for message in split(data):
            self.port.send_message(list(message))

    def __enter__(self):
        import threading

        self.port = self.port or open_port()
        self.done = threading.Event()

        def run():
            while not self.done.is_set():
                if wait := self.step(self.clock()):
                    self.done.wait(wait)

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.done.set()
        self.thread.join()
        if self.running:
            self.send(bytes([STOP]))
        self.port.close_port()
