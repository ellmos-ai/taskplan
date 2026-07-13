# -*- coding: utf-8 -*-
"""Vier Marker-Kategorien, einzeln schaltbar und kombinierbar.

Ein einzelner Marker reicht nie fuer alle Systeme: `TODO.md` liegt auch in
Ordnern, die keine Projekte sind; `.git` fehlt bei allem, was nie versioniert
wurde; und manche Strukturen erkennt man nur am Ordnernamen.
"""
import tempfile
import unittest
from pathlib import Path

from taskplan.markers import (
    DEFAULT_FLAG_FILE, DirPatternRule, ExpressionError, FileRule, FlagFileRule,
    GitRule, MarkerRules, SubdirRule, clear_flag, evaluate_expression, set_flag,
)
from taskplan.traversal import TraversalConfig, discover_projects


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


class TestDirPatterns(unittest.TestCase):
    """Ordnermerkmale: Punkt am Anfang, GROSSSCHREIBUNG — verbreitete Konventionen."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.rule = DirPatternRule(enabled=True)

    def test_leading_dot(self):
        self.assertTrue(self.rule.matches(_mkdir(self.tmp / ".RESEARCH")))

    def test_uppercase(self):
        self.assertTrue(self.rule.matches(_mkdir(self.tmp / "DEV_Foo")))
        self.assertTrue(self.rule.matches(_mkdir(self.tmp / "REL-PUB_Bar")))

    def test_ordinary_name_does_not_match(self):
        self.assertFalse(self.rule.matches(_mkdir(self.tmp / "notizen")))
        self.assertFalse(self.rule.matches(_mkdir(self.tmp / "src")))

    def test_disabled_never_matches(self):
        rule = DirPatternRule(enabled=False)
        self.assertFalse(rule.matches(_mkdir(self.tmp / ".RESEARCH")))

    def test_require_all_demands_every_pattern(self):
        """Punkt UND Grossschreibung — beides."""
        rule = DirPatternRule(enabled=True, require_all=True,
                              patterns=(r"^\.", r"[A-Z]"))
        self.assertTrue(rule.matches(_mkdir(self.tmp / ".AI")))
        self.assertFalse(rule.matches(_mkdir(self.tmp / ".klein")))

    def test_custom_pattern(self):
        rule = DirPatternRule(enabled=True, patterns=(r"^proj-",))
        self.assertTrue(rule.matches(_mkdir(self.tmp / "proj-alpha")))
        self.assertFalse(rule.matches(_mkdir(self.tmp / ".AI")))


class TestFileRule(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_claude_md_is_a_marker(self):
        project = _mkdir(self.tmp / "p")
        _touch(project / "CLAUDE.md")
        self.assertTrue(FileRule(enabled=True).matches(project))

    def test_require_all(self):
        """Streng: CLAUDE.md UND TODO.md muessen beide da sein."""
        rule = FileRule(enabled=True, names=("CLAUDE.md", "TODO.md"),
                        require_all=True)
        project = _mkdir(self.tmp / "p")
        _touch(project / "CLAUDE.md")
        self.assertFalse(rule.matches(project))
        _touch(project / "TODO.md")
        self.assertTrue(rule.matches(project))


class TestSubdirRule(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_dot_claude_subdir(self):
        project = _mkdir(self.tmp / "p")
        _mkdir(project / ".claude")
        self.assertTrue(SubdirRule(enabled=True).matches(project))

    def test_git_is_not_in_the_subdir_list(self):
        """`.git` hat eine EIGENE Kategorie — es ist ein staerkeres Signal als
        irgendein Subordner und soll im Ausdruck einzeln ansprechbar sein."""
        project = _mkdir(self.tmp / "p")
        _mkdir(project / ".git")
        self.assertFalse(SubdirRule(enabled=True).matches(project))
        self.assertTrue(GitRule(enabled=True).matches(project))

    def test_a_file_named_like_the_subdir_does_not_count(self):
        project = _mkdir(self.tmp / "p")
        _touch(project / ".claude")   # Datei, kein Verzeichnis
        self.assertFalse(SubdirRule(enabled=True).matches(project))


class TestGitRule(unittest.TestCase):
    """Git als eigene Kategorie: Wer `git init` gemacht hat, hat eine Grenze
    gezogen."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = _mkdir(self.tmp / "p")

    def test_repo(self):
        _mkdir(self.project / ".git")
        self.assertTrue(GitRule(enabled=True).matches(self.project))

    def test_worktree_or_submodule_has_git_as_a_FILE(self):
        """Die Tuecke: In Worktrees und Submodulen ist `.git` eine DATEI.
        Eine reine Verzeichnispruefung wuerde sie alle uebersehen."""
        _touch(self.project / ".git")
        self.assertTrue(GitRule(enabled=True).matches(self.project))

    def test_worktrees_can_be_excluded(self):
        _touch(self.project / ".git")
        self.assertFalse(
            GitRule(enabled=True, require_worktree_root=True).matches(self.project))

    def test_no_git(self):
        self.assertFalse(GitRule(enabled=True).matches(self.project))

    def test_disabled(self):
        _mkdir(self.project / ".git")
        self.assertFalse(GitRule(enabled=False).matches(self.project))


