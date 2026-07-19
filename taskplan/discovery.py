# -*- coding: utf-8 -*-
"""Abbrechbare und gecachte Projekt-Discovery."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from .config import (discovery_cache_config, discovery_mode, find_config_file,
                     registry_file, traversal_config)
from .traversal import Project, discover_projects

CACHE_VERSION = 1


def _mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _signature(config, mode: str, registry: str) -> str:
    configured = find_config_file()
    registry_path = (Path(registry).expanduser() if registry else
                     Path.home() / ".taskplan" / "projects.json")
    rules = config.rules.describe() if config.rules is not None else ""
    payload = {
        "roots": [str(path.resolve()) for path in config.roots],
        "levels": [(level.name, level.markers, level.is_work_unit)
                   for level in config.levels],
        "skip_dirs": config.skip_dirs,
        "max_depth": config.max_depth,
        "markers": config.markers,
        "rules": rules,
        "mode": mode,
        "registry": str(registry_path.resolve()),
        "registry_mtime": _mtime(registry_path),
        "config_mtime": _mtime(configured) if configured else 0,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         default=list).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_cache(path: Path, signature: str, ttl: int) -> list[Project] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if data.get("version") != CACHE_VERSION or data.get("signature") != signature:
        return None
    if ttl and time.time() - float(data.get("created_at", 0)) > ttl:
        return None
    try:
        return [Project(path=Path(item["path"]), root_id=str(item["root_id"]))
                for item in data.get("projects", [])]
    except (KeyError, TypeError, ValueError):
        return None


def _write_cache(path: Path, signature: str, projects: list[Project]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": CACHE_VERSION,
        "signature": signature,
        "created_at": time.time(),
        "projects": [{"path": str(project.path), "root_id": project.root_id}
                     for project in projects],
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def discover_cached(force: bool = False) -> tuple[list[Project], bool]:
    config = traversal_config()
    mode = discovery_mode()
    registry = registry_file()
    cache = discovery_cache_config()
    signature = _signature(config, mode, registry)
    if cache["enabled"] and not force:
        cached = _read_cache(cache["path"], signature, cache["ttl_seconds"])
        if cached is not None:
            return cached, True
    projects = discover_projects(config, mode, registry)
    if cache["enabled"]:
        try:
            _write_cache(cache["path"], signature, projects)
        except OSError:
            pass
    return projects, False


def payload(force: bool = False) -> dict:
    projects, cached = discover_cached(force=force)
    return {
        "cached": cached,
        "projects": [{"path": str(project.path), "root_id": project.root_id}
                     for project in projects],
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print(json.dumps(payload(force="--force" in args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
