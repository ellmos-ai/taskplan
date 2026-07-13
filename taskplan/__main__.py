# -*- coding: utf-8 -*-
"""CLI-Einstiegspunkt: `python -m taskplan <befehl>`."""
import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    command = args[0] if args else "help"
    rest = args[1:]

    if command == "doctor":
        from .doctor import run
        return run()

    if command == "next":
        from .runner import run
        role = "tasksolver"
        if "--role" in rest:
            index = rest.index("--role")
            if index + 1 < len(rest):
                role = rest[index + 1]
        return run(role=role, as_json="--json" in rest)

    if command == "prompt":
        from .workflows import get_workflow_prompt
        if not rest:
            print("Nutzung: python -m taskplan prompt <TASKSOLVER|TASKWRITER|MAINTAINER>",
                  file=sys.stderr)
            return 2
        try:
            print(get_workflow_prompt(rest[0]))
        except KeyError as exc:
            print(exc, file=sys.stderr)
            return 2
        return 0

    if command in ("help", "-h", "--help"):
        print("taskplan — Aufgabenverwaltung")
        print()
        print("Befehle:")
        print("  next [--role R] [--json]")
        print("            Fragt den SELEKTOR: was ist als naechstes dran?")
        print("            Liefert Modus (surface/deep), Aufwand, Root, Projekt,")
        print("            Task-IDs und die Rechte in diesem Projekt.")
        print("            Exit 0 = Buendel da, 1 = nichts zu tun,")
        print("            2 = Rolle abgeschaltet.")
        print()
        print("  doctor    Zeigt, welche Datenbank benutzt wird, und warnt bei")
        print("            widerspruechlichen Fundstellen (leere aktive DB,")
        print("            Daten woanders).")
        print()
        print("  prompt <ROLLE>")
        print("            Gibt den Rollen-Prompt aus (TASKSOLVER, TASKWRITER,")
        print("            MAINTAINER).")
        print()
        print("Als Bibliothek:  from taskplan import api as tasks")
        return 0

    print(f"Unbekannter Befehl: {command!r}. `python -m taskplan help` zeigt die Liste.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
