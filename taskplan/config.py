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


def selector_config():
    """Baut die SelectorConfig aus der Konfigurationsdatei."""
    from .selector import SelectorConfig

    config = load_config()
    loop = config.get("loop", {}) or {}
    deep = loop.get("deep", {}) or {}
    return SelectorConfig(
        deep_enabled=bool(deep.get("enabled", True)),
        effort_ceiling=str(loop.get("effort_ceiling", "medium")),
        easy_first_globally=bool(deep.get("easy_first_globally", True)),
        projects_per_dive=int(deep.get("projects_per_dive", 1)),
        max_bundle_size=int(loop.get("max_bundle_size", 3)),
    )


def traversal_config():
    """Baut die TraversalConfig aus der Konfigurationsdatei.

    Das Roots-Inventar wird NICHT dupliziert: `[traversal] roots_file` zeigt auf
    eine bestehende Roots-Liste (z. B. `lock_roots.json`). Zwei Listen wuerden
    unweigerlich auseinanderlaufen.
    """
    from .traversal import DEFAULT_SKIP_DIRS, Level, TraversalConfig, find_roots

    config = load_config()
    section = config.get("traversal", {}) or {}

    roots = []
    roots_file = section.get("roots_file", "")
    if roots_file:
        roots = find_roots(Path(roots_file).expanduser())
    roots += [Path(r).expanduser() for r in section.get("roots", []) or []]

    raw_levels = section.get("levels") or []
    if raw_levels:
        levels = [Level(name=str(level.get("name", f"level{i}")),
                        markers=tuple(level.get("markers", []) or []),
                        is_work_unit=bool(level.get("is_work_unit", False)))
                  for i, level in enumerate(raw_levels)]
    else:
        # Default: zweistufig. Root -> Projekt.
        levels = [Level(name="root"),
                  Level(name="project", is_work_unit=True)]

    return TraversalConfig(
        roots=roots,
        levels=levels,
        skip_dirs=tuple(section.get("skip_dirs", DEFAULT_SKIP_DIRS)),
    )


def lock_config() -> Dict[str, Any]:
    """Lock-Provider und die Pfade fremder Regelwerke.

    `provider = "lockmaster"` -> bekanntes Schema, deterministisch ausgewertet.
    `provider = "rules"`      -> fremdes System: NICHT auswerten, sondern die
                                 hinterlegten Regeldateien als Text in den Prompt
                                 reichen. Lieber ein Agent, der die echte Regel
                                 liest, als ein Parser, der sie errät.
    """
    section = load_config().get("locks", {}) or {}
    return {
        "provider": str(section.get("provider", "lockmaster")),
        "rule_paths": [Path(p).expanduser()
                       for p in section.get("rule_paths", []) or []],
        "max_depth": int(section.get("max_depth", 4)),
    }


def active_roles() -> Dict[str, bool]:
    """Welche Rollen laufen? Abgeschaltete Rolle -> Starter bricht sauber ab."""
    section = load_config().get("roles", {}) or {}
    return {
        "taskwriter": bool(section.get("taskwriter", True)),
        "tasksolver": bool(section.get("tasksolver", True)),
        "maintainer": bool(section.get("maintainer", True)),
        "combined": bool(section.get("combined", False)),
    }


def model_for(role: str) -> str:
    """Das Modell einer Rolle. Gehoert in die Config, nicht in den Starter."""
    section = load_config().get("models", {}) or {}
    return str(section.get(role) or section.get("default", ""))
