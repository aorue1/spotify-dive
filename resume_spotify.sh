#!/bin/bash
# Resolve Spotify IDs for Dig-tab suggestions once the search endpoint is free.
# Spotify rate-limits PER ENDPOINT, so this probes the exact endpoint the job
# uses — probing a different one tells you nothing. It also requires two clean
# probes a minute apart, because the limit is a rolling window that can open for
# a single request and immediately close again.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit 1
[ -f .env ] && source .env
say(){ echo "$(date '+%F %H:%M')  $*" >> resume_spotify.log; }

tok(){ curl -s -X POST https://accounts.spotify.com/api/token \
        -H "Authorization: Basic $(printf "$SPOTIFY_ID:$SPOTIFY_SECRET" | base64)" \
        -d grant_type=client_credentials \
        | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null; }
probe_search(){ curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $(tok)" \
        "https://api.spotify.com/v1/search?q=artist%3A%22Kolter%22&type=artist&limit=1"; }
count(){ python3 -c "
import json,os
try:
    d=json.load(open('rec_spotify_ids.json'))
    print(sum(1 for v in d['artist'].values() if v)+sum(1 for v in d['album'].values() if v))
except Exception: print(0)" 2>/dev/null; }

while true; do
  C=$(probe_search); say "search probe=$C"
  if [ "$C" = "200" ]; then
    sleep 60
    C2=$(probe_search); say "confirm=$C2"
    [ "$C2" = "200" ] && break
  fi
  sleep 900
done
say "search endpoint open"

B=$(count)
python3 resolve_recs.py >> resolve_recs.log 2>&1
A=$(count)
say "ids $B -> $A"
if [ "$A" -gt "$B" ]; then
  python3 build_dashboard.py >/dev/null 2>&1
  if [ "${AUTO_PUSH:-0}" = "1" ]; then
    git add -A >/dev/null 2>&1
    git commit -q -m "Dig suggestion IDs: $B -> $A" >/dev/null 2>&1 && git push -q >/dev/null 2>&1
    say "rebuilt + pushed"
  else say "rebuilt"; fi
else
  say "!! nothing resolved — see resolve_recs.log"
fi
