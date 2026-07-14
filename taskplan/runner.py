# -*- coding: utf-8 -*-
"""Die Bruecke zwischen Selektor und Prompt.

Der Selektor ist deterministischer Code — aber die Rollen sind LLM-Prompts. Ohne
einen Weg, den Selektor zu BEFRAGEN, bliebe seine Reihenfolge wirkungslos: Das
Modell wuerde weiter selbst waehlen, und genau das war das Problem.

    python -m taskplan next [--role tasksolver] [--json]

liefert das naechste Buendel: Modus, Aufwand, Root, Projekt, Task-IDs — und den
Lock-Kontext, der fuer dieses Projekt gilt. Der Prompt fragt, der Selektor
antwortet, das LLM urteilt.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .client import TaskClient
from .config import (
    active_roles,
    lock_config,
    model_for,
    selector_config,
    traversal_config,
)
from .locks import CREATE, MODIFY, READ, build_lock_view
from .selector import next_bundle


def _lock_view():
    """Erhebt den Lock-Zustand einmal pro Lauf."""
    locks = lock_config()
    traversal = traversal_config()
    return build_lock_view(
        provider=locks["provider"],
        roots=traversal.roots,
        rule_paths=locks["rule_paths"],
        max_depth=locks["max_depth"],
    ), locks["provider"]


def next_work(role: str = "tasksolver") -> dict:
    """Was ist als Naechstes dran? Der vollstaendige Kontext fuer einen Loop-Lauf."""
    roles = active_roles()
    if role in roles and not roles[role]:
        # Abgeschaltete Rolle bricht SAUBER ab, statt still leerzulaufen.
        return {"role": role, "active": False,
                "reason": f"Rolle '{role}' ist in der Konfiguration abgeschaltet."}

    store = TaskClient()
    view, provider = _lock_view()

    config = selector_config()
    # Der TASKWRITER braucht die Projektliste: Ist alles eingestuft, sucht er
    # das naechste Projekt, das noch GAR KEINE Aufgaben hat. Nur fuer ihn
    # erheben - fuer den Solver waere es verschwendete Zeit.
    if role in ("taskwriter", "maintainer"):
        from .config import discovery_mode, registry_file, traversal_config
        from .traversal import discover_projects
        config.projects = discover_projects(traversal_config(), discovery_mode(),
                                            registry_file())

    bundle = next_bundle(config, store, view, role=role)

    result = {
        "role": role,
        "active": True,
        "model": model_for(role),
        "lock_provider": provider,
        "db": str(store.db_path),
    }

    # Fremde Lock-Regeln gehen als TEXT weiter — nicht ausgewertet, sondern
    # dem LLM zum Lesen gegeben.
    if view.extra_rules:
        result["lock_rules"] = view.extra_rules

    if bundle is None:
        result["bundle"] = None
        if role == "taskwriter":
            result["reason"] = (
                "Nichts zu erfassen: Es gibt keine unklassifizierten Aufgaben mehr, "
                "und jedes erreichbare Projekt hat bereits Aufgaben. Das ist ein "
                "ehrlicher Leerlauf — es wird KEINE Arbeit erfunden."
            )
        elif role == "maintainer":
            result["reason"] = (
                "Kein freies Projekt: Jedes erreichbare Projekt ist entweder "
                "gesperrt oder wird gerade von einer anderen Rolle bearbeitet "
                "(aktive/zugewiesene Aufgabe). Ehrlicher Leerlauf."
            )
        else:
            result["reason"] = (
                "Kein erreichbares Buendel. Moegliche Gruende: alle offenen Aufgaben "
                "sind unklassifiziert (effort leer -> der TASKWRITER muss sie erst "
                "einstufen), zu gross (large/special), zentral (scope=central), oder "
                "ihre Projekte sind gesperrt. Das ist ein ehrlicher Leerlauf — es wird "
                "KEINE Arbeit erfunden, um den Loop zu fuellen."
            )
        return result

    project = Path(bundle.project_path) if bundle.project_path else None
    result["bundle"] = {
        "mode": bundle.mode,
        "effort": bundle.effort,
        "root_id": bundle.root_id,
        "project_path": bundle.project_path,
        "task_ids": [t["id"] for t in bundle.tasks],
        "tasks": [{"id": t["id"], "title": t["title"],
                   "priority": t["priority"], "effort": t["effort"]}
                  for t in bundle.tasks],
    }
    if project is not None:
        result["permissions"] = {
            "read": view.allows(project, READ),
            "create": view.allows(project, CREATE),
            "modify": view.allows(project, MODIFY),
        }
    return result


def run(role: str = "tasksolver", as_json: bool = False) -> int:
    work = next_work(role)

    if as_json:
        print(json.dumps(work, ensure_ascii=False, indent=2))
        return 0 if work.get("bundle") else 1

    if not work["active"]:
        print(f"[{role.upper()}] {work['reason']}")
        return 2

    print(f"[{role.upper()}]")
    print(f"  Datenbank : {work['db']}")
    if work.get("model"):
        print(f"  Modell    : {work['model']}")
    print(f"  Locks     : {work['lock_provider']}")
    print()

    bundle = work.get("bundle")
    if not bundle:
        print("  Nichts zu tun.")
        print()
        print(f"  {work['reason']}")
        return 1

    print(f"  Modus     : {bundle['mode']}")
    print(f"  Aufwand   : {bundle['effort']}")
    print(f"  Root      : {bundle['root_id']}")
    print(f"  Projekt   : {bundle['project_path'] or '(Wurzel)'}")
    print()
    print("  Aufgaben:")
    for task in bundle["tasks"]:
        print(f"    [{task['id']:>3}] {task['priority']:<8} {task['title']}")

    perms = work.get("permissions")
    if perms:
        print()
        print("  Rechte in diesem Projekt:")
        print(f"    lesen   : {'ja' if perms['read'] else 'nein'}")
        print(f"    anlegen : {'ja' if perms['create'] else 'nein'}")
        print(f"    aendern : {'ja' if perms['modify'] else 'NEIN (gesperrt)'}")

    if work.get("lock_rules"):
        print()
        print("  Fremde Lock-Regeln (LIES SIE und wende sie an):")
        for text in work["lock_rules"]:
            print("    " + text.replace("\n", "\n    "))
    return 0
