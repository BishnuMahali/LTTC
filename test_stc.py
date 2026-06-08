import unittest
from unittest.mock import patch, MagicMock
import subprocess
import os
import sys

# Ensure SRC directory is in path before importing STC
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "SRC"))

# Mocking modules that are not installed to allow importing STC
sys.modules["requests"] = MagicMock()
sys.modules["pydub"] = MagicMock()
sys.modules["pysrt"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["tkinter.filedialog"] = MagicMock()
sys.modules["tkinter.messagebox"] = MagicMock()
sys.modules["tkinter.ttk"] = MagicMock()

# Ensure subprocess.CREATE_NO_WINDOW exists for testing on non-Windows
if not hasattr(subprocess, "CREATE_NO_WINDOW"):
    subprocess.CREATE_NO_WINDOW = 0x08000000

import STC

class TestSTC(unittest.TestCase):
    def test_extract_audio_success(self):
        with patch("STC.subprocess.run") as mock_run:
            # Setup
            mock_run.return_value = MagicMock(returncode=0)
            video_path = "video.mp4"
            audio_path = "audio.wav"

            # Execute
            result = STC.extract_audio(video_path, audio_path)

            # Verify
            self.assertTrue(result)
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            command = args[0]
            self.assertEqual(command[0], "ffmpeg")
            self.assertIn(video_path, command)
            self.assertIn(audio_path, command)

    def test_extract_audio_failure(self):
        with patch("STC.subprocess.run") as mock_run:
            # Setup
            mock_run.side_effect = Exception("Subprocess error")
            video_path = "video.mp4"
            audio_path = "audio.wav"

            # Execute
            result = STC.extract_audio(video_path, audio_path)

            # Verify
            self.assertFalse(result)
            mock_run.assert_called_once()

if __name__ == "__main__":
    unittest.main()
