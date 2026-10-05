"""Projet sur disque : song.toml, pistes versionnées, provenance."""
from __future__ import annotations

import json
import shutil
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import tomli_w

SONG_FILE = "song.toml"


class ProjectError(Exception):
    pass


@dataclass
class Section:
    name: str
    start: float
    end: float


class Project:
    def __init__(self, root: Path):
        self.root = root
        self.data = tomllib.loads((root / SONG_FILE).read_text())

    @classmethod
    def create(cls, root: Path, title: str) -> "Project":
        if (root / SONG_FILE).exists():
            raise ProjectError(f"{root} contient déjà un projet")
        for d in ("source", "score", "takes", "tracks", "mix", "export"):
            (root / d).mkdir(parents=True, exist_ok=True)
        (root / SONG_FILE).write_text(tomli_w.dumps({"song": {"title": title}, "tracks": {}}))
        return cls(root)

    @classmethod
    def find(cls, start: Path | None = None) -> "Project":
        here = (start or Path.cwd()).resolve()
        for d in (here, *here.parents):
            if (d / SONG_FILE).exists():
                return cls(d)
        raise ProjectError("aucun projet ici (lance `arr init <nom>`)")

    def save(self) -> None:
        (self.root / SONG_FILE).write_text(tomli_w.dumps(self.data))

    # --- morceau

    @property
    def song(self) -> dict:
        return self.data.setdefault("song", {})

    @property
    def sections(self) -> list[Section]:
        return [Section(**s) for s in self.data.get("sections", [])]

    def set_sections(self, sections: list[Section]) -> None:
        self.data["sections"] = [vars(s) for s in sections]

    def section(self, name: str) -> Section:
        for s in self.sections:
            if s.name == name:
                return s
        known = ", ".join(s.name for s in self.sections) or "aucune"
        raise ProjectError(f"section inconnue : {name} (connues : {known})")

    # --- pistes

    @property
    def tracks(self) -> dict:
        return self.data.setdefault("tracks", {})

    def track_dir(self, track: str) -> Path:
        return self.root / "tracks" / track

    def versions(self, track: str) -> list[str]:
        return sorted(p.stem for p in self.track_dir(track).glob("v[0-9][0-9][0-9].flac"))

    def version_path(self, track: str, version: str | None = None) -> Path:
        if track not in self.tracks:
            known = ", ".join(self.tracks) or "aucune"
            raise ProjectError(f"piste inconnue : {track} (connues : {known})")
        version = version or self.tracks[track]["active"]
        path = self.track_dir(track) / f"{version}.flac"
        if not path.exists():
            raise ProjectError(f"{track} n'a pas de version {version}")
        return path

    def meta(self, track: str, version: str) -> dict:
        return json.loads((self.track_dir(track) / f"{version}.json").read_text())

    def new_version(self, track: str, meta: dict) -> tuple[str, Path]:
        """Réserve la prochaine version d'une piste ; l'appelant écrit le fichier audio."""
        d = self.track_dir(track)
        d.mkdir(parents=True, exist_ok=True)
        existing = self.versions(track)
        version = f"v{(int(existing[-1][1:]) if existing else 0) + 1:03d}"
        meta = {"created": datetime.now().isoformat(timespec="seconds"), **meta}
        (d / f"{version}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        return version, d / f"{version}.flac"

    def remove(self, track: str, version: str | None = None, *, purge: bool = False) -> list[Path]:
        """Retire une piste, ou une seule de ses versions ; renvoie les fichiers retirés.

        Par défaut ils vont dans la corbeille du projet (`trash/`) ; `purge` les efface.
        Si la version active disparaît, la plus récente qui reste devient active.
        """
        path = self.version_path(track, version) if version else None
        d = self.track_dir(track)
        last = version is None or self.versions(track) == [version]
        files = [d] if last else [path, path.with_suffix(".json")]
        self._discard(files, purge)
        if last:
            if track not in self.tracks:
                raise ProjectError(f"piste inconnue : {track}")
            del self.tracks[track]
        elif self.tracks[track]["active"] == version:
            self.tracks[track]["active"] = self.versions(track)[-1]
        self.save()
        return files

    def remove_take(self, name: str, *, purge: bool = False) -> list[Path]:
        """Retire une prise et ses stems (`tNNN.drums`...)."""
        path = self.take_path(name)
        stems = [t for t in self.tracks if t.startswith(f"{name}.")]
        files = [path, path.with_suffix(".json"), *(self.track_dir(t) for t in stems)]
        self._discard(files, purge)
        for t in stems:
            del self.tracks[t]
        self.save()
        return files

    def _discard(self, files: list[Path], purge: bool) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for f in files:
            if not f.exists():
                continue
            if purge:
                shutil.rmtree(f) if f.is_dir() else f.unlink()
            else:
                target = self.root / "trash" / stamp / f.relative_to(self.root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(target))

    # --- prises : rendus complets du morceau (voix et groupe)

    def takes(self) -> list[str]:
        return sorted(f.stem for f in (self.root / "takes").glob("t[0-9][0-9][0-9].flac"))

    def take_path(self, name: str) -> Path:
        path = self.root / "takes" / f"{name}.flac"
        if not path.exists():
            raise ProjectError(f"prise inconnue : {name} (connues : {', '.join(self.takes()) or 'aucune'})")
        return path

    def take_meta(self, name: str) -> dict:
        return json.loads(self.take_path(name).with_suffix(".json").read_text())

    def new_take(self, meta: dict) -> tuple[str, Path]:
        """Réserve la prochaine prise ; l'appelant écrit le fichier audio."""
        d = self.root / "takes"
        d.mkdir(exist_ok=True)
        existing = sorted(f.stem for f in d.glob("t[0-9][0-9][0-9].json"))
        name = f"t{(int(existing[-1][1:]) if existing else 0) + 1:03d}"
        meta = {"created": datetime.now().isoformat(timespec="seconds"), **meta}
        (d / f"{name}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        return name, d / f"{name}.flac"

    def activate(self, track: str, version: str) -> None:
        self.tracks.setdefault(track, {})["active"] = version
        self.save()
