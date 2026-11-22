"""Les règles écrites d'AGENTS.md sont vérifiées ici : une règle fausse coûte plus qu'une règle absente."""

import ast
import os
import re
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


# --- Pas de musique d'autrui dans le dépôt, qui est public

MUSIC = (".flac", ".wav", ".ogg", ".mp3", ".m4a", ".opus", ".aif", ".aiff", ".mid", ".midi", ".musicxml", ".mxl")
SHEETS = (".pdf", ".lrc", ".gp", ".gpx", ".gp5", ".mscz", ".sib")
WEIGHTS = (".gguf", ".safetensors", ".pt", ".pth", ".ckpt", ".bin", ".onnx", ".npy", ".npz")
# Les seuls artistes que nomment les exemples et les tests : ils sont inventés.
INVENTED_ARTISTS = {"Paper Lanterns", "The Night Shifts", "Hélène Faure", "4 Walls", "Artiste"}


def tracked() -> list[str]:
    return subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()


def test_no_music_lyrics_or_model_weights_are_versioned():
    found = [f for f in tracked() if f.lower().endswith(MUSIC + SHEETS + WEIGHTS) or Path(f).name == "lyrics.txt"]
    assert not found, f"audio, partition, paroles ou poids versionnés : {found}"
    binary = [f for f in tracked() if (ROOT / f).is_file() and b"\0" in (ROOT / f).read_bytes()[:8192]]
    assert not binary, f"fichiers binaires versionnés (le dépôt ne porte que du texte) : {binary}"


def test_examples_and_tests_name_only_invented_artists():
    """Un vrai morceau n'a rien à faire dans un dépôt public : les fiches de décision seules en gardent."""
    files = [
        *(f for f in (ROOT / "tests").glob("*.py") if f.name != "test_rules.py"),  # qui porte les motifs
        ROOT / "README.md",
        *(ROOT / "docs/manual").glob("*.md"),
        *SRC.rglob("*.py"),
    ]
    patterns = [
        r'\bartist\s*=\s*"([^"]+)"',
        r'"artist"\s*:\s*"([^"]+)"\s*[,}]',
        r'\["artist"\]\s*=\s*"([^"]+)"',
        r'folder_name\("[^"]*",\s*"([^"]+)"\)',
        r'\bsong\("[^"]*",\s*"[^"]*",\s*"([^"]+)"\)',
        r'lyrics fetch "([^"]+)"',
        r"« ([^»]+) » donne `",
    ]
    found = [
        f"{f.relative_to(ROOT)} : {m.group(1)}"
        for f in files
        for pattern in patterns
        for m in re.finditer(pattern, f.read_text())
        if m.group(1) not in INVENTED_ARTISTS
    ]
    assert not found, "artistes réels dans les exemples ou les tests (INVENTED_ARTISTS) :\n" + "\n".join(found)


def check_names():
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_names", ROOT / "scripts/check_names.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_names_from_the_local_library_are_refused(tmp_path):
    """Le hook pre-commit compare ce qu'ajoute un commit aux titres, artistes et paroles des projets."""
    names = check_names()
    song = tmp_path / "zorglub--la-riviere"
    song.mkdir()
    (song / "song.toml").write_text('title = "La Rivière noire"\nartist = "Zorglub"\n')
    (song / "lyrics.txt").write_text("[Verse]\nsous le pont passe la rivière noire\noh oh oh\n")
    (tmp_path / "vide").mkdir()
    library = names.library_names([tmp_path])
    lines = [
        ("tests/test_x.py", 1, 'title = "la riviere NOIRE"'),  # plusieurs mots : ni casse ni accents
        ("README.md", 2, "Un morceau de Zorglub."),  # un seul mot : avec sa majuscule
        ("src/arr/x.py", 3, "zorglub = Path.home()"),  # ... sinon un mot courant ferait échouer
        ("docs/manual/a.md", 4, "« Sous le pont passe la rivière noire »"),
        ("docs/decisions/012-x.md", 5, "mesuré sur La Rivière noire de Zorglub"),  # les fiches gardent leurs mesures
        ("tests/test_y.py", 6, "oh oh oh"),  # trop court pour dire quel morceau
    ]
    found = names.leaks(lines, library)
    assert [f.split(" : ")[0] for f in found] == [
        "tests/test_x.py:1",
        "README.md:2",
        "docs/manual/a.md:4",
        "docs/manual/a.md:4",
    ]
    assert names.library_names([tmp_path / "absent"]) == {}


def test_the_pre_commit_hook_checks_names_before_anything_else():
    hooks = (ROOT / "scripts/install-hooks.sh").read_text()
    assert "check_names.py --staged" in hooks.split('cat > "$dir/pre-commit"')[1].split("HOOK")[1]
