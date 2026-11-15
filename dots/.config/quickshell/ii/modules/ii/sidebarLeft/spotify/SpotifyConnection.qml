import QtQuick
import QtWebSockets
import Quickshell
import Quickshell.Io
import "SpotifyLogic.js" as Logic

// Instance-scoped: created only when the opt-in Spotify sidebar page is loaded.
Scope {
    id: root
    property bool connectEnabled: true
    property string dataPath: Quickshell.env("HOME") + "/.local/share/spotify-sidebar/soloist-data"
    property string helper: Quickshell.env("HOME") + "/.local/bin/ii-spotify-api"
    property var state: Logic.initial()
    readonly property bool connected: socket.status === WebSocket.Open
    readonly property bool loggedIn: connected && state.loggedIn
    readonly property bool active: loggedIn && state.active
    readonly property var current: Logic.entity(state.item)
    readonly property var queue: state.queue
    property double clock: Date.now()
    readonly property double position: connected ? Logic.position(state, clock) : 0
    property int positionRevision: 0
    property string endpointUrl: ""
    property string controlError: ""
    property string browseError: ""
    property bool authorized: false
    property var results: []
    property var nextOffset: null
    property int generation: 0
    property var queuedRequest: null
    readonly property bool busy: apiProc.running || queuedRequest !== null
    readonly property bool authorizing: authProc.running
    property int retryAfter: 0
    readonly property bool likedBusy: likedProc.running
    property string likedError: ""
    property int likedRetryAfter: 0
    property int likedGeneration: 0
    onLoggedInChanged: if (!loggedIn) likedGeneration += 1

    function playLiked() {
        if (!loggedIn || likedBusy || likedRetryAfter > 0) return;
        likedError = "";
        likedGeneration += 1;
        likedProc.requestGeneration = likedGeneration;
        likedProc.running = true;
    }

    function can(command) { return connected && Logic.allowed(state, command); }
    function send(command, fields) {
        fields = fields || {};
        // Starting an explicit playable URI is allowed independently of current-track actions.
        const explicitPlay = command === "play" && Logic.playableUri(fields.uri);
        if (command === "play" && fields.uri !== undefined && !explicitPlay) return false;
        if (!connected || !loggedIn || (!explicitPlay && !Logic.allowed(state, command))) return false;
        if (command === "seek") {
            if (!Number.isFinite(fields.position_ms) || current.duration <= 0) return false;
            fields = Object.assign({}, fields, {position_ms: Math.round(Logic.clampSeek(fields.position_ms, current.duration))});
        }
        controlError = "";
        socket.sendTextMessage(JSON.stringify(Object.assign({type: "command", command: command}, fields)));
        return true;
    }
    function setRepeat(mode) {
        if (mode === "track") {
            send("set_repeat_context", {enabled: false}); send("set_repeat_track", {enabled: true});
        } else {
            send("set_repeat_track", {enabled: false}); send("set_repeat_context", {enabled: mode === "context"});
        }
    }
    function receive(message) {
        let event;
        try { event = JSON.parse(message); } catch (_) { controlError = "Invalid playback update"; return; }
        if (!event || typeof event !== "object") return;
        if (event.type === "error") { controlError = String(event.message || "Playback command failed"); return; }
        const receivedAt = Date.now();
        const next = Logic.reduce(state, event, receivedAt);
        const anchorChanged = next.position !== state.position;
        state = next;
        clock = receivedAt;
        if (anchorChanged && ["playback_state", "position_sync"].indexOf(event.type) >= 0) positionRevision += 1;
        if (event.type === "auth_state" && event.logged_in) {
            send("get_state"); send("get_queue", {limit: 0});
        } else if (["track_changed", "playback_changed", "device_changed"].indexOf(event.type) >= 0 && loggedIn) {
            send("get_state");
        }
    }
    function discover() {
        addressFile.reload(); portFile.reload();
    }
    function resolveEndpoint() {
        let next = "";
        try { next = Logic.endpoint(addressFile.text(), portFile.text()); } catch (_) {}
        if (next !== endpointUrl) endpointUrl = next;
        // A failed socket at the same address needs an explicit reconnect.
        if (connectEnabled && endpointUrl && (socket.status === WebSocket.Error || socket.status === WebSocket.Closed)) {
            socket.active = false;
            Qt.callLater(function() { socket.active = root.connectEnabled && !!root.endpointUrl; });
        }
    }
    function request(args, append) {
        generation += 1;
        if (!append && args[0] !== "status") { results = []; nextOffset = null; }
        browseError = "";
        queuedRequest = {args: args, append: !!append, generation: generation};
        startNext();
    }
    function startNext() {
        if (apiProc.running || !queuedRequest) return;
        const req = queuedRequest; queuedRequest = null;
        apiProc.requestGeneration = req.generation;
        apiProc.appendResults = req.append;
        apiProc.command = [helper].concat(req.args);
        apiProc.running = true;
    }
    function authorize() {
        if (!authProc.running) { browseError = ""; authProc.running = true; }
    }

    FileView {
        id: addressFile
        path: root.dataPath + "/ws.addr"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: root.resolveEndpoint()
        onLoadFailed: { root.endpointUrl = ""; root.state = Logic.initial(); }
    }
    FileView {
        id: portFile
        path: root.dataPath + "/ws.port"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: root.resolveEndpoint()
        onLoadFailed: { root.endpointUrl = ""; root.state = Logic.initial(); }
    }
    Timer { interval: 3000; repeat: true; running: root.connectEnabled; triggeredOnStart: true; onTriggered: root.discover() }
    Timer { interval: 500; repeat: true; running: root.connected && root.state.status === "playing"; onTriggered: root.clock = Date.now() }
    Timer { interval: 1000; repeat: true; running: root.retryAfter > 0; onTriggered: root.retryAfter -= 1 }
    Timer { interval: 1000; repeat: true; running: root.likedRetryAfter > 0; onTriggered: root.likedRetryAfter -= 1 }
    WebSocket {
        id: socket
        url: root.endpointUrl
        active: root.connectEnabled && root.endpointUrl !== ""
        onTextMessageReceived: message => root.receive(message)
        onStatusChanged: (status) => {
            if (status !== WebSocket.Open) root.state = Logic.initial();
            if (status === WebSocket.Open) root.controlError = "";
        }
    }
    Process {
        id: apiProc
        property int requestGeneration: 0
        property bool appendResults: false
        stdout: StdioCollector { id: apiOutput }
        onExited: (code, status) => {
            if (Logic.isCurrent(requestGeneration, root.generation)) {
                try {
                    const result = JSON.parse(apiOutput.text);
                    if (result.error) {
                        root.browseError = String(result.error);
                        root.retryAfter = Math.max(0, Number(result.retry_after) || 0);
                        if (result.kind === "authorization" || result.kind === "setup") root.authorized = false;
                    } else if (result.authenticated !== undefined) {
                        root.authorized = result.authenticated === true;
                    } else {
                        root.authorized = true;
                        root.results = appendResults ? root.results.concat(result.items || []) : (result.items || []);
                        root.nextOffset = result.next_offset === undefined ? null : result.next_offset;
                    }
                } catch (_) { root.browseError = "Unable to load Spotify items. Check the installed API helper."; }
            }
            Qt.callLater(root.startNext);
        }
    }
    Process {
        id: likedProc
        property int requestGeneration: 0
        command: [root.helper, "liked-context"]
        stdout: StdioCollector { id: likedOutput }
        onExited: (code, status) => {
            if (requestGeneration !== root.likedGeneration || !root.loggedIn) return;
            try {
                const result = JSON.parse(likedOutput.text);
                if (result.error) {
                    root.likedError = String(result.error);
                    root.likedRetryAfter = Math.max(0, Number(result.retry_after) || 0);
                    if (result.kind === "authorization" || result.kind === "setup") root.authorized = false;
                } else if (code !== 0 || !/^spotify:user:[A-Za-z0-9._~-]+:collection$/.test(result.uri || "") || !(result.total > 0)) {
                    root.likedError = "Spotify could not confirm your Liked Songs library.";
                } else if (!root.send("play", {uri: result.uri})) {
                    root.likedError = "Unable to start Liked Songs. Check the Soloist connection.";
                }
            } catch (_) { root.likedError = "Unable to load Liked Songs. Check the installed API helper."; }
        }
    }
    Process {
        id: authProc
        command: [root.helper, "authorize"]
        stdout: StdioCollector { id: authOutput }
        onExited: (code, status) => {
            try {
                const result = JSON.parse(authOutput.text);
                root.authorized = result.authenticated === true;
                root.browseError = result.error || "";
            } catch (_) { root.browseError = "Spotify authorization did not finish."; }
        }
    }
}
