import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner


class BlockMlxWhisperImport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mlx_whisper":
            raise AssertionError("CLI import should not import mlx_whisper")
        return None


class CliImportTests(unittest.TestCase):
    def test_importing_cli_does_not_import_mlx_whisper(self):
        blocker = BlockMlxWhisperImport()
        sys.meta_path.insert(0, blocker)
        try:
            for name in list(sys.modules):
                if name == "meeting_capture.cli" or name.startswith("meeting_capture."):
                    sys.modules.pop(name)

            importlib.import_module("meeting_capture.cli")
        finally:
            sys.meta_path.remove(blocker)

    def test_record_command_reports_device_selection_errors_without_traceback(self):
        from meeting_capture.cli import cli
        from meeting_capture.recorder import DeviceSelectionError

        runner = CliRunner()
        with patch(
            "meeting_capture.recorder.record_audio",
            side_effect=DeviceSelectionError("No input device with audio signal was detected."),
        ):
            result = runner.invoke(cli, ["record", "--output", str(Path("test.wav"))])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error: No input device with audio signal was detected.", result.output)
        self.assertNotIn("Traceback", result.output)


if __name__ == "__main__":
    unittest.main()
