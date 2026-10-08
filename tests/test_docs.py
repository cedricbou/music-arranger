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
