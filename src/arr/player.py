"""Pilotage du lecteur multimédia local par D-Bus (MPRIS) : rien ne passe par Internet."""

from __future__ import annotations

import json
import subprocess

from arr.project import ProjectError

BUS = ["busctl", "--user"]
PREFIX = "org.mpris.MediaPlayer2."
OBJECT = ["/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player"]
NO_TRACK = "/org/mpris/MediaPlayer2/TrackList/NoTrack"


def players() -> list[str]:
    """Noms D-Bus des lecteurs ouverts (org.mpris.MediaPlayer2.vlc, ...firefox.instance_1234...)."""
    done = subprocess.run(
        [
            *BUS,
            "--json=short",
            "call",
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "ListNames",
        ],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return []
    return sorted(n for n in json.loads(done.stdout)["data"][0] if n.startswith(PREFIX))


def short(name: str) -> str:
    return name.removeprefix(PREFIX)


def _property(player: str, name: str):
    done = subprocess.run([*BUS, "--json=short", "get-property", player, *OBJECT, name], capture_output=True, text=True)
    return json.loads(done.stdout)["data"] if done.returncode == 0 else None


def playing(player: str) -> bool:
    return _property(player, "PlaybackStatus") == "Playing"


def pick(names: list[str], wanted: str, playing: set[str], required: bool) -> str | None:
    """Le lecteur à suivre parmi `names` ; fonction pure.

    `wanted` (réglage `player` d'audio.toml) est un fragment du nom. Sans réglage, le seul
    lecteur qui joue ; avec `required` (--play), aussi le seul lecteur ouvert, et une erreur
    plutôt que rien.
    """
    found = ", ".join(short(n) for n in names) or "aucun"
    if wanted:
        matches = [n for n in names if wanted.lower() in short(n).lower()]
        if not matches:
            raise ProjectError(
                f"lecteur « {wanted} » introuvable (player dans audio.toml) ; lecteurs ouverts : {found}"
            )
        return next((n for n in matches if n in playing), matches[0])
    if required and len(names) == 1:
        return names[0]
    active = [n for n in names if n in playing]
    if len(active) == 1:
        return active[0]
    if not required:
        return None
    if not names:
        raise ProjectError("aucun lecteur multimédia ouvert : lance la lecture à la main, sans --play")
    raise ProjectError(
        f"plusieurs lecteurs ouverts ({found}) : choisis-en un dans audio.toml, "
        f'section [capture] : player = "{short(names[0]).split(".")[0]}"'
    )


def choose(wanted: str, required: bool) -> str | None:
    """Le lecteur à suivre parmi ceux ouverts sur la machine (voir `pick`)."""
    names = players()
    return pick(names, wanted, {n for n in names if playing(n)}, required)


def now_playing(player: str, playing_only: bool = False) -> dict | None:
    """Morceau courant : {'id', 'title', 'artist', 'length' (secondes), 'seek'}, ou None.

    `seek` dit si le lecteur sait revenir au début du morceau (ce qu'il faut à --play).
    Avec `playing_only`, renvoie None si le lecteur est en pause : le son vient alors d'ailleurs.
    """
    if playing_only and not playing(player):
        return None
    meta = _property(player, "Metadata")
    if not meta or "xesam:title" not in meta:
        return None
    value = lambda key, default: meta.get(key, {}).get("data", default)
    track = value("mpris:trackid", "")
    return {
        "id": track,
        "title": value("xesam:title", ""),
        "artist": ", ".join(value("xesam:artist", [])),
        "length": value("mpris:length", 0) / 1e6,
        "seek": bool(track not in ("", NO_TRACK) and _property(player, "CanSeek") and _property(player, "CanControl")),
    }


def restart(player: str, track_id: str) -> None:
    """Revient au début du morceau et lance la lecture."""
    subprocess.run([*BUS, "call", player, *OBJECT, "Pause"], capture_output=True)
    subprocess.run([*BUS, "call", player, *OBJECT, "SetPosition", "ox", track_id, "0"], capture_output=True)
    subprocess.run([*BUS, "call", player, *OBJECT, "Play"], capture_output=True)


def pause(player: str) -> None:
    subprocess.run([*BUS, "call", player, *OBJECT, "Pause"], capture_output=True)
