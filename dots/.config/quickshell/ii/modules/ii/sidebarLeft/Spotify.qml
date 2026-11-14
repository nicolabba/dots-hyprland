import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "spotify" as Backend
import qs.modules.common
import qs.modules.common.widgets
import "spotify/SpotifyLogic.js" as Logic

Item {
    id: root
    implicitWidth: 420
    implicitHeight: 650
    property int viewIndex: 0
    property string libraryKind: "tracks"
    property string detailKind: ""
    property string detailId: ""
    property string detailTitle: ""
    property alias backend: backend

    Backend.SpotifyConnection { id: backend }
    function loadCurrent(offset, append) {
        let args;
        if (search.text.trim()) args = ["search", "--query", search.text.trim()];
        else if (detailId) args = [detailKind, "--id", detailId];
        else args = ["library", "--kind", libraryKind];
        args = args.concat(["--offset", String(offset || 0)]);
        backend.request(args, !!append);
    }
    function openItem(item) {
        if (item.kind === "album" || item.kind === "playlist") {
            detailKind = item.kind; detailId = item.uri.split(":")[2]; detailTitle = item.title;
            search.text = ""; loadCurrent(0, false);
        } else backend.send("play", {uri: item.uri});
    }
    Component.onCompleted: backend.request(["status"], false)
    Connections {
        target: backend
        function onAuthorizedChanged() { if (backend.authorized && root.viewIndex === 2) root.loadCurrent(0, false); }
    }
    Timer { id: searchDelay; interval: 500; onTriggered: root.loadCurrent(0, false) }

    component Chip: RippleButton {
        id: chip
        implicitHeight: 36
        implicitWidth: chipText.implicitWidth + 24
        padding: 8
        buttonRadius: Appearance.rounding.small
        contentItem: StyledText {
            id: chipText
            text: chip.buttonText
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: chip.toggled ? Appearance.colors.colOnPrimary : Appearance.colors.colOnLayer1
            font.pixelSize: 13
        }
    }
    component TrackRow: RippleButton {
        id: row
        required property var entry
        property bool browsing: false
        implicitHeight: 66
        buttonRadius: Appearance.rounding.small
        onClicked: browsing ? root.openItem(entry) : backend.send("play", {uri: entry.uri})
        contentItem: RowLayout {
            spacing: 10
            Rectangle {
                Layout.preferredWidth: 44; Layout.preferredHeight: 44
                radius: Appearance.rounding.small
                color: Appearance.colors.colLayer2
                Image { anchors.fill: parent; source: row.entry.image || ""; fillMode: Image.PreserveAspectFit; asynchronous: true }
                MaterialSymbol { anchors.centerIn: parent; visible: !row.entry.image; text: "music_note"; iconSize: 22 }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                StyledText { Layout.fillWidth: true; text: row.entry.title || "Unavailable item"; elide: Text.ElideRight; font.pixelSize: 14 }
                StyledText { Layout.fillWidth: true; text: row.entry.subtitle || row.entry.kind || ""; color: Appearance.colors.colSubtext; elide: Text.ElideRight; font.pixelSize: 12 }
            }
            IconToolbarButton {
                Layout.fillHeight: false; implicitWidth: 32; implicitHeight: 36
                text: row.browsing && ["album", "playlist"].indexOf(row.entry.kind) >= 0 ? "play_arrow" : "add_to_queue"
                enabled: backend.loggedIn && (text === "play_arrow" || backend.can("add_to_queue"))
                onClicked: text === "play_arrow" ? backend.send("play", {uri: row.entry.uri}) : backend.send("add_to_queue", {uri: row.entry.uri})
                StyledToolTip { text: parent.text === "play_arrow" ? "Play on Sidebar Spotify" : "Add to queue" }
            }
        }
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            MaterialSymbol { text: "music_note"; iconSize: 24 }
            StyledText { text: "Spotify"; font.pixelSize: 19; font.bold: true; Layout.fillWidth: true }
            StyledText {
                text: !backend.connected ? "Offline" : !backend.loggedIn ? "Pair device" : backend.active ? "This device" : "Connected"
                color: Appearance.colors.colSubtext
                font.pixelSize: 12
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Repeater {
                model: ["Now Playing", "Queue", "Library"]
                delegate: Chip {
                    required property int index
                    required property string modelData
                    Layout.fillWidth: true
                    buttonText: modelData
                    toggled: root.viewIndex === index
                    onClicked: { root.viewIndex = index; if (index === 2) root.loadCurrent(0, false); }
                }
            }
        }
        StyledText {
            Layout.fillWidth: true
            visible: !backend.connected || !backend.loggedIn || !!backend.controlError
            text: backend.controlError || (!backend.connected ? "Soloist is offline. Check ii-soloist.service." : "Select Sidebar Spotify in Spotify’s device picker to pair.")
            color: Appearance.colors.colSubtext
            wrapMode: Text.WordWrap
            font.pixelSize: 13
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.viewIndex
            Item {
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10
                    Item { Layout.fillHeight: true; Layout.minimumHeight: 0 }
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: Math.min(240, root.width - 48)
                        Layout.preferredHeight: Math.min(240, root.width - 48, root.height * 0.32)
                        color: Appearance.colors.colLayer2
                        radius: Appearance.rounding.normal
                        Image { anchors.fill: parent; source: backend.current.image; fillMode: Image.PreserveAspectFit; asynchronous: true }
                        MaterialSymbol { anchors.centerIn: parent; visible: !backend.current.image; text: "album"; iconSize: 72 }
                    }
                    StyledText { Layout.fillWidth: true; text: backend.connected ? backend.current.title : "Spotify is offline"; font.pixelSize: 21; font.bold: true; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight }
                    StyledText { Layout.fillWidth: true; text: backend.current.subtitle; horizontalAlignment: Text.AlignHCenter; color: Appearance.colors.colSubtext; elide: Text.ElideRight }
                    StyledText { Layout.fillWidth: true; text: backend.state.status === "buffering" ? "Buffering…" : ""; visible: !!text; color: Appearance.colors.colSubtext; horizontalAlignment: Text.AlignHCenter }
                    StyledSlider {
                        id: seek
                        Layout.fillWidth: true
                        from: 0; to: Math.max(1, backend.current.duration)
                        enabled: backend.can("seek") && backend.current.duration > 0
                        value: backend.position
                        usePercentTooltip: false
                        tooltipContent: Logic.formatTime(value)
                        onPressedChanged: if (!pressed) backend.send("seek", {position_ms: Math.round(Logic.clampSeek(value, backend.current.duration))})
                        Binding { target: seek; property: "value"; value: backend.position; when: !seek.pressed; restoreMode: Binding.RestoreBindingOrValue }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        StyledText { text: Logic.formatTime(seek.pressed ? seek.value : backend.position); font.pixelSize: 12; color: Appearance.colors.colSubtext }
                        Item { Layout.fillWidth: true }
                        StyledText { text: Logic.formatTime(backend.current.duration); font.pixelSize: 12; color: Appearance.colors.colSubtext }
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 12
                        IconToolbarButton { Layout.fillHeight: false; implicitWidth: 38; implicitHeight: 40; text: "shuffle"; toggled: backend.state.options.shuffle === true; enabled: backend.can("set_shuffle"); onClicked: backend.send("set_shuffle", {enabled: !backend.state.options.shuffle}) }
                        IconToolbarButton { Layout.fillHeight: false; implicitWidth: 38; implicitHeight: 40; text: "skip_previous"; enabled: backend.can("skip_prev"); onClicked: backend.send("skip_prev") }
                        IconToolbarButton { Layout.fillHeight: false; implicitWidth: 56; implicitHeight: 52; text: backend.state.status === "playing" ? "pause" : "play_arrow"; enabled: backend.can(backend.state.status === "playing" ? "pause" : "play"); onClicked: backend.send(backend.state.status === "playing" ? "pause" : "play") }
                        IconToolbarButton { Layout.fillHeight: false; implicitWidth: 38; implicitHeight: 40; text: "skip_next"; enabled: backend.can("skip_next"); onClicked: backend.send("skip_next") }
                        IconToolbarButton { Layout.fillHeight: false; implicitWidth: 38; implicitHeight: 40; text: backend.state.options.repeat === "track" ? "repeat_one" : "repeat"; toggled: !!backend.state.options.repeat && backend.state.options.repeat !== "off"; enabled: backend.can("set_repeat_context"); onClicked: backend.setRepeat(backend.state.options.repeat === "off" ? "context" : backend.state.options.repeat === "context" ? "track" : "off") }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        MaterialSymbol { text: "volume_up"; iconSize: 20 }
                        StyledSlider {
                            id: volume
                            Layout.fillWidth: true
                            from: 0; to: 100; stepSize: 1
                            value: backend.state.volume
                            enabled: backend.loggedIn
                            onMoved: backend.send("set_volume", {volume: Math.round(value)})
                            Binding { target: volume; property: "value"; value: backend.state.volume; when: !volume.pressed; restoreMode: Binding.RestoreBindingOrValue }
                        }
                        StyledText { text: Math.round(volume.value) + "%"; font.pixelSize: 12; Layout.preferredWidth: 38 }
                    }
                    Chip { Layout.alignment: Qt.AlignHCenter; visible: backend.loggedIn && !backend.active; buttonText: "Use this device"; onClicked: backend.send("activate") }
                    Item { Layout.fillHeight: true; Layout.minimumHeight: 0 }
                }
            }
            Item {
                ListView {
                    id: queueList
                    anchors.fill: parent
                    clip: true; spacing: 4
                    model: backend.queue
                    delegate: TrackRow { required property var modelData; width: queueList.width; entry: modelData; enabled: backend.loggedIn }
                    ScrollBar.vertical: ScrollBar {}
                }
                StyledText { anchors.centerIn: parent; visible: backend.queue.length === 0; text: backend.loggedIn ? "Your queue is empty" : "Connect Soloist to see the queue"; color: Appearance.colors.colSubtext }
            }
            ColumnLayout {
                spacing: 8
                TextField {
                    id: search
                    Layout.fillWidth: true
                    implicitHeight: 42
                    placeholderText: "Search tracks, albums and playlists"
                    color: Appearance.colors.colOnLayer1
                    placeholderTextColor: Appearance.colors.colSubtext
                    selectionColor: Appearance.colors.colPrimary
                    selectedTextColor: Appearance.colors.colOnPrimary
                    background: Rectangle { color: Appearance.colors.colLayer2; radius: Appearance.rounding.small }
                    onTextEdited: {
                        root.detailId = ""; root.detailTitle = "";
                        backend.generation += 1; backend.queuedRequest = null;
                        backend.results = []; backend.nextOffset = null;
                        searchDelay.restart();
                    }
                    onAccepted: { searchDelay.stop(); root.loadCurrent(0, false); }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: !search.text.trim() && !root.detailId
                    Repeater {
                        model: [{key: "tracks", label: "Liked"}, {key: "albums", label: "Albums"}, {key: "playlists", label: "Playlists"}]
                        delegate: Chip {
                            required property var modelData
                            Layout.fillWidth: true
                            buttonText: modelData.label
                            toggled: root.libraryKind === modelData.key
                            onClicked: { root.libraryKind = modelData.key; root.loadCurrent(0, false); }
                        }
                    }
                }
                RowLayout {
                    visible: !!root.detailId
                    IconToolbarButton { Layout.fillHeight: false; implicitWidth: 36; implicitHeight: 36; text: "arrow_back"; onClicked: { root.detailId = ""; root.detailTitle = ""; root.loadCurrent(0, false); } }
                    StyledText { Layout.fillWidth: true; text: root.detailTitle; elide: Text.ElideRight; font.bold: true }
                    IconToolbarButton { Layout.fillHeight: false; implicitWidth: 36; implicitHeight: 36; text: "play_arrow"; enabled: backend.loggedIn; onClicked: backend.send("play", {uri: "spotify:" + root.detailKind + ":" + root.detailId}) }
                }
                Chip { visible: !backend.authorized; Layout.fillWidth: true; buttonText: backend.authorizing ? "Waiting for Spotify authorization…" : "Connect library"; enabled: !backend.authorizing; onClicked: backend.authorize() }
                StyledText { visible: !!backend.browseError; Layout.fillWidth: true; text: backend.browseError + (backend.retryAfter > 0 ? " Retry in " + backend.retryAfter + "s." : ""); wrapMode: Text.WordWrap; font.pixelSize: 13; color: Appearance.colors.colSubtext }
                Backend.PagedList {
                    id: libraryList
                    objectName: "spotifyLibraryList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true; spacing: 4
                    entries: backend.results
                    pagingActive: root.visible && root.viewIndex === 2 && !searchDelay.running
                    authorized: backend.authorized
                    busy: backend.busy
                    blocked: !!backend.browseError || backend.retryAfter > 0
                    nextOffset: backend.nextOffset
                    onFetchNext: root.loadCurrent(backend.nextOffset, true)
                    delegate: TrackRow { required property var model; width: libraryList.width; entry: model; browsing: true }
                    ScrollBar.vertical: ScrollBar {}
                    StyledText { anchors.centerIn: parent; visible: !backend.busy && backend.authorized && !backend.results.length && !backend.browseError; text: "No items found"; color: Appearance.colors.colSubtext }
                }
                RowLayout {
                    visible: backend.busy
                    Layout.alignment: Qt.AlignHCenter
                    StyledText { text: "Loading Spotify…"; color: Appearance.colors.colSubtext; font.pixelSize: 12 }
                }
                Chip { visible: !!backend.browseError; Layout.fillWidth: true; buttonText: "Retry"; enabled: !backend.busy && backend.retryAfter <= 0; onClicked: root.loadCurrent(0, false) }
            }
        }
    }
}
