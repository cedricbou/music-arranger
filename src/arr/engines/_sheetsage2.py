"""Exécuté par le Python de l'environnement SheetSage2, pas par celui d'arr : n'importe rien d'arr.

usage : python _sheetsage2.py <audio> <dossier de sortie> <xpu|cpu>
"""

import sys

import soundfile as sf
import torch
from transformers import AutoModel

src, out, dev = sys.argv[1:4]
model = AutoModel.from_pretrained("m-a-p/SheetSage2", trust_remote_code=True).eval().to(dev)
wav, sr = sf.read(src, dtype="float32", always_2d=True)
model.transcribe(torch.from_numpy(wav.T), sampling_rate=sr, output_dir=out)
