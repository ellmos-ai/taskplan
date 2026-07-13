# TASKPLAN — Umbaukonzept: Von der Oberfläche in die Projekte

**Stand:** 2026-07-13 · **Status:** Konzept, nicht umgesetzt · **Autor:** Claude (Analyse + Entwurf), Auftrag Lukas Geiger

---

## 1. Befund: Warum der Loop an der Oberfläche bleibt

### 1.1 Die Rotationseinheit ist die Pipeline — eine Projektebene existiert nirgends

Die einzige „Projektliste" des Systems steht in `_control-center/_tasks/CLAUDE.md`, Abschnitt 5:
eine **flache Tabelle mit 13 Einträgen**, alle auf Top-Level-Pipeline-Ebene
(`.UNI`, `.AI`, `.COMPUTE`, `.HARDWARE`, `.PRODUCTION`, `.RESEARCH`, `.ROBLOX`, `.SOFTWARE`,
`.UMBRUCH`, `.GITHUBBOT`, `.SYNC`, `.WISSEN`, `.USR`).

Darunter gibt es **keine zweite Ebene**. Die Prompts sagen „Analysiere genau EIN Projekt"
(`TASKWRITER.txt` Z. 6) und „in genau EINEM Projekt" (`TASKSOLVER.txt` Z. 4) — aber die einzige
Liste, auf die sie sich beziehen können, sind diese 13 Pipelines. **Der Loop setzt Pipeline =
Projekt.** Die Begriffe sind im gesamten System nirgends definiert und werden konflatiert.

### 1.2 Die Flachheit vererbt sich vom Writer zum Solver

TASKWRITER liest die Root-Steuerdateien einer Pipeline und formalisiert daraus Aufgaben.
TASKSOLVER rotiert **nicht** selbst — er konsumiert die TASKPLAN-Queue nach Priorität und Alter.

Damit gilt: **Der Solver kann nur so tief arbeiten, wie der Writer geschrieben hat.**
Schreibt der Writer nur Pipeline-Root-Aufgaben, putzt der Solver nur Pipeline-Root-Dokus.
Das ist exakt das beobachtete Verhalten. Der Solver ist nicht das Problem — er ist das Symptom.

### 1.3 Empirischer Beleg: Der Loop ist an der Oberfläche fertig und läuft leer

Aus `TASKSOLVER_REG.WORKSTATION.txt` — was der Solver in 16 Tagen tatsächlich getan hat:
Encoding-Fixes, Pfadkorrekturen (`Users\User` → `lukas`), `STATE.md`-Aktualisierung,
`README`-Status, `releases.json`-Drift, TODO-Konsistenz. **Ausnahmslos Pflege der Root-Dokumentation.**

Aus `TASKWRITER_REG.WORKSTATION.txt`, Zyklus 3:

> **Loop 30 — .HARDWARE:** „Ergebnis: 0 neue Aufgaben."
> **Loop 31 — .PRODUCTION:** „Ergebnis: 0 neue Aufgaben."

Der Loop dreht sich im Kreis über 13 Wurzeln, deren Dokumentation er inzwischen sauber gepflegt
hat — und findet nichts mehr. **Er verhungert nicht an Aufgaben, sondern an Sichtbarkeit.**

### 1.4 Der unsichtbare Backlog — quantifiziert

Zahl der Steuerdateien (`TODO`/`ROADMAP`/`AUFGABEN`/`TASK`/`AKTIONSPLAN`) **unterhalb** der
Pipeline-Wurzel, die der Loop nie zu Gesicht bekommt:

| Pipeline | Root (sichtbar) | Tiefer (unsichtbar) |
|---|---|---|
| `.SOFTWARE` | 0 | **101** |
| `.RESEARCH` | 1 | **74** |
| `.AI` | 0 | **55** |
| `.ROBLOX` | 0 | **21** |
| `.UNI` | 1 | 0 |

**Der Loop sieht 13 Wurzeln. Real existieren über 250 Steuerdateien.** In der Task-DB liegen
nach 16 Tagen ganze **38 Tasks**, davon 29 erledigt. `.ROBLOX` (21 Spiele) kommt **kein einziges
Mal** vor. `.SOFTWARE` erscheint nur als Wurzel — obwohl die Registry dort 82+ Projekte führt.

### 1.5 Der Loop hat die Frage selbst gestellt — und korrekt nicht geraten

Das ist der wichtigste Befund, und er entlastet das System:

> `TASKWRITER_REG` (.SOFTWARE): „**82+ Unterprojekte NICHT einzeln geprüft** — Tiefenscan auf
> späteren Zyklus oder Subprojekt-Rotation verschoben (**User-Frage offen**)."
>
> Ende Zyklus 2: „Soll TASKWRITER ab Zyklus 3 auch in Unterprojekte scannen (Subprojekt-Tiefe),
> oder bleibt der Root-Level-Scan Standard? **Bisher keine Nutzerentscheidung dazu vorhanden** —
> weiterhin Root-Level-Scan als Default beibehalten."

Der Loop hat die Lücke dreimal protokolliert und die Entscheidung **nicht selbst getroffen**, weil
sein Qualitätsgate „keine erfundenen Nutzerentscheidungen" genau das verbietet. Das ist korrektes
Verhalten an einer fehlenden Spezifikation, kein Defekt. **Die fehlende Entscheidung ist der
Blocker — nicht der Code.**

### 1.6 Locks sind NICHT die Ursache (Korrektur einer naheliegenden Annahme)

Die Vermutung, Locks würden ganze Pipelines blockieren, trifft **nicht** den Kern:

