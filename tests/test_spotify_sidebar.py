"""Exercise the actual sidebar JS reducers/navigation and QML loading."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'dots/.config/quickshell/ii'
LOGIC=BASE/'modules/ii/sidebarLeft/spotify/SpotifyLogic.js'


class LogicTests(unittest.TestCase):
    def evaluate(self, body):
        self.assertTrue(LOGIC.exists(), 'Native Spotify sidebar logic missing')
        code=LOGIC.read_text().replace('.pragma library','')+'\n'+body
        return subprocess.check_output(['node','-e',code],text=True).strip()

    def test_outer_tab_selector_is_hidden_unless_multiple_tabs_exist(self):
        import re
        source = (BASE/'modules/ii/sidebarLeft/SidebarLeftContent.qml').read_text()
        match = re.search(r'Toolbar\s*\{\s*visible:\s*([^\n]+)', source)
        self.assertIsNotNone(match)
        assert match is not None
        expression = match.group(1)
        script = 'for (const count of [0,1,2,3,4]) { const tabButtonList=Array(count); const visible=(' + expression + '); if(visible!==(count>1)) throw Error("Wrong selector visibility for "+count+" tabs"); }'
        result = subprocess.run(['node','-e',script],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_visible_tabs_match_pages_for_every_policy_combination(self):
        result=self.evaluate('''for (let mask=0; mask<32; mask++) {
 const [ai,tr,an,cl,sp]=[0,1,2,3,4].map(n=>!!(mask&(1<<n)));
 const buttons=tabKeys(ai,tr,an,cl,sp), pages=pageKeys(ai,tr,an,cl,sp);
 if (buttons.some((v,i)=>v!==pages[i])) throw Error(JSON.stringify({mask,buttons,pages}));
 if (!pages.length) throw Error('Empty sidebar');
} console.log('ok');''')
        self.assertEqual(result,'ok')

    def test_reduce_real_soloist_events_and_clear_auth_state(self):
        result=self.evaluate('''let s=initial(); s=reduce(s,{type:'auth_state',logged_in:true,is_active:true});
s=reduce(s,{type:'playback_state',status:'playing',item:{uri:'spotify:track:abc',decorations:{identity:{name:'Song'},creators:[{entity:{decorations:{identity:{name:'Artist'}}}}],playback:{duration_ms:10000}}},position:{position_ms:2000,timestamp_ms:1000,speed:1},available_actions:{pause:{}}});
if (entity(s.item).title!=='Song'||entity(s.item).subtitle!=='Artist'||position(s,4000)!==5000) throw Error('Bad state');
s=reduce(s,{type:'volume_changed',volume:40}); if(s.volume!==40) throw Error('Volume lost');
s=reduce(s,{type:'queue_changed',upcoming:[{item:{uri:'spotify:track:def',decorations:{identity:{name:'Next'}}}}]});
if(s.queue[0].title!=='Next') throw Error('Queue lost');
s=reduce(s,{type:'auth_state',logged_in:false}); if(s.item.uri||s.queue.length||s.loggedIn) throw Error('Stale auth');
console.log('ok');''')
        self.assertEqual(result,'ok')

    def test_malformed_events_seek_bounds_and_disabled_actions(self):
        result=self.evaluate('''let s=initial(); for (const e of [null,{},[],{type:'playback_state',item:null,position:null},{type:'position_sync',position:{position_ms:'bad'}},{type:'queue_changed',upcoming:null}]) s=reduce(s,e);
if(position(s,1000)!==0) throw Error('Unknown duration');
s.loggedIn=true;s.status='playing';s.item={decorations:{playback:{duration_ms:10000}}};s.position={position_ms:9900,timestamp_ms:0,speed:1};
if(position(s,1000)!==10000||clampSeek(-2,10000)!==0) throw Error('Seek bound');
if(allowed(s,'skip_next')||!allowed(s,'activate')) throw Error('Action gate');
s.actions={skip_next:{}};if(!allowed(s,'skip_next'))throw Error('Available action disabled');
if(!isCurrent(3,3)||isCurrent(2,3))throw Error('Stale search accepted'); console.log('ok');''')
        self.assertEqual(result,'ok')

    def test_port_discovery_rejects_nonlocal_or_invalid_endpoints(self):
        result=self.evaluate('''if(endpoint('127.0.0.1','1234')!=='ws://127.0.0.1:1234')throw Error('Valid rejected');
for(const [a,p] of [['0.0.0.0','1234'],['192.168.1.4','1234'],['127.0.0.1','0'],['127.0.0.1','65536'],['127.0.0.1','1234junk']])if(endpoint(a,p)!=='')throw Error('Unsafe endpoint');console.log('ok');''')
        self.assertEqual(result,'ok')


class QmlConnectionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('qs'), 'Quickshell required')
    def test_actual_qml_connection_loads_and_reduces_events_offscreen(self):
        folder = BASE / 'modules/ii/sidebarLeft/spotify'
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'ws.addr').write_text('127.0.0.1')
            (p/'ws.port').write_text('1')
            source = p/'shell.qml'
            source.write_text('''import QtQuick
import Quickshell
import "''' + folder.as_uri() + '''" as Test
ShellRoot {
 Test.SpotifyConnection { id: backend; connectEnabled: false; dataPath: "''' + str(p) + '''" }
 Timer { interval: 100; running: true; onTriggered: {
  backend.receive(JSON.stringify({type:'auth_state',logged_in:true}));
  backend.receive(JSON.stringify({type:'track_changed',item:{uri:'spotify:track:abc',decorations:{identity:{name:'Fixture track'}}}}));
  if(backend.current.title==='Fixture track') console.log('SPOTIFY_QML_OK');
 } }
}
''')
            proc = subprocess.Popen(['qs','-p',str(source),'--no-color'],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            try:
                output,_ = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.terminate()
                output,_ = proc.communicate(timeout=5)
            self.assertIn('SPOTIFY_QML_OK',output,output)
            self.assertNotIn('ERROR:',output,output)


if __name__=='__main__':
    unittest.main()
