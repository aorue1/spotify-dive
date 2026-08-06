#!/bin/bash
# Wait for Spotify's rolling rate limit to clear, then run the two Spotify jobs
# SEQUENTIALLY. Lessons baked in from the 14:04 failure:
#  - a single 200 probe does not mean the quota is really open; require 2 clean
#    probes a minute apart before starting
#  - never trust exit status alone: verify each job actually produced output,
#    and retry later if it did not
#  - log loudly on failure so it cannot look like success
cd ~/Documents/"Spotify Dive" || exit 1
source .env
LOG=resume_labels.log
say(){ echo "$(date '+%F %H:%M')  $*" >> "$LOG"; }

tok(){ curl -s -X POST https://accounts.spotify.com/api/token \
      -H "Authorization: Basic $(printf "$SPOTIFY_ID:$SPOTIFY_SECRET" | base64)" \
      -d grant_type=client_credentials \
      | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null; }
# probe the SAME endpoint the job will hammer - limits are per-endpoint
probe_search(){ curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $(tok)" \
    "https://api.spotify.com/v1/search?q=artist%3A%22Kolter%22&type=artist&limit=1"; }
probe_album(){ curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $(tok)" \
    "https://api.spotify.com/v1/albums/7qg1D9nKMvb99jaRvW50re"; }
waitfor(){  # $1 = probe fn, $2 = label
  while true; do
    local c; c=$($1); say "$2 probe=$c"
    if [ "$c" = "200" ]; then sleep 60; local c2; c2=$($1); say "$2 confirm=$c2"
      [ "$c2" = "200" ] && return 0; fi
    sleep 900
  done; }

count(){ python3 -c "
import json,sys
try:
    d=json.load(open('$1'))
    if isinstance(d,dict) and 'artist' in d: print(sum(1 for v in d['artist'].values() if v)+sum(1 for v in d['album'].values() if v))
    else: print(sum(1 for v in d.values() if v))
except Exception: print(0)" 2>/dev/null || echo 0; }

rebuild(){ python3 build_dashboard.py >/dev/null 2>&1
  git add -A >/dev/null 2>&1
  git -c user.name="aorue1" commit -q -m "$1" >/dev/null 2>&1 && git push -q >/dev/null 2>&1 && say "   rebuilt + pushed"; }


waitfor probe_search "search"
BEFORE=$(count rec_spotify_ids.json)
say "resolving DIG suggestion IDs"
python3 resolve_recs.py >> resolve_recs.log 2>&1; RC=$?
AFTER=$(count rec_spotify_ids.json)
say "   resolve_recs exit=$RC  ids: $BEFORE -> $AFTER"
if [ "$AFTER" -gt "$BEFORE" ]; then rebuild "DIG suggestion IDs resolved: previews now embed";
else say "   !! resolve_recs produced nothing - see resolve_recs.log"; fi

say "=== done ==="