- Die Lock-Auswertung ist bereits **granular**: `_scripts/lock_scan.py` scannt rekursiv bis Tiefe 4,
  `_scripts/permissions.py::evaluate()` wertet `LOCK.permissions.json` **ordner-scoped** aus
  (`deny > ask > allow > default`).
- **Gegenbeweis** aus `TASKWRITER_REG` Loop 19 (`.RESEARCH/.LAB`): 12 Lab-Ordner, davon
  **6 aktive Locks in Sub-Projekten von 4 Labs** — korrekt erkannt und einzeln umgangen.
  Aber: **die ~8 ungelockten Labs wurden trotzdem nicht betreten.**

Der Loop steigt also selbst dort nicht ab, wo **kein** Lock liegt. Der Root-Level-Default ist die
Ursache, nicht der Lock.

**Berechtigt ist die Kritik an zwei anderen Stellen:**

1. Die *geschriebene* Regel in `_tasks/CLAUDE.md` (Z. 28–29, 173–174) ist grob:
   „Sonderfälle (`.SOFTWARE`, `.ROBLOX`, `.RESEARCH`) … Lock → Aufgaben zurückstellen,
   **Verzeichnis als ‚deferred' abhaken**". Das *ist* eine Ganz-Pipeline-Abschaltung — sie war
   nur nicht der Hauptgrund.
2. **Die Lese/Schreib-Unterscheidung fehlt komplett.** Nirgends steht, dass ein Lock nur das
   Schreiben betrifft und Analyse immer erlaubt ist. Das ist die eigentliche Lücke im Lock-Modell.

### 1.7 Das Datenmodell kann „leicht/mittel/groß" gar nicht ausdrücken

Das reale Schema (`taskplan/client.py`, Tabelle `rinnsal_tasks`):

```sql
id, title, description, status, priority, agent_id, tags, created_at, updated_at, done_at
```

| Gebraucht | Vorhanden? |
|---|---|
| Aufwand / Schwierigkeit (easy/medium/large) | **Existiert nicht** — weder Spalte noch Tag |
| Projekt / Pfad | **Keine Spalte** — nur Freitext in `tags`: `project=…` |
| Scope (lokal / zentral) | **Existiert nicht** |
| Typ / Provenienz | **Keine Spalte** — nur Freitext in `tags`: `source=…` |

Der Wunsch „erst leichte, dann mittlere; große zentrale nie autonom" ist mit dem heutigen Schema
**nicht modellierbar**. Er ließe sich nur als Prosa in den Prompt schreiben — und würde damit dem
Ermessen des Modells überlassen statt erzwungen.

Verschärfend: Der CLI-Wrapper `scanner_tasks.py` macht `--pipeline` zum **Pflichtfeld** und
`--project` zum **optionalen Beiwerk**. Die Oberflächlichkeit ist bis in die Werkzeugsignatur
zementiert.

### 1.8 Nebenbefund: gespaltene Datenbank (akut)

Es existieren **drei** ENV-Namen für dieselbe Sache und **zwei** Datenbanken:

| DB | Zustand |
|---|---|
| `~/.rinnsal/scanner_tasks.db` | **38 Tasks — die Live-DB** (via `$SCANNER_TASKS_DB` im Wrapper) |
| `~/.taskplan/taskplan.db` | **0 Tasks — leer** (Modul-Default, greift wenn `TASKPLAN_DB`/`RINNSAL_DB` fehlen) |

Auf diesem System ist **keine** der ENV-Variablen gesetzt. **Wer der Prompt-Anweisung „Nutze die
TASKPLAN-API" wörtlich folgt (`from taskplan import api`), schreibt in die leere DB** und sieht
keinen einzigen bestehenden Task. Nur der Wrapper trifft die richtige.

Präzise benannt: Es geht **nicht** um Datenverlust — nichts wird gelöscht. Es geht um **verwaiste
Schreibvorgänge in einer gespaltenen Datenbank**: Tasks landen in einer DB, die niemand liest, und
der bestehende Bestand ist für den Schreiber unsichtbar. Sollte unabhängig vom übrigen Umbau sofort
geschlossen werden.

### 1.9 Die Rinnsal-Ablösung: datentechnisch trivial, codetechnisch der eigentliche Aufwand

Rinnsal soll durch drei gekapselte Module ersetzt werden — **USMC** (Sessions + kuratiertes Memory),
**Gardener** (inhaltliche Suche über alles) und **TASKPLAN** (Aufgaben). Der geprüfte Ist-Stand:

**Zu migrieren ist praktisch nichts.**

| Datenbank | Memory/Sessions | Tasks |
|---|---|---|
| `~/.rinnsal/scanner_tasks.db` | — | **38 Zeilen** (echte Nutzdaten) |
| `.OS/rinnsal/rinnsal.db` (im Repo, März) | **0 / 0 / 0 / 0** | 0 |
| `~/.rinnsal/rinnsal.db` (laut Config der Default) | **existiert überhaupt nicht** | — |
| `~/.usmc/usmc_memory.db` | **0 Zeilen** | — |
| Gardeners `gardener.db` + `user.db` | **0 Zeilen** (nie geseedet) | — |

**Rinnsals Memory-Subsystem wurde auf diesem System nie benutzt.** Sämtliche `usmc_*`-Tabellen sind
in *allen* Datenbanken leer. Die einzigen echten Nutzdaten sind die **38 Tasks** — und selbst die
brauchen keine Migration, weil TASKPLAN den Tabellennamen `rinnsal_tasks` bewusst kompatibel hält
(`client.py:9-11`). Es ist ein **Consumer-Umschwenk, keine Datenwanderung**.

