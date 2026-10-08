#!/usr/bin/env python
"""Écrit docs/manual/reference.md à partir des commandes elles-mêmes.

La référence est générée, jamais éditée à la main : pour la changer, modifier l'aide ou la
docstring de la commande dans `src/arr/commands/`, puis relancer

    uv run python scripts/gen_reference.py

`tests/test_docs.py` échoue si le fichier n'est plus à jour.
"""

from __future__ import annotations

from pathlib import Path

import typer

from arr.cli import app

TARGET = Path(__file__).parent.parent / "docs/manual/reference.md"
HEADER = """# Référence des commandes

<!-- Fichier généré par scripts/gen_reference.py : ne pas l'éditer à la main. -->

Toutes les commandes d'`arr`, avec leurs arguments et leurs options, dans l'ordre de
`arr --help`. Cette page est produite à partir du code : elle est toujours à jour. Pour
des explications et des exemples, voir les autres pages du [manuel](README.md).

"""


def commands(group, prefix: str = "arr"):
    for name, command in group.commands.items():
        if hasattr(command, "commands"):
            yield from commands(command, f"{prefix} {name}")
        else:
            yield f"{prefix} {name}", command


def cell(text: str | None) -> str:
    return " ".join((text or "").split()).replace("|", "\\|")


def is_option(param) -> bool:
    return param.param_type_name == "option"


def default_of(param) -> str:
    if param.required:
        return "obligatoire"
    value = param.default
    if callable(value) or value is None or value == () or value == []:
        return ""
    if isinstance(value, bool):
        return "oui" if value else "non"
    return f"`{value}`"


def usage(name: str, command) -> str:
    parts = [name]
    if any(is_option(p) for p in command.params):
        parts.append("[OPTIONS]")
    for p in command.params:
        if not is_option(p):
            label = p.name.upper().rstrip("_") + ("..." if p.nargs == -1 else "")
            parts.append(label if p.required else f"[{label}]")
    return " ".join(parts)


def section(name: str, command) -> str:
    lines = [f"## `{name}`", "", "```", usage(name, command), "```", ""]
    if command.help:
        for paragraph in command.help.strip().split("\n\n"):
            lines += [" ".join(paragraph.split()), ""]
    arguments = [p for p in command.params if not is_option(p)]
    options = [p for p in command.params if is_option(p)]
    if arguments:
        lines += ["| Argument | Défaut | Rôle |", "|---|---|---|"]
        lines += [
            f"| `{p.name.upper().rstrip('_')}` | {default_of(p)} | {cell(getattr(p, 'help', ''))} |" for p in arguments
        ]
        lines.append("")
    if options:
        lines += ["| Option | Défaut | Rôle |", "|---|---|---|"]
        for p in options:
            flags = ", ".join(f"`{o}`" for o in [*p.opts, *p.secondary_opts])
            repeat = " (répétable)" if p.multiple else ""
            lines.append(f"| {flags} | {default_of(p)} | {cell(p.help)}{repeat} |")
        lines.append("")
    return "\n".join(lines)


def build() -> str:
    group = typer.main.get_command(app)
    found = list(commands(group))
    index = "\n".join(
        f"- [`{name}`](#{name.replace(' ', '-')}) : {cell((c.help or '').strip().splitlines()[0])}" for name, c in found
    )
    return HEADER + index + "\n\n" + "\n".join(section(name, c) for name, c in found)


if __name__ == "__main__":
    TARGET.write_text(build())
    print(f"{TARGET.relative_to(TARGET.parent.parent.parent)} : {len(build().splitlines())} lignes")
