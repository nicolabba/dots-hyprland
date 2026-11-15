import QtQuick
import QtQuick.Controls
import "SpotifyLogic.js" as Logic

// Values are milliseconds: never run them through StyledSlider's value
// smoothing. Keep pointer preview separate from authoritative playback updates.
Slider {
    id: root
    property real positionMs: 0
    property real durationMs: 0
    property string trackUri: ""
    property int positionRevision: 0
    property bool canSeek: false
    property color highlightColor: palette.highlight
    property color trackColor: palette.mid
    property color handleColor: highlightColor
    property bool pending: false
    property bool editing: false
    property bool movedDuringPress: false
    property string pressedTrack: ""
    readonly property real displayPosition: pressed || pending ? value : Logic.clampSeek(positionMs, durationMs)
    signal seekRequested(real positionMs)

    implicitHeight: 36
    leftPadding: 4; rightPadding: 4
    from: 0; to: Math.max(1, Logic.finite(durationMs, 0))
    stepSize: 5000
    enabled: canSeek && durationMs > 0 && !!trackUri
    focusPolicy: Qt.StrongFocus
    Accessible.name: "Playback position"
    Accessible.description: Logic.formatTime(displayPosition) + " of " + Logic.formatTime(durationMs)

    function cancelPending() { pending = false; reconcile.stop(); }
    function submit(selected) {
        if (!enabled) return;
        pending = true;
        reconcile.restart();
        seekRequested(Math.round(Logic.clampSeek(selected, durationMs)));
    }
    onPressedChanged: {
        if (pressed) {
            editing = true;
            movedDuringPress = false;
            pressedTrack = trackUri;
        } else if (movedDuringPress && pressedTrack === trackUri && enabled) {
            movedDuringPress = false;
            // Capture before the value binding can be restored on release.
            submit(value);
        }
        if (!pressed) editing = false;
    }
    onMoved: {
        if (pressed) movedDuringPress = true;
        else submit(value); // Keyboard/wheel interactions do not require a drag.
    }
    onTrackUriChanged: { movedDuringPress = false; cancelPending(); }
    onEnabledChanged: if (!enabled) { movedDuringPress = false; cancelPending(); }
    onPositionRevisionChanged: cancelPending()
    Binding {
        target: root; property: "value"
        value: Logic.clampSeek(root.positionMs, root.durationMs)
        when: !root.pressed && !root.editing && !root.pending
        restoreMode: Binding.RestoreNone
    }
    Timer { id: reconcile; interval: 1800; onTriggered: root.pending = false }

    background: Item {
        x: root.leftPadding; y: (root.height - 18) / 2
        width: root.availableWidth; height: 18
        Rectangle { anchors.fill: parent; radius: 6; color: root.trackColor }
        Rectangle { width: root.visualPosition * parent.width; height: parent.height; radius: 6; color: root.highlightColor }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * root.availableWidth - width / 2
        y: (root.height - height) / 2
        width: root.pressed ? 2 : 3; height: 33; radius: 2
        color: root.handleColor
        Rectangle { anchors.fill: parent; anchors.margins: -4; radius: 5; color: "transparent"; border.color: root.highlightColor; visible: root.activeFocus }
    }
    ToolTip.visible: pressed
    ToolTip.text: Logic.formatTime(displayPosition)
}
