import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class BlockMlxWhisperImport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mlx_whisper":
            raise AssertionError("Missing ffmpeg should be reported before mlx_whisper imports")
        return None


class TranscriberDependencyTests(unittest.TestCase):
    def test_missing_ffmpeg_exits_with_clear_message_before_importing_mlx(self):
        blocker = BlockMlxWhisperImport()
        sys.meta_path.insert(0, blocker)
        try:
            sys.modules.pop("meeting_capture.transcriber", None)
            transcriber = importlib.import_module("meeting_capture.transcriber")

            with patch("shutil.which", return_value=None):
                with self.assertRaisesRegex(SystemExit, "ffmpeg is required"):
                    transcriber.transcribe(Path("audio.wav"), Path("audio.txt"))
        finally:
            sys.meta_path.remove(blocker)


if __name__ == "__main__":
    unittest.main()
