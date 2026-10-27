"""Configuration remains inside a standalone Studio checkout."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class ConfigurationTests(unittest.TestCase):
    def test_ignores_parent_env_and_loads_local_env_from_any_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            studio = parent / 'standalone_studio'
            studio.mkdir()
            (parent / '.env').write_text('TYPESAFE_API_KEY=parent-key\n')
            with patch.object(server, 'HERE', studio), patch.dict(os.environ, {}, clear=True):
                server.load_env()
                self.assertNotIn('TYPESAFE_API_KEY', os.environ)
                (studio / '.env').write_text('TYPESAFE_API_KEY=local-key\n')
                server.load_env()
                self.assertEqual(os.environ['TYPESAFE_API_KEY'], 'local-key')

    def test_process_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            studio = Path(directory)
            (studio / '.env').write_text('TYPESAFE_API_KEY=local-key\nSTUDIO_GENERATOR=codex\n')
            with patch.object(server, 'HERE', studio), patch.dict(os.environ, {'TYPESAFE_API_KEY': 'process-key'}, clear=True):
                server.load_env()
                self.assertEqual(os.environ['TYPESAFE_API_KEY'], 'process-key')
                self.assertEqual(os.environ['STUDIO_GENERATOR'], 'codex')
