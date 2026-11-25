"""Vrais moteurs sur un signal synthétique : `uv run pytest -m slow`.

Exclus par défaut et de la CI : il faut les modèles installés (`arr models pull`), et pour
le MIDI le séquenceur ALSA. Ils vérifient qu'une machine fraîchement installée fonctionne,
pas la qualité musicale.
"""

import threading
import time

import numpy as np
import pytest

from arr import audio, engines, measure

pytestmark = pytest.mark.slow


def click_song(seconds: float = 12.0, bpm: float = 120.0) -> np.ndarray:
    """Un « morceau » minimal : un clic par temps sur une basse tenue."""
    beat = 60 / bpm
    t = np.arange(int(seconds * audio.SR)) / audio.SR
    bass = (0.2 * np.sin(2 * np.pi * 55 * t)).astype(np.float32)
    song = np.stack([bass, bass], axis=1)
    return audio.add_clicks(song, [(i * beat, i % 4 == 0) for i in range(int(seconds / beat))])


def test_beat_tracker_finds_the_tempo(tmp_path):
    from arr.engines import analysis

    engines.offline()
    path = tmp_path / "clics.flac"
    audio.save(path, click_song())
    beats, _ = analysis.beats(path)
    assert abs(60 / measure.period(beats) - 120) < 1.0


REPAIR = """
import importlib, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
import pretty_midi
from transformers import AutoConfig
import _sheetsage2

config = AutoConfig.from_pretrained("m-a-p/SheetSage2", trust_remote_code=True)
notation = importlib.import_module(type(config).__module__.rsplit(".", 1)[0] + ".notation_sheetsage2")
out = Path(sys.argv[1])
folder = out / "notation"
folder.mkdir(parents=True)
ids = [i % 4 + 1 for i in range(40)]
ids[12:] = [4] + ids[12:-1]  # une mesure de cinq temps : 1 2 3 4 4
rows = lambda r: "".join("\\t".join(map(str, x)) + "\\n" for x in r)
(folder / "song_beats.txt").write_text(rows([[0.5 * i, n, 4, 4] for i, n in enumerate(ids)]))
chords = [[2.0 * i, 2.0 * i + 2, "A:maj" if i % 2 else "D:maj"] for i in range(9)] + [[18.0, 19.5, "D:maj"]]
chords[-1][1] = 19.484
chords.append([19.484, 19.5, "C#:sus4"])  # 16 ms en fin de morceau
(folder / "song_chords.txt").write_text(rows(chords))
(folder / "song_keys.txt").write_text(rows([[0.0, 19.5, "D:major"]]))
(folder / "song_structures.txt").write_text(rows([[0.0, 8.0, "verse"], [8.0, 19.5, "chorus"]]))
midi = pretty_midi.PrettyMIDI()
for name in ("Vocal", "Ins"):
    voice = pretty_midi.Instrument(0, name=name)
    voice.notes = [pretty_midi.Note(100, 62 + i % 5, 0.5 * i + 0.02, 0.5 * i + 0.4) for i in range(38)]
    midi.instruments.append(voice)
midi.write(str(folder / "song_melody.mid"))
read = lambda f: [[float(a), float(b), v] for a, b, v in (l.split("\\t") for l in (folder / f).read_text().split("\\n") if l)]
try:
    notation.generate_abc_from_data((folder / "song_melody.mid").read_bytes(), [l.split("\\t") for l in
        (folder / "song_beats.txt").read_text().split("\\n") if l], read("song_chords.txt"),
        read("song_keys.txt"), read("song_structures.txt"))
    refused = None
except ValueError as exc:
    refused = str(exc)
grid = {"beats": [0.5 * i for i in range(39)], "bars": [2.0 * i for i in range(10)]}
print(json.dumps({"refused": refused, "measures": _sheetsage2.repair(notation, out, grid)}))
"""


