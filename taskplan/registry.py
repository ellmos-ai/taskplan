# -*- coding: utf-8 -*-
"""Manuelle Projekt-Registry — der Fallback, wenn die Automatik nicht reicht.

Die Auto-Erkennung sucht nach MARKERN (`TODO.md`, `.git`, `pyproject.toml`, …).
Das funktioniert, solange ein System diese Konventionen benutzt. Ein anderer
Anwender hat vielleicht:

  - Projekte ohne jede Steuerdatei (die Struktur steckt in einem Wiki),
  - eine Kategorie-Ebene, die faelschlich wie ein Projekt aussieht,
  - Projekte, die zusammengehoeren und als EINES bearbeitet werden sollen,
  - oder schlicht andere Dateinamen.

Fuer all das gibt es diese Registry: eine gepflegte Liste, die die Automatik
ergaenzt (`hybrid`) oder ersetzt (`manual`).

Sie ist bewusst eine schlichte JSON-Datei — sie soll von Hand editierbar sein,
und der MAINTAINER pflegt sie automatisch nach.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .traversal import Project

DEFAULT_REGISTRY_NAME = "projects.json"


@dataclass
class RegistryEntry:
    path: str
    root_id: str
    note: str = ""
    added_by: str = ""
    added_at: str = ""

    def to_project(self) -> Optional[Project]:
        resolved = Path(os.path.expandvars(self.path)).expanduser()
        if not resolved.is_dir():
            return None   # Umbenannt oder geloescht -> ueberspringen, nicht crashen
        return Project(path=resolved, root_id=self.root_id)


def registry_path(configured: str = "") -> Path:
    if configured:
        return Path(os.path.expandvars(configured)).expanduser()
    return Path.home() / ".taskplan" / DEFAULT_REGISTRY_NAME


def load_registry(configured: str = "") -> List[RegistryEntry]:
    path = registry_path(configured)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = []
    for raw in data.get("projects", []):
        if not isinstance(raw, dict) or not raw.get("path"):
            continue
        entries.append(RegistryEntry(
            path=str(raw["path"]),
            root_id=str(raw.get("root_id", "")),
            note=str(raw.get("note", "")),
            added_by=str(raw.get("added_by", "")),
            added_at=str(raw.get("added_at", "")),
        ))
    return entries


def save_registry(entries: List[RegistryEntry], configured: str = "") -> Path:
    path = registry_path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            "Manuell gepflegte Projekte. Ergaenzt die Auto-Erkennung (hybrid) "
            "oder ersetzt sie (manual). Von Hand editierbar; der MAINTAINER "
            "pflegt sie nach."
        ),
        "projects": [
            {"path": e.path, "root_id": e.root_id, "note": e.note,
             "added_by": e.added_by, "added_at": e.added_at}
            for e in entries
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def add_project(path: str, root_id: str, note: str = "", added_by: str = "",
                configured: str = "") -> bool:
    """Traegt ein Projekt ein. Doppelte Pfade werden NICHT dupliziert.

    Returns True, wenn neu eingetragen; False, wenn schon vorhanden.
    """
    entries = load_registry(configured)
    normalized = Path(os.path.expandvars(path)).expanduser().resolve()
    for entry in entries:
        existing = Path(os.path.expandvars(entry.path)).expanduser()
        try:
            if existing.resolve() == normalized:
                return False
        except OSError:
            continue
    entries.append(RegistryEntry(
        path=str(normalized), root_id=root_id, note=note, added_by=added_by,
        added_at=datetime.now().strftime("%Y-%m-%d"),
    ))
    save_registry(entries, configured)
    return True


def remove_project(path: str, configured: str = "") -> bool:
    """Entfernt einen Eintrag. Loescht NICHTS auf der Platte — nur den Eintrag."""
    entries = load_registry(configured)
    target = Path(os.path.expandvars(path)).expanduser()
    kept = []
    removed = False
    for entry in entries:
        current = Path(os.path.expandvars(entry.path)).expanduser()
        if current == target or str(current) == str(target):
            removed = True
            continue
        kept.append(entry)
    if removed:
        save_registry(kept, configured)
    return removed


def registered_projects(configured: str = "") -> List[Project]:
    """Die eingetragenen Projekte, die es real noch gibt."""
    return [p for p in (e.to_project() for e in load_registry(configured))
            if p is not None]
