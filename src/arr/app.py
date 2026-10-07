"""L'application Typer, ses sous-groupes et les constantes partagées par les commandes."""

from __future__ import annotations

import typer

from arr import engines
from arr.project import ProjectError

app = typer.Typer(help="Réarranger un morceau : partition, prises complètes, greffe de stems.", no_args_is_help=True)
sections_app = typer.Typer(help="Parties du morceau (intro, couplet, refrain...).", no_args_is_help=True)
models_app = typer.Typer(help="Poids des modèles.", no_args_is_help=True)
lyrics_app = typer.Typer(help="Paroles du morceau.", no_args_is_help=True)
app.add_typer(sections_app, name="sections")
app.add_typer(lyrics_app, name="lyrics")
app.add_typer(models_app, name="models")


ORIGINAL = "source/original.flac"
ANALYSIS = "analysis.json"
SCORE = "score/score.abc"
LYRICS = "lyrics.txt"
ON_BEAT = 0.035  # un temps de la prise est « calé » s'il tombe à moins de 35 ms d'un temps de l'original
MAX_STRETCH = 0.03  # au-delà de 3 % d'écart de tempo, une prise n'est plus la même interprétation


def run() -> None:
    try:
        app()
    except ProjectError as e:
        typer.secho(f"erreur : {e}", fg="red", err=True)
        raise SystemExit(1)


@app.callback()
def main(ctx: typer.Context) -> None:
    # Les modèles ne touchent le réseau que dans `models pull` (`lyrics fetch` interroge LRCLIB).
    if ctx.invoked_subcommand != "models":
        engines.offline()