def test_a_refused_score_is_rewritten_by_the_sheetsage2_environment(tmp_path):
    """La reprise tourne avec le vrai module de partition de SheetSage2, sans le modèle."""
    import json
    import os
    import subprocess

    from arr.engines import SS2_PYTHON, transcription

    engines.offline()
    driver = tmp_path / "driver.py"
    driver.write_text(REPAIR)
    out = tmp_path / "score"
    done = subprocess.run(
        [str(SS2_PYTHON), str(driver), str(out), str(transcription.SCRIPT.parent)],
        capture_output=True,
        text=True,
        env=os.environ,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    result = json.loads(done.stdout.splitlines()[-1])
    assert "non-consecutive beat IDs" in result["refused"]  # SheetSage2 seul refuse
    abc = (out / "score.abc").read_text()
    assert result["measures"] == 10 and "M:4/4" in abc and "M:5/4" not in abc
    assert '"C#sus4"' not in abc  # l'accord de 16 ms s'est fondu dans le précédent


def test_separation_stems_add_up_to_the_song(tmp_path):
    from arr.engines.separation import separate

    engines.offline()
    song = click_song()
    path = tmp_path / "clics.flac"
    audio.save(path, song)
    stems = separate(path, "htdemucs_6s")
    assert set(stems) == {"drums", "bass", "other", "vocals", "guitar", "piano"}
    assert all(len(s) == len(song) for s in stems.values())
    total = sum(stems.values())
    assert np.corrcoef(total[:, 0], song[:, 0])[0, 1] > 0.95


def test_midi_goes_out_and_comes_back_through_the_alsa_loopback():
    """Le vrai `aplaymidi` vers le port de bouclage du noyau, relu par le vrai `aseqdump`.

    Aucun matériel et aucune pédale touchée : « Midi Through » existe dès que le module
    snd-seq-dummy est chargé. Attention : ce bouclage prouve les octets et leur ordre, pas
    qu'ils sortent de l'ordinateur — seul « Tx bytes » de `/proc/asound/card*/midi0` le dit.
    """
    from arr import midi

    if not any("Midi Through" in name for _, name in midi.ports()):
        pytest.skip("pas de port « Midi Through » (module snd-seq-dummy absent)")
    heard: list[str] = []
    listening = threading.Thread(target=lambda: heard.extend(midi.events("Midi Through", seconds=4)), daemon=True)
    listening.start()
    time.sleep(1.0)  # aseqdump doit être abonné au port avant l'envoi
    midi.send(midi.bank_select(2) + midi.program_change(5, 2), "Midi Through")
    listening.join(6)
    assert len(heard) == 3, heard  # les trois messages, dans l'ordre où ils ont été écrits
    assert "controller 0, value 0" in heard[0] and "controller 32, value 1" in heard[1]
    assert "Program change" in heard[2] and "1, program 4" in heard[2]  # canal 2, programme 5


def test_the_transport_leaves_on_the_virtual_port_and_a_client_hears_it():
    """Le vrai port virtuel « arr:transport », relu par un client du séquenceur comme le serait namfoop."""
    import rtmidi

    from arr import midi

    plan = midi.clock_plan([(0.0, 0.5, 1), (0.5, 1.0, 1)], [(0.0, 1.0)], since=-0.5)
    heard = []
    with midi.Transport(plan, lambda s: s - 0.5) as transport:
        probe = rtmidi.MidiIn(rtmidi.API_LINUX_ALSA, name="probe")
        probe.ignore_types(timing=False)
        probe.open_port(next(i for i, n in enumerate(probe.get_ports()) if n.startswith("arr:")))
        begin = time.monotonic()
        while time.monotonic() - begin < 1.6:
            transport.heard(time.monotonic() - begin, time.monotonic(), False)
            while message := probe.get_message():
                heard.append(bytes(message[0]))
            time.sleep(0.005)
    time.sleep(0.05)
    while message := probe.get_message():
        heard.append(bytes(message[0]))
    assert heard.count(b"\xf8") == 72 and heard.index(b"\xfa") == 24  # une noire de décompte, puis Start
    assert heard[-1] == b"\xfc"