class TestExpression(unittest.TestCase):
    """UND, ODER, NICHT, Klammern — weil "alles oder eines" nicht reicht."""

    def _eval(self, expression, **values):
        base = {"dir_patterns": False, "files": False, "subdirs": False,
                "git": False, "flag_file": False}
        base.update(values)
        return evaluate_expression(expression, base)

    def test_and(self):
        self.assertTrue(self._eval("dir_patterns AND files",
                                   dir_patterns=True, files=True))
        self.assertFalse(self._eval("dir_patterns AND files", dir_patterns=True))

    def test_or(self):
        self.assertTrue(self._eval("dir_patterns OR files", files=True))
        self.assertFalse(self._eval("dir_patterns OR files"))

    def test_not(self):
        self.assertTrue(self._eval("NOT git"))
        self.assertFalse(self._eval("NOT git", git=True))

    def test_wenn_nicht_combination(self):
        """"Ein Projekt ist, was eine CLAUDE.md hat, aber KEIN Git-Repo ist"."""
        self.assertTrue(self._eval("files AND NOT git", files=True))
        self.assertFalse(self._eval("files AND NOT git", files=True, git=True))

    def test_parentheses_change_precedence(self):
        # ohne Klammern: NOT > AND > OR
        self.assertTrue(self._eval("git OR files AND subdirs", git=True))
        # mit Klammern erzwungen
        self.assertFalse(self._eval("(git OR files) AND subdirs", git=True))
        self.assertTrue(self._eval("(git OR files) AND subdirs",
                                   git=True, subdirs=True))

    def test_realistic_rule(self):
        """Der Fall des Nutzers: GROSS geschriebener Ordner MIT CLAUDE.md —
        oder irgendetwas mit einer Flagdatei."""
        expression = "(dir_patterns AND files) OR flag_file"
        self.assertTrue(self._eval(expression, dir_patterns=True, files=True))
        self.assertFalse(self._eval(expression, dir_patterns=True))
        self.assertTrue(self._eval(expression, flag_file=True))

    def test_german_keywords(self):
        self.assertTrue(self._eval("files UND NICHT git", files=True))
        self.assertTrue(self._eval("files ODER git", git=True))

    def test_unknown_marker_is_an_error_not_a_silent_false(self):
        """Ein Tippfehler in der Konfiguration darf nicht still zu 'trifft nie'
        werden — dann fande der Loop schweigend gar nichts mehr."""
        with self.assertRaises(ExpressionError):
            self._eval("dateien AND git")

    def test_broken_expression_raises(self):
        with self.assertRaises(ExpressionError):
            self._eval("(files AND git")
        with self.assertRaises(ExpressionError):
            self._eval("files AND")

    def test_expression_wins_over_combine(self):
        tmp = Path(tempfile.mkdtemp())
        project = _mkdir(tmp / "DEV_Alpha")   # nur Ordnermuster, keine Datei
        rules = MarkerRules(
            dir_patterns=DirPatternRule(enabled=True),
            files=FileRule(enabled=True, names=("CLAUDE.md",)),
            subdirs=SubdirRule(enabled=False),
            git=GitRule(enabled=False),
            flag_file=FlagFileRule(enabled=False),
            combine="any",                             # waere True
            expression="dir_patterns AND files",       # ist False
        )
        self.assertFalse(rules.matches(project))

    def test_flag_keeps_special_status_unless_named(self):
        tmp = Path(tempfile.mkdtemp())
        project = _mkdir(tmp / "unauffaellig")
        set_flag(project)
        # Ausdruck erwaehnt flag_file NICHT -> Sonderstatus greift
        rules = MarkerRules(files=FileRule(enabled=True),
                            expression="files AND git")
        self.assertTrue(rules.matches(project))
        # Ausdruck erwaehnt flag_file -> der Nutzer hat die Kontrolle
        rules = MarkerRules(files=FileRule(enabled=True),
                            expression="flag_file AND git")
        self.assertFalse(rules.matches(project))


