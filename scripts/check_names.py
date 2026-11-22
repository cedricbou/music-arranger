"""Refuse les titres, artistes et paroles des morceaux de la bibliothèque locale dans le dépôt.

Le dépôt est public : un exemple, un test ou une note ne nomme que des morceaux inventés. Les
noms réels sont lus dans les projets de l'utilisateur (`song.toml`, `lyrics.txt`), jamais
écrits dans le dépôt. Sans bibliothèque (la CI), il n'y a rien à comparer.

usage : python scripts/check_names.py --staged   lignes ajoutées par le commit en cours (hook pre-commit)
        python scripts/check_names.py --all      tous les fichiers suivis

ARR_LIBRARY : dossiers des projets, séparés par « : » (défaut : ~/Musique).
ARR_ALLOW_NAMES=1 : passer outre, à la demande de l'utilisateur.
Exemptées : les fiches de docs/decisions/, qui gardent leurs mesures sur de vrais morceaux.
"""

import os
import re
import subprocess
import sys
import tomllib
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXEMPT = ("docs/decisions/",)
SHORTEST = 4  # un nom plus court (« Up », « Bar ») ressemble trop à un mot courant
LYRIC_WORDS = 5  # une ligne de paroles plus courte (« oh oh oh ») ne dit rien de son morceau


def fold(text: str, case: bool = False) -> str:
    """Sans accents, ponctuation réduite à des espaces, en minuscules sauf `case` : « Rivière ! » donne « riviere »."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", plain if case else plain.lower()).split())


def needle(value: str) -> str:
    """Un nom de plusieurs mots se cherche sans casse ; un seul mot (« Home ») garde sa majuscule,
    sinon il se confondrait avec le mot courant (`Path.home`). Préfixe « = » : casse respectée."""
    words = fold(value, case=True)
    return fold(value) if " " in words else f"={words}"


def library_names(roots: list[Path]) -> dict[str, str]:
    """{nom cherché : d'où il vient} pour chaque titre, artiste et ligne de paroles des projets."""
    names: dict[str, str] = {}
    for root in roots:
        for song in sorted(root.glob("*/song.toml")):
            try:
                data = tomllib.loads(song.read_text())
            except (OSError, tomllib.TOMLDecodeError):
                continue
            for key in ("title", "artist"):
                value = str(data.get(key, ""))
                if len(fold(value)) >= SHORTEST:
                    names.setdefault(needle(value), f"{key} de {song.parent.name}")
        for lyrics in sorted(root.glob("*/lyrics.txt")):
            for line in lyrics.read_text(errors="ignore").splitlines():
                value = fold(re.sub(r"^\[[^\]]*\]", "", line))
                if len(value.split()) >= LYRIC_WORDS:
                    names.setdefault(value, f"paroles de {lyrics.parent.name}")
    return names


def leaks(lines: list[tuple[str, int, str]], names: dict[str, str]) -> list[str]:
    """`fichier:ligne : « nom » (origine)` pour chaque ligne qui contient un nom, mot entier."""
    found = []
    for path, number, text in lines:
        if path.startswith(EXEMPT):
            continue
        folded, cased = f" {fold(text)} ", f" {fold(text, case=True)} "
        for name, origin in names.items():
            exact = name.startswith("=")
            if f" {name.lstrip('=')} " in (cased if exact else folded):
                found.append(f"{path}:{number} : « {name.lstrip('=')} » ({origin})")
    return found


def staged_lines() -> list[tuple[str, int, str]]:
    diff = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--no-color", "--diff-filter=ACMR"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    lines, path, number = [], "", 0
    for row in diff.splitlines():
        if row.startswith("+++ "):
            path = row[6:] if row.startswith("+++ b/") else ""
        elif row.startswith("@@"):
            number = int(re.search(r"\+(\d+)", row).group(1))
        elif row.startswith("+") and path:
            lines.append((path, number, row[1:]))
            number += 1
    return lines


def tracked_lines() -> list[tuple[str, int, str]]:
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    lines = []
    for path in files:
        try:
            text = (ROOT / path).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        lines += [(path, n, line) for n, line in enumerate(text.splitlines(), 1)]
    return lines


def main(argv: list[str]) -> int:
    if os.environ.get("ARR_ALLOW_NAMES"):
        return 0
    if argv not in (["--staged"], ["--all"]):
        print(__doc__, file=sys.stderr)
        return 2
    roots = [Path(p).expanduser() for p in os.environ.get("ARR_LIBRARY", "~/Musique").split(":") if p]
    names = library_names([r for r in roots if r.is_dir()])
    if not names:
        return 0
    found = leaks(staged_lines() if argv == ["--staged"] else tracked_lines(), names)
    if found:
        print(
            "✗ noms ou paroles de vrais morceaux (le dépôt est public, les exemples sont inventés) :", file=sys.stderr
        )
        print("\n".join(f"  {f}" for f in found), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
