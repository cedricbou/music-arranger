"""Point d'entrée de la commande `arr`.

Les commandes vivent dans `arr.commands`, un module par domaine ; les importer suffit à
les enregistrer dans l'application. L'ordre des imports ci-dessous est celui de
`arr --help` : il suit le déroulé du travail, ne pas le trier.
"""
# isort: skip_file

from arr.app import app, run
from arr.commands import project  # noqa: F401
from arr.commands import score  # noqa: F401
from arr.commands import takes  # noqa: F401
from arr.commands import tracks  # noqa: F401
from arr.commands import play  # noqa: F401
from arr.commands import review  # noqa: F401
from arr.commands import align  # noqa: F401
from arr.commands import sheet  # noqa: F401
from arr.commands import chordpro  # noqa: F401
from arr.commands import truth  # noqa: F401
from arr.commands import studio  # noqa: F401
from arr.commands import midi  # noqa: F401
from arr.commands import system  # noqa: F401
from arr.commands._common import add_track  # réexporté pour les tests

__all__ = ["add_track", "app", "run"]
