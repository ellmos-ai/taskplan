# -*- coding: utf-8 -*-
"""Der Selektor: ein Zustandsautomat, kein Prompt-Absatz.

## Warum das hier Code ist und keine Prosa

Die Reihenfolge "erst die Oberflaeche, dann in die Tiefe; erst alle leichten,
dann die mittleren" stand bisher nur als Text im Prompt. Als Text ist sie eine
BITTE, die das Modell in jedem Durchlauf neu auslegt — und genau deshalb ist der
Loop nie in die Tiefe eskaliert, sondern leergelaufen ("0 neue Aufgaben", waehrend
ueber 250 Steuerdateien unterhalb der Wurzeln unangetastet lagen).

Arbeitsteilung:
    Selektor (hier)  WAS ist als naechstes dran — deterministisch, testbar
    LLM (Prompt)     URTEIL — ist das leicht? sicher? bestanden?

## Die Reihenfolge (Nutzervorgabe 2026-07-13)

`effort` ist die PRIMAERE Sortierdimension, die Root-Rotation nur die sekundaere:

    Oberflaechen-Sweep (alle Roots)
      -> Deep-Dive EASY in Root A
      -> zurueck an die Oberflaeche
      -> Deep-Dive EASY in Root B
      -> ... bis KEINE Root mehr easy hat
      -> ERST JETZT: der medium-Durchgang

Begruendung des Nutzers: Leichte Aufgaben entlasten genau die, die tief in einem
Spezialthema stecken. Eine liegengebliebene Kleinigkeit in Projekt A abzuraeumen
ist wertvoller, als in Projekt B in die Tiefe zu gehen. Deshalb existiert die
Unterscheidung easy/harder ueberhaupt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Protocol

from .locks import MODIFY, LockView

SURFACE = "surface"
DEEP = "deep"

# Autonom loesbar sind nur diese. `large`/`special` und alles mit scope=central
# bleiben dem Nutzer vorbehalten — das Gate sitzt hier, nicht im Prompt.
AUTONOMOUS_EFFORTS = ("easy", "medium")


class TaskStore(Protocol):
    """Das Protokoll, gegen das der Selektor arbeitet. Er kennt kein SQL.

    Damit ist der Zustandsautomat unabhaengig davon, WO die Aufgaben liegen —
    und gegen einen In-Memory-Store testbar.
    """

    def list(self, **kwargs) -> list: ...


@dataclass
class SelectorConfig:
    deep_enabled: bool = True
    effort_ceiling: str = "medium"          # easy | medium
    easy_first_globally: bool = True        # easy ueber ALLE Roots vor dem ersten medium
    projects_per_dive: int = 1
    max_bundle_size: int = 3

    def allowed_efforts(self) -> tuple[str, ...]:
        ceiling = self.effort_ceiling if self.effort_ceiling in AUTONOMOUS_EFFORTS else "easy"
        return AUTONOMOUS_EFFORTS[:AUTONOMOUS_EFFORTS.index(ceiling) + 1]


@dataclass
class Bundle:
    """Was der Loop in diesem Durchlauf tut."""
    mode: str                     # surface | deep
    effort: str                   # easy | medium
    root_id: str
    project_path: str
    tasks: List[dict] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.tasks)


def _is_selectable(task: dict, allowed_efforts: tuple[str, ...]) -> bool:
    """Darf der Solver das autonom anfassen?

    Unklassifizierte Aufgaben (`effort` leer) werden NICHT als leicht behandelt.
    Lieber liegen lassen als faelschlich fuer harmlos halten — der TASKWRITER
    klassifiziert sie nach.
    """
    if task.get("scope", "local") == "central":
        return False
    return task.get("effort", "") in allowed_efforts


def _reachable(task: dict, locks: LockView) -> bool:
    """Ist das Projekt der Aufgabe ueberhaupt beschreibbar?

    Gesperrte Projekte werden herausgefiltert, BEVOR das LLM sie sieht — ein
    Lock in einem Projekt sperrt aber nur DIESES, nicht seine Nachbarn und nicht
    die ganze Pipeline. Genau das war der alte Fehler.
    """
    project = task.get("project_path") or ""
    if not project:
        return True   # Ohne Projektbezug (Root-Aufgabe) greift kein Projekt-Lock.
    return locks.allows(Path(project), MODIFY)


def _candidates(store: TaskStore, effort: str, locks: LockView,
                surface: bool) -> List[dict]:
    """Offene, erreichbare Aufgaben eines Aufwandsgrads.

    `surface=True`  -> Aufgaben OHNE project_path (Root-/Wurzelaufgaben)
    `surface=False` -> Aufgaben MIT project_path (in den Projekten)
    """
    tasks = store.list(status="open", effort=effort, limit=500)
    out = []
    for task in tasks:
        if task.get("scope", "local") == "central":
            continue
        has_project = bool(task.get("project_path"))
        if surface == has_project:
            continue
        if not _reachable(task, locks):
            continue
        out.append(task)
    return out


def _bundle_from(tasks: List[dict], mode: str, effort: str,
                 max_size: int) -> Bundle:
    """Bildet das kleinste sinnvolle Buendel: EIN Projekt, bis zu `max_size` Aufgaben.

    Nicht nach Anzahl buendeln und keine unabhaengigen Projekte mischen — ein
    Buendel soll ein ueberpruefbares Zwischenziel ergeben.
    """
    first = tasks[0]
    project = first.get("project_path") or ""
    root = first.get("root_id") or ""
    same = [t for t in tasks
            if (t.get("project_path") or "") == project
            and (t.get("root_id") or "") == root][:max_size]
    return Bundle(mode=mode, effort=effort, root_id=root,
                  project_path=project, tasks=same)


def next_bundle(config: SelectorConfig, store: TaskStore,
                locks: LockView) -> Optional[Bundle]:
    """Was ist als Naechstes dran? None = nichts zu tun.

    Gibt der Selektor None zurueck, endet der Durchlauf EHRLICH als Leerlauf —
    statt dass das Modell sich Arbeit sucht, um den Loop zu fuellen.
    """
    efforts = config.allowed_efforts()

    # effort ist die primaere Dimension: erst ALLE easy (Oberflaeche wie Tiefe),
    # dann erst medium. Deshalb die aeussere Schleife ueber den Aufwand.
    for effort in efforts:
        # 1. Oberflaeche zuerst — sie ist billig und entlastet sofort.
        surface = _candidates(store, effort, locks, surface=True)
        if surface:
            return _bundle_from(surface, SURFACE, effort, config.max_bundle_size)

        # 2. Dann in die Projekte.
        if not config.deep_enabled:
            continue
        deep = _candidates(store, effort, locks, surface=False)
        if deep:
            return _bundle_from(deep, DEEP, effort, config.max_bundle_size)

        # 3. Dieser Aufwandsgrad ist systemweit erschoepft -> naechsthoeherer.
        if not config.easy_first_globally:
            # Sonst waere die Rotation primaer und der Aufwand sekundaer —
            # genau die Reihenfolge, die der Nutzer verworfen hat.
            break

    return None
