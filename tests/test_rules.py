"""Les règles écrites d'AGENTS.md sont vérifiées ici : une règle fausse coûte plus qu'une règle absente."""

import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src/arr"
# Exécuté par l'environnement isolé de SheetSage2, jamais importé par arr : ses imports sont les siens.
FOREIGN = {SRC / "engines/_sheetsage2.py"}
MODULES = {f: ast.parse(f.read_text()) for f in sorted(SRC.rglob("*.py")) if f not in FOREIGN}


def rel(path: Path) -> str:
    return str(path.relative_to(SRC))


def imports(tree: ast.Module, top_level_only: bool = False):
    """(ligne, module importé), au niveau du module seulement ou partout."""
    nodes = tree.body if top_level_only else ast.walk(tree)
    for node in nodes:
        if isinstance(node, ast.Import):
            yield from ((node.lineno, a.name) for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            yield node.lineno, node.module


def strings(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def only_in(allowed: set[str], found: list[tuple[str, int, str]]) -> list[str]:
    return [f"{path}:{line} {what}" for path, line, what in found if path not in allowed]


# --- Local uniquement


def test_only_three_modules_can_reach_the_network():
    """`arr models pull`, `arr lyrics fetch`, et le cache des poids de beat_this (lu hors ligne)."""
    network = {"urllib", "http", "socket", "requests", "httpx", "aiohttp", "huggingface_hub", "ftplib", "smtplib"}
    found = [(rel(f), n, m) for f, t in MODULES.items() for n, m in imports(t) if m.split(".")[0] in network]
    allowed = {"lyrics.py", "commands/system.py", "engines/analysis.py"}
    assert not only_in(allowed, found), "accès réseau hors des modules permis :\n" + "\n".join(only_in(allowed, found))


def test_every_command_but_models_pull_runs_offline(monkeypatch):
    from types import SimpleNamespace

    from arr.app import main

    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        monkeypatch.delenv(name, raising=False)
    main(SimpleNamespace(invoked_subcommand="models"))
    assert "HF_HUB_OFFLINE" not in os.environ
    main(SimpleNamespace(invoked_subcommand="render"))
    assert os.environ["HF_HUB_OFFLINE"] == os.environ["TRANSFORMERS_OFFLINE"] == "1"


# --- `arr --help` reste instantané

HEAVY = {"torch", "torchaudio", "demucs", "beat_this", "sounddevice", "triton", "transformers"}


def test_heavy_libraries_are_imported_inside_functions():
    # separation.py n'est importé que dans les fonctions des commandes qui séparent.
    allowed = {"engines/separation.py"}
    found = [
        (rel(f), n, m)
        for f, t in MODULES.items()
        for n, m in imports(t, top_level_only=True)
        if m.split(".")[0] in HEAVY
    ]
    late = [
        (rel(f), n, m)
        for f, t in MODULES.items()
        for n, m in imports(t, top_level_only=True)
        if m == "arr.engines.separation"
    ]
    problems = only_in(allowed, found) + only_in(set(), late)
    assert not problems, "imports lourds au niveau d'un module :\n" + "\n".join(problems)


def test_loading_the_cli_loads_no_heavy_library():
    probe = f"import sys, arr.cli; print(sorted(m for m in {sorted(HEAVY)!r} if m in sys.modules))"
    loaded = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True).stdout.strip()
    assert loaded == "[]", f"`arr --help` charge {loaded}"


# --- La carte son par studio.py, le MIDI par midi.py, Spotify par spotify.py


def programs(names: set[str]) -> list[tuple[str, int, str]]:
    return [(rel(f), n, s) for f, t in MODULES.items() for n, s in strings(t) if s in names]


def test_the_sound_card_is_reached_only_through_studio():
    found = programs({"parec", "pactl", "pw-cat", "pw-record"})
    found += [(rel(f), n, m) for f, t in MODULES.items() for n, m in imports(t) if m.split(".")[0] == "sounddevice"]
    assert not only_in({"studio.py"}, found), "\n".join(only_in({"studio.py"}, found))


def test_midi_is_reached_only_through_midi():
    found = programs({"aplaymidi", "aseqdump", "aseqsend", "amidi", "aconnect"})
    assert not only_in({"midi.py"}, found), "\n".join(only_in({"midi.py"}, found))


def test_spotify_is_reached_only_through_spotify():
    found = [(rel(f), n, s) for f, t in MODULES.items() for n, s in strings(t) if s == "busctl" or "org.mpris" in s]
    assert not only_in({"spotify.py"}, found), "\n".join(only_in({"spotify.py"}, found))


def test_nothing_plays_on_the_speakers_behind_studio():
    """Aucun lecteur direct : tout son passe par studio.py, que les tests remplacent par un faux."""
    found = programs({"pw-play", "paplay", "aplay", "speaker-test", "ffplay", "mpv", "vlc", "playerctl"})
    assert not found, "\n".join(only_in(set(), found))


# --- Non destructif


def removals(tree: ast.Module):
    """(ligne, fonction englobante, appel) pour chaque appel qui retire ou déplace un fichier."""

    def calls(node, function):
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function
            if isinstance(child, ast.Call) and isinstance(f := child.func, ast.Attribute):
                owner = f.value.id if isinstance(f.value, ast.Name) else ""
                if f.attr in ("unlink", "rmdir", "rmtree") or (
                    owner in ("os", "shutil") and f.attr in ("remove", "move")
                ):
                    yield child.lineno, inner, f"{owner + '.' if owner else '.'}{f.attr}"
            yield from calls(child, inner)

    yield from calls(tree, "<module>")


def test_files_are_removed_only_at_the_known_places():
    """Seul `arr rm` retire de l'audio, vers trash/ par défaut ; le reste ne touche que des fichiers temporaires."""
    allowed = {
        ("project.py", "_discard"),  # arr rm : vers trash/, ou définitivement avec --purge
        ("commands/tracks.py", "rm"),  # arr rm --purge trash : vider la corbeille
        ("commands/takes.py", "render"),  # le WAV temporaire du moteur, une fois converti en prise
        ("commands/system.py", "install_audiocpp"),  # archive téléchargée, dossier partiel, lien `current`
    }
    found = [(rel(f), n, fn, what) for f, t in MODULES.items() for n, fn, what in removals(t)]
    unknown = [f"{p}:{n} {what} dans {fn}()" for p, n, fn, what in found if (p, fn) not in allowed]
    assert not unknown, "fichiers retirés hors des endroits connus :\n" + "\n".join(unknown)


def test_no_audio_or_model_weights_are_versioned():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    heavy = (".flac", ".wav", ".ogg", ".mp3", ".m4a", ".gguf", ".safetensors", ".pt", ".pth", ".ckpt", ".bin")
    found = [f for f in tracked if f.lower().endswith(heavy)]
    assert not found, f"audio ou poids versionnés : {found}"
