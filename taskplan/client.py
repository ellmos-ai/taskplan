# -*- coding: utf-8 -*-
"""
TaskClient -- SQLite-basiertes Task-Management
================================================

Kanonische Implementierung des Task-Systems (extrahiert aus rinnsal/tasks,
2026-07-11). Zero external dependencies (nur stdlib).

Kompatibilitaet: Der Tabellenname bleibt `rinnsal_tasks`, damit bestehende
DBs (~/.rinnsal/rinnsal.db, ~/.rinnsal/scanner_tasks.db) und Consumer
(rinnsal-Seam, homebase hb_state_task_*, _tasks-Scanner) ohne Migration
weiterlaufen.

Default-DB-Aufloesung (nur wenn kein db_path uebergeben wird):
    1. ENV TASKPLAN_DB
    2. ENV RINNSAL_DB (Kompatibilitaet)
    3. ~/.taskplan/taskplan.db
Die Rinnsal-Fassade (rinnsal.tasks.client) injiziert stattdessen ihren
eigenen Default (~/.rinnsal/rinnsal.db bzw. Rinnsal-Config).

Author: Lukas Geiger
License: MIT
"""
import os
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime


TASK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rinnsal_tasks (
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

CREATE INDEX IF NOT EXISTS idx_tasks_status ON rinnsal_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON rinnsal_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON rinnsal_tasks(agent_id);
"""

VALID_STATUSES = ('open', 'active', 'done', 'cancelled')
VALID_PRIORITIES = ('critical', 'high', 'medium', 'low')


def get_default_db_path() -> str:
    """Loest den Default-Pfad zur Task-DB auf.

    Reihenfolge:
    1. ENV TASKPLAN_DB
    2. ENV RINNSAL_DB (Kompatibilitaet mit bestehenden Rinnsal-Setups)
    3. ~/.taskplan/taskplan.db (Verzeichnis wird bei Bedarf angelegt)

    Explizit uebergebene Pfade (db_path-Parameter) haben immer Vorrang und
    laufen nicht durch diese Funktion.
    """
    env_path = os.environ.get("TASKPLAN_DB", "") or os.environ.get("RINNSAL_DB", "")
    if env_path:
        return str(Path(env_path).expanduser())
    taskplan_dir = Path.home() / ".taskplan"
    taskplan_dir.mkdir(exist_ok=True)
    return str(taskplan_dir / "taskplan.db")


class TaskClient:
    """
    Task-Management Client mit eigener SQLite-Tabelle.

    Verwendung:
        client = TaskClient()  # Default: siehe get_default_db_path()
        client.add("Feature X implementieren", priority="high")
        tasks = client.list()
        client.done(1)
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        agent_id: str = "default"
    ):
        if db_path is None:
            db_path = get_default_db_path()
        self._is_memory = str(db_path) == ':memory:'
        self.db_path = db_path if self._is_memory else Path(db_path)
        self.agent_id = agent_id
        self._shared_conn = None
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._is_memory:
            if self._shared_conn is None:
                # check_same_thread=False: die eine geteilte Connection wird
                # auch aus Poll-Threads (Telegram/Discord on_message) genutzt.
                self._shared_conn = sqlite3.connect(
                    ':memory:', check_same_thread=False)
                self._shared_conn.execute("PRAGMA foreign_keys=ON")
            return self._shared_conn
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _close_conn(self, conn: sqlite3.Connection) -> None:
        if not self._is_memory:
            conn.close()

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        try:
            conn.executescript(TASK_SCHEMA_SQL)
            conn.commit()
        finally:
            if not self._is_memory:
                self._close_conn(conn)

    def add(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        tags: str = ""
    ) -> Dict:
        """Erstellt einen neuen Task."""
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"priority muss einer von {VALID_PRIORITIES} sein")

        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                INSERT INTO rinnsal_tasks
                    (title, description, status, priority, agent_id, tags, created_at, updated_at)
                VALUES (?, ?, 'open', ?, ?, ?, ?, ?)
            """, (title, description, priority, self.agent_id, tags, now, now))
            conn.commit()
            return {
                'id': cursor.lastrowid,
                'title': title,
                'description': description,
                'status': 'open',
                'priority': priority,
                'agent_id': self.agent_id,
                'tags': tags,
                'created_at': now,
            }
        finally:
            self._close_conn(conn)

    def list(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        include_done: bool = False,
        limit: int = 50
    ) -> List[Dict]:
        """Listet Tasks auf."""
        conn = self._get_conn()
        try:
            conditions = []
            params: list = []

            if status:
                conditions.append("status = ?")
                params.append(status)
            elif not include_done:
                conditions.append("status NOT IN ('done', 'cancelled')")

            if priority:
                conditions.append("priority = ?")
                params.append(priority)

            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(limit)

            rows = conn.execute(f"""
                SELECT id, title, description, status, priority,
                       agent_id, tags, created_at, updated_at, done_at
                FROM rinnsal_tasks
                {where}
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5
                    END,
                    created_at ASC
                LIMIT ?
            """, params).fetchall()

            return [self._row_to_dict(r) for r in rows]
        finally:
            self._close_conn(conn)

    def get(self, task_id: int) -> Optional[Dict]:
        """Holt einen einzelnen Task."""
        conn = self._get_conn()
        try:
            row = conn.execute("""
                SELECT id, title, description, status, priority,
                       agent_id, tags, created_at, updated_at, done_at
                FROM rinnsal_tasks WHERE id = ?
            """, (task_id,)).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            self._close_conn(conn)

    def done(self, task_id: int) -> bool:
        """Markiert einen Task als erledigt."""
        return self._set_status(task_id, 'done')

    def activate(self, task_id: int) -> bool:
        """Setzt einen Task auf 'active'."""
        return self._set_status(task_id, 'active')

    def cancel(self, task_id: int) -> bool:
        """Storniert einen Task."""
        return self._set_status(task_id, 'cancelled')

    def reopen(self, task_id: int) -> bool:
        """Oeffnet einen erledigten/stornierten Task erneut."""
        return self._set_status(task_id, 'open')

    def update(
        self,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[str] = None
    ) -> bool:
        """Aktualisiert Task-Felder."""
        if priority and priority not in VALID_PRIORITIES:
            raise ValueError(f"priority muss einer von {VALID_PRIORITIES} sein")

        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            fields = ["updated_at = ?"]
            params: list = [now]

            if title is not None:
                fields.append("title = ?")
                params.append(title)
            if description is not None:
                fields.append("description = ?")
                params.append(description)
            if priority is not None:
                fields.append("priority = ?")
                params.append(priority)
            if tags is not None:
                fields.append("tags = ?")
                params.append(tags)

            params.append(task_id)
            cursor = conn.execute(
                f"UPDATE rinnsal_tasks SET {', '.join(fields)} WHERE id = ?",
                params
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self._close_conn(conn)

    def delete(self, task_id: int) -> bool:
        """Loescht einen Task permanent."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM rinnsal_tasks WHERE id = ?", (task_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self._close_conn(conn)

    def count(self) -> Dict:
        """Zaehlt Tasks nach Status."""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT status, COUNT(*) FROM rinnsal_tasks GROUP BY status
            """).fetchall()
            result = {s: 0 for s in VALID_STATUSES}
            for status, cnt in rows:
                result[status] = cnt
            result['total'] = sum(result.values())
            return result
        finally:
            self._close_conn(conn)

    def _set_status(self, task_id: int, status: str) -> bool:
        now = datetime.now().isoformat()
        conn = self._get_conn()
        try:
            done_at = now if status == 'done' else None
            cursor = conn.execute(
                "UPDATE rinnsal_tasks SET status = ?, updated_at = ?, done_at = ? WHERE id = ?",
                (status, now, done_at, task_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self._close_conn(conn)

    @staticmethod
    def _row_to_dict(row) -> Dict:
        return {
            'id': row[0], 'title': row[1], 'description': row[2],
            'status': row[3], 'priority': row[4], 'agent_id': row[5],
            'tags': row[6], 'created_at': row[7], 'updated_at': row[8],
            'done_at': row[9],
        }
