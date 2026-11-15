# Spotify Liked Songs and seeking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkboxes for tracking.

**Goal:** Play the complete Liked Songs collection and make native elapsed time/scrubbing reliable.

**Architecture:** Keep Soloist as the only playback target and the existing read-only PKCE helper for account/library metadata. Resolve the authenticated account's collection URI and nonempty library before sending a single context-play command. Use receipt-time-safe playback anchors and a small, directly testable Qt Quick seek control without the shared slider's value smoothing.

**Tech Stack:** Python stdlib, QML/Qt Quick Controls, Quickshell, JavaScript, Node, QtTest.

**Spec:** User-approved reduced scope in this conversation and `.hermes/handoffs/2026-11-15-spotify-sidebar-enhancements.md` (home-relative handoff).

## Global Constraints

- No mixes/radios, playlist creation, new OAuth scopes, generic MPRIS, or cloud polling for playback progress.
- Preserve network startup fix, pairing data, read-only authorization, infinite scrolling and transparency.
- Use `feature/spotify-sidebar-enhancements`; work in the existing clean checkout rather than create an unrequested worktree.
- No merge/push. Deploy through explicit existing backup path only after verification. Live tests must restore original playback as closely as supported.

## Review Focus

- Account identifiers must be validated literally; collection playback must not become an arbitrary-URI bypass.
- Empty/missing/unavailable libraries and API failure must not start an incomplete queue or overwrite independent browsing.
- Pause/buffer/track-switch events must not retain a running clock or previous-track position.
- Drag release, keyboard seeks, track changes during a drag and rejected seeks must not send unintended commands.
- Deployment must contain newly introduced QML files, with no shell/service restart disrupting audio.

### Task 1: Native Liked Songs context

**Files:** `dots/.local/bin/ii-spotify-api`, `spotify/SpotifyConnection.qml`, `spotify/SpotifyLogic.js`, `Spotify.qml`, `tests/test_spotify_api.py`, `tests/test_spotify_sidebar.py` (QML paths under `dots/.config/quickshell/ii/modules/ii/sidebarLeft/`).

**Interfaces:** helper operation `liked-context` returns `{uri, total}` using `GET /me` and a one-item saved-track page; `Logic.playableUri(uri)` narrowly validates existing content URIs plus `spotify:user:<validated-id>:collection`; backend `playLiked()` uses its own Process/generation so browsing cannot consume its response.

- [x] Write helper and URI tests for real collection shape, 3800-item/paged library (no enumeration), unavailable first item, empty library, malformed account IDs, API failures and unchanged scopes.
- [x] Run targeted unittest files; observe expected failures.
- [x] Implement helper and independent backend operation with explicit errors, cooldown feedback, cancellation on disconnect; add discoverable Play Liked Songs action in Liked view.
- [x] Run targeted tests and verify backend requests do not overwrite library results or play after cancellation.

### Task 2: Progress and seek interaction

**Files:** `spotify/SpotifyLogic.js`, `spotify/SpotifyConnection.qml`, new `spotify/SpotifySeek.qml`, `Spotify.qml`, `tests/test_spotify_sidebar.py`, new `tests/qml/tst_spotify_seek.qml`.

**Interfaces:** `reduce(previous,event,receivedAt)` anchors playback transitions, missing/stale timestamps and track changes; backend exposes a revision for authoritative position events. `SpotifySeek` takes `positionMs`, `durationMs`, `trackUri`, `positionRevision`, emits `seekRequested(positionMs)`, and exposes `cancelPending()` for failed/disallowed commands. Use ordinary Qt Controls rendering primitives with caller-supplied shell colors and no animated `value`.

- [x] Reproduce shared StyledSlider smoothing and current transition/keyboard behavior with Node/QML assertions; record the failing behavioral result.
- [x] Write tests covering advance/pause/buffer/resume, missing/stale anchors, track reset and finite bounds; real QtTest pointer and keyboard interaction must cover preview, one seek on release, clamping, rejection, track changes and authoritative reconciliation.
- [x] Implement the smallest anchor and seek component changes that satisfy those tests. Preserve existing 500 ms clock; do not add Web API polling.
- [x] Run targeted tests, then whole suite.

### Task 3: Review, deployment and verification

**Files:** `dots/.local/bin/ii-soloist` deployment manifest, `docs/spotify-soloist.md`, tests as required.

- [x] Test deployment includes SpotifySeek.qml, then add it to the manifest.
- [x] Run `python -m unittest discover -s tests -v`, helper py_compile, `systemd-analyze --user verify` for Soloist units/timer, and `git diff --check`.
- [x] Obtain one independent whole-feature review and fix material findings with RED→GREEN tests.
- [x] Deploy using `ii-soloist setup-sidebar`; compare deployed sources and inspect shell errors. Verify actual native page, advancing elapsed time, pointer/keyboard seek and collection continuation without changing unrelated players; restore previous context/track/paused state as supported.
- [x] Document actual evidence and limitations, leave changes on feature branch without merge/push.
