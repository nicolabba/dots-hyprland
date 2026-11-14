# Spotify Soloist Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the verified windowless Soloist backend start with the desktop and update safely before its official builds expire.

**Architecture:** Independent systemd user service and daily updater timer. Python standard-library helpers load private credentials, download/validate official builds, gate updates on playback state, atomically activate releases and retain bounded rollback. Source is in this repository; binaries, credentials, pairing and updater state are outside Git.

**Tech Stack:** Python 3, unittest, systemd user units, Soloist ctl, HTTPS, optional notify-send.

**Spec:** docs/superpowers/specs/2026-11-14-spotify-soloist-backend-design.md

## Global Constraints
- Branch: feature/spotify-sidebar in nicolabba/dots-hyprland. This branch delivers the whole native Spotify sidebar: persistent Soloist backend, native Quickshell tab, Spotify-only playback/queue controls, and library/playlists/search integration. This document covers the first backend milestone only; subsequent milestones stay on this same feature branch. Do not push without instruction.
- Preserve ~/.local/share/spotify-sidebar/soloist-data and ~/.config/spotify-sidebar/soloist-api-key.
- No automatic music playback, visible window, root service or firewall changes.
- WebSocket bind: 127.0.0.1:0. Cache: ~/.cache/spotify-sidebar/soloist, 256 MB. Initial volume: 25.
- Official archive: https://soloist-builds.spotifycdn.com/soloist_release_x86_64.tar.gz. Builds expire 90 days after build timestamp.
- Daily checks; defer on playing or unknown status; warn within 14 days of expiry.
- Retain one prior build; never knowingly roll back to an expired executable.
- Do not distribute Soloist binaries or secrets through Git.

## Review Focus
- Network outage, HTML download or malicious archive: leave the current executable untouched and report failure.
- Playback starts or control becomes unavailable during staging: defer immediately before activation.
- Restart loses previously present login or candidate fails: restore a valid prior executable and report rollback/failure.
- Timer runs before/after desktop session: do not start playback or resurrect a deliberately stopped service.
- API keys, cached session files and exception/command logging: no credential disclosure in repository, journal or notifications.

## File Structure
- `dots/.local/bin/ii-soloist`: launcher and lifecycle/update command entry point, with importable pure update helpers for testing.
- `dots/.config/systemd/user/ii-soloist.service`: graphical-session backend service.
- `dots/.config/systemd/user/ii-soloist-update.service`: bounded update job.
- `dots/.config/systemd/user/ii-soloist-update.timer`: persistent daily schedule with randomized delay.
- `tests/test_soloist_backend.py`: standard-library unit and isolated subprocess integration tests.
- `docs/spotify-soloist.md`: explicit setup/disable/update/rollback/credential instructions and limitations.

### Task 1: Launcher and reproducible user-local setup
**Interfaces:** `ii-soloist run` loads the API-key file privately and execs the installed binary; `ii-soloist setup` deploys/enables only the dedicated units/helpers, downloads the initial official binary if absent and preserves pairing. Internal `paths(home: Path) -> dict[str, Path]` centralizes the fixed user-local paths.
- [ ] Write failing tests for key-file presence, owner-only permissions, empty/multiline key rejection, argument construction, localhost binding and unchanged pairing directory. Use a fake executable and test HOME; never use real credentials in fixtures.
- [ ] Run `python -m unittest discover -s tests -p 'test_soloist_backend.py' -v` and confirm the expected missing implementation failure.
- [ ] Implement launcher/setup with user-local deployment, idempotence, no whole-desktop installer invocation, secure umask, no key text in error messages, and no automatic credential generation. Keep production files independent of checkout lifetime.
- [ ] Re-run focused tests; verify setup twice against isolated HOME with systemctl mocked. Commit this tested unit.

