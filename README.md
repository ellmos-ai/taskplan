# taskplan

Standalone SQLite task module — the third pillar of the `.MEMORY` stack
(**USMC** curated session memory · **GARDENER** organic memory + cross-source
index · **TASKPLAN** tasks). Extracted from `rinnsal/tasks` on 2026-07-11
(decision [U 2026-07-11]); rinnsal now imports it back through a seam with a
bundled fallback. Zero external dependencies (stdlib only), Python ≥ 3.10.

## Scope: Tasks are NOT tickets

Tasks (this module) and tickets (file-based ticket systems such as
`_control-center/_TICKETS`, IDs like `T-YYYYMMDD-NN`) are **separate systems**.
Tickets *can* lead to tasks, but do not have to. The only bridge is
`api.add_from_ticket(ticket_id, title, ...)`, which creates a regular task
tagged `ticket:<id>`. taskplan never imports, mirrors, or manages tickets.

## Usage

```python
from taskplan import api as tasks

tasks.init(agent_id="opus")
tasks.add("Implement feature X", priority="high")
tasks.add_from_ticket("T-20260711-01", "Fix reported crash")

for t in tasks.list():
    print(f"[{t['id']}] {t['title']} ({t['status']})")

tasks.done(1)
```

## Importierbare Workflow-Prompts

TASKPLAN liefert die systemweiten Rollen **TASKSOLVER** und **TASKWRITER** als
Paketressourcen mit. Dadurch verwenden Python-Integrationen, Agenten-Starter und
das lokale Control-Center dieselbe kanonische Promptfassung:

```python
from taskplan import (
    TASKSOLVER,
    TASKWRITER,
    get_workflow_prompt,
    get_workflow_prompt_path,
    list_workflows,
)

print(list_workflows())
print(get_workflow_prompt("TASKSOLVER"))
print(get_workflow_prompt_path("TASKWRITER"))
```

- **TASKSOLVER** erledigt pro Loop ein zusammenhängendes Aufgaben-Bundle in
  genau einem Projekt und markiert Tasks erst nach empirischer Prüfung als erledigt.
- **TASKWRITER** erkennt und formalisiert pro Loop Aufgaben in genau einem
  Projekt, führt sie aber nicht aus.
- Tasks bleiben von Tickets getrennt; beide Workflows benutzen TASKPLAN als
  Task-Speicher und respektieren lokale Projekt-, Lock- und Rechtekonventionen.

Or with an explicit client:

```python
from taskplan import TaskClient
client = TaskClient(db_path="~/.rinnsal/scanner_tasks.db", agent_id="scanner")
```

## Database resolution (when no `db_path` is given)

1. env `TASKPLAN_DB`
2. env `RINNSAL_DB` (compatibility)
3. `~/.taskplan/taskplan.db`

## Compatibility

- Table name stays **`rinnsal_tasks`** so existing databases
  (`~/.rinnsal/rinnsal.db`, `~/.rinnsal/scanner_tasks.db`) and consumers keep
  working without migration.
- **rinnsal** (`rinnsal.tasks.client`) prefers taskplan when installed and
  injects its own default DB (`~/.rinnsal/rinnsal.db` / rinnsal config);
  without taskplan it falls back to its bundled copy. The import path
  `rinnsal.tasks.client.TaskClient` stays stable (used by the homebase
  `hb_state_task_*` seam and the `_tasks` scanner).
- Statuses: `open`, `active`, `done`, `cancelled` · Priorities: `critical`,
  `high`, `medium`, `low`.

## Tests

```
python -m unittest discover -s tests -v
```

## License

MIT — Lukas Geiger
