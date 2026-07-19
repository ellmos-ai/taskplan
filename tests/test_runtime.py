# -*- coding: utf-8 -*-
"""Provider-, Goal- und Timeout-Vertrag der nutzerneutralen Worker-Runtime."""
import io
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest import mock

from taskplan import config as cfg
from taskplan import runner
from taskplan.__main__ import main
from taskplan.runtime import apply_backoff, runtime_profile, startup_prompt


class TestProviderModels(unittest.TestCase):
    def test_provider_role_model_beats_legacy_models(self):
        data = {
            "execution": {"provider": "codex"},
            "models": {"default": "legacy"},
            "providers": {
                "codex": {
                    "models": {"default": "gpt-default", "tasksolver": "gpt-solver"},
                    "reasoning_effort": {"default": "high", "tasksolver": "xhigh"},
                }
            },
        }
        with mock.patch.object(cfg, "load_config", return_value=data):
            self.assertEqual(cfg.model_for("tasksolver"), "gpt-solver")
            self.assertEqual(cfg.model_for("taskwriter"), "gpt-default")
            profile = cfg.provider_runtime("tasksolver")
        self.assertEqual(profile["reasoning_effort"], "xhigh")
        self.assertEqual(profile["continuation"], "goal")

    def test_legacy_models_remain_compatible(self):
        with mock.patch.object(cfg, "load_config", return_value={
                "models": {"default": "sonnet", "tasksolver": "opus"}}), \
                mock.patch.dict(cfg.os.environ, {"TASKPLAN_PROVIDER": ""}):
            self.assertEqual(cfg.model_for("tasksolver"), "opus")
            self.assertEqual(cfg.model_for("taskwriter"), "sonnet")

    def test_explicit_provider_is_user_neutral(self):
        data = {"providers": {"codex": {"models": {"default": "gpt"}}}}
        with mock.patch.object(cfg, "load_config", return_value=data):
            self.assertEqual(runtime_profile("maintainer", "codex")["model"], "gpt")

    def test_explicit_provider_never_inherits_legacy_other_provider_model(self):
        data = {
            "models": {"default": "claude-sonnet"},
            "providers": {"codex": {"continuation": "goal"}},
        }
        with mock.patch.object(cfg, "load_config", return_value=data):
            self.assertEqual(cfg.model_for("tasksolver", "codex"), "")


class TestCodexGoalPrompt(unittest.TestCase):
    def test_codex_gets_explicit_persisted_goal(self):
        data = {
            "language": {"prompts": "de"},
            "providers": {"codex": {
                "continuation": "goal",
                "empty_policy": "keep_goal",
                "idle_backoff_seconds": 45,
            }},
        }
        with mock.patch.object(cfg, "load_config", return_value=data):
            prompt = startup_prompt("tasksolver", "codex", "de")
        self.assertIn("persistiertes Goal", prompt)
        self.assertIn("genau ein", prompt)
        self.assertIn("Exit 3", prompt)
        self.assertIn("45 Sekunden", prompt)
        self.assertIn("python -m taskplan next --role tasksolver --json", prompt)

    def test_one_shot_provider_does_not_request_goal(self):
        data = {"providers": {"other": {"continuation": "one_shot"}}}
        with mock.patch.object(cfg, "load_config", return_value=data):
            prompt = startup_prompt("taskwriter", "other", "de")
        self.assertNotIn("persistiertes Goal", prompt)
        self.assertIn("genau einen TASKPLAN-Durchlauf", prompt)

    def test_runtime_cli_exposes_fields_for_thin_starters(self):
        data = {"providers": {"codex": {"models": {"tasksolver": "gpt-x"}}}}
        output = io.StringIO()
        with mock.patch.object(cfg, "load_config", return_value=data), redirect_stdout(output):
            code = main(["runtime", "--role", "tasksolver", "--provider", "codex",
                         "--field", "model"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue().strip(), "gpt-x")

    def test_backoff_uses_a_real_injected_timer(self):
        calls = []
        data = {"providers": {"codex": {"idle_backoff_seconds": 17}}}
        with mock.patch.object(cfg, "load_config", return_value=data):
            seconds = apply_backoff("tasksolver", "codex", sleeper=calls.append)
        self.assertEqual(seconds, 17)
        self.assertEqual(calls, [17])


class TestDiscoveryTimeout(unittest.TestCase):
    def test_bounded_discovery_returns_instead_of_hanging(self):
        expired = subprocess.TimeoutExpired(["python", "discovery"], 0.02)
        with mock.patch.object(runner.subprocess, "run", side_effect=expired):
            with self.assertRaises(runner.ProjectDiscoveryTimeout):
                runner._discover_projects_bounded(0.02)

    def test_retryable_selector_error_has_exit_code_three(self):
        work = {
            "role": "taskwriter", "active": True, "bundle": None,
            "retryable": True, "reason": "timeout",
        }
        with mock.patch.object(runner, "next_work", return_value=work):
            self.assertEqual(runner.run("taskwriter", as_json=True), 3)


if __name__ == "__main__":
    unittest.main()
