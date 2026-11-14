"""Prevent cold-boot session restoration before networking is ready."""
from test_soloist_backend import module, ROOT
import configparser
from urllib.error import URLError, HTTPError
from unittest.mock import patch
import io
import unittest


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.m=module()

    def test_service_waits_for_network_before_starting_soloist(self):
        c=configparser.ConfigParser(interpolation=None)
        c.read(ROOT/'dots/.config/systemd/user/ii-soloist.service')
        self.assertEqual(c['Service'].get('ExecStartPre'), '%h/.local/bin/ii-soloist wait-network')
        self.assertGreaterEqual(int(c['Service']['TimeoutStartSec']),70)

    def test_network_gate_retries_until_reachable_without_fixed_boot_delay(self):
        self.assertTrue(hasattr(self.m,'wait_network'),'Network readiness gate missing')
        clock=[0.0]
        attempts=iter([False,False,True])
        def sleep(seconds): clock[0]+=seconds
        with patch.object(self.m.time,'monotonic',side_effect=lambda:clock[0]),patch.object(self.m.time,'sleep',side_effect=sleep):
            self.m.wait_network(probe=lambda:next(attempts),timeout=10)
        self.assertEqual(clock[0],4)
        clock[0]=0
        with patch.object(self.m.time,'monotonic',side_effect=lambda:clock[0]),patch.object(self.m.time,'sleep',side_effect=sleep):
            self.m.wait_network(probe=lambda:True,timeout=10)
        self.assertEqual(clock[0],0)

    def test_offline_start_times_out_for_systemd_retry_without_starting_player(self):
        self.assertTrue(hasattr(self.m,'wait_network'),'Network readiness gate missing')
        clock=[0.0]
        def sleep(seconds): clock[0]+=seconds
        with patch.object(self.m.time,'monotonic',side_effect=lambda:clock[0]),patch.object(self.m.time,'sleep',side_effect=sleep):
            with self.assertRaises(self.m.BackendError):
                self.m.wait_network(probe=lambda:False,timeout=5)
        self.assertEqual(clock[0],5)

    def test_network_probe_checks_tls_reachability_without_credentials(self):
        self.assertTrue(hasattr(self.m,'network_ready'),'Network readiness probe missing')
        seen=[]
        def unavailable(request,timeout):
            seen.append(request)
            raise URLError('offline')
        with patch.object(self.m.urllib.request,'urlopen',side_effect=unavailable):
            self.assertFalse(self.m.network_ready())
        self.assertEqual(seen[0].full_url,'https://accounts.spotify.com/api/token')
        self.assertEqual(seen[0].get_method(),'HEAD')
        self.assertEqual(seen[0].data,None)
        self.assertFalse(seen[0].has_header('Authorization'))
        for code,expected in [(405,True),(503,False)]:
            error=HTTPError('https://accounts.spotify.com/api/token',code,'test',{},io.BytesIO(b''))
            with self.subTest(code=code),patch.object(self.m.urllib.request,'urlopen',side_effect=error):
                self.assertEqual(self.m.network_ready(),expected)
