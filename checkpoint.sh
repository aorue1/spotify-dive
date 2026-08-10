#!/bin/bash
# Commit the enrichment caches periodically while a long crawl runs, so a crash
# or a flat battery never costs hours of API calls. Exits once no crawl is left.
# Committing is opt-in (AUTO_PUSH=1) and should point at a PRIVATE repo — these
# caches sit next to your listening data.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit 1
CRAWLS="enrich_releases.py|enrich_labels.py|enrich_deezer.py|mine_recs.py|mine_lastfm.py|resolve_recs.py|enrich_mb.py|enrich_mb2.py"
while true; do
  sleep 1200
  if ! git diff --quiet -- '*.json'; then
    N=$(python3 -c "
import json
try:
    d=json.load(open('release_meta.json')); print(f\"{sum(1 for v in d.values() if v)}/{len(d)} releases\")
except Exception: print('caches')" 2>/dev/null)
    if [ "${AUTO_PUSH:-0}" = "1" ]; then
      git add -A -- '*.json' >/dev/null 2>&1
      git commit -q -m "checkpoint: enrichment caches ($N)" >/dev/null 2>&1 && git push -q >/dev/null 2>&1
      echo "$(date '+%F %H:%M') checkpointed ($N)" >> checkpoint.log
    else
      echo "$(date '+%F %H:%M') caches changed ($N) — AUTO_PUSH off, not committed" >> checkpoint.log
    fi
  fi
  pgrep -f "$CRAWLS" >/dev/null || { echo "$(date '+%F %H:%M') crawls done, exiting" >> checkpoint.log; break; }
done
