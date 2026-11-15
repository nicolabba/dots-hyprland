import QtQuick
import QtQuick.Controls
import QtTest
import "../../dots/.config/quickshell/ii/modules/ii/sidebarLeft/spotify" as Spotify

TestCase {
    id: test
    name: "SpotifySeek"
    width: 400; height: 160
    visible: true
    when: windowShown
    property var seek
    Component {
        id: factory
        Spotify.SpotifySeek { width: 320; height: 40; durationMs: 200000; positionMs: 20000; trackUri: "spotify:track:a"; canSeek: true }
    }
    SignalSpy { id: requests; signalName: "seekRequested" }
    function init() { seek = createTemporaryObject(factory, test, {x:20,y:30}); verify(seek); requests.target=seek; requests.clear(); wait(20); }
    function test_authoritative_updates_are_immediate_and_do_not_send() {
        compare(seek.value,20000);
        seek.positionMs=150000;
        compare(seek.value,150000);
        compare(requests.count,0);
        seek.visible=false; seek.positionMs=160000; seek.visible=true;
        compare(seek.value,160000);
    }
    function test_drag_previews_and_releases_once_despite_live_updates() {
        mousePress(seek,40,20); mouseMove(seek,240,20,30);
        verify(seek.pressed);
        let selected=seek.value;
        verify(selected>130000);
        compare(requests.count,0);
        seek.positionMs=30000;
        compare(seek.value,selected);
        compare(seek.displayPosition,selected);
        mouseRelease(seek,240,20);
        compare(requests.count,1);
        fuzzyCompare(requests.signalArguments[0][0],selected,1);
        compare(seek.value,selected);
        seek.positionMs=selected+200; seek.positionRevision++;
        compare(seek.value,selected+200);
    }
    function test_keyboard_seeks_and_bounds() {
        seek.forceActiveFocus(); keyClick(Qt.Key_Right);
        compare(requests.count,1); compare(requests.signalArguments[0][0],25000);
        seek.cancelPending(); seek.positionMs=199000;
        keyClick(Qt.Key_Right); compare(requests.count,2); compare(requests.signalArguments[1][0],200000);
        seek.cancelPending(); seek.positionMs=1000;
        keyClick(Qt.Key_Left); compare(requests.count,3); compare(requests.signalArguments[2][0],0);
    }
    function test_track_change_during_drag_cancels_release() {
        mousePress(seek,40,20); mouseMove(seek,240,20,20);
        seek.trackUri="spotify:track:b"; seek.positionMs=0;
        mouseRelease(seek,240,20);
        compare(requests.count,0); compare(seek.value,0);
    }
    function test_disallowed_or_unknown_duration_never_seeks() {
        seek.canSeek=false; mouseClick(seek,240,20);
        compare(requests.count,0);
        seek.canSeek=true; seek.durationMs=0;
        verify(!seek.enabled); mouseClick(seek,240,20); compare(requests.count,0);
    }
    function test_disallow_during_drag_cancels_release() {
        mousePress(seek,40,20); mouseMove(seek,240,20,20);
        seek.canSeek=false; mouseRelease(seek,240,20);
        compare(requests.count,0);
    }
    function test_failed_seek_and_timeout_reconcile() {
        mouseClick(seek,240,20); compare(requests.count,1);
        seek.cancelPending(); compare(seek.value,20000);
        mouseClick(seek,240,20); compare(requests.count,2);
        tryCompare(seek,"pending",false,2500);
        compare(seek.value,20000);
    }
}
