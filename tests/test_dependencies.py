"""Tests for the dependency detection module."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from meeting_capture import dependencies


class DependencyCheckTests(unittest.TestCase):
    # --- ffmpeg ---------------------------------------------------------------

    def test_ffmpeg_installed_when_on_path(self):
        with patch("shutil.which", return_value="/usr/local/bin/ffmpeg"):
            status = dependencies._check_ffmpeg()
        self.assertTrue(status.installed)
        self.assertEqual(status.name, "ffmpeg")
        self.assertEqual(status.install_command, "brew install ffmpeg")

    def test_ffmpeg_missing_when_not_on_path(self):
        with patch("shutil.which", return_value=None):
            status = dependencies._check_ffmpeg()
        self.assertFalse(status.installed)
        self.assertIn("brew install ffmpeg", status.install_command)

    # --- Ollama --------------------------------------------------------------

    def test_ollama_missing_when_binary_absent(self):
        with patch("shutil.which", return_value=None):
            status = dependencies._check_ollama()
        self.assertFalse(status.installed)
        self.assertIn("brew install ollama", status.install_command)

    def test_ollama_server_down_when_binary_present_but_server_unreachable(self):
        with patch("shutil.which", return_value="/usr/local/bin/ollama"), \
             patch.object(dependencies, "_ollama_server_reachable", return_value=False):
            status = dependencies._check_ollama()
        self.assertFalse(status.installed)
        self.assertIn("server not running", status.name)
        self.assertEqual(status.install_command, "brew services start ollama")

    def test_ollama_model_missing_when_server_up_but_model_absent(self):
        with patch("shutil.which", return_value="/usr/local/bin/ollama"), \
             patch.object(dependencies, "_ollama_server_reachable", return_value=True), \
             patch.object(dependencies, "_ollama_model_pulled", return_value=False):
            status = dependencies._check_ollama()
        self.assertFalse(status.installed)
        self.assertIn("model", status.name.lower())
        self.assertEqual(status.install_command, "ollama pull llama3.1:8b")

    def test_ollama_fully_installed_when_everything_ready(self):
        with patch("shutil.which", return_value="/usr/local/bin/ollama"), \
             patch.object(dependencies, "_ollama_server_reachable", return_value=True), \
             patch.object(dependencies, "_ollama_model_pulled", return_value=True):
            status = dependencies._check_ollama()
        self.assertTrue(status.installed)
        self.assertEqual(status.install_command, "")

    # --- aggregation ---------------------------------------------------------

    def test_missing_dependencies_filters_correctly(self):
        statuses = [
            dependencies.DependencyStatus("a", True, "", ""),
            dependencies.DependencyStatus("b", False, "", "brew install b"),
            dependencies.DependencyStatus("c", False, "", "brew install c"),
        ]
        missing = dependencies.missing_dependencies(statuses)
        self.assertEqual([s.name for s in missing], ["b", "c"])

    def test_combined_install_command_joins_with_and(self):
        statuses = [
            dependencies.DependencyStatus("a", True, "", ""),  # skipped
            dependencies.DependencyStatus("b", False, "", "brew install b"),
            dependencies.DependencyStatus("c", False, "", "brew install c && brew services start c"),
        ]
        cmd = dependencies.combined_install_command(statuses)
        self.assertEqual(cmd, "brew install b && brew install c && brew services start c")

    def test_combined_install_command_empty_when_nothing_missing(self):
        statuses = [
            dependencies.DependencyStatus("a", True, "", ""),
            dependencies.DependencyStatus("b", True, "", ""),
        ]
        self.assertEqual(dependencies.combined_install_command(statuses), "")


if __name__ == "__main__":
    unittest.main()