**Eine verbreitete Annahme ist falsch herum:** USMC übernimmt nichts *aus* Rinnsal — **Rinnsal hat
von USMC abgeschrieben.** `rinnsal/memory/__init__.py:5`: *„Based on USMC."* Rinnsal **baut das
USMC-Schema nach**, statt das Modul zu importieren; daher heißen seine Tabellen `usmc_facts`,
`usmc_sessions` usw. Es sind zwei Kopien desselben Schemas. Rinnsals eigene TODO benennt das offen
(*„USMC importieren statt duplizieren — vermeidet Schema-Drift"*), Checkbox offen.

**Stand der Dreiteilung:**

| Modul | Extraktion | Rinnsal-Seam | Daten |
|---|---|---|---|
| **TASKPLAN** | ✅ erledigt 2026-07-11 | ✅ `rinnsal/tasks/client.py` | 38 Zeilen |
| **USMC** | ⚠️ Modul existiert — aber Rinnsal dupliziert es weiter | ❌ offen | 0 |
| **GARDENER** | ⚠️ Konzeptionell fertig, **außer Betrieb** | — | 0 |

**Gardener ist der Engpass.** Sein `pip install -e` ist gebrochen (einer der drei, die der
Pfadwechsel am 2026-07-11 zerlegt hat) — `import gardener` löst versehentlich auf den *Datenordner*
`~/gardener` auf statt auf den Code. Beide DBs sind leer, `seed.py` lief nie. Der geplante
Cross-Source-Index (systemweite Suche über `bach.db`, Claude-Memories, `.remember`) ist vollständig
beschlossen — und zu **null Prozent** implementiert.

**Der eigentliche Aufwand liegt im Code, nicht in den Daten:**

1. Rinnsals `memory/`-Duplikat durch einen echten `usmc`-Import ersetzen (offene Checkbox).
2. `usmc` überhaupt erst pip-installieren, Gardeners Install reparieren.
3. Den **einzigen echten Import-Consumer** umhängen: `ellmos-stack/services/telegram_gateway.py`
   (`from rinnsal import memory` / `import tasks`).

> **Warnung, die ein Deployment sonst zerlegt:** `MODULE-CONSUMER-INVENTORY.md` behauptet, `usmc`
> und `taskplan` seien regulär installiert. **Installiert ist nur `taskplan`.** `usmc` und `rinnsal`
> sind es *nicht* — `from rinnsal import memory` würde auf einem frischen Interpreter schlicht
> fehlschlagen. Das Inventar ist falsch und gehört korrigiert.

**Konsequenz für TASKPLAN (dieses Konzept):** Der Umbau ist von der Rinnsal-Ablösung **entkoppelt**.
TASKPLAN ist bereits extrahiert; es muss nur (a) den DB-Split beheben (§1.8) und (b) den
Tabellennamen `rinnsal_tasks` **weiterhin kompatibel halten**, solange `ellmos-unified-gui` und
`ellmos-homebase-mcp` direkt darauf lesen. Ein Umbenennen der Tabelle wäre ein eigener, koordinierter
Schritt — **nicht Teil dieses Umbaus.**

### 1.10 Keine Konfiguration für Tiefe oder Modus

Es gibt **keinen einzigen Schalter**. Tiefe und Verhalten stecken ausschließlich in Prompt-Prosa und
der Rotationstabelle. `scan_projects.py` hätte ein `--max-depth` (Default 4) — die Loops rufen es
nicht auf; `TASKWRITER.txt` Z. 45 verbietet sogar „keinen unbeschränkten Baumscan".

### 1.11 Nebenbefund: Das Modell ist im Starter festgenagelt

`START-TASKSOLVER.bat` und `START-TASKWRITER.bat` starten beide fest mit `--model claude-sonnet-5`.
Das Modell selbst ist korrekt (Sonnet 5 und Opus 4.8 sind die gesetzten Zielmodelle) — **das Problem
ist die Verdrahtung**: Die Modellwahl steckt hartcodiert in zwei `.bat`-Dateien der Installation,
statt in der Modul-Konfiguration zu stehen.

Damit ist sie (a) nicht ohne Datei-Edit änderbar, (b) nicht pro Rolle differenzierbar (ein leichter
Maintainer-Durchlauf braucht kein Denkmodell) und (c) nicht nutzerneutral — ein anderer Anwender
erbt Lukas' Modellwahl. Gehört als Achse in die Config (§7).

---

## 2. Die Leitentscheidung des Umbaus

> **Die Auswahl gehört als deterministischer Selektor in den Code — nicht als Prosa in den Prompt.**

Die surface→deep- und easy→harder-Verschachtelung ist ein **Zustandsautomat**. Als Prompt-Text
formuliert bleibt sie eine Bitte, die das Modell in jedem Durchlauf neu interpretiert — genau das
hat den Loop leerlaufen lassen, statt ihn in die Tiefe eskalieren zu lassen.

**Arbeitsteilung:**

| Instanz | Zuständig für |
|---|---|
| **Selektor (Code)** | *Was* ist als Nächstes dran: Modus, Pipeline, Projekt, Bundle. Deterministisch, testbar, reproduzierbar. |
| **LLM (Prompt)** | *Urteil*: Ist das leicht? Ist es sicher? Ist es bestanden? Ist die Aufgabe echt? |

Der Selektor entscheidet nicht über Qualität, das LLM nicht über Reihenfolge.

---

## 3. Datenmodell (Fundament — alles andere hängt daran)

Additive Migration, keine bestehende Spalte ändert sich (`rinnsal_tasks` bleibt der Tabellenname):

```sql
ALTER TABLE rinnsal_tasks ADD COLUMN project_path TEXT DEFAULT '';   -- Leaf-Projekt, nicht Pipeline
ALTER TABLE rinnsal_tasks ADD COLUMN root_id      TEXT DEFAULT '';   -- Pipeline/Root (neutral benannt)
ALTER TABLE rinnsal_tasks ADD COLUMN effort       TEXT DEFAULT '';   -- easy | medium | large | special
ALTER TABLE rinnsal_tasks ADD COLUMN scope        TEXT DEFAULT 'local'; -- local | central
ALTER TABLE rinnsal_tasks ADD COLUMN source       TEXT DEFAULT '';   -- Provenienz (raus aus tags)
CREATE INDEX IF NOT EXISTS idx_tasks_effort  ON rinnsal_tasks(effort);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON rinnsal_tasks(project_path);
```

Die bestehende `tags`-Freitextkonvention (`pipeline=…;project=…;source=…`) wird beim ersten Lauf
**einmalig in die neuen Spalten migriert** und bleibt rückwärtskompatibel befüllt.

### 3.1 Die Aufwandsklassen — die Definition entscheidet über alles

| Klasse | Definition | Für TASKSOLVER |
|---|---|---|
| **easy** | Eine Datei oder wenige, ein Projekt, reversibel, mechanisch prüfbar (Encoding, Pfad, Doku-Drift, Lint, fehlender Test) | **Immer** |
| **medium** | Mehrere Dateien in **einem** Projekt, kein Architekturwechsel, testbar (kleines Feature, Bugfix mit Testabdeckung, Refactor) | **Nur wenn keine easy mehr** |
| **large** | Architektur, projektübergreifend, Migration, Schema-Wechsel | **Nie autonom** |
| **special** | Braucht Domänenwissen, Fachentscheidung, Credentials, externe/irreversible Aktion (Release, Upload, Mail, Kauf, Löschung) | **Nie autonom** |
| **scope = central** | Betrifft geteilte Infrastruktur, auf die andere Projekte bauen | **Nie autonom**, unabhängig vom Aufwand |

**Gate im Selektor (nicht im Prompt):**
`solver_darf(task) := effort ∈ {easy, medium} ∧ scope = local ∧ effort ≤ config.effort_ceiling`

Wer klassifiziert? Der **TASKWRITER** beim Anlegen (er hat den Projektkontext gelesen). Der
**TASKSOLVER** darf eine Klasse **nach oben** korrigieren, wenn sich eine Aufgabe beim Anfassen als
größer erweist — dann legt er sie zurück, statt sie durchzuboxen. **Nach unten korrigieren darf er
nie** (sonst hebelt er sein eigenes Gate aus).

---

## 4. Der Selektor: Zustandsautomat statt Prosa

Der vom Nutzer beschriebene Ablauf — **wörtlich als Spezifikation**, der Rücksprung zur Oberfläche
zwischen zwei Deep-Dives ist Teil der Spec, kein Overhead:

```
        ┌────────────────────────────────────────────────┐
        │  SURFACE SWEEP (alle Roots)                    │
        │  Root-Aufgaben erkennen + easy abarbeiten       │
        └───────────────────────┬────────────────────────┘
                                ▼
        ┌────────────────────────────────────────────────┐
        │  DEEP DIVE — EASY, in EINE Root                │
        │  leichte Aufgaben in den Projekten dieser Root │
        └───────────────────────┬────────────────────────┘
                                │ keine easy mehr in dieser Root
                                ▼
                    ZURÜCK ZUM SURFACE SWEEP
                                │
                                ▼
        ┌────────────────────────────────────────────────┐
        │  DEEP DIVE — EASY, in die NÄCHSTE Root         │
        └───────────────────────┬────────────────────────┘
                                │
                               ...  bis KEINE Root mehr easy hat
                                ▼
        ╔════════════════════════════════════════════════╗
        ║  ERST JETZT: HARDER-DURCHGANG (medium)         ║
        ║  gleiche Reihenfolge, gleiche Rücksprünge      ║
        ╚════════════════════════════════════════════════╝
```

**Die Regel, die das erzwingt — und ihre Begründung (Nutzervorgabe 2026-07-13):**

> **Leichte Aufgaben werden global erschöpft, bevor irgendwo eine mittlere angefasst wird.**
> Nicht easy→harder *innerhalb* einer Root, sondern easy über **alle** Roots, dann harder über alle.

Der Grund ist nicht Ordnungsliebe, sondern **Entlastung**: Leichte, sofort abarbeitbare Aufgaben
nehmen genau denjenigen Ballast ab, die gerade tief in einem speziellen Thema eines Projekts
stecken. Eine liegengebliebene Kleinigkeit in Projekt A ist wertvoller abgeräumt als eine mittlere
Aufgabe in Projekt B vertieft — **deshalb** existiert die Unterscheidung easy/harder überhaupt.

Daraus folgt für den Selektor: `effort` ist die **primäre** Sortierdimension, die Root-Rotation die
sekundäre. Ein `medium`-Task ist erst wählbar, wenn systemweit **kein** `easy`-Task mehr offen und
erreichbar ist (nicht gelockt, nicht blockiert).

**Kernfunktion im Package (deterministisch, ohne LLM, unit-testbar):**

```python
def next_bundle(config: LoopConfig, db: TaskClient, locks: LockView) -> Bundle | None:
    """Liefert (modus, root, projekt, tasks) — oder None, wenn nichts erlaubt/übrig ist."""
```

Gibt der Selektor `None` zurück, endet der Durchlauf **ehrlich als Leerlauf** — statt dass das
Modell sich Arbeit sucht, um den Loop zu füllen.

### 4.1 Die Ebenen — nutzerneutral konfigurierbar, nicht fest verdrahtet

Bisher gibt es **gar keine** Definition von „Pipeline" vs. „Projekt" — die Begriffe werden
konflatiert (§1.1). Der Umbau definiert sie nicht *inhaltlich* (das wäre wieder Lukas' Installation
im Modul), sondern **strukturell als konfigurierbare Ebenen**:

| Ebene | Bedeutung | Woher |
|---|---|---|
| **Root** | Einstiegspunkt der Traversierung (hier: Pipeline-Überordner / Slot) | Umgebungs-Config |
| **Projekt** | Arbeitseinheit unterhalb einer Root | Erkannt über **Marker** |

> Ein **Projekt** ist ein Verzeichnis unterhalb einer Root, das mindestens einen **Projekt-Marker**
> trägt. Marker sind konfigurierbar; Default: eine eigene Steuerdatei (`TODO.md`, `ROADMAP.md`,
> `AUFGABEN.*`), ein `.git`-Verzeichnis oder ein Build-/Paket-Manifest (`pyproject.toml`,
> `package.json`, …).

**Die Ebenenzahl ist selbst eine Einstellung, kein Gesetz.** Manche Installationen haben
Root → Projekt; andere Root → Slot → Unterprojekt; eine flache Installation hat nur Roots. Das
Modell ist deshalb eine **Liste von Ebenen**, nicht ein fest verdrahtetes Zweierpaar:

```toml
# Beispiel: dreistufig (Überordner → Slot → Unterprojekt)
[[traversal.levels]]
name    = "root"        # Einstiegspunkte aus dem Roots-Inventar
[[traversal.levels]]
name    = "slot"        # Zwischenebene, rein gruppierend
markers = []            # keine Marker noetig — jedes Unterverzeichnis ist ein Slot
[[traversal.levels]]
name    = "project"     # die eigentliche Arbeitseinheit
markers = ["TODO.md", "ROADMAP.md", ".git", "pyproject.toml"]
is_work_unit = true     # <- auf DIESER Ebene wird gearbeitet und gelockt
```

Wer nur zwei Ebenen braucht, lässt `slot` weg. Wer vier braucht, hängt eine an. **Genau eine Ebene
trägt `is_work_unit = true`** — sie bestimmt, was ein „Projekt" im Sinne von Rotation, Lock-Scope
und `project_path` ist.

Damit **findet** der Selektor Projekte, statt sie in einer handgepflegten Liste nachschlagen zu
müssen — und das Modul bleibt frei von den Namen und der Tiefe einer konkreten Installation.

---

## 5. Das Lock-Modell: drei Achsen statt eines Schalters

Ein Lock ist heute faktisch ein Ja/Nein. Das ist zu grob. Der Umbau macht ihn dreiachsig:

| Aktion | Regel |
|---|---|
| **Lesen / Analysieren** | **Immer erlaubt**, auch bei fremdem Lock. Ein Lock schützt vor Änderung, nicht vor Kenntnisnahme. Analyse darf nie blockiert werden. |
| **Neue Datei anlegen** | **In der Regel erlaubt** (kein Konflikt mit fremder Arbeit an bestehenden Dateien). Ausnahme: `LOCK.user*.txt` und explizites `deny` in `LOCK.permissions.json`. |
| **Bestehende Datei ändern** | **Nur ohne fremden Lock im Scope.** Hier greift `deny > ask > allow`. |

**Und entscheidend — der Lock-Scope wird gelesen, nicht vermutet:**

> Ein Lock in `.RESEARCH/.LAB/.RH/PP__RH_Even_Dominance/` sperrt **dieses Projekt**, nicht die
> Pipeline `.RESEARCH` und nicht ihre 74 Geschwister.

Sobald Rotation und Tasks auf Projektebene laufen, löst sich das ohnehin: Ein Lock trifft dann sein
Projekt statt zwölf Nachbarn. **Das Lock-Problem und das Oberflächen-Problem sind derselbe Defekt** —
sie werden in einem Zug behoben. Die grobe „Verzeichnis deferred abhaken"-Regel in
`_tasks/CLAUDE.md` (Z. 28–29, 173–174) wird ersatzlos gestrichen.

Der `LockView` wird **einmal pro Durchlauf** aus `lock_scan.py`/`permissions.py` aufgebaut und dem
Selektor übergeben — der filtert gesperrte Projekte heraus, bevor das LLM sie überhaupt sieht.

---

## 6. Die dritte Rolle: MAINTAINER

Gleiche Oberfläche/Tiefe-Logik, eigenes Register, eigener Prompt. Aufgabe: Projektdateien und
Verzeichnisse sauber halten.

| Aufgabe | Regel |
|---|---|
| Falsch abgelegte Dateien an den richtigen Ort verschieben | Zielort muss **belegt** sein, nicht geraten. Kein Verschieben in gelockte Ziele. |
| `TODO.md` → `DONE.md` leeren | **Nur erledigte Punkte** umziehen. Historie bleibt erhalten. |
| Inkonsistenzen zwischen Steuerdateien auflösen | „Nach aktuellster Änderung" gilt **nur für Status-/Zustandsfelder**. Kuratierter Inhalt gewinnt nie per Zeitstempel. |
| Architekturverzeichnisse in Dateien aktualisieren | Gegen den realen Baum, nicht gegen die Erinnerung. |
| Zu lange Logs kürzen („cut and clue") | **Archivieren vor Kürzen.** Nie hart löschen. |
| Probleme erkennen und für den Nutzer sichtbar machen | Eigene Datei, z. B. `BEFUNDE.md` — keine stillen Reparaturen an Zweifelsfällen. |

**Der Maintainer ist die schreib-lastigste und potenziell destruktivste Rolle** (Dateien
verschieben, TODOs leeren, Logs schneiden). Er braucht das Lock-Modell aus §5 am dringendsten und
bekommt zusätzlich ein hartes Gate:

> **Nie hart löschen. Immer archivieren oder in den Papierkorb (reversibel).**
> Präzedenzfall ist TASKWRITERs eigenes Gate „Entferne nichts blind".

---

## 7. Konfiguration: orthogonale Achsen statt Modus-Enum

Der Nutzerwunsch („nur Oberfläche / Oberfläche plus deep / nur easy deep / easy plus harder deep
/ usw.") ist keine Liste von Modi, sondern ein Satz **unabhängiger Achsen**. Als Enum bräuchte man
für jedes „usw." einen neuen Wert; als Achsen ist die Kombinatorik geschenkt.

Die Achsen: **Tiefe** (Oberfläche / Tiefe) × **Aufwandsdecke** (easy / medium) × **aktive Rollen**
(einzeln an/aus) × **Ausführungsform** (getrennt / zusammengelegt) × **Aufgabenquellen** (welche
Dateien, welches Format).

**Rollen einzeln abschaltbar:** Steht eine Rolle auf `false` und wird ihr Starter trotzdem
aufgerufen, **bricht der Durchlauf beim Start sauber ab** (mit Meldung, kein stiller Leerlauf) —
so kann ein Starter im Autostart bleiben, ohne dass man ihn entfernen muss.

**„3-in-1" (`combined = true`):** Ein Worker durchläuft alle *aktiven* Rollen nacheinander im selben
Kontext, statt drei getrennte Instanzen zu starten. Der Reiz ist der geteilte Kontext — wer gerade
als Writer ein Projekt gelesen hat, kann es als Solver ohne erneutes Einlesen bearbeiten.
Die Schalter kombinieren sich frei: **`maintainer = false` + `combined = true` ergibt genau den
2-in-1-Worker** aus deinem Beispiel, ohne dass es dafür einen eigenen Modus bräuchte.

> **Default: alle drei Rollen aktiv, getrennte Instanzen** (`combined = false`).
> Die Rollentrennung ist eine Qualitätsgrenze — der Writer soll *nicht* ausführen, was er gerade
> selbst formuliert hat (TASKWRITERs Gate „Keine Aufgaben-Ausführung durch TASKWRITER"). Im
> `combined`-Modus muss diese Grenze **innerhalb** des Workers als Phasenwechsel erhalten bleiben:
> erst vollständig schreiben, dann als Solver neu bewerten — nicht beides in einem Zug vermischen.

```toml
# taskplan.toml — Modul-Verhalten (nutzerneutral, gehört zum Package)
[loop]
depth          = "surface+deep"   # surface | surface+deep | deep
effort_ceiling = "medium"         # easy | medium   (large/special nie autonom)

[loop.deep]
enabled             = true   # false = reiner Oberflaechenbetrieb (heutiges Verhalten)
easy_first_globally = true   # easy ueber ALLE Roots erschoepfen, erst dann medium (§4)
return_to_surface   = true   # zwischen zwei Deep-Dives zurueck an die Oberflaeche
roots_per_dive      = 1      # genau eine Root pro Tauchgang
projects_per_dive   = 1      # genau ein Projekt pro Durchlauf

# --- Rollen: einzeln abschaltbar, optional zusammengelegt -------------------
[roles]
taskwriter = true
tasksolver = true
maintainer = true    # false => Maintainer-Start bricht sofort sauber ab

# "3-in-1": EIN Worker deckt alle aktiven Rollen nacheinander ab, statt drei
# getrennte Instanzen. Kombiniert sich frei mit den Schaltern oben —
# maintainer=false + combined=true ergibt faktisch einen 2-in-1-Worker.
combined = false     # Default: getrennte Instanzen, alle drei aktiv

# --- Aufgabenquellen: welche Dateien enthalten Aufgaben? --------------------
# Nicht hartcodiert — andere Installationen nutzen andere Konventionen.
# NICHT zu verwechseln mit traversal.levels.markers (§4.1): Marker sagen
# "hier IST ein Projekt", Sources sagen "hier STEHEN Aufgaben drin".
# Ueberschneidung ist normal (TODO.md ist oft beides), Gleichsetzung nicht.
[[sources]]
file   = "TODO.md"
format = "markdown_checkbox"    # - [ ] offen / - [x] erledigt
[[sources]]
file   = "AUFGABEN.txt"
format = "plain_lines"          # eine Aufgabe je nicht-leerer Zeile
[[sources]]
file   = "ROADMAP.md"
format = "markdown_checkbox"
read_only = true                # Kontext/Ziele — hier schreibt der Writer nicht hinein
[[sources]]
glob   = "*.todo"               # statt festem Namen auch Muster moeglich
format = "plain_lines"

# Eingebaute Parser: markdown_checkbox | markdown_bullet | plain_lines |
# yaml_frontmatter | jsonl. Reicht das nicht, registriert die Installation
# einen eigenen Parser — das Modul erzwingt keine Textkonvention.

[locks]
read_always_allowed = true
create_allowed      = true   # neue Datei in gelocktem Ordner
modify_requires_free_scope = true

# Modellwahl gehoert ins Modul, nicht in den Starter (§1.11) — pro Rolle
# einstellbar, mit neutralem Default. Die Starter lesen sie nur noch aus.
[models]
default    = "claude-sonnet-5"
taskwriter = "claude-sonnet-5"   # Analyse/Formalisierung
tasksolver = "claude-opus-4-8"   # Umsetzung, braucht mehr Urteil
maintainer = "claude-sonnet-5"   # mechanische Pflege
```

**Das Roots-Inventar wird NICHT neu erfunden — es existiert bereits.**
`OneDrive/_scripts/lock_roots.json` führt heute schon **17 Roots**, `default_max_depth: 4`,
`shallow_depth: 2` und `skip_dirs` — also fast exakt die Traversierungs-Konfiguration, die der
Selektor braucht. Eine zweite Roots-Liste würde unweigerlich auseinanderlaufen und verstößt gegen
die stehende Regel „keine Duplikate erzeugen".

> **Vorgabe:** Der Selektor **liest `lock_roots.json`** (ggf. um `project_markers` erweitert) als
> einzige Quelle der Wahrheit für Roots und Tiefe. Das Package bringt nur das **Schema** und einen
> Loader mit; die Datei selbst bleibt Umgebungsdatum.

**Ungeklärte Diskrepanz — braucht eine Nutzerentscheidung (siehe §10):**
Es gibt **17 Lock-Roots**, aber **13 Rotations-Pipelines**. Beide Listen beschreiben „wo das System
arbeitet", sind aber nicht deckungsgleich. Zu klären, bevor der Selektor gebaut wird:

- Sind das dieselben Orte mit unterschiedlichem Zweck (Lock-Scan **überwacht** breiter,
  Rotation **bearbeitet** enger)? → dann braucht ein Root ein Feld `traversal: true|false`.
- Oder sind vier Roots schlicht nie in die Rotation aufgenommen worden? → dann ist die
  13er-Liste unvollständig, und der Umbau schließt die Lücke.

Das ist eine echte Designentscheidung, keine Formalie — sie bestimmt, welche vier Bereiche der Loop
heute überhaupt nicht anfasst.

### 7.1 Der Speicher ist austauschbar (Backend-Abstraktion)

Heute ist der Speicher hart verdrahtet: SQLite, Tabelle `rinnsal_tasks`, Pfad aus drei ENV-Namen.
Ein anderer Anwender kann TASKPLAN damit **nur** benutzen, wenn er auch unsere DB benutzt — und ein
Anwender, der seine Aufgaben längst in einem anderen System führt, kann die Loops gar nicht erst
einsetzen.

> **Vorgabe:** Der Speicher ist ein **Adapter hinter einem schmalen Protokoll**. Unser SQLite-Backend
> ist der empfohlene Default — aber es ist *ein* Backend, nicht *das* Backend.

Das Protokoll ist bewusst klein, damit fremde Systeme realistisch anschließbar bleiben:

```python
class TaskStore(Protocol):
    def add(self, task: Task) -> Task: ...
    def get(self, task_id: str) -> Task | None: ...
    def list(self, *, status=None, effort=None, project_path=None,
             scope=None, limit=50) -> list[Task]: ...
    def update(self, task_id: str, **fields) -> bool: ...
    def find_duplicate(self, root_id, source, title) -> Task | None: ...
```

Der **Selektor arbeitet ausschließlich gegen dieses Protokoll** — er kennt kein SQL. Damit ist der
Zustandsautomat (§4) unabhängig davon, wo die Aufgaben liegen.

```toml
[storage]
backend = "sqlite"                 # sqlite (empfohlen) | files | custom
path    = "~/.taskplan/taskplan.db"   # nur fuer sqlite; EIN Ort, ENV-Wildwuchs entfaellt (§1.8)

# Alternative: Aufgaben bleiben in den Projektdateien, keine DB
# backend = "files"                # Quelle der Wahrheit sind die [[sources]]-Dateien selbst

# Alternative: fremdes System (Issue-Tracker, eigene DB, ...)
# backend      = "custom"
# entry_point  = "meinpaket.tasks:MeinStore"   # muss TaskStore erfuellen
```

**Zwei Backends bringt das Modul selbst mit:**

| Backend | Wahrheit liegt in | Für wen |
|---|---|---|
| `sqlite` *(Default, empfohlen)* | einer DB | Wer Status, Aufwand und Historie über viele Projekte hinweg abfragen will |
| `files` | den `[[sources]]`-Dateien | Wer keine DB will — Aufgaben leben in `TODO.md` & Co., die Loops lesen und schreiben dort direkt |

Das `files`-Backend ist mehr als eine Geste: Es macht TASKPLAN für ein einzelnes Repo brauchbar,
ohne dass jemand eine Datenbank aufsetzen muss. Preis: kein `effort`-Index, also langsamere globale
Auswahl — bei wenigen Projekten irrelevant.

**Grenze, die ehrlich benannt gehört:** Ein fremdes Backend kann `effort` und `scope` (§3) nicht
zwingend abbilden. Fehlen sie, degradiert der Selektor kontrolliert — er behandelt unklassifizierte
Aufgaben als `medium`/`local` und **meldet das**, statt still ein anderes Verhalten zu zeigen.

### 7.2 Nutzerneutralität — die Trennlinie

| Ins Package (`taskplan/`) | In die Installation (Env) |
|---|---|
| Traversierung, Selektor, Zustandsautomat | Die konkreten Roots (`.UNI`, `.AI`, …) |
| Aufwandsklassen und ihre Gates | Pfade, Host-Namen, DB-Ort |
| Lock-Achsenmodell | `MANIFEST.md`-Regelkette |
| Die drei Rollen-Prompts | Register-Dateien, Rotationsstand |
| Config-**Schema** + Defaults | Die konkreten Config-**Werte** |
| `TaskStore`-Protokoll + die 2 mitgelieferten Backends | Backend-Wahl, fremde Adapter |
| Die eingebauten Datei-Parser | Welche Aufgabendateien es hier gibt |

> **Warnung an die Umsetzung:** Dieses Konzept ist aus Lukas' Logs abgeleitet. Es darf **kein**
> Pipeline-Name (`.UNI`, `.AI`, `.SOFTWARE`, …) und **kein** Host-Name (`WORKSTATION`) im Package
> landen. Die 13er-Liste ist Installationsdatum, keine Modul-Eigenschaft.

---

## 8. Umsetzungsreihenfolge (die Kopplung gibt sie vor)

**Der Writer ist der Upstream-Fix.** Der Solver-Deep-Mode verhungert ohne Deep-Backlog — erst muss
jemand die Projektebene formalisiert haben, bevor jemand sie abarbeiten kann.

| # | Schritt | Warum zuerst |
|---|---|---|
| **0** | **DB-Split beheben** (§1.8): `TASKPLAN_DB` auf die Live-DB setzen, ENV-Namen konsolidieren | Sofort, unabhängig. Sonst schreibt jeder API-Nutzer in die leere DB. |
| **1** | **Datenmodell** (§3): Spalten + Migration der `tags`-Konvention | Fundament — ohne `effort` kein Gate. |
| **1b** | **`TaskStore`-Protokoll** (§7.1) + SQLite-Backend dahinter | Muss **vor** dem Selektor stehen, sonst wird gegen SQL gebaut statt gegen das Protokoll — und die Austauschbarkeit ist nachträglich nicht mehr einzuziehen. |
| **2** | **Ebenen-Definition + Traversierung** (§4.1) | Ohne „was ist ein Projekt" kein Abstieg. |
| **3** | **Selektor** (§4) als Code, gegen `TaskStore`, mit Unit-Tests | Das Herzstück. Ersetzt Prompt-Prosa. Testbar gegen einen In-Memory-Store. |
| **4** | **Lock-Achsenmodell** (§5) + `LockView` | Muss vor dem ersten Deep-Dive stehen. |
| **5** | **TASKWRITER auf Tiefe** — klassifiziert `effort` beim Anlegen | Füllt den Deep-Backlog. |
| **6** | **TASKSOLVER auf Tiefe** — konsumiert mit Gate | Kann erst jetzt sinnvoll tauchen. |
| **7** | **MAINTAINER** (§6) als dritte Rolle | Neue Funktion, baut auf 1–4 auf. |
| **8** | **Config** (§7) + Neutralitäts-Audit | Schließt den Umbau ab. |

---

## 9. Woran man misst, ob der Umbau gewirkt hat

| Kennzahl | Heute | Ziel |
|---|---|---|
| Tasks mit `project_path` auf Leaf-Ebene | 0 | > 100 |
| Berührte Projekte in `.SOFTWARE` | 0 von 82+ | wächst monoton |
| Berührte Projekte in `.ROBLOX` | 0 von 21 | > 0 |
| Deep-Dives im Register | 0 | ≥ 1 pro Zyklus |
| Loops mit „0 neue Aufgaben" | 2 von 2 (Zyklus 3) | nur bei echt leerem Backlog |
| Wegen Lock übersprungene **Pipelines** | mehrfach | 0 (nur noch **Projekte**) |

---

## 10. Offene Punkte für den Nutzer

1. **`effort_ceiling` im Regelbetrieb:** `medium` (Vorschlag) oder konservativ `easy`?
2. **Wer klassifiziert bei Altlasten?** Die 8 offenen Tasks haben kein `effort`. Vorschlag: der
   erste TASKWRITER-Deep-Lauf klassifiziert sie nach.
3. **`.ROBLOX` und `.SOFTWARE`** waren als „Sonderfälle mit eigener Pipeline" von der Rotation
   faktisch ausgenommen. Sollen sie im Deep-Mode regulär mitlaufen?
4. **Maintainer-Autonomie:** Darf er Dateien eigenständig verschieben, oder nur vorschlagen und der
   Nutzer bestätigt? (Vorschlag: verschieben ja, aber nur reversibel und mit Beleg für den Zielort.)
5. **17 Lock-Roots vs. 13 Rotations-Pipelines** (§7): dieselben Orte mit unterschiedlichem Zweck —
   oder vier Bereiche, die nie in die Rotation aufgenommen wurden und deshalb heute unbearbeitet
   bleiben?
6. **Welche Rolle bekommt welches Modell?** (§7, `[models]`) — offen ist **allein die Zuordnung**,
   nicht die Modellwahl selbst (siehe unten). Vorschlag: TASKSOLVER auf Opus 4.8 (er setzt um und
   braucht Urteil), TASKWRITER und MAINTAINER auf Sonnet 5. Passt die Aufteilung?

### Bereits entschieden (2026-07-13, nicht mehr offen)

- **Harder-Modus:** easy wird **global über alle Roots** erschöpft, erst dann läuft der
  medium-Durchgang (§4). Begründung: leichte Aufgaben entlasten die, die tief in Spezialthemen
  arbeiten — deshalb existiert die Unterscheidung.
- **Ebenen:** nicht fest verdrahtet, sondern als konfigurierbare Ebenenliste
  (Root → *optional* Slot → Projekt), mit genau einer Arbeitsebene (§4.1).
- **Welche Modelle:** Sonnet 5 und Opus 4.8 sind gesetzt. **Wo die Wahl steht:** in der Modul-Config,
  nicht im Starter (§1.11, §7). Offen bleibt allein die Zuordnung pro Rolle — Frage 6.
- **Rollen und Modi:** einzeln abschaltbar; `combined` legt sie in *einem* Worker zusammen.
  Default: alle drei aktiv und getrennt (§7).
- **Aufgabenquellen und Speicher:** beides konfigurierbar statt hartcodiert (§7, §7.1).