class TestFlagFile(unittest.TestCase):
    """Die ausdrueckliche Ansage — sie schlaegt jede Heuristik."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = _mkdir(self.tmp / "voellig-unauffaellig")

    def test_set_and_match(self):
        set_flag(self.project)
        self.assertTrue(FlagFileRule(enabled=True).matches(self.project))

    def test_flag_wins_even_when_nothing_else_matches(self):
        rules = MarkerRules(
            dir_patterns=DirPatternRule(enabled=True),
            files=FileRule(enabled=True),
            subdirs=SubdirRule(enabled=True),
            git=GitRule(enabled=True),
            combine="all",          # STRENG: alles muesste treffen
        )
        self.assertFalse(rules.matches(self.project))
        set_flag(self.project)
        self.assertTrue(rules.matches(self.project),
                        "Die Flagdatei wurde von combine='all' ueberstimmt!")

    def test_clear(self):
        set_flag(self.project)
        self.assertTrue(clear_flag(self.project))
        self.assertFalse(FlagFileRule(enabled=True).matches(self.project))

    def test_clear_without_flag(self):
        self.assertFalse(clear_flag(self.project))

    def test_custom_flag_name(self):
        set_flag(self.project, name="itsa.project")
        self.assertTrue(FlagFileRule(enabled=True, name="itsa.project")
                        .matches(self.project))
        self.assertFalse(FlagFileRule(enabled=True, name=DEFAULT_FLAG_FILE)
                         .matches(self.project))

    def test_flag_can_be_disabled(self):
        """Manche Nutzer wollen keine fremden Dateien in ihren Projekten."""
        set_flag(self.project)
        self.assertFalse(FlagFileRule(enabled=False).matches(self.project))


class TestCombine(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Ordner mit Grossschreibung UND CLAUDE.md
        self.both = _mkdir(self.tmp / "DEV_Alpha")
        _touch(self.both / "CLAUDE.md")
        # nur Grossschreibung
        self.only_dir = _mkdir(self.tmp / "DEV_Beta")
        # nur CLAUDE.md
        self.only_file = _mkdir(self.tmp / "gamma")
        _touch(self.only_file / "CLAUDE.md")

    def _rules(self, combine):
        return MarkerRules(
            dir_patterns=DirPatternRule(enabled=True),
            files=FileRule(enabled=True, names=("CLAUDE.md",)),
            subdirs=SubdirRule(enabled=False),
            git=GitRule(enabled=False),
            flag_file=FlagFileRule(enabled=False),
            combine=combine,
        )

    def test_any_is_generous(self):
        rules = self._rules("any")
        self.assertTrue(rules.matches(self.both))
        self.assertTrue(rules.matches(self.only_dir))
        self.assertTrue(rules.matches(self.only_file))

    def test_all_is_strict(self):
        rules = self._rules("all")
        self.assertTrue(rules.matches(self.both))
        self.assertFalse(rules.matches(self.only_dir))
        self.assertFalse(rules.matches(self.only_file))

    def test_no_active_rule_matches_nothing(self):
        rules = MarkerRules(
            dir_patterns=DirPatternRule(enabled=False),
            files=FileRule(enabled=False),
            subdirs=SubdirRule(enabled=False),
            git=GitRule(enabled=False),
            flag_file=FlagFileRule(enabled=False),
        )
        self.assertFalse(rules.matches(self.both))


class TestRulesInTraversal(unittest.TestCase):
    """Die Regeln greifen in der echten Projektsuche."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = _mkdir(self.tmp / ".X")
        _touch(self.root / "DEV_MitClaude" / "CLAUDE.md")
        _mkdir(self.root / "DEV_NurGross")
        _mkdir(self.root / "kleinschrift")

    def test_strict_finds_only_the_complete_one(self):
        config = TraversalConfig(
            roots=[self.root], max_depth=2,
            rules=MarkerRules(
                dir_patterns=DirPatternRule(enabled=True),
                files=FileRule(enabled=True, names=("CLAUDE.md",)),
                subdirs=SubdirRule(enabled=False),
                git=GitRule(enabled=False),
                flag_file=FlagFileRule(enabled=False),
                combine="all"))
        names = [p.name for p in discover_projects(config, "auto")]
        self.assertEqual(names, ["DEV_MitClaude"])

    def test_generous_finds_both_marked(self):
        config = TraversalConfig(
            roots=[self.root], max_depth=2,
            rules=MarkerRules(
                dir_patterns=DirPatternRule(enabled=True),
                files=FileRule(enabled=True, names=("CLAUDE.md",)),
                subdirs=SubdirRule(enabled=False),
                git=GitRule(enabled=False),
                flag_file=FlagFileRule(enabled=False),
                combine="any"))
        names = sorted(p.name for p in discover_projects(config, "auto"))
        self.assertEqual(names, ["DEV_MitClaude", "DEV_NurGross"])

    def test_flag_rescues_the_unmarked_one(self):
        """Der letzte Automatik-Fallback: eine Datei ablegen, fertig."""
        set_flag(self.root / "kleinschrift")
        config = TraversalConfig(
            roots=[self.root], max_depth=2,
            rules=MarkerRules(
                dir_patterns=DirPatternRule(enabled=True),
                files=FileRule(enabled=False),
                subdirs=SubdirRule(enabled=False),
                git=GitRule(enabled=False),
                flag_file=FlagFileRule(enabled=True),
                combine="all"))
        names = sorted(p.name for p in discover_projects(config, "auto"))
        self.assertIn("kleinschrift", names)


