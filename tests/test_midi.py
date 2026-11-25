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


def played(song: bytes) -> bytes:
    """Les octets des messages d'un fichier MIDI minimal, dans l'ordre où ils sont joués."""
    track, out = song[22:-4], b""  # après l'en-tête et l'entête de piste, sans la fin de piste
    while track:
        assert track[0] == 0, "les messages sont tous au temps zéro"
        message = midi.split(track[1:])[0]
        out, track = out + message, track[1 + len(message) :]
    return out


@pytest.fixture
def alsa(monkeypatch, tmp_path):
    """Remplace `aplaymidi` : renvoie la liste de ports ci-dessus, et garde les envois."""
    sent = []

    def run(args, **kwargs):
        if args[1:] == ["-l"]:
            return subprocess.CompletedProcess(args, 0, PORTS, "")
        sent.append((args[args.index("-p") + 1], played(Path(args[-1]).read_bytes())))
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


def test_a_minimal_midi_file_carries_the_messages_at_time_zero():
    song = midi.smf([midi.program_change(5), midi.control_change(7, 100)])
    assert song.startswith(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60MTrk")
    assert song.endswith(b"\x00\xc0\x04\x00\xb0\x07\x64\x00\xff\x2f\x00")
    assert played(song) == b"\xc0\x04\xb0\x07\x64"


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


def test_send_calls_aplaymidi_without_its_tail(monkeypatch):
    """`aseqsend` dit envoyer sans rien faire sortir vers la carte : c'est `aplaymidi` (fiche 011)."""
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, PORTS if args[1:] == ["-l"] else "", "")

    monkeypatch.setattr(midi, "_run", run)
    midi.send(midi.program_change(5), "14:0")
    assert calls[0] == ["aplaymidi", "-l"]
    assert calls[1][:5] == ["aplaymidi", "-d", "0", "-p", "14:0"]  # sans -d 0 : deux secondes d'attente


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


# --- le transport d'une lecture : horloge, Start, position, Stop

BAR = 2.0  # une mesure de 4/4 à 120 à la noire


def bars_4_4(count: int, start: float = 0.0) -> list[tuple[float, float, int]]:
    return [(start + i * BAR, start + (i + 1) * BAR, 4) for i in range(count)]


def test_song_position_and_transport_bytes_read_like_the_spec():
    assert midi.song_position(128) == b"\xf2\x00\x01"  # LSB puis MSB, sept bits chacun
    assert midi.song_position(16383) == b"\xf2\x7f\x7f"
    with pytest.raises(ProjectError):
        midi.song_position(16384)
    said = [s for s, _ in midi.describe(b"\xfa\xf8\xf2\x00\x01\xfb\xfc")]
    assert said == ["Start", "horloge", "position 128 (doubles-croches)", "Continue", "Stop"]


def test_each_bar_gets_24_ticks_per_beat_spread_over_its_length():
    bars = bars_4_4(2) + [(4.0, 5.0, 2)] + [(5.0, 7.4, 4)]  # une mesure de 2/4, puis un ralenti
    plan = midi.clock_plan(bars, [(0.0, 7.4)])
    assert len(plan) == 96 + 96 + 48 + 96
    assert plan[0] == (0.0, 0) and plan[96] == (2.0, 96) and plan[192] == (4.0, 192) and plan[240] == (5.0, 240)
    assert plan[1][0] == pytest.approx(0.5 / 24)
    assert plan[241][0] - plan[240][0] == pytest.approx(0.6 / 24)  # le tempo de l'enregistrement


