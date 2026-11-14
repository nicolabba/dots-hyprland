# Native Spotify Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete feature/spotify-sidebar with native Spotify-only playback, queue and authorized library/search alongside existing sidebar tabs.
**Architecture:** QML connects directly to Soloist's localhost WebSocket for event-driven state/control; a Python standard-library subprocess helper handles Spotify Web API OAuth PKCE and read-only browsing. Reuse existing sidebar tokens/widgets; leave generic MPRIS unchanged.
**Tech Stack:** Quickshell/QtQuick/QtWebSockets, Python 3, unittest, Spotify Web API PKCE.
**Spec:** docs/superpowers/specs/2026-11-14-spotify-sidebar-design.md

## Global Constraints
- Same feature/spotify-sidebar branch in nicolabba/dots-hyprland. No push, secrets or proprietary binaries in Git.
- Persistent Soloist data: ~/.local/share/spotify-sidebar/soloist-data; localhost WebSocket only.
- Client ID: ~/.config/spotify-sidebar/client-id; redirect http://127.0.0.1:43821/callback; PKCE, no client secret.
- Read-only scopes user-library-read playlist-read-private playlist-read-collaborative. Private OAuth tokens never passed through QML/stdout.
- Default Spotify tab disabled for other users; explicitly enable this user's setup.
- Playback/queue remains available without Web API authorization. Never control another MPRIS player.

## Review Focus
- Denied/forged/abandoned callback: no token storage; validate state/path and bound request timeout.
- Missing/expired tokens, refresh rotation, 401/403/429 and offline: actionable errors, bounded retry/backoff, no token disclosure.
- Rapid navigation/search and page requests: discard stale results; query-encode input and cap pagination.
- Restart/disconnect/unpaired Soloist: clear stale state, rediscover files, reconnect without assuming another player.
- Sidebar policy/closet combinations, malformed metadata/unknown duration: correct tab-page mapping and usable layout.

### Task 1: Read-only API helper and real authorization
**Files:** create dots/.local/bin/ii-spotify-api; tests/test_spotify_api.py; update docs/spotify-soloist.md.
**Interfaces:** CLI emits one non-secret JSON result: `status`, `authorize`, `library --kind tracks|albums|playlists --offset N`, `search --query TEXT --offset N`, `playlist --id ID --offset N`, `album --id ID --offset N`. Browsing returns items [{uri,title,subtitle,image,kind}], next_offset or null. Failures {error,kind,retry_after?}; authorization emits completion only, never tokens.
- [ ] Write/run failing tests for credential-format checks, PKCE/state validation, private token storage, refresh preservation/rotation, 401 once, 403/429 handling, query encoding, entity normalization and pagination, including current playlist items envelope and missing metadata.
- [ ] Implement helper with loopback callback, browser authorization, suppress query logs, private token files, request timeouts, persistent Retry-After and strict API host/path policy. Bind callback before opening browser. Preserve token client identity and reject mismatched app tokens.
- [ ] Run focused tests to green and full suite; start actual authorization for this user's Client ID and read back only authenticated status and real library/search metadata. User action may be required; do not fabricate successful API data.
- [ ] Commit helper/tests/docs.

### Task 2: Native event-driven sidebar and whole-feature review
**Files:** create services/Spotify.qml, modules/ii/sidebarLeft/Spotify.qml and helper JS as needed; modify modules/common/Config.qml, modules/ii/sidebarLeft/SidebarLeftContent.qml, targeted deployment helper; add tests/test_spotify_sidebar.py.
**Interfaces:** service properties connected/loggedIn/active/playback/item/queue/position/duration/volume/options/actions/error, methods send(command,fields), browse(args), authorize(). QML displays Now Playing/Queue/Library+Search, pages results and sends playable URIs to Soloist only.
- [ ] Write/run failing tests against extracted real JS/QML logic and offscreen Quickshell for entity mapping, event handling, malformed frames, disconnect/reconnect port changes, tab/page indexes including closet mode, search-generation guards, seek clamping and available-actions gating.
- [ ] Implement native QML styled with shared widgets; port-file watching/retry and a single WebSocket, granular events and queue refresh; interpolate position from server anchors. Python helper processes own browsing credentials; never bind tokens in QML. Serialize requests and reject stale generations; debounce search and show auth/offline/rate-limit errors distinctly.
- [ ] Run focused and full tests; deploy only changed files with backups, enable Spotify config, load a disposable native preview before touching the running shell. Verify rendered sidebar, native controls, queue and actual authenticated library/search. Check service remains logged in and paused after tests and existing tabs still load.
- [ ] Commit, package whole branch for one fresh independent code review (includes backend). Fix important findings RED→GREEN, full suite/systemd verification, verify final branch/status/commits. No merge or push. Report any unverified/blocked API behavior explicitly.

## Execution
Native execution chosen by user. Client ID saved in response to proposed native layout; proceed with that layout. Baseline backend suite: 20 passing tests, runtime Soloist service/timer verified. Existing backend ledger is separate; include its rulings in whole-feature review. Design/layout can be adjusted by user without redoing backend.
