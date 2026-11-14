# Native Spotify sidebar — UI and browsing milestone

## Intent
Complete feature/spotify-sidebar with a Spotify tab beside Intelligence/Translator/Anime, using the existing sidebar frame, appearance tokens and shared controls. Soloist remains the sole local audio backend; no browser player, visible client window or generic MPRIS selection.

## Approaches
The user chose a native widget over embedding the Spotify web player. Local Soloist WebSocket control replaces both generic MPRIS selection and cloud playback controls. Spotify Web API is reserved for search and personal-library browsing because Soloist's documented local API only exposes playback/queue, not those browsing endpoints.

## Native interface
A single Spotify sidebar tab contains Now Playing, Queue, and Library/Search views. Now Playing displays artwork/title/artist, seek, previous/play-pause/next, volume, shuffle/repeat and explicit device activation when inactive. Queue lists upcoming items. Library shows saved tracks, albums and playlists; selecting an album/playlist opens its tracks. Search covers tracks/albums/playlists, with pagination. Selecting playable results sends their URI only to Soloist. Playback controls remain usable without Web API authorization.

## Boundaries and proposed decisions
QML owns UI and an event-driven QtWebSockets connection to Soloist. Rediscover localhost port files and reconnect after service/update restarts; clamp/interpolate position from server anchors. Honor available_actions and handle missing artwork, empty state, unknown duration, inactive device, buffering, disconnected and unpaired states visibly. No cached success claim after disconnect.

A separate Python 3 standard-library helper owns Spotify Web API requests and Authorization Code with PKCE. A user-created Web API app supplies a public client ID; no client secret is requested. Proposed redirect URI: http://127.0.0.1:43821/callback. Bind only loopback; validate state and callback path; suppress callback query logs, time out abandoned authorization and store refreshed tokens privately outside Git. Request read-only library/playlist scopes only. Never reuse the Soloist key as a Web API credential.

Use debounce/cancel or generation IDs to prevent stale searches replacing newer results, respect Retry-After/429 without retry loops, paginate with documented current limits, refresh expired tokens once, and present authorization/scope/offline failures separately. No recommendation feeds, playlist editing, remote-device picker or cloud playback controls in this milestone.

## Deployment and verification
All tracked changes stay in nicolabba/dots-hyprland; deploy only changed scripts/QML after backing up live targets and do not run a whole desktop install. Preserve existing policy-gated AI/Translator/Anime tabs, including closet-mode index behavior. Add a Spotify enable option, default off for other users, enabled explicitly for this user's setup. Keep credentials and binaries out of the checkout.

Tests cover QML loading and tab/page mapping under policy combinations, real Soloist event/control handling without activating another player, helper OAuth/state/token error cases, API pagination/rate-limit behavior and search-result generations. Verify rendered sidebar and live playback/queue controls plus real account library/search after user authorization. One independent whole-feature review follows; completing only playback controls is not completion of library/search.

## Prerequisite still needed
User must create a Web API application in Spotify Developer Dashboard, register the proposed redirect URI, select Web API and provide/save its public client ID. The existing Soloist API key and pairing cannot authorize Web API library reads. UI/browsing design awaits approval; backend service/updater is already installed and verified, final code review pending until the whole feature is ready.
