# -*- coding: utf-8 -*-
"""
taskplan -- Eigenstaendiges Task-Modul der .MEMORY-Saeule
=========================================================

Drittes Modul der Gedaechtnis-Saeule (USMC + GARDENER + TASKPLAN,
Entscheidung [U 2026-07-11]). Extrahiert aus rinnsal/tasks; Rinnsal
importiert es seither zurueck (Seam mit gebuendeltem Fallback).

Abgrenzung: Tasks sind KEINE Tickets. Tickets (z. B. das dateibasierte
Ticket-System) koennen ueber api.add_from_ticket() zu Tasks fuehren,
muessen es aber nicht -- beide Systeme bleiben getrennt.
"""
__version__ = "0.3.0"

from .client import (  # noqa: F401
    TaskClient,
    TASK_SCHEMA_SQL,
    SCHEMA_V2_COLUMNS,
    VALID_STATUSES,
    VALID_PRIORITIES,
    VALID_EFFORTS,
    VALID_SCOPES,
    get_default_db_path,
    count_tasks_in,
)

from .config import (  # noqa: F401
    load_config,
    find_config_file,
    configured_db_path,
)

from .workflows import (  # noqa: F401
    TASKSOLVER,
    TASKWRITER,
    get_workflow_prompt,
    get_workflow_prompt_path,
    list_workflows,
)
