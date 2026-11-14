.pragma library

function tabKeys(ai, translator, anime, closet, spotify) {
    return [].concat(ai ? ["ai"] : [], translator ? ["translator"] : [], anime && !closet ? ["anime"] : [], spotify ? ["spotify"] : []);
}
function pageKeys(ai, translator, anime, closet, spotify) {
    var keys = tabKeys(ai, translator, anime, closet, spotify);
    if (!keys.length) keys.push("placeholder");
    if (anime && closet) keys.push("anime");
    return keys;
}
function initial() {
    return {loggedIn: false, active: false, status: "idle", item: {}, context: {}, position: {}, volume: 25, options: {}, actions: {}, queue: []};
}
function object(value) { return value && typeof value === "object" && !Array.isArray(value) ? value : {}; }
function entity(value) {
    var e = object(value), d = object(e.decorations);
    var creators = Array.isArray(d.creators) ? d.creators : [];
    var covers = object(d.visual_identity).cover;
    covers = Array.isArray(covers) ? covers : [];
    var cover = covers.find(function(c) { return c && (c.size === "large" || c.size === "xlarge"); }) || covers[0] || {};
    var image = typeof cover.url === "string" && /^https:\/\/i\.scdn\.co\//.test(cover.url) ? cover.url : "";
    return {uri: e.uri || "", title: object(d.identity).name || "Nothing playing",
        subtitle: creators.map(function(c) { return object(object(object(c).entity).decorations).identity; }).map(function(c) { return object(c).name || ""; }).filter(Boolean).join(", "),
        image: image, kind: e.entity_type || "", duration: Math.max(0, Number(object(d.playback).duration_ms) || 0)};
}
function reduce(previous, event) {
    var e = object(event), s = Object.assign({}, previous);
    switch(e.type) {
    case "auth_state":
        if (!e.logged_in) s = initial();
        s.loggedIn = e.logged_in === true; s.active = e.is_active === true; break;
    case "playback_state":
        s.status = typeof e.status === "string" ? e.status : "idle";
        s.item = object(e.item); s.context = object(e.context); s.position = object(e.position);
        s.volume = Math.max(0, Math.min(100, Number(e.volume) || 0)); s.active = e.is_active === true;
        s.options = object(e.options); s.actions = object(e.available_actions); break;
    case "track_changed": s.item = object(e.item); break;
    case "playback_changed": s.status = e.status || "idle"; break;
    case "position_sync": s.position = object(e.position); break;
    case "volume_changed": s.volume = Math.max(0, Math.min(100, Number(e.volume) || 0)); break;
    case "device_changed": s.active = e.is_active === true; break;
    case "context_changed": s.context = object(e.context); break;
    case "options_changed": s.options = object(e.options); break;
    case "queue_changed": s.queue = (Array.isArray(e.upcoming) ? e.upcoming : []).map(function(x) { return entity(object(x).item); }).filter(function(x) { return !!x.uri; }); break;
    }
    return s;
}
function position(s, now) {
    var p = object(s.position), duration = entity(s.item).duration;
    var start = Number(p.position_ms) || 0, timestamp = typeof p.timestamp_ms === "number" && Number.isFinite(p.timestamp_ms) ? p.timestamp_ms : now;
    var speed = s.status === "playing" ? Math.max(0, Number(p.speed) || 0) : 0;
    return clampSeek(start + Math.max(0, now - timestamp) * speed, duration);
}
function clampSeek(value, duration) { return Math.max(0, Math.min(Math.max(0, duration || 0), Number(value) || 0)); }
function isCurrent(generation, current) { return generation === current; }
function endpoint(address, port) {
    var a = String(address).trim(), p = String(port).trim();
    return a === "127.0.0.1" && /^[0-9]+$/.test(p) && Number(p) > 0 && Number(p) < 65536 ? "ws://127.0.0.1:" + Number(p) : "";
}
function allowed(s, command) {
    if (!s.loggedIn) return false;
    if (["activate", "deactivate", "set_volume", "get_state", "get_queue"].indexOf(command) >= 0) return true;
    var key = command === "set_shuffle" ? "shuffle" : command.indexOf("set_repeat_") === 0 ? "set_repeat" : command;
    return Object.prototype.hasOwnProperty.call(object(s.actions), key);
}
function formatTime(ms) {
    var seconds = Math.floor(Math.max(0, ms || 0) / 1000);
    return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
}
