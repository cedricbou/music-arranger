"""Les commandes MIDI : ports, envoi, écoute. Aucun test ne parle au séquenceur ALSA."""

import subprocess
from pathlib import Path

import pytest

from arr import midi, studio
from arr.cli import app
from arr.project import ProjectError
from tests.helpers import runner

PORTS = """ Port    Client name                      Port name
  0:0    System                           Timer
 14:0    Midi Through                     Midi Through Port-0
 20:0    PreSonus AudioBox iTwo           PreSonus AudioBox iTwo MIDI 1
 24:0    KOMPLETE KONTROL A49             KOMPLETE KONTROL A49 MIDI 1
142:0    PipeWire-System                  input
"""


@pytest.fixture
def alsa(monkeypatch, tmp_path):
    """Remplace `aseqsend` : renvoie la liste de ports ci-dessus, et garde les envois."""
    sent = []

    def run(args, **kwargs):
        if args[1:] == ["-l"]:
            return subprocess.CompletedProcess(args, 0, PORTS, "")
        sent.append((args[args.index("-p") + 1], Path(args[args.index("-s") + 1]).read_bytes()))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(midi, "_run", run)
    monkeypatch.setattr(studio, "CONFIG", tmp_path / "audio.toml")
    return sent


# --- les messages, octet par octet


def test_messages_are_the_bytes_the_manuals_print():
    assert midi.program_change(5) == b"\xc0\x04"  # les programmes s'affichent à partir de 1
    assert midi.program_change(5, 3) == b"\xc2\x04"
    assert midi.control_change(7, 100) == b"\xb0\x07\x64"
    assert midi.control_change(7, 100, 16) == b"\xbf\x07\x64"
    assert midi.bank_select(2) == b"\xb0\x00\x00\xb0\x20\x01"  # banque 2 : MSB 0, LSB 1
    assert midi.bank_select(130) == b"\xb0\x00\x01\xb0\x20\x01"
    assert midi.hexa(midi.program_change(5)) == "C0 04"


@pytest.mark.parametrize(
    "call",
    [
        lambda: midi.program_change(0),
        lambda: midi.program_change(129),
        lambda: midi.program_change(5, 17),
        lambda: midi.control_change(128, 0),
        lambda: midi.control_change(7, 200),
    ],
)
def test_out_of_range_values_are_refused(call):
    with pytest.raises(ProjectError):
        call()


def test_describe_splits_a_stream_into_messages():
    said = midi.describe(midi.bank_select(2) + midi.program_change(12))
    assert [text for text, _ in said] == [
        "contrôleur 0 = 0, canal 1",
        "contrôleur 32 = 1, canal 1",
        "changement de programme 12, canal 1",
    ]


# --- le choix du port


def test_the_default_port_is_the_first_hardware_one(alsa):
    assert midi.find_port() == ("20:0", "PreSonus AudioBox iTwo MIDI 1")  # ni System, ni Through, ni PipeWire
    assert midi.find_port("itwo") == ("20:0", "PreSonus AudioBox iTwo MIDI 1")
    assert midi.find_port("24:0") == ("24:0", "KOMPLETE KONTROL A49 MIDI 1")
    assert midi.find_port("Midi Through") == ("14:0", "Midi Through Port-0")


def test_an_unknown_port_names_the_command_that_lists_them(alsa):
    with pytest.raises(ProjectError, match="arr midi ports"):
        midi.find_port("zorglub")


def test_without_a_hardware_port_the_message_says_so(alsa, monkeypatch):
    monkeypatch.setattr(midi, "ports", lambda: [("14:0", "Midi Through Port-0")])
    with pytest.raises(ProjectError, match="aucun port MIDI matériel"):
        midi.find_port()


def test_missing_alsa_utils_is_explained(monkeypatch):
    def absent(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", absent)
    with pytest.raises(ProjectError, match="alsa-utils"):
        midi.ports()


def test_ports_marks_the_one_in_use(alsa):
    result = runner.invoke(app, ["midi", "ports"])
    assert result.exit_code == 0, result.output
    assert "port      automatique -> PreSonus AudioBox iTwo MIDI 1 (20:0)  canal 1" in result.output
    assert "▶   20:0  PreSonus AudioBox iTwo MIDI 1" in result.output
    assert "    14:0  Midi Through Port-0" in result.output


# --- envoyer


def test_send_a_program_change(alsa):
    result = runner.invoke(app, ["midi", "send", "--pc", "5"])
    assert result.exit_code == 0, result.output
    assert alsa == [("20:0", b"\xc0\x04")]
    assert "changement de programme 5, canal 1  (C0 04)" in result.output


def test_send_a_controller_on_a_chosen_channel_and_port(alsa):
    result = runner.invoke(app, ["midi", "send", "--cc", "7", "--value", "100", "--channel", "3", "--port", "14:0"])
    assert result.exit_code == 0, result.output
    assert alsa == [("14:0", b"\xb2\x07\x64")]
    assert "contrôleur 7 = 100, canal 3  (B2 07 64)" in result.output


def test_a_bank_is_sent_just_before_the_program(alsa):
    result = runner.invoke(app, ["midi", "send", "--bank", "2", "--pc", "12"])
    assert result.exit_code == 0, result.output
    assert alsa == [("20:0", b"\xb0\x00\x00\xb0\x20\x01\xc0\x0b")]  # un seul envoi, dans l'ordre


def test_the_configured_port_and_channel_are_used(alsa):
    studio.CONFIG.write_text('[midi]\nport = "Midi Through"\nchannel = 4\n')
    result = runner.invoke(app, ["midi", "send", "--pc", "1"])
    assert result.exit_code == 0, result.output
    assert alsa == [("14:0", b"\xc3\x00")]
    assert midi.settings() == {"port": "Midi Through", "channel": 4}


def test_send_needs_something_to_send(alsa):
    with pytest.raises(ProjectError, match="rien à envoyer"):
        runner.invoke(app, ["midi", "send"], catch_exceptions=False)
    with pytest.raises(ProjectError, match="s'envoie seul"):
        runner.invoke(app, ["midi", "send", "--pc", "5", "--cc", "7"], catch_exceptions=False)
    assert not alsa


# --- écouter


def test_monitor_shows_what_arrives(alsa, monkeypatch):
    lines = ["20:0   Program change          0, program 4", "20:0   Control change          0, controller 7, value 100"]
    monkeypatch.setattr(midi, "events", lambda port, seconds=None: iter(lines))
    result = runner.invoke(app, ["midi", "monitor", "--seconds", "2"])
    assert result.exit_code == 0, result.output
    assert "écoute de 20:0  PreSonus AudioBox iTwo MIDI 1 pendant 2 s" in result.output
    assert all(line in result.output for line in lines)
    assert "2 messages" in result.output
