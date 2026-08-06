#!/bin/bash
# Weekly incremental refresh. Everything here is idempotent and cache-skipping:
# each crawler only touches entities it has never seen, so a normal week is a
# couple of minutes of API work, not a rebuild.
# Jobs run STRICTLY SEQUENTIALLY - concurrent crawlers are what got us banned.
cd ~/Documents/"Spotify Dive" || exit 1
source .env
LOG=refresh.log
say(){ echo "$(date '+%F %H:%M')  $*" >> "$LOG"; }

# Single-instance lock: a long crawl may still be running from a previous week
# (or from a manual launch). Two crawlers racing on the same cache file is how
# the Spotify ban happened.
LOCK=.refresh.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  say "another refresh/crawl holds the lock - skipping this run"; exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM
for c in enrich_releases.py enrich_labels.py mine_recs.py resolve_recs.py; do
  if pgrep -f "$c" >/dev/null; then say "$c already running - skipping this run"; exit 0; fi
done

# macOS has no coreutils `timeout`; this is a portable watchdog.
run(){
  local label="$1" secs="$2"; shift 2
  say "→ $label"
  "$@" >/dev/null 2>&1 &
  local pid=$!
  ( sleep "$secs"; kill -0 "$pid" 2>/dev/null && { kill -TERM "$pid" 2>/dev/null; sleep 5; kill -9 "$pid" 2>/dev/null; } ) &
  local wd=$!
  wait "$pid" 2>/dev/null; local rc=$?
  kill "$wd" 2>/dev/null
  [ "$rc" -ne 0 ] && say "   (exit $rc after $(( SECONDS )) s)"
  return 0
}

say "=== weekly refresh start ==="

# 0. capture anything the 4-hourly poller has not yet grabbed
run "poll recent plays"        300  python3 poll_recent.py

# 1. rebuild the base dataset (merges plays_incremental.jsonl, dedups by ts)
run "rebuild base dataset"     600  python3 build_data.py

# 2. enrichment - each skips everything already cached
run "discogs: new releases"    3600 python3 enrich_releases.py
run "discogs: new artists"     1800 python3 enrich_v3.py
run "deezer: labels discogs lacks" 2400 python3 enrich_deezer.py
run "musicbrainz: origins"     1800 python3 enrich_mb.py
run "musicbrainz: city->country" 1800 python3 enrich_mb2.py
run "lastfm: similar artists"  900  python3 mine_lastfm.py
run "discogs: rec catalogues"  1800 python3 mine_recs.py

# 3. Spotify jobs only if we are not rate-limited (probe first, never hang)
TOK=$(curl -s -X POST https://accounts.spotify.com/api/token \
  -H "Authorization: Basic $(printf "$SPOTIFY_ID:$SPOTIFY_SECRET" | base64)" \
  -d grant_type=client_credentials | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOK" \
  "https://api.spotify.com/v1/search?q=artist%3A%22Kolter%22&type=artist&limit=1")
if [ "$CODE" = "200" ]; then
  run "spotify: suggestion ids"  1800 python3 resolve_recs.py
else
  say "spotify search rate-limited (probe=$CODE) - suggestion ids skipped this week"
fi

# 4. render + persist
run "rebuild dashboard"        300  python3 build_dashboard.py
if ! git diff --quiet; then
  git add -A >/dev/null 2>&1
  git -c user.name="aorue1" commit -q -m "weekly refresh $(date '+%F')" >/dev/null 2>&1 \
    && git push -q >/dev/null 2>&1 && say "committed + pushed"
else
  say "nothing changed"
fi
say "=== weekly refresh done ==="
