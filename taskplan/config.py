# -*- coding: utf-8 -*-
"""TASKPLAN-Konfiguration.

Die Datenbankwahl gehoert in die Konfiguration, nicht in den Code und nicht in
den Starter: Unser SQLite-Backend ist der empfohlene Default, aber ein anderer
Anwender soll TASKPLAN auch dann benutzen koennen, wenn seine Aufgaben woanders
liegen.

Suchreihenfolge der Konfigurationsdatei:
    1. ENV TASKPLAN_CONFIG (expliziter Pfad)
    2. ./taskplan.toml      (Projekt-lokal)
    3. ~/.taskplan/taskplan.toml  (Benutzer-weit)

TOML wird nur gelesen, wenn `tomllib` verfuegbar ist (Python >= 3.11). Auf
aelteren Versionen bleibt das Modul benutzbar — die Konfiguration wird dann
ignoriert und es gelten ENV-Variablen und Defaults. Zero dependencies bleibt
Zero dependencies.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib  # Python >= 3.11
except ImportError:  # pragma: no cover - nur auf Python 3.10
    tomllib = None  # type: ignore[assignment]


def config_search_paths() -> list[Path]:
    """Die Orte, an denen nach einer Konfiguration gesucht wird — in dieser Reihenfolge."""
    explicit = os.environ.get("TASKPLAN_CONFIG", "")
    paths = []
    if explicit:
        paths.append(Path(explicit).expanduser())
    paths.append(Path.cwd() / "taskplan.toml")
    paths.append(Path.home() / ".taskplan" / "taskplan.toml")
    return paths


def find_config_file() -> Optional[Path]:
    """Erste existierende Konfigurationsdatei — oder None."""
    for path in config_search_paths():
        if path.is_file():
            return path
    return None


def load_config() -> Dict[str, Any]:
    """Laedt die Konfiguration. Leeres Dict, wenn keine da ist oder TOML fehlt."""
    if tomllib is None:
        return {}
    path = find_config_file()
    if path is None:
        return {}
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except (OSError, ValueError):
        # Eine kaputte Konfiguration darf das Modul nicht lahmlegen — sie wird
        # ignoriert, damit ENV und Default weiterhin greifen.
        return {}


def configured_db_path() -> str:
    """Der in der Konfiguration hinterlegte DB-Pfad — oder "" wenn keiner."""
    storage = load_config().get("storage", {})
    path = storage.get("path", "") if isinstance(storage, dict) else ""
    return str(Path(path).expanduser()) if path else ""
