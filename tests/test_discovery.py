# -*- coding: utf-8 -*-
"""Snapshot-Cache und Unterprozess-Vertrag der Projekt-Discovery."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from taskplan import discovery, runner
from taskplan.traversal import Level, TraversalConfig


class TestDiscoveryCache(unittest.TestCase):
    def test_second_scan_comes_from_cache(self):
        tmp = Path(tempfile.mkdtemp())
        root = tmp / "root"
        project = root / "project"
        project.mkdir(parents=True)
        (project / "TODO.md").write_text("todo", encoding="utf-8")
        cache = tmp / "projects-cache.json"
        config = TraversalConfig(
            roots=[root],
            levels=[Level("root"), Level("project", is_work_unit=True)],
            max_depth=2,
            markers=("TODO.md",),
        )
        patches = (
            mock.patch.object(discovery, "traversal_config", return_value=config),
            mock.patch.object(discovery, "discovery_mode", return_value="auto"),
            mock.patch.object(discovery, "registry_file", return_value=""),
            mock.patch.object(discovery, "find_config_file", return_value=None),
            mock.patch.object(discovery, "discovery_cache_config", return_value={
                "enabled": True, "path": cache, "ttl_seconds": 900}),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            first, first_cached = discovery.discover_cached()
            (project / "TODO.md").unlink()
            second, second_cached = discovery.discover_cached()
        self.assertFalse(first_cached)
        self.assertTrue(second_cached)
        self.assertEqual([p.path for p in first], [project])
        self.assertEqual([p.path for p in second], [project])


class TestBoundedSubprocess(unittest.TestCase):
    def test_valid_payload_is_reconstructed(self):
        payload = {"cached": True, "projects": [
            {"path": "C:/portable/project", "root_id": "root"}]}
        completed = subprocess.CompletedProcess(
            args=["python"], returncode=0,
            stdout=json.dumps(payload), stderr="")
        with mock.patch.object(runner.subprocess, "run", return_value=completed):
            projects = runner._discover_projects_bounded(5)
        self.assertEqual(projects[0].root_id, "root")
        self.assertEqual(projects[0].path, Path("C:/portable/project"))


if __name__ == "__main__":
    unittest.main()
