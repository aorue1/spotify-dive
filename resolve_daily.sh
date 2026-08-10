#!/bin/bash
# Resolve DIG suggestion IDs. Self-gating and idempotent: skips anything already
# cached, aborts cleanly if /v1/search is rate-limited, and becomes a ~1s no-op
# once every suggestion has an ID. Safe to run daily forever.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit 1
source .env
say(){ echo "$(date '+%F %H:%M')  $*" >> resolve_daily.log; }
pgrep -f resolve_recs.py >/dev/null && { say "already running - skip"; exit 0; }
TOK=$(curl -s -X POST https://accounts.spotify.com/api/token \
  -H "Authorization: Basic $(printf "$SPOTIFY_ID:$SPOTIFY_SECRET" | base64)" \
  -d grant_type=client_credentials | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOK" \
  "https://api.spotify.com/v1/search?q=artist%3A%22Kolter%22&type=artist&limit=1")
[ "$CODE" != "200" ] && { say "search rate-limited ($CODE) - will retry tomorrow"; exit 0; }
B=$(python3 -c "import json,os;d=json.load(open('rec_spotify_ids.json')) if os.path.exists('rec_spotify_ids.json') else {'artist':{},'album':{}};print(sum(1 for v in d['artist'].values() if v)+sum(1 for v in d['album'].values() if v))")
python3 resolve_recs.py >> resolve_recs.log 2>&1
A=$(python3 -c "import json,os;d=json.load(open('rec_spotify_ids.json')) if os.path.exists('rec_spotify_ids.json') else {'artist':{},'album':{}};print(sum(1 for v in d['artist'].values() if v)+sum(1 for v in d['album'].values() if v))")
say "ids $B -> $A"
if [ "$A" -gt "$B" ]; then
  python3 build_dashboard.py >/dev/null 2>&1
  if [ "${AUTO_PUSH:-0}" = "1" ]; then
    git add -A >/dev/null 2>&1
  git commit -q -m "DIG suggestion IDs: $B -> $A" >/dev/null 2>&1 && git push -q >/dev/null 2>&1 && say "rebuilt + pushed"
  fi
fi
