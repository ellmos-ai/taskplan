# -*- coding: utf-8 -*-
"""Importierbare TASKPLAN-Workflow-Prompts.

TASKSOLVER und TASKWRITER sind Paketressourcen und damit sowohl aus Python
importierbar als auch für CLI-/Batch-Starter als reale Dateien auflösbar.
"""
from importlib import resources
import os
from pathlib import Path


_WORKFLOW_FILES = {
    "TASKSOLVER": "TASKSOLVER.txt",
    "TASKWRITER": "TASKWRITER.txt",
}


def _normalize_name(name: str) -> str:
    normalized = name.strip().upper()
    if normalized not in _WORKFLOW_FILES:
        available = ", ".join(_WORKFLOW_FILES)
        raise KeyError(f"Unbekannter TASKPLAN-Workflow {name!r}; verfügbar: {available}")
    return normalized


def list_workflows() -> tuple[str, ...]:
    """Liefert die Namen aller gebündelten TASKPLAN-Workflows."""
    return tuple(_WORKFLOW_FILES)


def get_workflow_prompt(name: str) -> str:
    """Lädt einen Workflow-Prompt als UTF-8-Text."""
    filename = _WORKFLOW_FILES[_normalize_name(name)]
    return resources.files("taskplan.prompts").joinpath(filename).read_text(
        encoding="utf-8"
    )


def get_workflow_prompt_path(name: str) -> Path:
    """Liefert den realen Dateipfad eines installierten Workflow-Prompts.

    Setuptools installiert TASKPLAN unverpackt, sodass die Ressource regulär im
    Dateisystem liegt. Ein exotischer Zip-Importer wird bewusst abgelehnt, weil
    externe Starter einen dauerhaft gültigen Pfad benötigen.
    """
    filename = _WORKFLOW_FILES[_normalize_name(name)]
    resource = resources.files("taskplan.prompts").joinpath(filename)
    try:
        path = Path(os.fspath(resource)).resolve()
    except TypeError as exc:  # pragma: no cover - nur bei Zip-Importern
        raise RuntimeError(
            "Der Workflow-Prompt liegt nicht als reale Datei vor"
        ) from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


TASKSOLVER = get_workflow_prompt("TASKSOLVER")
TASKWRITER = get_workflow_prompt("TASKWRITER")

