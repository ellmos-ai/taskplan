# -*- coding: utf-8 -*-
"""Schema v2: Aufwand, Scope, Projektpfad und getrennte Zuweisung.

Deckt die drei Luecken ab, die das Umbaukonzept (§3, §3.0) benennt:
  1. effort/scope fehlten komplett -> "erst leichte, dann mittlere" war nicht erzwingbar
  2. project_path lag nur als Freitext in tags -> nicht abfragbar
  3. agent_id trug DREI Bedeutungen (Anleger/Bearbeiter/Rolle) und wurde beim
     Zuweisen ueberschrieben -> die Herkunft ging verloren
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from taskplan.client import TaskClient, VALID_EFFORTS, VALID_SCOPES


class TestSchemaV2Columns(unittest.TestCase):
    """Die neuen Spalten existieren und sind befuellbar."""

    def setUp(self):
        self.client = TaskClient(db_path=":memory:", agent_id="test")

    def test_new_columns_exist(self):
        conn = self.client._get_conn()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(rinnsal_tasks)")}
        for col in ("project_path", "root_id", "effort", "scope", "source",
                    "created_by", "assigned_to", "delegation_status"):
            self.assertIn(col, cols, f"Spalte {col} fehlt")

    def test_add_with_effort_and_scope(self):
        t = self.client.add("Encoding fixen", effort="easy", scope="local",
                            project_path="/p/foo", root_id=".AI")
        self.assertEqual(t["effort"], "easy")
        self.assertEqual(t["scope"], "local")
        self.assertEqual(t["project_path"], "/p/foo")
        self.assertEqual(t["root_id"], ".AI")

    def test_defaults_are_safe(self):
        """Ohne Angabe: kein effort (= unklassifiziert), scope lokal."""
        t = self.client.add("Ohne Angaben")
        self.assertEqual(t["effort"], "")
        self.assertEqual(t["scope"], "local")

    def test_invalid_effort_rejected(self):
        with self.assertRaises(ValueError):
            self.client.add("Kaputt", effort="winzig")

    def test_invalid_scope_rejected(self):
        with self.assertRaises(ValueError):
            self.client.add("Kaputt", scope="global")

    def test_valid_values(self):
        self.assertEqual(VALID_EFFORTS, ("easy", "medium", "large", "special"))
        self.assertEqual(VALID_SCOPES, ("local", "central"))


class TestAssignmentSeparatesOrigin(unittest.TestCase):
    """Der Kern von §3.0: Zuweisen darf die Herkunft NICHT zerstoeren."""

    def setUp(self):
        self.client = TaskClient(db_path=":memory:", agent_id="scanner")

    def test_created_by_is_set_from_agent_id(self):
        t = self.client.add("Neu")
        self.assertEqual(t["created_by"], "scanner")

    def test_assign_sets_assigned_to(self):
        t = self.client.add("Neu")
        self.assertTrue(self.client.assign(t["id"], to="claude"))
        got = self.client.get(t["id"])
        self.assertEqual(got["assigned_to"], "claude")
        self.assertEqual(got["delegation_status"], "assigned")

    def test_assign_does_not_overwrite_created_by(self):
        """DER Regressionstest. Der alte Wrapper ueberschrieb agent_id beim
        Zuweisen — damit war unwiederbringlich weg, wer den Task anlegte."""
        t = self.client.add("Neu")
        self.client.assign(t["id"], to="claude")
        got = self.client.get(t["id"])
        self.assertEqual(got["created_by"], "scanner",
                         "Zuweisen hat die Herkunft ueberschrieben!")

    def test_assign_twice_keeps_origin(self):
        t = self.client.add("Neu")
        self.client.assign(t["id"], to="claude")
        self.client.assign(t["id"], to="gemini")
        got = self.client.get(t["id"])
        self.assertEqual(got["created_by"], "scanner")
        self.assertEqual(got["assigned_to"], "gemini")

    def test_assign_unknown_task(self):
        self.assertFalse(self.client.assign(9999, to="claude"))


class TestFiltering(unittest.TestCase):
    """Der Selektor braucht Filter auf effort/scope/project — sonst kann er
    'erst alle easy, dann medium' nicht durchsetzen."""

    def setUp(self):
        self.client = TaskClient(db_path=":memory:", agent_id="test")
        self.client.add("E1", effort="easy", root_id=".AI", project_path="/a")
        self.client.add("E2", effort="easy", root_id=".SW", project_path="/b")
        self.client.add("M1", effort="medium", root_id=".AI", project_path="/a")
        self.client.add("L1", effort="large", scope="central", root_id=".AI")

    def test_filter_by_effort(self):
        self.assertEqual(len(self.client.list(effort="easy")), 2)
        self.assertEqual(len(self.client.list(effort="medium")), 1)

    def test_filter_by_scope(self):
        self.assertEqual(len(self.client.list(scope="central")), 1)
        self.assertEqual(len(self.client.list(scope="local")), 3)

    def test_filter_by_root(self):
        self.assertEqual(len(self.client.list(root_id=".AI")), 3)

    def test_filter_by_project(self):
        self.assertEqual(len(self.client.list(project_path="/a")), 2)

    def test_combined_filter(self):
        """Genau die Abfrage, die der Selektor stellt: leichte, lokale Aufgaben."""
        r = self.client.list(effort="easy", scope="local")
        self.assertEqual(len(r), 2)


class TestMigrationOfExistingDb(unittest.TestCase):
    """Bestandsdatenbanken (v1-Schema) muessen additiv migriert werden —
    ohne Datenverlust und idempotent."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = Path(self.tmp) / "alt.db"
        # v1-Schema von Hand anlegen, wie es in der Live-DB liegt
        conn = sqlite3.connect(str(self.db))
        conn.executescript("""
            CREATE TABLE rinnsal_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                priority TEXT NOT NULL DEFAULT 'medium',
                agent_id TEXT NOT NULL DEFAULT 'default',
                tags TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                done_at TEXT
            );
        """)
        conn.execute(
            "INSERT INTO rinnsal_tasks (title, agent_id, tags, created_at, updated_at) "
            "VALUES ('Alt', 'scanner', 'pipeline=.AI;project=C:/p/x;source=TODO.md', "
            "'2026-01-01', '2026-01-01')")
        conn.commit()
        conn.close()

    def test_migration_adds_columns_without_data_loss(self):
        client = TaskClient(db_path=str(self.db), agent_id="test")
        rows = client.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Alt")
        self.assertEqual(rows[0]["agent_id"], "scanner")
        self.assertEqual(rows[0]["effort"], "")

    def test_migration_is_idempotent(self):
        TaskClient(db_path=str(self.db), agent_id="test")
        TaskClient(db_path=str(self.db), agent_id="test")  # zweimal -> kein Fehler
        client = TaskClient(db_path=str(self.db), agent_id="test")
        self.assertEqual(len(client.list()), 1)

    def test_backfill_from_tags_is_explicit_not_automatic(self):
        """Backfill schreibt in Produktionsdaten. Er darf NIE beim Oeffnen
        automatisch laufen — nur auf ausdruecklichen Aufruf."""
        client = TaskClient(db_path=str(self.db), agent_id="test")
        self.assertEqual(client.list()[0]["project_path"], "",
                         "Backfill lief automatisch — das ist ein stiller Schreibzugriff!")

        n = client.backfill_from_tags()
        self.assertEqual(n, 1)
        row = client.list()[0]
        self.assertEqual(row["root_id"], ".AI")
        self.assertEqual(row["project_path"], "C:/p/x")
        self.assertEqual(row["source"], "TODO.md")
        self.assertEqual(row["tags"], "pipeline=.AI;project=C:/p/x;source=TODO.md",
                         "tags wurden zerstoert — Rueckwaertskompatibilitaet verletzt")

    def test_backfill_sets_created_by_from_agent_id(self):
        client = TaskClient(db_path=str(self.db), agent_id="test")
        client.backfill_from_tags()
        self.assertEqual(client.list()[0]["created_by"], "scanner")


