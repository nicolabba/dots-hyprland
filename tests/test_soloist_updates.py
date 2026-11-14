"""Updater tests: real local files and executables, fake network/service boundary."""
from test_soloist_backend import module
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone
import io
import tarfile
import tempfile
import unittest
import json
import fcntl


def fake_player(timestamp, state='paused'):
    return ('#!/usr/bin/env python3\nimport sys,json\n'
            f'if "--version" in sys.argv: print("soloist 1.2.3 build {timestamp} (test) (linux/x86_64)")\n'
            f'else: print(json.dumps({{"status": {state!r}}}))\n').encode()


def archive(path, entries):
    with tarfile.open(path, 'w:gz') as t:
        for name, payload, kind in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(payload) if kind == tarfile.REGTYPE else 0
            t.addfile(info, io.BytesIO(payload) if info.size else None)


class FakeService:
    def __init__(self, active=False, healthy=(True,), logged=True):
        self.enabled = active
        self.results = iter(healthy)
        self.restarts = 0
        self.logged = logged

    def active(self):
        return self.enabled

    def logged_in(self):
        return self.logged

    def restart(self, require_login):
        self.restarts += 1
        return next(self.results, True)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.m = module()
        self.assertTrue(hasattr(self.m, 'update'), 'Safe updater is missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.p = self.m.paths(self.home)
        self.p['binary'].parent.mkdir(parents=True)
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.old = 1794528000  # 2026-11-13 UTC
        self.new = 1794614400  # 2026-11-14 UTC
        self.p['binary'].write_bytes(fake_player(self.old))
        self.p['binary'].chmod(0o700)

    def fetch(self, timestamp=None):
        def write(path):
            archive(path, [('soloist', fake_player(timestamp or self.new), tarfile.REGTYPE)])
        return write

    def update(self, service=None, fetch=None):
        return self.m.update(self.p, fetch=fetch or self.fetch(), service=service or FakeService(), now=self.now)

    def test_only_new_valid_builds_are_eligible(self):
        current = self.m.read_build(self.p['binary'])
        for ts, expected in [(self.old, False), (self.old - 1, False), (self.new, True)]:
            b = self.m.parse_build(f'soloist 1.2.3 build {ts} (linux/x86_64)')
            self.assertEqual(self.m.eligible(b, current, self.now), expected)
        for text in ['garbage', f'soloist 1.2.3 build {self.new} (linux/arm64)']:
            with self.assertRaises(self.m.BackendError):
                self.m.parse_build(text)
        for ts in [self.new + 86400, self.old - 90 * 86400]:
            with self.assertRaises(self.m.BackendError):
                self.m.eligible(self.m.parse_build(f'soloist 1.2.3 build {ts} (linux/x86_64)'), current, self.now)

    def test_same_build_is_noop(self):
        before = self.p['binary'].read_bytes()
        self.assertEqual(self.update(fetch=self.fetch(self.old))['outcome'], 'unchanged')
        self.assertEqual(self.p['binary'].read_bytes(), before)

    def test_inactive_service_updates_without_starting_it(self):
        service = FakeService()
        result = self.update(service)
        self.assertEqual(result['outcome'], 'updated')
        self.assertEqual(service.restarts, 0)
        self.assertEqual(self.m.read_build(self.p['binary']).timestamp, self.new)
        self.assertEqual(self.m.read_build(self.p['previous']).timestamp, self.old)
        self.assertEqual(json.loads(self.p['status'].read_text())['outcome'], 'updated')

    def test_playing_or_unknown_state_defers_without_download(self):
        for state in ['playing', 'unknown']:
            with self.subTest(state=state):
                self.p['binary'].write_bytes(fake_player(self.old, state))
                def forbidden(path):
                    self.fail('Must not download while playing/unknown')
                self.assertEqual(self.update(FakeService(active=True), forbidden)['outcome'], 'deferred')

    def test_playback_started_during_download_defers_activation(self):
        def fetch(path):
            self.fetch()(path)
            self.p['binary'].write_bytes(fake_player(self.old, 'playing'))
        self.assertEqual(self.update(FakeService(active=True), fetch)['outcome'], 'deferred')
        self.assertEqual(self.m.read_build(self.p['binary']).timestamp, self.old)

    def test_paused_active_service_is_restarted_and_health_checked(self):
        service = FakeService(active=True)
        self.assertEqual(self.update(service)['outcome'], 'updated')
        self.assertEqual(service.restarts, 1)

    def test_failed_candidate_rolls_back_and_verifies_previous(self):
        service = FakeService(active=True, healthy=(False, True))
        result = self.update(service)
        self.assertEqual(result['outcome'], 'rolled_back')
        self.assertEqual(service.restarts, 2)
        self.assertEqual(self.m.read_build(self.p['binary']).timestamp, self.old)

    def test_expired_old_binary_is_not_used_for_rollback(self):
        self.p['binary'].write_bytes(fake_player(self.old - 91 * 86400))
        service = FakeService(active=True, healthy=(False,))
        result = self.update(service)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(service.restarts, 1)
        self.assertEqual(self.m.read_build(self.p['binary']).timestamp, self.new)

    def test_invalid_archive_never_replaces_executable(self):
        before = self.p['binary'].read_bytes()
        cases = [[('../soloist', b'bad', tarfile.REGTYPE)],
                 [('soloist', b'', tarfile.SYMTYPE)],
                 [('soloist', b'bad', tarfile.REGTYPE)] * 2,
                 [('soloist', b'<html>error', tarfile.REGTYPE)]]
        for entries in cases:
            with self.subTest(entries=len(entries)):
                def fetch(path):
                    archive(path, entries)
                self.assertEqual(self.update(fetch=fetch)['outcome'], 'failed')
                self.assertEqual(self.p['binary'].read_bytes(), before)
        payload = self.home / 'oversized.tar.gz'
        archive(payload, [('soloist', b'x' * 128, tarfile.REGTYPE)])
        with patch.object(self.m, 'MAX_BINARY', 64):
            with self.assertRaises(self.m.BackendError):
                self.m.extract_binary(payload, self.home / 'candidate')

    def test_timeout_does_not_disclose_sensitive_details(self):
        def fail(path):
            raise TimeoutError('private-test-token')
        result = self.update(fetch=fail)
        self.assertEqual(result['outcome'], 'failed')
        self.assertNotIn('private-test-token', json.dumps(result))
        self.assertEqual(self.m.read_build(self.p['binary']).timestamp, self.old)

    def test_lock_contention_defers(self):
        with self.p['lock'].open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.update()['outcome'], 'deferred')

    def test_malformed_control_output_is_unknown(self):
        self.p['binary'].write_text('#!/bin/sh\nprintf not-json\n')
        self.assertEqual(self.m.playback_state(self.p['binary'], self.p['data']), 'unknown')
