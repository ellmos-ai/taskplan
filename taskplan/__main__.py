# -*- coding: utf-8 -*-
"""CLI-Einstiegspunkt: `python -m taskplan <befehl>`."""
import sys


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    command = args[0] if args else "help"

    if command == "doctor":
        from .doctor import run
        return run()

    if command in ("help", "-h", "--help"):
        print("taskplan — Aufgabenverwaltung")
        print()
        print("Befehle:")
        print("  doctor    Zeigt, welche Datenbank benutzt wird, und warnt bei")
        print("            widerspruechlichen Fundstellen (leere aktive DB,")
        print("            Daten woanders).")
        print()
        print("Als Bibliothek:  from taskplan import api as tasks")
        return 0

    print(f"Unbekannter Befehl: {command!r}. `python -m taskplan help` zeigt die Liste.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