def test_count_in_and_pickup_only_give_the_tempo_then_bar_1_starts():
    # la mesure 1 commence à 0,5 s (une levée d'un temps) ; un décompte d'une mesure la précède
    plan = midi.clock_plan(bars_4_4(2, start=0.5), [(0.0, 4.5)], since=-1.5)
    numbered = [i for i, (_, n) in enumerate(plan) if n is not None]
    assert plan[0][0] == pytest.approx(-1.5) and all(n is None for _, n in plan[: numbered[0]])
    assert plan[numbered[0]] == (0.5, 0) and numbered[0] == 4 * 24  # 1,5 s de décompte et un temps de levée
    steps = [b[0] - a[0] for a, b in zip(plan, plan[1:], strict=False)]
    assert max(steps) == pytest.approx(min(steps))  # un seul tempo, du décompte au morceau


def test_sections_played_out_of_order_carry_their_position():
    bars = bars_4_4(12)
    plan = midi.clock_plan(bars, [(16.0, 20.0), (0.0, 2.0)])  # mesures 9-10, puis la mesure 1
    assert plan[0] == (0.0, 8 * 96)
    assert plan[192] == (pytest.approx(4.0), 0) and len(plan) == 3 * 96


def test_messages_start_continue_and_jump_like_a_daw():
    tick = b"\xf8"
    assert midi.messages(None, None, False) == (tick, False)
    assert midi.messages(None, 0, False) == (b"\xfa" + tick, True)
    assert midi.messages(0, 1, True) == (tick, True)
    assert midi.messages(None, 768, False) == (midi.song_position(128) + b"\xfb" + tick, True)
    assert midi.messages(95, 0, True) == (midi.song_position(0) + tick, True)  # tour de boucle
    assert midi.messages(10, None, True) == (b"\xfc" + tick, False)


class Port:
    def __init__(self):
        self.sent, self.closed = [], False

    def send_message(self, message):
        self.sent.append(bytes(message))

    def close_port(self):
        self.closed = True


def stream(transport, blocks: range, where, paused: bool = False, delay: float = 0.0):
    """Le flux annonce sa position toutes les 10 ms ; le fil d'envoi passe chaque milliseconde."""
    for k in blocks:
        transport.heard(where(k), k * 0.01 + delay, paused)
        for j in range(10):
            transport.step(k * 0.01 + j * 0.001)


def test_ticks_leave_when_their_moment_leaves_the_speakers():
    plan = midi.clock_plan(bars_4_4(2), [(0.0, 4.0)], since=-2.0)
    port = Port()
    t = midi.Transport(plan, lambda s: s - 2.0, port=port)  # deux secondes de décompte
    stream(t, range(250), lambda k: k * 0.01, delay=0.1)  # 2,5 s ; chaque bloc sort 100 ms plus tard
    start = port.sent.index(b"\xfa")
    assert port.sent[0] == b"\xf8" and start == 96  # une mesure de tops, puis Start
    # 2,5 s moins les 100 ms de sortie : 0,4 s de mesure 1 entendue, donc 20 tops
    assert port.sent[start + 1 :].count(b"\xf8") == 20


def test_pause_sends_stop_and_resume_sends_position_and_continue():
    plan = midi.clock_plan(bars_4_4(4), [(0.0, 8.0)])
    port = Port()
    t = midi.Transport(plan, lambda s: s, port=port)
    stream(t, range(100), lambda k: k * 0.01)  # une seconde de lecture
    stream(t, range(100, 150), lambda k: 1.0, paused=True)  # en pause : la position ne bouge plus
    assert port.sent[-1] == b"\xfc" and port.sent.count(b"\xf8") == 48
    stream(t, range(150, 160), lambda k: 1.0 + (k - 150) * 0.01)  # reprise à la seconde 1
    assert port.sent[port.sent.index(b"\xfc") + 1 :][:2] == [midi.song_position(8), b"\xfb"]
    stream(t, range(160, 170), lambda k: 4.0 + (k - 160) * 0.01)  # flèche : la mesure 3
    assert midi.song_position(32) in port.sent
    t.clock = lambda: 1.7  # le fil, s'il passe, n'a plus rien de dû
    with t:  # à la fermeture, le morceau qui tournait s'arrête
        pass
    assert port.sent[-1] == b"\xfc" and port.closed
