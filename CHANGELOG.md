# Changelog

## 0.2.0 — 2026-07-11

### Added
- TASKSOLVER und TASKWRITER als gebündelte, importierbare Workflow-Prompts.
- `get_workflow_prompt()`, `get_workflow_prompt_path()` und `list_workflows()`.
- Paketdaten-Konfiguration und Tests für Import, Lookup, UTF-8 und reale Promptpfade.

## 0.1.0 — 2026-07-11

### Added
- Initial extraction from `rinnsal/tasks` (decision [U 2026-07-11],
  `.MEMORY` stack: USMC + GARDENER + TASKPLAN).
- `taskplan.client.TaskClient` — SQLite task CRUD (table `rinnsal_tasks`
  kept for data compatibility), WAL mode, `:memory:` support.
- `taskplan.api` — singleton convenience API (`init`, `add`, `list`, `done`,
  `next_task`, `active_tasks`, …).
- `api.add_from_ticket()` — the only ticket→task bridge (tag `ticket:<id>`);
  tasks and tickets remain separate systems.
- Own default DB resolution: `TASKPLAN_DB` > `RINNSAL_DB` >
  `~/.taskplan/taskplan.db` (the rinnsal facade injects its own default).
- Test suite (17 tests, ported from rinnsal + default-path and ticket-bridge
  coverage).
