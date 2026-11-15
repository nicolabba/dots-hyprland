"""Exercise actual seek UI and connection against isolated local fixtures."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT/'dots/.config/quickshell/ii/modules/ii/sidebarLeft/spotify'


class SeekInteractionTests(unittest.TestCase):
    def test_real_qml_pointer_keyboard_and_reconciliation(self):
        runner = '/usr/lib/qt6/bin/qmltestrunner'
        if not Path(runner).exists(): runner = shutil.which('qmltestrunner')
        if not runner: self.skipTest('QtTest QML runner required')
        run = subprocess.run([runner,'-input',str(ROOT/'tests/qml'),'-o','-,txt'],
            capture_output=True,text=True,timeout=20,env=dict(os.environ,QT_QPA_PLATFORM='offscreen'))
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertIn('0 failed',run.stdout)


class ConnectionInteractionTests(unittest.TestCase):
    def run_fixture(self, result, cancel=False, seek=False):
        try:
            from websockets.sync.server import serve
            from websockets.exceptions import ConnectionClosed
        except ImportError:
            self.skipTest('websockets Python package required for local fixture')
        if not shutil.which('qs'): self.skipTest('Quickshell required')
        commands=[]
        connections=[]
        def handle(ws):
            try: observe(ws)
            except ConnectionClosed: pass  # qs fixture termination has no close frame.

        def observe(ws):
            connections.append(ws)
            ws.send(json.dumps({'type':'auth_state','logged_in':True,'is_active':True}))
            for message in ws:
                d=json.loads(message);commands.append(d)
                if d['command']=='get_state':
                    ws.send(json.dumps({'type':'playback_state','status':'playing','is_active':True,
                        'item':{'uri':'spotify:track:a','decorations':{'playback':{'duration_ms':200000}}},
                        'position':{'position_ms':20000,'speed':1},'available_actions':{'seek':{},'play':{}}}))
                elif d['command']=='seek': ws.send(json.dumps({'type':'error','message':'Fixture rejected seek'}))
        with tempfile.TemporaryDirectory() as temp, serve(handle,'127.0.0.1',0) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            p=Path(temp);(p/'ws.addr').write_text('127.0.0.1');(p/'ws.port').write_text(str(server.socket.getsockname()[1]))
            helper=p/'helper'
            helper.write_text('#!/usr/bin/env python3\nimport json,sys,time\nif sys.argv[1]=="liked-context":\n time.sleep(0.4)\n print('+repr(json.dumps(result))+')\nelse:\n print(json.dumps({"items":[{"uri":"spotify:track:library","title":"Library sentinel"}],"next_offset":10}))\n')
            helper.chmod(0o700)
            script=p/'shell.qml'
            action='backend.playLiked(); backend.request(["library"], false);'
            if seek: action='backend.send("seek", {position_ms:999999}); if(backend.send("seek", {position_ms:NaN})) console.log("BAD_NAN");'
            script.write_text('''import QtQuick
import Quickshell
import "'''+BACKEND.as_uri()+'''" as Test
ShellRoot {
 Test.SpotifyConnection { id:backend; authorized:true; dataPath:"'''+str(p)+'''"; helper:"'''+str(helper)+'''" }
 Timer { interval:20; repeat:true; running:true; onTriggered:{ if(backend.loggedIn) { stop(); '''+action+''' } } }
 '''+('Timer { interval:200; running:true; onTriggered: backend.connectEnabled=false }' if cancel else '')+'''
 Timer { interval:1100; running:true; onTriggered:{
 console.log("FIXTURE_RESULT", JSON.stringify({authorized:backend.authorized,results:backend.results,error:backend.likedError,cooldown:backend.likedRetryAfter,control:backend.controlError,position:backend.position}));
 } }
}
''')
            proc=subprocess.Popen(['qs','-p',str(script),'--no-color'],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            try:
                try: output,_=proc.communicate(timeout=1.8)
                except subprocess.TimeoutExpired: proc.terminate(); output,_=proc.communicate(timeout=5)
            finally:
                for ws in connections: ws.close()
                server.shutdown();thread.join(timeout=5)
            self.assertNotIn('ERROR:',output,output)
            self.assertNotIn('BAD_NAN',output,output)
            lines=[line.split('FIXTURE_RESULT ',1)[1] for line in output.splitlines() if 'FIXTURE_RESULT ' in line]
            self.assertTrue(lines,output)
            return commands,json.loads(lines[-1])

    def test_liked_play_is_independent_of_browsing(self):
        commands,state=self.run_fixture({'uri':'spotify:user:fixture:collection','total':3800})
        plays=[d for d in commands if d['command']=='play']
        self.assertEqual(plays,[{'type':'command','command':'play','uri':'spotify:user:fixture:collection'}])
        self.assertEqual(state['results'][0]['title'],'Library sentinel')
        self.assertEqual(state['error'],'')

    def test_disconnect_cancels_pending_collection_play(self):
        commands,_=self.run_fixture({'uri':'spotify:user:fixture:collection','total':3800},cancel=True)
        self.assertFalse(any(d['command']=='play' for d in commands))

    def test_failed_or_invalid_collection_does_not_start_playback(self):
        for result in [{'error':'Empty library','kind':'empty'},{'error':'Rate limited','retry_after':30}, {'uri':'spotify:track:wrong','total':5}]:
            with self.subTest(result=result):
                commands,state=self.run_fixture(result)
                self.assertFalse(any(d['command']=='play' for d in commands))
                self.assertTrue(state['error'])
                if 'retry_after' in result: self.assertGreater(state['cooldown'],0)

    def test_seek_is_clamped_and_error_is_reported(self):
        commands,state=self.run_fixture({},seek=True)
        self.assertEqual([d['position_ms'] for d in commands if d['command']=='seek'],[200000])
        self.assertEqual(state['control'],'Fixture rejected seek')
        self.assertGreater(state['position'],20000)

    def test_liked_authorization_failure_exposes_reconnection(self):
        for kind in ['authorization','setup']:
            with self.subTest(kind=kind):
                commands,state=self.run_fixture({'error':'Connect library again','kind':kind})
                self.assertFalse(state['authorized'])
                self.assertFalse(any(d['command']=='play' for d in commands))
