"""Installed-service contracts and isolated deployment checks."""
from test_soloist_backend import module, ROOT
from test_soloist_updates import fake_player
import configparser
from pathlib import Path
import tempfile
import unittest

UNITS = ROOT / 'dots/.config/systemd/user'


class DeploymentTests(unittest.TestCase):
    def test_service_starts_with_session_and_does_not_start_music(self):
        path = UNITS / 'ii-soloist.service'
        self.assertTrue(path.exists(), 'Session service missing')
        c = configparser.ConfigParser(interpolation=None)
        c.read(path)
        self.assertEqual(c['Unit']['PartOf'], 'graphical-session.target')
        self.assertEqual(c['Install']['WantedBy'], 'graphical-session.target')
        self.assertNotIn('Wants', c['Unit'])
        self.assertEqual(c['Service']['ExecStart'], '%h/.local/bin/ii-soloist run')
        self.assertEqual(c['Service']['Restart'], 'on-failure')
        self.assertIn('StartLimitBurst', c['Unit'])
        self.assertEqual(c['Service']['UMask'], '0077')
        self.assertEqual(c['Unit']['OnFailure'], 'ii-soloist-failure.service')

    def test_timer_is_daily_persistent_and_job_is_bounded(self):
        path = UNITS / 'ii-soloist-update.timer'
        self.assertTrue(path.exists(), 'Update timer missing')
        c = configparser.ConfigParser(interpolation=None)
        c.read(path)
        self.assertEqual(c['Timer']['OnCalendar'], 'daily')
        self.assertEqual(c['Timer']['Persistent'], 'true')
        self.assertEqual(c['Install']['WantedBy'], 'timers.target')
        c.read(UNITS / 'ii-soloist-update.service')
        self.assertEqual(c['Service']['ExecStart'], '%h/.local/bin/ii-soloist update')
        self.assertEqual(c['Service']['Type'], 'oneshot')
        self.assertGreaterEqual(int(c['Service']['TimeoutStartSec']), 240)

    def test_deployment_is_idempotent_and_never_copies_credentials(self):
        m = module()
        self.assertTrue(hasattr(m, 'deploy'), 'Dedicated deployment helper missing')
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            p = m.paths(home)
            p['key'].parent.mkdir(parents=True)
            p['key'].write_text('do-not-copy-or-overwrite')
            p['data'].mkdir(parents=True)
            marker = p['data'] / 'paired'
            marker.write_text('preserve')
            for _ in range(2):
                m.deploy(home, ROOT / 'dots')
            self.assertEqual((home / '.local/bin/ii-soloist').read_bytes(), (ROOT / 'dots/.local/bin/ii-soloist').read_bytes())
            self.assertEqual(p['key'].read_text(), 'do-not-copy-or-overwrite')
            self.assertEqual(marker.read_text(), 'preserve')
            self.assertTrue((home / '.config/systemd/user/ii-soloist-update.timer').exists())

    def test_sidebar_deployment_backs_up_live_files_and_preserves_config(self):
        m = module()
        self.assertTrue(hasattr(m, 'deploy_sidebar'), 'Sidebar deployment missing')
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            config = home / '.config/illogical-impulse/config.json'
            config.parent.mkdir(parents=True)
            config.write_text('{"policies":{"weeb":2},"sidebar":{"translator":{"enable":true}}}')
            target = home / '.config/quickshell/ii/modules/common/Config.qml'
            target.parent.mkdir(parents=True)
            target.write_text('original-live-config')
            backup = m.deploy_sidebar(home, ROOT / 'dots')
            self.assertEqual((backup / '.config/quickshell/ii/modules/common/Config.qml').read_text(), 'original-live-config')
            settings = __import__('json').loads(config.read_text())
            self.assertEqual(settings['policies']['weeb'], 2)
            self.assertTrue(settings['sidebar']['translator']['enable'])
            self.assertTrue(settings['sidebar']['spotify']['enable'])
            self.assertTrue((home / '.local/bin/ii-spotify-api').exists())
            self.assertTrue((home / '.config/quickshell/ii/modules/ii/sidebarLeft/spotify/SpotifyConnection.qml').exists())
            seek = '.config/quickshell/ii/modules/ii/sidebarLeft/spotify/SpotifySeek.qml'
            self.assertEqual((home / seek).read_bytes(), (ROOT / 'dots' / seek).read_bytes())
            m.deploy_sidebar(home, ROOT / 'dots')

    def test_safe_setup_rejects_unmanaged_running_player(self):
        m = module()
        self.assertTrue(hasattr(m, 'ensure_no_unmanaged_daemon'), 'Safe migration check missing')
        with tempfile.TemporaryDirectory() as d:
            p = m.paths(Path(d))
            p['binary'].parent.mkdir(parents=True)
            p['binary'].write_bytes(fake_player(1794614400))
            p['binary'].chmod(0o700)
            p['data'].mkdir(parents=True)
            (p['data'] / 'soloist.pid').write_text(str(__import__('os').getpid()))
            with self.assertRaises(m.BackendError):
                m.ensure_no_unmanaged_daemon(p)
