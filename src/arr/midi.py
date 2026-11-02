"""MIDI en direct : piloter les pédales de scène par la sortie MIDI de la carte son.

Installation visée : l'ordinateur joue sur une PreSonus AudioBox iTwo, dont la sortie MIDI
va à l'entrée MIDI d'un multi-effets (un Boss GT-6B pour la basse). La pédale change de son
sur un changement de programme ; ses pédales d'expression et ses assignations répondent à
des contrôleurs (CC).

Tout passe par le séquenceur ALSA, en sous-processus (`alsa-utils`) : `aseqsend` pour
envoyer, `aseqdump` pour écouter. Rien n'est jamais écrit dans la pédale : ni SysEx, ni
sauvegarde, ni restauration de patches.

Réglages dans ~/.config/arr/audio.toml (tous facultatifs) :

    [midi]
    port = ""        # fragment du nom du port, ou son adresse ; "" = le premier port matériel
    channel = 1      # canal des messages envoyés
"""

from __future__ import annotations

import re
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
    """Ports du séquenceur ALSA : (adresse « 20:0 », nom)."""
    listing = _run(["aseqsend", "-l"]).stdout
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


def describe(data: bytes) -> list[tuple[str, bytes]]:
    """Découpe une suite d'octets en messages, chacun avec sa description en clair."""
    said, i = [], 0
    while i < len(data):
        kind, channel = data[i] & 0xF0, (data[i] & 0x0F) + 1
        if kind == 0xC0:
            said.append((f"changement de programme {data[i + 1] + 1}, canal {channel}", data[i : i + 2]))
            i += 2
        elif kind == 0xB0:
            said.append((f"contrôleur {data[i + 1]} = {data[i + 2]}, canal {channel}", data[i : i + 3]))
            i += 3
        else:
            said.append((f"message {data[i]:02X}", data[i:]))
            break
    return said


def hexa(data: bytes) -> str:
    """Les octets d'un message, comme les écrivent les manuels : « C0 04 »."""
    return " ".join(f"{b:02X}" for b in data)


def send(data: bytes, port: str = "") -> tuple[str, str]:
    """Envoie des octets MIDI bruts, et renvoie l'adresse et le nom du port utilisé."""
    address, name = find_port(port)
    with tempfile.TemporaryDirectory() as folder:
        message = Path(folder) / "message.mid"  # aseqsend n'envoie que le contenu d'un fichier
        message.write_bytes(data)
        _run(["aseqsend", "-p", address, "-s", str(message)])
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
