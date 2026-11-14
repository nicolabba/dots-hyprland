# Spotify sidebar — independent review and resolution

## Reviewed range and verdict

One independent reviewer examined `9073d94037cf8b6804a808613a28932c01076d66..109c47d6ba4e4e8a237c8022e7c1df9607fb577b` on `feature/spotify-sidebar`. Original verdict: **with fixes**. No critical findings, two reproduced important findings, no deferred minors and an empty declined-to-judge list.

The reviewer independently ran the original 39-test suite and systemd verification and reproduced port-change WebSocket reconnection using two isolated servers. Real playback, credentials, live services and desktop were not touched by that reviewer.

## Resolved findings

### P1: Updater late-state safety
The final guard preceded blocking login inspection and backup copying. Regression tests first reproduced updates restarting after playback began or a service stopped in that window, and rollback restarting an explicitly stopped service.

Fix: stage login inspection and backup before a final service/playback recheck; use systemd's conditional `try-restart` instead of unconditional restart. Failed-candidate recovery restores an unexpired prior executable, but defers its restart when the unit has stopped, playback is busy or its state is unavailable. The notification distinguishes this deferred recovery from a healthy restarted rollback.

Regression tests:
- `test_late_playback_or_stop_during_login_check_defers_update`
- `test_playback_during_previous_binary_copy_defers_activation`
- `test_stop_during_candidate_health_check_never_restarts_rollback`
- `test_service_restart_uses_atomic_try_restart_not_start`

### P2: Refresh failures mistaken for revoked authorization
Tests first reproduced token-endpoint 429 and 503 being labeled authorization failures.

Fix: refresh 429 uses a persisted Retry-After cooldown honored by browsing and direct token refresh; 5xx is a temporary error and retains the saved grant. Invalid-grant/client authentication failures still request authorization. Retry-After on a transient refresh outage is also respected.

Regression tests:
- `test_refresh_429_preserves_authorization_and_blocks_further_token_requests`
- `test_refresh_503_is_temporary_not_revoked_authorization`
- `test_refresh_invalid_grant_is_reported_as_authorization_failure`

## Verification after fixes

- Full `python -m unittest discover -s tests -v`: **46 passed**, no skips/failures.
- Both Python helpers compile; `git diff --check` and `systemd-analyze --user verify` pass.
- Patched helpers deployed; source/runtime hashes match and Soloist MainPID remained unchanged.
- Actual Web API status remains authenticated and a live library read succeeds.
- Fixes were verified by parent-owned RED→GREEN regressions and the full suite, not by commissioning a second independent review.

## Rulings made during execution

1. Implement the launcher first and finish opt-in setup when updater/units exist, rather than create a fake bootstrap path. Task-order deviation only; all setup acceptance checks subsequently passed.
2. Update an inactive service's executable without starting it. This preserves intentional stops; the newer executable runs when the user/session next starts the service.
3. Consolidate the independent review at the complete-feature boundary rather than reviewing backend and UI separately. This reduced duplicated review context; backend findings surfaced later and are now fixed.
4. Keep the WebSocket connection in an instance-scoped component under the Spotify page rather than the global services namespace. This avoids coupling optional page construction/dependencies to the whole shell; the connection may be recreated when that page is reconstructed.
5. Restore only the on-disk prior executable when recovery restart would resurrect a stopped service or disturb busy/unknown playback. Automatic recovery can remain deferred until a safe/manual restart; the updater reports that condition instead of interrupting audio.

## Remaining evidence boundaries

The newly enabled session service still needs an actual reboot-startup check. Pairing persistence through a previous reboot and subsequent managed service restarts were verified separately. Candidate replacement/rollback and transient token-service errors are covered by isolated tests, not forced failures against the live Spotify account. No merge or push has been authorized.
