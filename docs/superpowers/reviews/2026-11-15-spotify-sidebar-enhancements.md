# Spotify Liked Songs and scrubber — verification

## Delivered scope

- Library → Liked → Play Liked Songs starts the account's native collection on Soloist, not one saved track or a first-page queue.
- Unanimated native seek control with drag preview, a single release seek, five-second keyboard steps and authoritative/error/timeout reconciliation.
- Local progress anchors cover pause/buffer/resume and track changes; existing 500 ms timer retained.
- Personalized mixes/radios explicitly excluded by the user. No new OAuth scopes, playlist writes or private web-client tokens.

## Automated evidence

`python -m unittest discover -s tests -q`: **61 tests passed**. The suite includes an actual QtTest run with seven behavioral tests plus init/cleanup (9 pass records), Node reducer tests, isolated actual-QML/WebSocket collection/control tests and deployment checks.

Tests were observed failing before the helper/URI implementation, transition fixes, seek component/binding fixes and deployment-manifest fix. The final review's recovery regression was also observed RED for both authorization and setup errors, then GREEN.

Additional checks passed: Python compilation of both helpers, `systemd-analyze --user verify` of Soloist service units and update timer, `git diff --check`.

The legacy slider reproduction used its shared `SmoothedAnimation` velocity of 850 units/sec: after assigning a target of 150000 ms, the rendered value was approximately 3.376 after 600 ms. The Spotify-specific control has no `Behavior on value`.

## Independent review

One independent whole-feature reviewer inspected tracked and untracked source/tests and ran focused checks. One material finding: Liked Songs authorization/setup errors retained `authorized=true`, hiding Connect library. Fixed by sharing browsing's authorization invalidation behavior; new actual-QML/WebSocket regression covers both error kinds. No deferred minor findings.

Reviewer did not judge real-account playback, appearance or seek latency; the live checks below address those separately.

## Deployment and live evidence

Deployed with the existing explicit `ii-soloist setup-sidebar` workflow. Backup:

`~/.local/state/spotify-sidebar/backups/20261115-202940-pcyrsx2a`

All deployed helpers and Spotify QML/JS files were compared byte-for-byte with checkout sources. The shared Config and outer sidebar host matched before deployment. Soloist stayed active with **MainPID 1469** before and after deployment and live tests; no playback-service restart occurred. No Spotify-related errors appeared in the inspected latest 100 shell log lines.

Observed in the actual native sidebar:

- Existing transparency, artwork and internal navigation retained; new Play Liked Songs action visible in Library → Liked without clipping.
- Clicking that action started playback with the native collection context. Earlier capability check verified a 3800-track library and 25 upcoming entries; no library enumeration is used.
- Elapsed text and thumb updated during actual playback.
- Pointer seek reached **100726 ms**. A subsequent right-arrow seek reached **106182 ms** (5456 ms difference including time elapsed between observations); screenshot showed matching elapsed text/position rather than the old smoothed thumb.
- Clicking Next changed the current track while retaining the collection context.
- The original track AND context were restored, paused and inactive, at **5570 ms** versus original **5571 ms**. Sidebar closed after testing; cursor restored approximately to its starting position.

Private probe snapshots remain under Hermes scratch, not Git; credentials were not logged or copied. The real-account test did not deliberately introduce unavailable tracks or empty the library; those cases use isolated helper fixtures. The earlier cold-boot network readiness fix is unchanged, and an actual corrected cold boot remains unverified.

## Implementation choices

- Work stayed in the existing checkout on `feature/spotify-sidebar-enhancements`, rather than creating an unrequested worktree. The checkout therefore remains on that branch.
- A small Spotify-specific Qt Controls slider receives the shell palette instead of changing shared StyledSlider behavior; its rendering primitives are maintained separately.
- No merge or push performed.
