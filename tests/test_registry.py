# -*- coding: utf-8 -*-
"""Manuelle Projekt-Registry: der Fallback, wenn die Automatik nicht reicht.

Nutzerneutralitaet heisst nicht "unsere Marker sind konfigurierbar" — es heisst
auch: Ein System, dessen Struktur sich UEBERHAUPT NICHT aus Dateinamen ableiten
laesst, muss TASKPLAN trotzdem benutzen koennen.
"""
import tempfile
import unittest
from pathlib import Path

from taskplan.registry import (
    add_project, load_registry, registered_projects, remove_project,
)
from taskplan.traversal import TraversalConfig, discover_projects


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


class TestRegistryCrud(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.file = str(self.tmp / "projects.json")
        self.project = self.tmp / "ohne-marker"
        self.project.mkdir()

    def test_add_and_load(self):
        self.assertTrue(add_project(str(self.project), ".X", note="kein Marker",
                                    added_by="maintainer", configured=self.file))
        entries = load_registry(self.file)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].root_id, ".X")
        self.assertEqual(entries[0].note, "kein Marker")
        self.assertEqual(entries[0].added_by, "maintainer")
        self.assertTrue(entries[0].added_at)

    def test_add_is_idempotent(self):
        add_project(str(self.project), ".X", configured=self.file)
        self.assertFalse(add_project(str(self.project), ".X", configured=self.file))
        self.assertEqual(len(load_registry(self.file)), 1)

    def test_remove(self):
        add_project(str(self.project), ".X", configured=self.file)
        self.assertTrue(remove_project(str(self.project), configured=self.file))
        self.assertEqual(load_registry(self.file), [])

    def test_remove_does_not_touch_disk(self):
        """`remove` entfernt den EINTRAG — nichts auf der Platte."""
        add_project(str(self.project), ".X", configured=self.file)
        remove_project(str(self.project), configured=self.file)
        self.assertTrue(self.project.is_dir(), "Das Verzeichnis wurde geloescht!")

    def test_missing_directory_is_skipped_not_crashed(self):
        add_project(str(self.tmp / "gibtsnicht"), ".X", configured=self.file)
        self.assertEqual(registered_projects(self.file), [])

    def test_missing_file_yields_empty(self):
        self.assertEqual(load_registry(str(self.tmp / "nix.json")), [])


class TestDiscoveryModes(unittest.TestCase):
    """auto / manual / hybrid — der Schalter fuer fremde Systeme."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.file = str(self.tmp / "projects.json")
        self.root = self.tmp / ".X"
        # Automatisch erkennbar (traegt einen Marker)
        _touch(self.root / "mit-marker" / "TODO.md")
        # NICHT erkennbar — genau der Fall, um den es geht
        (self.root / "ohne-marker").mkdir(parents=True)
        self.config = TraversalConfig(
            roots=[self.root], max_depth=2, markers=("TODO.md",))
        add_project(str(self.root / "ohne-marker"), ".X",
                    note="hat keine Steuerdatei", configured=self.file)

    def test_auto_misses_the_unmarked_project(self):
        found = discover_projects(self.config, "auto", self.file)
        self.assertEqual([p.name for p in found], ["mit-marker"])

    def test_manual_sees_only_the_registry(self):
        found = discover_projects(self.config, "manual", self.file)
        self.assertEqual([p.name for p in found], ["ohne-marker"])

    def test_hybrid_sees_both(self):
        found = discover_projects(self.config, "hybrid", self.file)
        self.assertEqual(sorted(p.name for p in found),
                         ["mit-marker", "ohne-marker"])

    def test_hybrid_does_not_duplicate(self):
        """Ein Projekt, das BEIDE finden, darf nur einmal erscheinen."""
        add_project(str(self.root / "mit-marker"), ".X", configured=self.file)
        found = discover_projects(self.config, "hybrid", self.file)
        names = [p.name for p in found]
        self.assertEqual(len(names), len(set(names)), f"Dubletten: {names}")
        self.assertEqual(sorted(names), ["mit-marker", "ohne-marker"])

    def test_registry_wins_on_conflict(self):
        """Wer von Hand eintraegt, hat einen Grund — der Eintrag gewinnt."""
        add_project(str(self.root / "mit-marker"), ".ANDERS",
                    note="gehoert eigentlich woanders hin", configured=self.file)
        found = discover_projects(self.config, "hybrid", self.file)
        by_name = {p.name: p.root_id for p in found}
        self.assertEqual(by_name["mit-marker"], ".ANDERS")


class TestCustomMarkers(unittest.TestCase):
    """Auch die Automatik ist anpassbar: eigene Marker statt unserer Konvention."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        _touch(self.tmp / ".X" / "fremdes-projekt" / "Backlog.rst")
        _touch(self.tmp / ".X" / "unser-projekt" / "TODO.md")

    def test_default_markers_miss_foreign_convention(self):
        config = TraversalConfig(roots=[self.tmp / ".X"], max_depth=2,
                                 markers=("TODO.md",))
        names = [p.name for p in discover_projects(config, "auto")]
        self.assertEqual(names, ["unser-projekt"])

    def test_custom_markers_find_it(self):
        config = TraversalConfig(roots=[self.tmp / ".X"], max_depth=2,
                                 markers=("Backlog.rst",))
        names = [p.name for p in discover_projects(config, "auto")]
        self.assertEqual(names, ["fremdes-projekt"])


if __name__ == "__main__":
    unittest.main()
