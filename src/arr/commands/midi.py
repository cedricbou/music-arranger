"""MIDI en direct : tester et piloter les pédales de scène par la sortie MIDI de la carte son."""

from __future__ import annotations

import time
from typing import Optional

import typer

from arr.app import midi_app
from arr.project import ProjectError


@midi_app.command("ports")
def midi_ports() -> None:
    """Liste les ports MIDI de la machine, et montre celui qu'arr utilise.

    Le port à retenir est celui de l'interface qui porte la prise MIDI OUT (« iTwo » ici) :
    c'est par elle que les messages partent vers la pédale.
    """
    from arr import midi, studio

    cfg = midi.settings()
    known = midi.ports()
    chosen = None
    try:
        chosen = midi.find_port(cfg["port"])
    except ProjectError as e:
        typer.secho(f"attention : {e}", fg="yellow", err=True)
    typer.echo(
        f"réglages ([midi] de {studio.CONFIG}{'' if studio.CONFIG.exists() else ', absent : valeurs par défaut'})"
    )
    typer.echo(
        f"  port      {cfg['port'] or 'automatique'}"
        + (f" -> {chosen[1]} ({chosen[0]})" if chosen else "")
        + f"  canal {cfg['channel']}"
    )
    typer.echo("ports MIDI (pour [midi] port)")
    for address, name in known:
        mark = "▶" if chosen and address == chosen[0] else " "
        typer.echo(f"{mark} {address:>6}  {name}")


@midi_app.command("send")
def midi_send(
    pc: Optional[int] = typer.Option(
        None, "--pc", min=1, max=128, help="Numéro de programme à envoyer, de 1 à 128 comme l'affiche la pédale."
    ),
    cc: Optional[int] = typer.Option(None, "--cc", min=0, max=127, help="Numéro de contrôleur à envoyer, de 0 à 127."),
    value: int = typer.Option(127, "--value", min=0, max=127, help="Valeur du contrôleur, de 0 à 127."),
    bank: Optional[int] = typer.Option(
        None, "--bank", min=1, max=128, help="Banque à sélectionner juste avant le programme (contrôleurs 0 et 32)."
    ),
    channel: Optional[int] = typer.Option(
        None, "--channel", min=1, max=16, help="Canal MIDI ; sinon celui d'audio.toml (1 par défaut)."
    ),
    port: Optional[str] = typer.Option(
        None, "--port", help="Fragment du nom du port MIDI, ou son adresse ; sinon celui d'audio.toml."
    ),
) -> None:
    """Envoie un changement de programme ou un contrôleur, pour tester une pédale.

    De quoi vérifier le câble, le canal et les réglages de la pédale avant de compter dessus :

        arr midi send --pc 5            # la pédale doit changer de son
        arr midi send --cc 7 --value 0  # le contrôleur 7, à 0

    Les numéros de programme vont de 1 à 128, comme les affichent les pédales ; les octets
    réellement envoyés sont repris dans la sortie. Rien n'est écrit dans la pédale.
    """
    from arr import midi

    cfg = midi.settings()
    channel = channel or cfg["channel"]
    if pc is None and cc is None and bank is None:
        raise ProjectError("rien à envoyer : donne --pc 5 (programme) ou --cc 7 --value 100 (contrôleur)")
    if cc is not None and (pc is not None or bank is not None):
        raise ProjectError("--cc s'envoie seul : un contrôleur ne se mêle pas à un changement de programme")
    data = b""
    if bank is not None:
        data += midi.bank_select(bank, channel)
    if pc is not None:
        data += midi.program_change(pc, channel)
    if cc is not None:
        data += midi.control_change(cc, value, channel)
    address, name = midi.send(data, port if port is not None else cfg["port"])
    typer.echo(f"{address}  {name}")
    for said, message in midi.describe(data):
        typer.echo(f"  {said}  ({midi.hexa(message)})")


@midi_app.command("monitor")
def midi_monitor(
    port: Optional[str] = typer.Option(
        None, "--port", help="Fragment du nom du port MIDI, ou son adresse ; sinon celui d'audio.toml."
    ),
    seconds: Optional[float] = typer.Option(None, help="Durée de l'écoute ; sinon jusqu'à Ctrl+C."),
) -> None:
    """Affiche les messages MIDI reçus, pour voir ce qu'envoie une pédale ou un clavier.

    L'autre moitié du test : appuie sur un sélecteur de la pédale et regarde ce qui arrive.
    Rien ne vient si la pédale n'envoie pas ses changements de programme (chez Boss, un
    réglage « MIDI PC OUT » dans l'utilitaire) ou si son câble MIDI OUT n'est pas branché.
    """
    from arr import midi

    address, name = midi.find_port(port if port is not None else midi.settings()["port"])
    typer.echo(f"écoute de {address}  {name}" + (f" pendant {seconds:g} s" if seconds else " (Ctrl+C arrête)"))
    heard, started = 0, time.monotonic()
    try:
        for line in midi.events(address, seconds):
            typer.echo(f"  {line}")
            heard += 1
    except KeyboardInterrupt:
        pass
    typer.echo(f"{heard} message{'s' if heard > 1 else ''} en {time.monotonic() - started:.0f} s")
