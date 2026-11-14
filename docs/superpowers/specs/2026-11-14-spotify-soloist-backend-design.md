# Spotify Soloist persistent backend

## Intent and scope
Deliver the whole native Spotify left-sidebar integration on feature/spotify-sidebar, styled and integrated like the existing AI/Anime tabs, with Spotify-only controls, queue, library, playlists and search. This design covers the first milestone: making the already-tested windowless Soloist backend persistent and keeping its expiring official binary updated. Widget UI, library/search integration and Web API OAuth are subsequent milestones on this same feature branch, not separate feature branches. Backend completion alone does not complete the feature.

## Approved approach
User approved a systemd user service and daily update timer. Alternatives discussed were manual updates (risk of 90-day expiry) and tying playback to Quickshell (unnecessary lifecycle coupling). All source belongs in nicolabba/dots-hyprland on a feature branch; no remote push is implied.

## Requirements
- Start with the graphical desktop session without a window or automatic music playback.
- Preserve ~/.local/share/spotify-sidebar/soloist-data and the existing private ~/.config/spotify-sidebar/soloist-api-key; neither credentials nor binary archives may enter Git.
- Control WebSocket bound only to 127.0.0.1; discover its OS-assigned port through Soloist's data directory.
- Daily update checks against Spotify's official Linux archive. Validate candidate executable, Linux/x86_64 platform, build age and newer timestamp before atomic activation.
- Never replace/restart a running daemon during playback or when its playback state cannot be determined. Recheck immediately before activation.
- Keep one previous binary for rollback while it is unexpired. Verify restored authentication after a replacement; rollback if the new daemon cannot start or restore a previously existing login.
- Persist update outcome and notify on failure or approaching expiry. An offline machine must retain its working binary and retry later.
- Use user-local files only. No system-wide updater/service or automatic firewall relaxation.
- Document that builds expire 90 days after their build timestamp. No cryptographic authenticity claim unless Spotify supplies verifiable signatures/checksums; HTTPS and binary checks are not publisher signature verification.

## Proposed implementation decisions
Use Python 3 standard-library scripts under dots/.local/bin, matching the repository's dotfile deployment layout, with unittest coverage under tests. Units live under dots/.config/systemd/user. A dedicated opt-in setup helper deploys only this integration and enables its service/timer; do not run the whole desktop installer for this task.

Install official executable payloads outside the source repository under ~/.local/share/spotify-sidebar/soloist/. Preserve the existing paired data path. Keep API key loading in the backend launcher, never in the unit text or a command logged by the setup/updater. Soloist requires the key as an argument; document the resulting same-user/root process-argument visibility limitation.

Persist updater status separately from credentials for future widget health display. Notify using notify-send when available and always report in the journal/status file. Warn within 14 days of expiry. Keep updates opt-in for other repository users and do not bundle Spotify's proprietary executable.

## Evidence and constraints
The spike verified official Soloist 1.3.10.71 (20261113), pairing, local control, queue/metadata, advancing playback position and a running native PipeWire stream. Stored pairing restored after reboot without reauthorization. Initial discovery needed temporary LAN-only mDNS and TCP pairing access through firewalld; no permanent rule is currently authorized. A random pairing port must not be hardcoded from the spike.

## Acceptance
Unit tests exercise update safety, invalid downloads, expiry/newness, unknown and playing states, atomic replacement and bounded rollback. systemd-analyze accepts the units. Live service starts using existing credentials, restores pairing and stays paused; stop/start restores login again. Timer is enabled, its no-update run succeeds against the real official endpoint, and service failure notifications do not expose secrets. Report reboot autostart as configured rather than newly reboot-tested.

## Approval
Approved in conversation before planning. Repository/feature-branch placement additionally requested by the user. Source layout and warning threshold are implementation proposals, not previously specified user requirements.
