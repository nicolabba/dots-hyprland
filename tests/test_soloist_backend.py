"""Behavioral tests for the user-local Soloist backend; no real credentials."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import io
import tarfile
import fcntl

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'dots/.local/bin/ii-soloist'


def module():
    loader = importlib.machinery.SourceFileLoader('ii_soloist', str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    m = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = m
    loader.exec_module(m)
    return m


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'Soloist integration is missing')
        self.m = module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.p = self.m.paths(self.home)
        self.p['key'].parent.mkdir(parents=True)
        self.p['key'].write_text('private-test-token\n')
        self.p['key'].chmod(0o600)

    def test_private_key_and_fixed_local_control_arguments(self):
        args = self.m.launch_arguments(self.p)
        self.assertEqual(args[args.index('--api-key') + 1], 'private-test-token')
        self.assertEqual(args[args.index('--ws') + 1], '127.0.0.1:0')
        self.assertEqual(args[args.index('--data-dir') + 1], str(self.home / '.local/share/spotify-sidebar/soloist-data'))
        self.assertNotIn('--single-track', args)

    def test_invalid_credentials_fail_without_disclosing_key(self):
        for text, mode in [('', 0o600), ('secret\nsecond', 0o600), ('private-test-token', 0o644)]:
            with self.subTest(mode=mode, empty=not text):
                self.p['key'].write_text(text)
                self.p['key'].chmod(mode)
                with self.assertRaises(self.m.BackendError) as e:
                    self.m.launch_arguments(self.p)
                self.assertNotIn('private-test-token', str(e.exception))
                self.assertNotIn('secret', str(e.exception))
        self.p['key'].unlink()
        with self.assertRaises(self.m.BackendError):
            self.m.launch_arguments(self.p)

    def test_real_run_executes_fake_player_and_preserves_pairing(self):
        self.p['binary'].parent.mkdir(parents=True)
        self.p['binary'].write_text('#!/usr/bin/env python3\nimport sys,json\nprint(json.dumps(sys.argv[1:]))\n')
        self.p['binary'].chmod(0o700)
        self.p['data'].mkdir(parents=True)
        marker = self.p['data'] / 'paired-test'
        marker.write_text('preserve')
        r = subprocess.run([sys.executable, str(SCRIPT), 'run'], env=dict(os.environ, HOME=str(self.home)), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        args = json.loads(r.stdout)
        self.assertEqual(args[args.index('--device-name') + 1], 'Sidebar Spotify')
        self.assertEqual(marker.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
