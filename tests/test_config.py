import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dasyante.config import load_environment


class ConfigTests(unittest.TestCase):
    def test_local_credentials_replace_stale_environment_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text('# local keys\nTAVILY_API_KEY="test-new"\nHUNTER_API_KEY=test-hunter\n')
            with patch.dict(os.environ, {"TAVILY_API_KEY": "test-old"}, clear=True):
                load_environment(path)
                self.assertEqual(os.environ["TAVILY_API_KEY"], "test-new")
                self.assertEqual(os.environ["HUNTER_API_KEY"], "test-hunter")

    def test_missing_file_preserves_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"TINYFISH_API_KEY": "test-key"}, clear=True):
                load_environment(Path(directory) / ".env")
                self.assertEqual(os.environ["TINYFISH_API_KEY"], "test-key")

    def test_explicit_file_and_unknown_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("TINYFISH_API_KEY=test-key\nUNRELATED=value\n")
            with patch.dict(os.environ, {"DASYANTE_ENV_FILE": str(path)}, clear=True):
                load_environment()
                self.assertEqual(os.environ["TINYFISH_API_KEY"], "test-key")
                self.assertNotIn("UNRELATED", os.environ)

    def test_invalid_line_reports_line_number_not_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("TAVILY_API_KEY=test-key\nsecret-without-assignment\n")
            with self.assertRaisesRegex(ValueError, "line 2") as error:
                load_environment(path)
            self.assertNotIn("secret-without-assignment", str(error.exception))
