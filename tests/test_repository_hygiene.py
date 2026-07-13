# -*- coding: utf-8 -*-
"""Repository hygiene checks for local secrets and generated task data."""
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestRepositoryHygiene(unittest.TestCase):
    def setUp(self):
        if not (ROOT / ".git").exists():
            self.skipTest("repository hygiene checks require Git metadata")

    def check_ignored(self, relative_path: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", relative_path],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode == 0

    def test_local_secret_patterns_are_ignored(self):
        samples = [
            ".env",
            ".env.local",
            ".npmrc",
            "credentials.json",
            "api.secret.json",
            "taskplan_token.txt",
            "npm_recovery_codes.txt",
            "id_ed25519.key",
            "private.pem",
            "client.p12",
            "bundle.crt",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(self.check_ignored(sample))

    def test_examples_remain_trackable(self):
        for sample in (".env.example", ".env.sample"):
            with self.subTest(sample=sample):
                self.assertFalse(self.check_ignored(sample))

    def test_sqlite_sidecars_and_onedrive_conflicts_are_ignored(self):
        samples = [
            "taskplan.db",
            "taskplan.db-shm",
            "taskplan.db-wal",
            "taskplan.sqlite",
            "taskplan.sqlite3",
            "taskplan.sqlite-shm",
            "taskplan.sqlite-wal",
            "README-Mac Studio.md",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(self.check_ignored(sample))


if __name__ == "__main__":
    unittest.main()
