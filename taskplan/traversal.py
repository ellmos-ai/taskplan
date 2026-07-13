# -*- coding: utf-8 -*-
"""Ebenen-Traversierung: Roots finden, Projekte erkennen.

Der Kern des Oberflaechen-Problems war eine fehlende Definition: "Pipeline" und
"Projekt" wurden im ganzen System nirgends unterschieden. Die Rotation kannte nur
eine flache Liste von 13 Wurzeln — eine Projektebene existierte gar nicht. Der
Loop setzte deshalb Pipeline = Projekt und ist nie hinabgestiegen.

Hier wird die Ebene strukturell definiert, nicht per Namensliste:

    Root     Einstiegspunkt der Traversierung (kommt aus der Umgebung)
    Level    eine Ebene darunter; genau eine traegt `is_work_unit`
    Projekt  ein Verzeichnis auf der Arbeitsebene, das einen MARKER traegt

Damit bleibt das Modul frei von den Namen UND von der Verzeichnistiefe einer
konkreten Installation. Wer zwei Ebenen braucht, laesst den Slot weg; wer vier
braucht, haengt eine an.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

DEFAULT_MARKERS = ("TODO.md", "ROADMAP.md", "AUFGABEN.md", "AUFGABEN.txt",
                   ".git", "pyproject.toml", "package.json")

DEFAULT_SKIP_DIRS = ("_archive", "_archiviert", "node_modules", ".venv",
                     "__pycache__", ".git", "dist", "build")


@dataclass(frozen=True)
class Level:
    """Eine Ebene der Traversierung.

    `markers` leer = jedes Unterverzeichnis zaehlt (reine Gruppierungsebene,
    z. B. ein Slot). `is_work_unit` markiert die Ebene, auf der tatsaechlich
    gearbeitet und gelockt wird — genau eine Ebene traegt sie.
    """
    name: str
    markers: tuple[str, ...] = ()
    is_work_unit: bool = False

    def __post_init__(self):
        if isinstance(self.markers, list):
            object.__setattr__(self, "markers", tuple(self.markers))


@dataclass
class TraversalConfig:
    roots: List[Path] = field(default_factory=list)
    levels: List[Level] = field(default_factory=list)
    skip_dirs: tuple[str, ...] = DEFAULT_SKIP_DIRS

    def __post_init__(self):
        self.roots = [Path(r) for r in self.roots]
        self.skip_dirs = tuple(self.skip_dirs)

    @property
    def work_level_index(self) -> int:
        """Index der Arbeitsebene. Ohne Markierung gilt die letzte Ebene."""
        for index, level in enumerate(self.levels):
            if level.is_work_unit:
                return index
        return len(self.levels) - 1


@dataclass(frozen=True)
class Project:
    """Eine Arbeitseinheit — das, was Rotation, Lock-Scope und `project_path` meinen."""
    path: Path
    root_id: str

    @property
    def name(self) -> str:
        return self.path.name


def find_roots(lock_roots_json: Path) -> List[Path]:
    """Liest das Roots-Inventar aus `lock_roots.json`.

    Die Datei existiert bereits und wird vom Lock-Scanner gepflegt. Eine zweite
    Roots-Liste anzulegen wuerde unweigerlich auseinanderlaufen — deshalb wird
    diese hier wiederverwendet statt dupliziert.

    Nicht (mehr) existierende Eintraege werden uebersprungen, nicht als Fehler
    behandelt: Ein umbenannter Ordner darf den ganzen Lauf nicht abbrechen.
    """
    path = Path(lock_roots_json)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    raw_roots = data.get("roots", [])
    roots: List[Path] = []
    for entry in raw_roots:
        # Ein Root kann ein blosser Pfad sein oder ein Objekt mit "path".
        raw = entry.get("path") if isinstance(entry, dict) else entry
        if not raw:
            continue
        candidate = Path(str(raw)).expanduser()
        if candidate.is_dir():
            roots.append(candidate)
    return roots


def _has_marker(directory: Path, markers: Iterable[str]) -> bool:
    return any((directory / marker).exists() for marker in markers)


def find_projects(config: TraversalConfig,
                  only_root: Optional[Path] = None) -> List[Project]:
    """Findet alle Arbeitseinheiten unterhalb der konfigurierten Roots.

    Steigt genau so tief wie die Ebenenliste vorgibt — kein unbegrenzter
    Baumscan. Ein Marker auf einer HOEHEREN Ebene macht diese nicht zur
    Arbeitseinheit (ein `TODO.md` im Slot-Ordner ist Slot-Doku, kein Projekt).
    """
    if not config.levels:
        return []

    work_index = config.work_level_index
    if work_index <= 0:
        return []  # Die Root selbst ist die Arbeitsebene -> keine Projekte darunter

    work_level = config.levels[work_index]
    markers = work_level.markers or DEFAULT_MARKERS

    roots = [Path(only_root)] if only_root is not None else config.roots
    projects: List[Project] = []

    for root in roots:
        if not root.is_dir():
            continue
        # Ebene fuer Ebene absteigen — nicht rglob, sonst waere die Ebenenzahl
        # bedeutungslos und ein tief verschachteltes TODO.md wuerde faelschlich
        # als Projekt gelten.
        current = [root]
        for depth in range(1, work_index + 1):
            nxt: List[Path] = []
            for parent in current:
                try:
                    children = [c for c in parent.iterdir() if c.is_dir()]
                except OSError:
                    continue
                for child in children:
                    if child.name in config.skip_dirs:
                        continue
                    if depth == work_index:
                        if _has_marker(child, markers):
                            nxt.append(child)
                    else:
                        nxt.append(child)
            current = nxt
        projects.extend(Project(path=p, root_id=root.name) for p in current)

    return projects
