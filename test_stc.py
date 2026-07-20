import unittest
from unittest.mock import patch, MagicMock
import os
import json
import base64
import sys

# Setup mocks to prevent actual GUI creation during import
sys.modules['requests'] = MagicMock()
sys.modules['pydub'] = MagicMock()
sys.modules['pydub.silence'] = MagicMock()
sys.modules['pysrt'] = MagicMock()

class MockTkinterModule(MagicMock):
    pass
sys.modules['tkinter'] = MockTkinterModule()

class MockCtkModule(MagicMock):
    class CTk:
        pass
    def set_appearance_mode(self, mode): pass
    def set_default_color_theme(self, theme): pass

sys.modules['customtkinter'] = MockCtkModule()

class MockDnDModule(MagicMock):
    class TkinterDnD:
        class DnDWrapper:
            pass
    DND_FILES = "DND_FILES"

sys.modules['tkinter.filedialog'] = MagicMock()
sys.modules['tkinter.messagebox'] = MagicMock()
sys.modules['tkinterdnd2'] = MockDnDModule()

try:
    import keyring
    import keyring.errors
except ImportError:
    pass

# Mock the STC module to test only the methods
class MockVar:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value

# Now import the class we're testing
import SRC.STC as STC
STC.CONFIG_FILE = "test_config.json"

class TestSTCSettings(unittest.TestCase):
    def setUp(self):
        # Clean up any test config file
        if os.path.exists(STC.CONFIG_FILE):
            os.remove(STC.CONFIG_FILE)

        # Create a mock instance of STCGui without initializing Tkinter
        self.gui = MagicMock()
        self.gui.engine_var = MockVar("Sarvam AI (Cloud)")
        self.gui.lang_var = MockVar("Bengali")
        self.gui.model_var = MockVar("base")
        self.gui.sarvam_plan_var = MockVar("Starter")
        self.gui.sarvam_custom_rpm_var = MockVar("60")
        self.gui.chunk_len_var = MockVar("5")
        self.gui.chunking_mode_var = MockVar("throttle")
        self.gui.enable_chunking_var = MockVar(True)
        self.gui.smart_silence_var = MockVar(True)
        self.gui.key_var = MockVar()

    def tearDown(self):
        if os.path.exists(STC.CONFIG_FILE):
            os.remove(STC.CONFIG_FILE)

    @patch('keyring.set_password')
    def test_save_settings_with_keyring(self, mock_set_password):
        self.gui.key_var.set("test_secure_key")

        # Call the method we modified
        STC.STCGui.save_settings(self.gui)

        # Verify keyring was used
        mock_set_password.assert_called_once_with("SarvamTimedCaptions", "api_key", "test_secure_key")

        # Verify it wasn't saved in plain text
        with open(STC.CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            self.assertNotIn("api_key", cfg)
            self.assertNotIn("key_enc", cfg)

    @patch('keyring.set_password', side_effect=keyring.errors.NoKeyringError("No backend"))
    def test_save_settings_fallback_plaintext(self, mock_set_password):
        self.gui.key_var.set("test_fallback_key")

        # Call the method we modified
        STC.STCGui.save_settings(self.gui)

        # Verify it was saved in plain text due to keyring failure
        with open(STC.CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            self.assertEqual(cfg.get("api_key"), "test_fallback_key")
            self.assertNotIn("key_enc", cfg)

    @patch('keyring.get_password', return_value="loaded_secure_key")
    def test_load_settings_with_keyring(self, mock_get_password):
        # Create a dummy config
        with open(STC.CONFIG_FILE, "w") as f:
            json.dump({"engine": "Whisper (Local)"}, f)

        STC.STCGui.load_settings(self.gui)

        mock_get_password.assert_called_once_with("SarvamTimedCaptions", "api_key")
        self.assertEqual(self.gui.key_var.get(), "loaded_secure_key")

    @patch('keyring.get_password', side_effect=keyring.errors.NoKeyringError("No backend"))
    def test_load_settings_fallback_plaintext(self, mock_get_password):
        # Create a config with plaintext key
        with open(STC.CONFIG_FILE, "w") as f:
            json.dump({"api_key": "loaded_fallback_key"}, f)

        STC.STCGui.load_settings(self.gui)

        self.assertEqual(self.gui.key_var.get(), "loaded_fallback_key")

    @patch('keyring.get_password', side_effect=keyring.errors.NoKeyringError("No backend"))
    def test_load_settings_migrate_key_enc(self, mock_get_password):
        # Create a config with old key_enc format
        with open(STC.CONFIG_FILE, "w") as f:
            json.dump({"key_enc": base64.b64encode(b"legacy_key").decode()}, f)

        STC.STCGui.load_settings(self.gui)

        self.assertEqual(self.gui.key_var.get(), "legacy_key")

if __name__ == '__main__':
    unittest.main()
