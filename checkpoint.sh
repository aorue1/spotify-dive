#!/bin/bash
# Commit+push enrichment caches every 20 min while any crawl runs, so a crash
# never costs hours of API work. Exits once all crawls are done.
cd ~/Documents/"Spotify Dive"
CRAWLS="enrich_releases.py|enrich_labels.py|mine_recs.py|mine_lastfm.py|enrich_mb.py|enrich_mb2.py"
while true; do
  sleep 1200
  if ! git diff --quiet -- '*.json'; then
    N=$(python3 - <<'PY' 2>/dev/null
import json,os
try:
    d=json.load(open('release_meta.json')); print(f"{sum(1 for v in d.values() if v)}/{len(d)} releases")
except Exception: print("caches")
PY
)
    git add -A -- '*.json' >/dev/null 2>&1
    git -c user.name="aorue1" commit -q -m "checkpoint: enrichment caches ($N)" >/dev/null 2>&1 \
      && git push -q >/dev/null 2>&1 \
      && echo "$(date '+%F %H:%M') pushed checkpoint ($N)" >> checkpoint.log
  fi
  pgrep -f "$CRAWLS" >/dev/null || { echo "$(date '+%F %H:%M') all crawls done, checkpointer exiting" >> checkpoint.log; break; }
done
