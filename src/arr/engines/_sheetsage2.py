"""Exécuté par le Python de l'environnement SheetSage2, pas par celui d'arr : n'importe rien d'arr.

usage : python _sheetsage2.py <audio> <dossier de sortie> <xpu|cpu> [grille.json]

Si SheetSage2 refuse d'écrire la partition (`abc_error` dans result.json), elle est réécrite
sur la grille d'`arr analyze` (grille.json : {"beats": [...], "bars": [...]}), ou à défaut sur
ses propres temps renumérotés : les intervalles trop courts sont fondus dans leurs voisins, les
notes posées sur la nouvelle grille (`_notation`, à côté de ce script). Les fichiers de
SheetSage2 restent tels quels ; le compte rendu va dans repair.json : l'erreur d'origine, et
celle de la reprise si elle échoue aussi.
"""

import importlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

import _notation
import pretty_midi
import soundfile as sf
import torch
from transformers import AutoModel


def rows(path):
    return [line.split("\t") for line in path.read_text().splitlines() if line.strip()]


def intervals(path):
    return [[float(a), float(b), v] for a, b, v, *_ in rows(path)]


def repair(notation, out, grid):
    """Réécrit score.abc avec `notation`, le module de partition de SheetSage2 ; renvoie le nombre de mesures."""
    folder = out / "notation"
    own = [[float(t), int(i), int(n)] for t, i, n, *_ in rows(folder / "song_beats.txt")]
    start, end = own[0][0], own[-1][0]
    if grid and len(grid["beats"]) >= 2 and grid["bars"]:
        beats = _notation.beat_rows(grid["beats"], grid["bars"], start, end)
    else:
        size = Counter(n for _, _, n in own).most_common(1)[0][0]
        first = next(t for t, i, _ in own if i == 1)
        beats = _notation.beat_rows([t for t, _, _ in own], [first], start, end, size)
    times = [b[0] for b in beats]
    fields = [
        _notation.merge_slivers(intervals(folder / f"song_{name}.txt"), times, notation.SUBBEAT_DIVISION)
        for name in ("chords", "keys", "structures")
    ]
    melody = pretty_midi.PrettyMIDI(str(folder / "song_melody.mid"))
    for voice in melody.instruments:
        notes = _notation.fit_notes([(n.start, n.end, n.pitch) for n in voice.notes], times, notation.SUBBEAT_DIVISION)
        voice.notes = [pretty_midi.Note(100, p, s, e) for s, e, p in notes]
    data = io.BytesIO()
    melody.write(data)
    text, score = notation.generate_abc_from_data(data.getvalue(), beats, *fields)
    (out / "score.abc").write_text(text)
    return len(score.measures)


def main():
    src, out, dev = sys.argv[1:4]
    grid = json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv) > 4 else None
    out = Path(out)
    model = AutoModel.from_pretrained("m-a-p/SheetSage2", trust_remote_code=True).eval().to(dev)
    wav, sr = sf.read(src, dtype="float32", always_2d=True)
    model.transcribe(torch.from_numpy(wav.T), sampling_rate=sr, output_dir=str(out))
    (out / "repair.json").unlink(missing_ok=True)
    error = json.loads((out / "result.json").read_text()).get("abc_error")
    if not error:
        return
    report = {"error": error, "repair_error": None, "measures": 0}
    try:
        notation = importlib.import_module(type(model).__module__.rsplit(".", 1)[0] + ".notation_sheetsage2")
        report["measures"] = repair(notation, out, grid)
    except Exception as exc:  # toute erreur de la reprise est rapportée, comme celle de SheetSage2
        report["repair_error"] = str(exc)
    (out / "repair.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
