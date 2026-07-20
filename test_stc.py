import sys
import unittest
from unittest.mock import MagicMock, patch
import os
import subprocess

# Mock modules that might not be available or require GUI/Web dependencies
sys.modules['requests'] = MagicMock()
sys.modules['pydub'] = MagicMock()
sys.modules['pydub.silence'] = MagicMock()
sys.modules['pysrt'] = MagicMock()
sys.modules['tkinter'] = MagicMock()
sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()

class MockCTk:
    pass

class MockCustomTkinter(MagicMock):
    pass

ctk_mock = MockCustomTkinter()
ctk_mock.CTk = MockCTk
sys.modules['customtkinter'] = ctk_mock

class MockDnDWrapper:
    pass

tkinterdnd2_mock = MagicMock()
tkinterdnd2_mock.TkinterDnD.DnDWrapper = MockDnDWrapper
tkinterdnd2_mock.DND_FILES = "DND_FILES"
sys.modules['tkinterdnd2'] = tkinterdnd2_mock

sys.modules['whisper'] = MagicMock()

if not hasattr(subprocess, 'CREATE_NO_WINDOW'):
    subprocess.CREATE_NO_WINDOW = 0x08000000

# Import the correct STC module
import importlib.util
spec = importlib.util.spec_from_file_location("STC", os.path.join(os.path.dirname(__file__), 'SRC', 'STC.py'))
STC = importlib.util.module_from_spec(spec)
sys.modules["STC"] = STC
spec.loader.exec_module(STC)

class TestSTC(unittest.TestCase):
    def test_detect_hardware_acceleration_no_torch(self):
        sys.modules['torch'] = None
        info = STC.detect_hardware_acceleration()
        self.assertEqual(info['recommended'], 'cpu')
        self.assertFalse(info['cuda_available'])
        self.assertEqual(info['devices'], [])

    def test_detect_hardware_acceleration_with_torch_no_cuda(self):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        sys.modules['torch'] = mock_torch
        info = STC.detect_hardware_acceleration()
        self.assertEqual(info['recommended'], 'cpu')
        self.assertFalse(info['cuda_available'])

    def test_detect_hardware_acceleration_with_cuda(self):
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.device_count.return_value = 1
        mock_torch.cuda.get_device_name.return_value = 'Test GPU'
        sys.modules['torch'] = mock_torch
        info = STC.detect_hardware_acceleration()
        self.assertEqual(info['recommended'], 'cuda')
        self.assertTrue(info['cuda_available'])
        self.assertEqual(info['devices'], ['Test GPU'])

    @patch('subprocess.run')
    def test_extract_audio_success(self, mock_run):
        mock_run.return_value = MagicMock()
        result = STC.extract_audio('video.mp4', 'audio.wav')
        self.assertTrue(result)
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_extract_audio_failure(self, mock_run):
        mock_run.side_effect = Exception("FFmpeg failed")
        result = STC.extract_audio('video.mp4', 'audio.wav')
        self.assertFalse(result)

    def test_split_audio_fixed(self):
        class MockAudio:
            def __init__(self, length):
                self.length = length
            def __len__(self):
                return self.length
            def __getitem__(self, key):
                return f"slice_{key.start}_{key.stop}"

        audio = MockAudio(10000) # 10 seconds
        chunks = STC.split_audio_fixed(audio, 3000) # 3 seconds chunk
        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[0]['start_sec'], 0.0)
        self.assertEqual(chunks[0]['duration_sec'], 3.0)
        self.assertEqual(chunks[3]['duration_sec'], 1.0) # last chunk 1 sec

    @patch('os.path.exists')
    @patch('os.listdir')
    def test_check_whisper_model_cached(self, mock_listdir, mock_exists):
        mock_exists.return_value = True
        mock_listdir.return_value = ["tiny.pt", "base.pt"]
        self.assertTrue(STC.check_whisper_model_cached("tiny"))
        self.assertFalse(STC.check_whisper_model_cached("large"))

if __name__ == '__main__':
    unittest.main()