if __name__ == "__main__":
    unittest.main()


class TestClassificationCanBeAddedLater(unittest.TestCase):
    """DIE Sackgasse, die der TASKWRITER-Loop aufgedeckt hat (2026-07-14).

    `add()` konnte effort/scope setzen, `update()` NICHT. Damit waren
    unklassifizierte Altlasten dauerhaft unerreichbar:
      - der TASKSOLVER faesst sie nicht an (effort leer = nicht als leicht
        behandeln),
      - der TASKWRITER konnte sie nicht nachstufen (update kennt effort nicht).
    Ein Zustand, aus dem es keinen Ausweg gab — ausser einem direkten
    SQL-Eingriff, den die Prompts ausdruecklich verbieten.

    Das Nachstufen ist die EINZIGE Bruecke zwischen Altbestand und Selektor.
    """

    def setUp(self):
        self.client = TaskClient(db_path=":memory:", agent_id="scanner")

    def test_effort_can_be_set_later(self):
        task = self.client.add("Altlast ohne Einstufung")
        self.assertEqual(task["effort"], "")

        self.assertTrue(self.client.update(task["id"], effort="easy"))
        self.assertEqual(self.client.get(task["id"])["effort"], "easy")

    def test_scope_and_project_can_be_set_later(self):
        task = self.client.add("Altlast")
        self.client.update(task["id"], scope="central",
                           project_path="/p/x", root_id=".AI", source="TODO.md")
        got = self.client.get(task["id"])
        self.assertEqual(got["scope"], "central")
        self.assertEqual(got["project_path"], "/p/x")
        self.assertEqual(got["root_id"], ".AI")
        self.assertEqual(got["source"], "TODO.md")

    def test_invalid_effort_is_rejected_on_update_too(self):
        """Das Gate darf nicht durch die Hintertuer umgehbar sein."""
        task = self.client.add("X")
        with self.assertRaises(ValueError):
            self.client.update(task["id"], effort="winzig")

    def test_invalid_scope_is_rejected_on_update_too(self):
        task = self.client.add("X")
        with self.assertRaises(ValueError):
            self.client.update(task["id"], scope="global")

    def test_update_does_not_touch_origin(self):
        """Nachstufen darf NICHT die Herkunft ueberschreiben."""
        task = self.client.add("X")
        self.client.update(task["id"], effort="medium")
        self.assertEqual(self.client.get(task["id"])["created_by"], "scanner")

    def test_reclassified_task_becomes_selectable(self):
        """Der eigentliche Beweis: Nach dem Nachstufen SIEHT der Selektor sie."""
        from taskplan.locks import LockView
        from taskplan.selector import SelectorConfig, next_bundle

        task = self.client.add("Altlast", project_path="/p/a", root_id=".AI")
        self.assertIsNone(next_bundle(SelectorConfig(), self.client, LockView()),
                          "Unklassifiziert darf NICHT waehlbar sein")

        self.client.update(task["id"], effort="easy")
        bundle = next_bundle(SelectorConfig(), self.client, LockView())
        self.assertIsNotNone(bundle, "Nach dem Nachstufen muss sie waehlbar sein")
        self.assertEqual(bundle.tasks[0]["id"], task["id"])
