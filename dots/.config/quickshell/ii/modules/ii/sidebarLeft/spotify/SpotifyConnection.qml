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

    function can(command) { return connected && Logic.allowed(state, command); }
    function send(command, fields) {
        fields = fields || {};
        // Starting an explicit playable URI is allowed independently of current-track actions.
        const explicitPlay = command === "play" && /^spotify:(track|album|playlist|episode):[A-Za-z0-9]+$/.test(fields.uri || "");
        if (!connected || !loggedIn || (!explicitPlay && !Logic.allowed(state, command))) return false;
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
        state = Logic.reduce(state, event);
        clock = Date.now();
        if (event.type === "auth_state" && event.logged_in) {
            send("get_state"); send("get_queue", {limit: 30});
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
