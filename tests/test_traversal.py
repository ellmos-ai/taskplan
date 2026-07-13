# -*- coding: utf-8 -*-
"""Ebenen-Traversierung: Was ist eine Root, was ein Projekt?

Bisher gab es diese Definition NIRGENDS im System — "Pipeline" und "Projekt"
wurden konflatiert, und der Loop setzte Pipeline = Projekt. Genau deshalb ist er
nie in die Projekte hinabgestiegen.

Die Ebenen sind konfigurierbar, nicht fest verdrahtet: Manche Installation hat
Root -> Projekt, eine andere Root -> Slot -> Unterprojekt.
"""
import tempfile
import unittest
from pathlib import Path

from taskplan.traversal import Level, TraversalConfig, find_projects, find_roots


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


class TestTwoLevel(unittest.TestCase):
    """Der Normalfall: Root -> Projekt."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Root .AI mit zwei Projekten und einem Nicht-Projekt
        _touch(self.tmp / ".AI" / "SKILLS" / "TODO.md")
        _touch(self.tmp / ".AI" / "MCP" / "pyproject.toml")
        _touch(self.tmp / ".AI" / "nur-ein-ordner" / "notizen.txt")   # kein Marker
        _touch(self.tmp / ".AI" / "README.md")                        # Root-Datei
        self.config = TraversalConfig(
            roots=[self.tmp / ".AI"],
            levels=[
                Level(name="root"),
                Level(name="project",
                      markers=["TODO.md", "ROADMAP.md", "pyproject.toml", ".git"],
                      is_work_unit=True),
            ],
        )

    def test_finds_marked_projects_only(self):
        projects = find_projects(self.config)
        names = sorted(p.path.name for p in projects)
        self.assertEqual(names, ["MCP", "SKILLS"])

    def test_project_knows_its_root(self):
        projects = find_projects(self.config)
        for project in projects:
            self.assertEqual(project.root_id, ".AI")

    def test_unmarked_directory_is_not_a_project(self):
        projects = find_projects(self.config)
        self.assertNotIn("nur-ein-ordner", [p.path.name for p in projects])


class TestThreeLevel(unittest.TestCase):
    """Root -> Slot -> Projekt. Der Slot gruppiert nur, gearbeitet wird tiefer."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _touch(self.tmp / ".SW" / "CASH" / "Rechnung" / "TODO.md")
        _touch(self.tmp / ".SW" / "CASH" / "Miete" / "TODO.md")
        _touch(self.tmp / ".SW" / "DATA" / "Parser" / "TODO.md")
        # Ein TODO.md auf SLOT-Ebene darf NICHT als Arbeitseinheit zaehlen
        _touch(self.tmp / ".SW" / "CASH" / "TODO.md")
        self.config = TraversalConfig(
            roots=[self.tmp / ".SW"],
            levels=[
                Level(name="root"),
                Level(name="slot"),                       # keine Marker: alles ist ein Slot
                Level(name="project", markers=["TODO.md"], is_work_unit=True),
            ],
        )

    def test_work_unit_is_the_deepest_level(self):
        projects = find_projects(self.config)
        names = sorted(p.path.name for p in projects)
        self.assertEqual(names, ["Miete", "Parser", "Rechnung"])

    def test_slot_itself_is_not_a_work_unit(self):
        """CASH hat selbst ein TODO.md — ist aber die Slot-Ebene, keine Arbeitseinheit."""
        projects = find_projects(self.config)
        self.assertNotIn("CASH", [p.path.name for p in projects])


class TestSkipDirs(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _touch(self.tmp / ".AI" / "echt" / "TODO.md")
        _touch(self.tmp / ".AI" / "_archive" / "alt" / "TODO.md")
        _touch(self.tmp / ".AI" / "node_modules" / "krempel" / "TODO.md")
        self.config = TraversalConfig(
            roots=[self.tmp / ".AI"],
            levels=[Level(name="root"),
                    Level(name="project", markers=["TODO.md"], is_work_unit=True)],
            skip_dirs=["_archive", "node_modules"],
        )

    def test_skipped_dirs_yield_no_projects(self):
        names = [p.path.name for p in find_projects(self.config)]
        self.assertEqual(names, ["echt"])


class TestRootsFromLockRoots(unittest.TestCase):
    """Das Roots-Inventar wird NICHT neu erfunden: lock_roots.json existiert
    bereits und ist die Quelle der Wahrheit. Zwei Listen wuerden auseinanderlaufen."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "a").mkdir()
        (self.tmp / "b").mkdir()
        self.lock_roots = self.tmp / "lock_roots.json"
        self.lock_roots.write_text(
            '{"default_max_depth": 4, "skip_dirs": ["_archive"], '
            f'"roots": ["{(self.tmp / "a").as_posix()}", '
            f'"{(self.tmp / "b").as_posix()}", '
            f'"{(self.tmp / "fehlt").as_posix()}"]}}',
            encoding="utf-8")

    def test_reads_roots(self):
        roots = find_roots(self.lock_roots)
        self.assertEqual(sorted(r.name for r in roots), ["a", "b"])

    def test_missing_root_is_skipped_not_crashed(self):
        """Ein Eintrag, der nicht mehr existiert, darf den Lauf nicht abbrechen."""
        roots = find_roots(self.lock_roots)
        self.assertNotIn("fehlt", [r.name for r in roots])

    def test_missing_file_yields_empty(self):
        self.assertEqual(find_roots(self.tmp / "gibtsnicht.json"), [])


if __name__ == "__main__":
    unittest.main()