if __name__ == "__main__":
    unittest.main()


class TestDirPatternTrap(unittest.TestCase):
    """Die Falle, die erst der Lauf gegen ein echtes System zeigte.

    Ordnermuster sind mit combine="any" GEFAEHRLICH, wenn die Zwischenebenen
    derselben Konvention folgen wie die Projekte: Das Muster trifft die
    KATEGORIE, der Scan haelt dort an und steigt nie zu den echten Projekten ab.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = _mkdir(self.tmp / ".SW")
        # Kategorie GROSS geschrieben — genau wie die Projekte darunter
        _touch(self.root / "CASH" / "DEV_Rechnung" / "TODO.md")
        _touch(self.root / "DATA" / "DEV_Parser" / "TODO.md")

    def test_dir_patterns_alone_stops_at_the_category(self):
        config = TraversalConfig(
            roots=[self.root], max_depth=3,
            rules=MarkerRules(dir_patterns=DirPatternRule(enabled=True),
                              files=FileRule(enabled=False),
                              subdirs=SubdirRule(enabled=False),
                              git=GitRule(enabled=False),
                              flag_file=FlagFileRule(enabled=False),
                              combine="any"))
        names = sorted(p.name for p in discover_projects(config, "auto"))
        self.assertEqual(names, ["CASH", "DATA"],
                         "Erwartet: der Scan bleibt an den Kategorien haengen")

    def test_files_only_reaches_the_real_projects(self):
        config = TraversalConfig(
            roots=[self.root], max_depth=3,
            rules=MarkerRules(dir_patterns=DirPatternRule(enabled=False),
                              files=FileRule(enabled=True, names=("TODO.md",)),
                              subdirs=SubdirRule(enabled=False),
                              git=GitRule(enabled=False),
                              flag_file=FlagFileRule(enabled=False)))
        names = sorted(p.name for p in discover_projects(config, "auto"))
        self.assertEqual(names, ["DEV_Parser", "DEV_Rechnung"])

    def test_combination_also_reaches_them(self):
        """`dir_patterns AND files` rettet die Ordnermuster: Die Kategorie hat
        keine TODO.md und faellt damit heraus."""
        config = TraversalConfig(
            roots=[self.root], max_depth=3,
            rules=MarkerRules(dir_patterns=DirPatternRule(enabled=True),
                              files=FileRule(enabled=True, names=("TODO.md",)),
                              subdirs=SubdirRule(enabled=False),
                              git=GitRule(enabled=False),
                              flag_file=FlagFileRule(enabled=False),
                              expression="dir_patterns AND files"))
        names = sorted(p.name for p in discover_projects(config, "auto"))
        self.assertEqual(names, ["DEV_Parser", "DEV_Rechnung"])
