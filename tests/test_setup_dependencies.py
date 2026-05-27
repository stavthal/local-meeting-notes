from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SetupDependencyTests(unittest.TestCase):
    def test_setup_installs_ffmpeg_for_mlx_whisper_audio_loading(self):
        setup = (ROOT / "setup.sh").read_text(encoding="utf-8")

        self.assertIn("brew install ffmpeg", setup)


if __name__ == "__main__":
    unittest.main()
