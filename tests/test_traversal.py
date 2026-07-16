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


class TestAutoDepth(unittest.TestCase):
    """Der Normalfall: Die Roots sind UNTERSCHIEDLICH tief.

    Auf dem realen System liegen Spiele direkt unter ihrer Wurzel, Software-
    Projekte aber eine Kategorie-Ebene tiefer. Eine starre Ebenenzahl fand
    deshalb nur die eine Sorte — mit levels=2 lieferte .SOFTWARE genau NULL
    Projekte, obwohl dort 81 liegen.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # flach: Projekt direkt unter der Root
        _touch(self.tmp / ".ROBLOX" / "SpielA" / "TODO.md")
        _touch(self.tmp / ".ROBLOX" / "SpielB" / "TODO.md")
        # tief: Kategorie-Ebene dazwischen
        _touch(self.tmp / ".SW" / "CASH" / "Rechnung" / "TODO.md")
        _touch(self.tmp / ".SW" / "DATA" / "Parser" / "pyproject.toml")
        self.config = TraversalConfig(
            roots=[self.tmp / ".ROBLOX", self.tmp / ".SW"],
            max_depth=3,
            markers=("TODO.md", "pyproject.toml"),
        )

    def test_finds_both_shallow_and_deep_projects(self):
        names = sorted(p.name for p in find_projects(self.config))
        self.assertEqual(names, ["Parser", "Rechnung", "SpielA", "SpielB"])

    def test_root_id_is_the_root_not_the_category(self):
        by_name = {p.name: p.root_id for p in find_projects(self.config)}
        self.assertEqual(by_name["Rechnung"], ".SW")
        self.assertEqual(by_name["SpielA"], ".ROBLOX")

    def test_does_not_descend_into_a_project(self):
        """Ein Unterordner eines Projekts ist Teil davon, kein eigenes Projekt."""
        _touch(self.tmp / ".ROBLOX" / "SpielA" / "modul" / "TODO.md")
        names = [p.name for p in find_projects(self.config)]
        self.assertNotIn("modul", names)

    def test_max_depth_is_respected(self):
        """Kein unbegrenzter Baumscan — sonst faehrt man sich in OneDrive fest."""
        _touch(self.tmp / ".SW" / "A" / "B" / "C" / "D" / "TODO.md")
        names = [p.name for p in find_projects(self.config)]
        self.assertNotIn("D", names)


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

    def test_env_vars_in_paths_are_expanded(self):
        r"""Die echten Roots stehen als %USERPROFILE%\OneDrive\... in der Datei.
        Ohne Aufloesung findet man NULL Roots — genau das passierte zuerst."""
        import os
        os.environ["TP_TEST_ROOT"] = str(self.tmp)
        roots_file = self.tmp / "env_roots.json"
        roots_file.write_text(
            '{"roots": [{"path": "%TP_TEST_ROOT%/a", "shallow": true}]}'
            if os.name == "nt" else
            '{"roots": [{"path": "$TP_TEST_ROOT/a"}]}',
            encoding="utf-8")
        roots = find_roots(roots_file)
        self.assertEqual([r.name for r in roots], ["a"])


if __name__ == "__main__":
    unittest.main()
