"""Pilotage du lecteur Spotify local par D-Bus (MPRIS) : rien ne passe par Internet."""

from __future__ import annotations

import json
import subprocess

BUS = ["busctl", "--user"]
PLAYER = ["org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player"]


def _property(name: str):
    done = subprocess.run([*BUS, "--json=short", "get-property", *PLAYER, name], capture_output=True, text=True)
    return json.loads(done.stdout)["data"] if done.returncode == 0 else None


def now_playing(playing_only: bool = False) -> dict | None:
    """Morceau courant : {'id', 'title', 'artist', 'length'} (secondes), ou None sans Spotify.

    Avec `playing_only`, renvoie None si Spotify est en pause : le son vient alors d'ailleurs.
    """
    if playing_only and _property("PlaybackStatus") != "Playing":
        return None
    meta = _property("Metadata")
    if not meta or "xesam:title" not in meta:
        return None
    value = lambda key, default: meta.get(key, {}).get("data", default)
    return {
        "id": value("mpris:trackid", ""),
        "title": value("xesam:title", ""),
        "artist": ", ".join(value("xesam:artist", [])),
        "length": value("mpris:length", 0) / 1e6,
    }


def restart(track_id: str) -> None:
    """Revient au début du morceau et lance la lecture."""
    subprocess.run([*BUS, "call", *PLAYER, "Pause"], capture_output=True)
    subprocess.run([*BUS, "call", *PLAYER, "SetPosition", "ox", track_id, "0"], capture_output=True)
    subprocess.run([*BUS, "call", *PLAYER, "Play"], capture_output=True)


def pause() -> None:
    subprocess.run([*BUS, "call", *PLAYER, "Pause"], capture_output=True)
