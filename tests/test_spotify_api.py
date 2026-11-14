"""Spotify Web API helper behavior, with no real account secrets."""
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'dots/.local/bin/ii-spotify-api'


def load():
    loader = importlib.machinery.SourceFileLoader('ii_spotify_api', str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    m = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = m
    loader.exec_module(m)
    return m


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'Spotify API integration missing')
        self.m = load()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.folder = self.home / '.config/spotify-sidebar'
        self.folder.mkdir(parents=True)
        (self.folder / 'client-id').write_text('a' * 32)
        self.api = self.m.Api(self.home)

    def token(self, **fields):
        self.api.store_tokens(dict(access_token='private-access', refresh_token='private-refresh', expires_in=3600, **fields))

    def test_client_id_format_is_validated_without_repair(self):
        (self.folder / 'client-id').write_text('not-a-client-id')
        with self.assertRaises(self.m.ApiError):
            self.m.Api(self.home)

    def test_callback_rejects_wrong_path_forged_or_duplicate_state(self):
        for target in ['/wrong?state=good&code=x', '/callback?state=bad&code=x', '/callback?state=good&state=bad&code=x']:
            with self.subTest(target=target):
                with self.assertRaises(self.m.ApiError):
                    self.m.callback_code(target, 'good')
        self.assertEqual(self.m.callback_code('/callback?state=good&code=abc', 'good'), 'abc')
        with self.assertRaises(self.m.ApiError):
            self.m.callback_code('/callback?state=good&error=access_denied', 'good')

    def test_pkce_uses_s256_and_keeps_verifier_out_of_authorize_url(self):
        verifier, url, state = self.m.authorization_request('a' * 32)
        params = parse_qs(urlsplit(url).query)
        self.assertTrue(43 <= len(verifier) <= 128)
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertEqual(params['redirect_uri'], ['http://127.0.0.1:43821/callback'])
        self.assertEqual(params['state'], [state])
        self.assertNotIn(verifier, url)
        self.assertNotIn('user-modify-playback-state', params['scope'][0])

    def test_token_storage_is_private_and_does_not_escape_in_status(self):
        self.token()
        p = self.folder / 'web-api-tokens.json'
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        result = self.api.status()
        self.assertTrue(result['authenticated'])
        self.assertNotIn('private-', json.dumps(result))
        (self.folder / 'client-id').write_text('b' * 32)
        self.assertFalse(self.m.Api(self.home).status()['authenticated'])

    def test_refresh_preserves_old_refresh_token_then_accepts_rotation(self):
        self.token()
        d = self.api.tokens()
        d['expires_at'] = 0
        self.api.write_tokens(d)
        with patch.object(self.api, 'http', return_value={'access_token':'new-access','expires_in':3600}):
            self.assertEqual(self.api.access_token(), 'new-access')
        self.assertEqual(self.api.tokens()['refresh_token'], 'private-refresh')
        with patch.object(self.api, 'http', return_value={'access_token':'newer','refresh_token':'rotated','expires_in':3600}):
            self.api.access_token(force=True)
        self.assertEqual(self.api.tokens()['refresh_token'], 'rotated')

    def test_search_query_is_encoded_and_private_transport_not_returned(self):
        self.token()
        seen = []
        def http(url, **kwargs):
            seen.append(url)
            return {'tracks': {'items': [{'uri':'spotify:track:abc','name':'Test','type':'track','artists':[{'name':'Artist'}], 'album':{'images':[{'url':'https://i.scdn.co/image/test'}]}}], 'next':None}}
        with patch.object(self.api, 'http', side_effect=http):
            result = self.api.browse('search', query='rock & roll?')
        self.assertEqual(parse_qs(urlsplit(seen[0]).query)['q'], ['rock & roll?'])
        self.assertEqual(result['items'][0]['title'], 'Test')
        self.assertEqual(result['items'][0]['subtitle'], 'Artist')
        self.assertNotIn('private-', json.dumps(result))

    def test_current_playlist_envelope_and_removed_items(self):
        self.token()
        data = {'items':[{'item':{'uri':'spotify:track:a','name':'Track','type':'track'}}, {'item':None}, {'track':{'uri':'spotify:track:b','name':'Legacy','type':'track'}}], 'next':'https://api.spotify.com/v1/playlists/id/items?offset=10'}
        with patch.object(self.api, 'http', return_value=data):
            result = self.api.browse('playlist', entity_id='a'*22)
        self.assertEqual([x['title'] for x in result['items']], ['Track','Legacy'])
        self.assertEqual(result['next_offset'], 10)
        with self.assertRaises(self.m.ApiError):
            self.api.browse('playlist', entity_id='../me')

    def test_saved_track_album_and_playlist_normalization(self):
        self.token()
        fixtures = [('tracks', {'track':{'type':'track','uri':'spotify:track:a','name':'Song'}}, 'Song'), ('albums', {'album':{'type':'album','uri':'spotify:album:a','name':'Album'}}, 'Album'), ('playlists', {'type':'playlist','uri':'spotify:playlist:a','name':'List','owner':{'display_name':'Owner'}}, 'List')]
        for kind, item, title in fixtures:
            with self.subTest(kind=kind), patch.object(self.api, 'http', return_value={'items':[item], 'next':None}):
                self.assertEqual(self.api.browse('library', kind=kind)['items'][0]['title'], title)

    def test_rate_limit_is_persisted_and_prevents_immediate_retry(self):
        self.token()
        error = HTTPError('https://api.spotify.com/v1/search',429,'private-access',{'Retry-After':'30'},io.BytesIO(b''))
        with patch.object(self.api, 'http', side_effect=error):
            with self.assertRaises(self.m.ApiError) as e:
                self.api.browse('search', query='test')
        self.assertEqual(e.exception.kind, 'rate_limit')
        self.assertNotIn('private-access', str(e.exception))
        with patch.object(self.api, 'http', side_effect=AssertionError('Network must not be called')):
            with self.assertRaises(self.m.ApiError) as e:
                self.api.browse('search', query='test')
        self.assertEqual(e.exception.kind, 'rate_limit')

    def test_refresh_429_preserves_authorization_and_blocks_further_token_requests(self):
        self.token()
        old=self.api.tokens(); old['expires_at']=0; self.api.write_tokens(old)
        calls=[]
        def fail_refresh(url,**kwargs):
            calls.append(url)
            raise HTTPError(url,429,'throttled',{'Retry-After':'30'},io.BytesIO(b'{}'))
        with patch.object(self.api,'http',side_effect=fail_refresh):
            with self.assertRaises(self.m.ApiError) as first:
                self.api.browse('library')
            self.assertEqual(first.exception.kind,'rate_limit')
            self.assertTrue(self.api.status()['authenticated'])
            self.assertTrue(self.api.cooldown_path.exists())
            with self.assertRaises(self.m.ApiError) as second:
                self.api.browse('library')
            self.assertEqual(second.exception.kind,'rate_limit')
            with self.assertRaises(self.m.ApiError):
                self.api.access_token(force=True)
        self.assertEqual(len(calls),1)
        self.assertNotIn('private-',str(first.exception))

    def test_refresh_503_is_temporary_not_revoked_authorization(self):
        self.token()
        old=self.api.tokens(); old['expires_at']=0; self.api.write_tokens(old)
        error=HTTPError('https://accounts.spotify.com/api/token',503,'unavailable',{},io.BytesIO(b'{}'))
        with patch.object(self.api,'http',side_effect=error):
            with self.assertRaises(self.m.ApiError) as result:
                self.api.browse('library')
        self.assertEqual(result.exception.kind,'temporary')
        self.assertTrue(self.api.status()['authenticated'])
        self.assertEqual(self.api.tokens()['refresh_token'],'private-refresh')

    def test_refresh_invalid_grant_is_reported_as_authorization_failure(self):
        self.token()
        error=HTTPError('https://accounts.spotify.com/api/token',400,'invalid',{},io.BytesIO(b'{"error":"invalid_grant"}'))
        with patch.object(self.api,'http',side_effect=error):
            with self.assertRaises(self.m.ApiError) as result:
                self.api.access_token(force=True)
        self.assertEqual(result.exception.kind,'authorization')

    def test_401_retries_only_once_and_403_is_actionable(self):
        self.token()
        error = HTTPError('https://api.spotify.com/v1/me/tracks',401,'unauthorized',{},io.BytesIO(b''))
        with patch.object(self.api, 'http', side_effect=error), patch.object(self.api,'access_token',return_value='private-access'):
            with self.assertRaises(self.m.ApiError) as e:
                self.api.browse('library')
        self.assertEqual(e.exception.kind, 'authorization')
        error = HTTPError('https://api.spotify.com/v1/me/tracks',403,'forbidden',{},io.BytesIO(b''))
        with patch.object(self.api, 'http', side_effect=error):
            with self.assertRaises(self.m.ApiError) as e:
                self.api.browse('library')
        self.assertEqual(e.exception.kind, 'permission')


if __name__ == '__main__':
    unittest.main()