### Task 2: Idle-safe updates and bounded recovery
**Interfaces:** `parse_build(text: str) -> Build` extracts executable version, timestamp and Linux/x86_64 identity; `eligible(candidate: Build, current: Build | None, now: datetime) -> bool`; `playback_state(binary: Path, data: Path) -> str` returns playing/paused/stopped/unknown using bounded Soloist ctl calls. `ii-soloist update` owns a nonblocking exclusive lock and returns a persisted outcome: unchanged/deferred/updated/rolled_back/failed.
- [ ] Add failing tests for older/same/newer/future/expired build timestamps; invalid version and architecture; traversal, symlink, duplicate and oversized archive payloads; download timeouts; active playback and missing/malformed ctl state; a playing transition immediately before activation; concurrent updater invocation; notification key redaction.
- [ ] Add failing isolated integration tests with fake executables/services for atomic replacement, no-update, paused activation, failed restart with valid rollback, expired rollback refusal and preservation of an inactive service. Model previously logged-in vs newly unpaired state explicitly.
- [ ] Run the focused tests and confirm failures describe missing behavior, not fixture defects.
- [ ] Implement bounded HTTPS download in same-filesystem staging, regular-file-only targeted extraction, candidate version execution with timeout, build comparison, playback double-check and atomic executable activation. Reject non-official redirect destinations; never execute an archive member before validating its path/type/size.
- [ ] Restart only a service that was active; poll bounded readiness and restored login, then rollback if needed. Make recovery health-aware and preserve the known-good candidate/previous release identity. If the service is inactive, update without starting it.
- [ ] Persist non-secret status atomically and journal/notify failures and <=14-day expiry. Status failure must not overwrite useful download/restart evidence; bounded rollback errors must be surfaced.
- [ ] Run focused tests, then commit updater plus tests.

### Task 3: Session service, daily timer, live migration and documentation
**Interfaces:** unit names `ii-soloist.service`, `ii-soloist-update.service`, `ii-soloist-update.timer`; service invokes `%h/.local/bin/ii-soloist run`, update service invokes `%h/.local/bin/ii-soloist update`. Desktop lifecycle uses graphical-session.target; no independent activation of that target.
- [ ] Add failing unit contract tests for graphical-session lifecycle, restart limits, secret-free ExecStart, user-local executable paths, persistent daily timer and bounded update job duration sufficient for download/recovery. Test idempotent deployment and explicit disable instructions.
- [ ] Implement units, opt-in setup and documentation. Document official HTTPS trust vs unavailable publisher-signature verification, 90-day expiration, process-argument key exposure, offline failures, disabling both units, preserving paired state and firewall discovery troubleshooting. Do not make permanent firewall changes.
- [ ] Run `python -m unittest discover -s tests -v`, syntax compilation, `systemd-analyze --user verify` on new units and `git diff --check`. Preserve the existing weather test.
- [ ] Inspect current test-daemon state without printing its argv. If playing, defer migration; otherwise terminate only the identified test process and deploy the tracked integration using its dedicated helper.
- [ ] Read back exact service and timer enabled/active state. Verify Soloist logged in after service start, localhost socket binding, paused state, and login restoration after stop/start. Do not claim actual reboot verification.
- [ ] Run the real updater against the official endpoint; verify same-build unchanged and paused state preserved. The simulated tests cover replacement/failure and playing deferral without forcing an unnecessary live update.
- [ ] Request one independent whole-branch review, address substantive findings, rerun affected tests plus the full suite, and commit the finished milestone. Verify branch/status/commit; do not push.

## Baseline and Handoff
Repository checkout: /home/nicolabba/.cache/dots-hyprland. Clean main at 9073d940 before branch creation. Existing `python -m unittest discover -s tests -v` passed (one weather positioning test). Feature branch created before writing these documents. No backend implementation changed yet.

Plan self-review: all approved service/updater requirements map to tasks 1–3; widget UI/search are explicitly excluded. The five review-focus conditions each have tests above. Existing Soloist credentials and binaries are external runtime inputs, not fixtures.
