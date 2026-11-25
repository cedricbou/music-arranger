"""La documentation suit le code : ces tests échouent quand l'une dérive de l'autre."""

import re
from pathlib import Path

import typer

from arr.cli import app

ROOT = Path(__file__).parent.parent
AGENTS = (ROOT / "AGENTS.md").read_text()
README = (ROOT / "README.md").read_text()


def commands(group=None, prefix="arr") -> list[str]:
    """Toutes les commandes, sous la forme tapée par l'utilisateur : « arr lyrics fetch »."""
    group = group or typer.main.get_command(app)
    found = []
    for name, command in group.commands.items():
        full = f"{prefix} {name}"
        found += commands(command, full) if hasattr(command, "commands") else [full]
    return found


def test_every_command_is_documented_in_the_readme():
    missing = [c for c in commands() if not re.search(rf"`{re.escape(c)}\b", README)]
    assert not missing, f"commandes absentes du README : {missing}"


def test_code_map_matches_the_source_tree():
    code_map = AGENTS.split("## Carte du code")[1].split("```")[1]
    listed = set(re.findall(r"^\s+([\w/]+\.py)\b", code_map, flags=re.M))
    listed |= set(re.findall(r"\b(test_\w+\.py)", code_map))
    real = {str(f.relative_to(ROOT / "src/arr")) for f in (ROOT / "src/arr").rglob("*.py") if f.name != "__init__.py"}
    real |= {f.name for f in (ROOT / "tests").glob("*.py") if f.name != "__init__.py"}
    assert listed == real, f"en trop dans AGENTS.md : {sorted(listed - real)} ; absents : {sorted(real - listed)}"


def test_agents_guide_stays_short():
    assert len(AGENTS.splitlines()) <= 150, "AGENTS.md doit rester sous 150 lignes : déplacer le détail dans docs/"
    wide = [i for i, line in enumerate(AGENTS.splitlines(), 1) if len(line) > 110]
    assert not wide, (
        f"AGENTS.md, lignes de plus de 110 caractères : {wide} (allonger les lignes ne raccourcit pas le guide)"
    )


def test_every_decision_is_indexed():
    decisions = ROOT / "docs/decisions"
    index = (decisions / "README.md").read_text()
    missing = [f.name for f in decisions.glob("[0-9]*.md") if f.name not in index]
    assert not missing, f"fiches absentes de docs/decisions/README.md : {missing}"
    for number in re.findall(r"fiches? ((?:\d{3}(?:, | ou | et )?)+)", AGENTS):
        for n in re.findall(r"\d{3}", number):
            assert list(decisions.glob(f"{n}-*.md")), f"AGENTS.md cite la fiche {n}, qui n'existe pas"


def test_no_source_file_is_too_long():
    long = {
        str(f.relative_to(ROOT)): n
        for f in (ROOT / "src/arr").rglob("*.py")
        if (n := len(f.read_text().splitlines())) > 400
    }
    assert not long, f"fichiers de plus de 400 lignes, à découper : {long}"


# --- le manuel (docs/manual/)

MANUAL = ROOT / "docs/manual"


def leaf_commands(group=None, prefix="arr"):
    group = group or typer.main.get_command(app)
    for name, command in group.commands.items():
        if hasattr(command, "commands"):
            yield from leaf_commands(command, f"{prefix} {name}")
        else:
            yield f"{prefix} {name}", command


def test_command_reference_is_up_to_date():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_reference", ROOT / "scripts/gen_reference.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert (MANUAL / "reference.md").read_text() == generator.build(), (
        "docs/manual/reference.md n'est plus à jour : uv run python scripts/gen_reference.py"
    )


def test_every_command_and_parameter_is_described():
    """La référence est générée depuis ces textes : un texte manquant y laisse un trou."""
    undocumented = [name for name, command in leaf_commands() if not (command.help or "").strip()]
    undocumented += [
        f"{name} {param.name}"
        for name, command in leaf_commands()
        for param in command.params
        if not (getattr(param, "help", None) or "").strip()
    ]
    assert not undocumented, f"sans docstring ou sans help= : {undocumented}"


def test_every_audio_setting_is_in_the_manual(monkeypatch):
    from arr import midi, studio

    monkeypatch.setattr(studio, "CONFIG", ROOT / "absent.toml")
    monkeypatch.setattr(studio, "_device_names", lambda: [])
    page = (MANUAL / "audio.md").read_text()
    settings = {**studio.config(), "midi": midi.settings()}  # audio.toml porte aussi la section [midi]
    missing = [
        f"{section}.{key}" for section, keys in settings.items() for key in keys if f"`{section}.{key}`" not in page
    ]
    assert not missing, f"réglages d'audio.toml absents de docs/manual/audio.md : {missing}"


def test_every_environment_variable_is_in_the_manual():
    source = "\n".join(f.read_text() for f in (ROOT / "src/arr").rglob("*.py"))
    manual = "\n".join(f.read_text() for f in MANUAL.glob("*.md"))
    missing = [v for v in sorted(set(re.findall(r'environ\.get\("(ARR_\w+)"', source))) if f"`{v}`" not in manual]
    assert not missing, f"variables d'environnement absentes du manuel : {missing}"


def test_manual_pages_are_indexed_and_links_resolve():
    index = (MANUAL / "README.md").read_text()
    unlisted = [f.name for f in MANUAL.glob("*.md") if f.name != "README.md" and f"({f.name})" not in index]
    assert not unlisted, f"pages absentes du sommaire docs/manual/README.md : {unlisted}"
    broken = [
        f"{page.name} -> {target}"
        for page in MANUAL.glob("*.md")
        for target in re.findall(r"\]\(([^)#]+\.md)\)", page.read_text())
        if not (page.parent / target).resolve().exists()
    ]
    assert not broken, f"liens cassés dans le manuel : {broken}"


