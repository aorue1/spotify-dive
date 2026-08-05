# Guide for Claude Code

You are helping someone set up **Spotify Dive** — a personal listening-analytics
dashboard built from their own Spotify data export. Assume they are **not a
developer**. Be concrete, do the work for them, and never make them read code.

## The one-sentence version
They request a data export from Spotify, drop the zip in a folder, and you run
four scripts that produce a single self-contained `Spotify Dive.html` they can
double-click.

## Onboarding order (do not reorder — step 1 has a long lead time)

1. **Get them to request the export FIRST**, because it takes up to 30 days.
   Send them to <https://www.spotify.com/account/privacy/>, tell them to tick
   **"Extended streaming history"** (NOT just "Account data" — that one is
   shallow), and to click the confirmation link in the email Spotify sends,
   or the request is never queued. Nothing else can proceed without it.

2. **While they wait, get the free API credentials.** All are self-serve and
   instant except where noted. Write them into `.env` (copy `.env.example`):
   - `DISCOGS_TOKEN` — <https://www.discogs.com/settings/developers> → "Generate token"
   - `LASTFM_KEY` — <https://www.last.fm/api/account/create> (any name/description)
   - `SPOTIFY_ID` / `SPOTIFY_SECRET` — <https://developer.spotify.com/dashboard>
     → Create app → tick **Web API** → redirect URI `http://127.0.0.1:8888/callback`
     (Spotify rejects `localhost`; the literal loopback IP is required)
   - `CONTACT_EMAIL` — theirs; MusicBrainz asks for a contact in the User-Agent
   The dashboard still builds with none of these — they only add genre, label,
   origin and recommendation data.

3. **When the zip arrives**, unzip into `~/Downloads/spotify_export/` so that
   `~/Downloads/spotify_export/Spotify Extended Streaming History/*.json` exists.

4. **Build:**
   ```
   python3 build_data.py          # parse the export        (seconds)
   python3 build_dashboard.py     # render the HTML         (<1 second)
   open "Spotify Dive.html"
   ```
   They have a working dashboard at this point. Everything below is enrichment.

5. **Enrich, one at a time, never in parallel.** Running crawlers concurrently
   is what earned a 23-hour Spotify ban during development. In this order:
   ```
   python3 enrich_releases.py   # genres+labels per release (Discogs)  ~3h
   python3 enrich_v3.py         # artist-level fallback     (Discogs)  ~1.5h
   python3 enrich_deezer.py     # labels Discogs lacks      (Deezer)   ~1h
   python3 enrich_mb.py && python3 enrich_mb2.py   # artist origin (MusicBrainz) ~45m
   python3 mine_lastfm.py       # similar artists           (Last.fm)  ~5m
   python3 mine_recs.py         # unheard releases          (Discogs)  ~10m
   python3 resolve_recs.py      # Spotify IDs for previews             ~20m
   python3 build_dashboard.py   # re-render
   ```
   All are **resumable and incremental** — they skip anything already cached, so
   re-running is cheap and safe. Run them in the background and check the logs.

6. **Optional, keeps it current:**
   - `python3 spotify_auth.py` then
     `launchctl load ~/Library/LaunchAgents/com.<name>.spotifydive.poll.plist`
     — captures new plays every 4h (Spotify only retains the last 50 plays, so
     a less frequent poll silently loses listens)
   - `weekly_refresh.sh` via launchd for a weekly rebuild

## Things that will bite you
- **`ms_played` is the truth, not play counts.** Hours listened is the honest
  metric; a skipped track still counts as a "play".
- **Shared accounts.** If someone else used their login on a device, that
  listening is in the data and will distort everything. Look for a cluster of
  out-of-character artists on one platform in one era. `build_data.py` has an
  `is_ios`-style exclusion showing how to cut it; adapt the rule, don't copy it.
- **Genre belongs to the release, not the artist** — an artist's records differ.
  Never flatten an artist to one genre.
- **Never match a Discogs artist by name alone.** ~30% of long-tail artists are
  wrong that way (a house producer resolved to a classical violinist). Anchor
  every query on a release title you know they made — `enrich_v3.py` shows how.
- **Discogs "country" is the pressing country, not the artist's origin.** It put
  The Doors in Russia. Use MusicBrainz for origin.
- **Rate limits:** Discogs 60/min · MusicBrainz 1/sec (hard) · Last.fm ~5/sec ·
  Spotify undocumented and unforgiving. One job at a time, always.

## Where things live
`build_data.py` → `listening_base.json` → `build_dashboard.py` → `Spotify Dive.html`
(self-contained: data, d3-geo and the globe are all inlined; no server needed).
The `*_meta.json` / `*_cache.json` files are enrichment caches — keep them, they
cost hours of API calls to regenerate.