def test_readme_points_to_the_manual():
    assert "docs/manual/" in README, "le README doit renvoyer vers le manuel"


# --- le style de la documentation : les règles de docs/style-doc.md qui se mécanisent

DOCS = ROOT / "docs"
CODE = sorted([*(ROOT / "src/arr").rglob("*.py"), *(ROOT / "tests").glob("*.py"), *(ROOT / "scripts").glob("*.py")])
SHELL = sorted((ROOT / "scripts").glob("*.sh"))
# Une fiche de décision dit ce qui était le cas pour justifier son choix, et se remplace au lieu
# de se réécrire ; la référence est engendrée ; le guide de style doit nommer ce qu'il proscrit.
EXEMPT = {DOCS / "manual/reference.md", DOCS / "style-doc.md"}
WRITTEN = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    *(p for p in DOCS.rglob("*.md") if "decisions" not in p.relative_to(DOCS).parts and p not in EXEMPT),
    *(ROOT / ".claude").rglob("*.md"),
]
ISSUE_NUMBER = re.compile(r"(?<![\w&/])#\d+\b")
# Le sous-ensemble mécanisable de la règle 1 : « ne … plus » et « l'ancien » sont aussi du
# vocabulaire du domaine (une prise qui n'est plus active, l'ancienne version d'une piste).
PAST = re.compile(
    r"désormais|auparavant|anciennement|c'était|ont disparu"
    r"|(a|ont) été (retiré|remplacé|écarté|supprimé|déplacé|abandonné|introduit)e?s?"
    r"|(avant|depuis) (la PR )?#\d|[Cc]orrigé le \d{2}/\d{2}",
    re.I,
)
# Les fichiers d'un projet de morceau ou de la configuration de l'utilisateur : le manuel doit les
# nommer, et ils ne sont jamais dans le dépôt.
USER_FILES = ("song.toml", "sheet.toml", "audio.toml", "lyrics.txt", "analysis.json", "analysis_frames.npz")
USER_DIRS = ("setlists/", "takes/", "tracks/", "score/", "export/", "trash/", "truth/")


def code_tokens(path: Path, kinds: tuple) -> list[tuple[int, str]]:
    import io
    import tokenize

    tokens = tokenize.generate_tokens(io.StringIO(path.read_text()).readline)
    return [(t.start[0], t.string) for t in tokens if t.type in kinds]


def docstrings(path: Path) -> list[tuple[int, str]]:
    import ast

    nodes = ast.walk(ast.parse(path.read_text()))
    kinds = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    return [(getattr(n, "lineno", 1), d) for n in nodes if isinstance(n, kinds) and (d := ast.get_docstring(n))]


def where(path: Path, line: int, text: str) -> str:
    return f"{path.relative_to(ROOT)}:{line}: {text.strip()[:70]}"


def test_no_issue_number_in_the_code():
    """Règle 2 : l'historique est dans git ; un numéro d'issue dans le code ne dit rien à qui le lit."""
    import tokenize

    data = {ROOT / "tests/test_workflow.py"}  # les numéros y sont les données d'essai du cycle
    found = [
        where(f, n, s)
        for f in CODE
        if f not in data
        for n, s in code_tokens(f, (tokenize.COMMENT, tokenize.STRING))
        if ISSUE_NUMBER.search(s)
    ]
    found += [
        where(f, n, line)
        for f in SHELL
        for n, line in enumerate(f.read_text().splitlines(), 1)
        if ISSUE_NUMBER.search(line)
    ]
    assert not found, "numéros d'issue dans le code (règle 2 de docs/style-doc.md) :\n" + "\n".join(found)


def test_docs_and_comments_describe_the_present():
    """Règle 1 : un texte faux se supprime, un texte vrai se dit au présent."""
    import tokenize

    found = [
        where(f, n, line) for f in WRITTEN for n, line in enumerate(f.read_text().splitlines(), 1) if PAST.search(line)
    ]
    found += [
        where(f, n, s)
        for f in CODE
        for n, s in [*code_tokens(f, (tokenize.COMMENT,)), *docstrings(f)]
        if PAST.search(s)
    ]
    assert not found, "le passé raconté au lieu de l'état actuel (règle 1 de docs/style-doc.md) :\n" + "\n".join(found)


def test_every_cited_path_exists():
    """Un chemin cité qui n'existe plus envoie le lecteur nulle part, et personne ne le voit."""
    import subprocess

    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    cited = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_./-]*\.(py|md|toml|sh|yml|txt|json)")
    stale = [
        f"{doc.relative_to(ROOT)} : `{ref}`"
        for doc in [*WRITTEN, DOCS / "style-doc.md"]
        for ref in sorted(set(re.findall(r"`([^`\s]+)`", doc.read_text())))
        if cited.fullmatch(ref)
        and ref not in USER_FILES
        and not ref.startswith(USER_DIRS)
        and not (ROOT / ref).exists()
        and not any(t.endswith(f"/{ref}") for t in tracked)
    ]
    assert not stale, "chemins cités qui n'existent pas :\n" + "\n".join(stale)


def test_written_docs_stay_readable_in_one_go():
    """Au-delà de 600 lignes, un agent lit un document en morceaux et rate des invariants."""
    import warnings

    for doc in WRITTEN:
        if (n := len(doc.read_text().splitlines())) > 600:
            warnings.warn(
                f"{doc.relative_to(ROOT)} : {n} lignes (> 600) : découper par famille de sujets", stacklevel=1
            )
