"""Append newly played tracks to plays_incremental.jsonl (deduped by played_at).
Spotify only keeps the last 50 plays, so run this every few hours."""
import os, json, base64, time, urllib.parse, urllib.request, urllib.error

CID = os.environ['SPOTIFY_ID']; SEC = os.environ['SPOTIFY_SECRET']
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
rt = json.load(open('.spotify_tokens.json'))['refresh_token']

req = urllib.request.Request('https://accounts.spotify.com/api/token',
    data=urllib.parse.urlencode({'grant_type': 'refresh_token', 'refresh_token': rt}).encode(),
    headers={'Authorization': 'Basic ' + base64.b64encode(f'{CID}:{SEC}'.encode()).decode(),
             'Content-Type': 'application/x-www-form-urlencoded'})
tok = json.load(urllib.request.urlopen(req, timeout=20))['access_token']

seen = set()
if os.path.exists('plays_incremental.jsonl'):
    for line in open('plays_incremental.jsonl'):
        try: seen.add(json.loads(line)['ts'])
        except Exception: pass

r = urllib.request.Request('https://api.spotify.com/v1/me/player/recently-played?limit=50',
                           headers={'Authorization': 'Bearer ' + tok})
try:
    items = json.load(urllib.request.urlopen(r, timeout=25)).get('items', [])
except urllib.error.HTTPError as e:
    # Rate-limited or transient: exit quietly so launchd just retries next cycle.
    # Spotify keeps the last 50 plays, so a skipped 4-hourly run loses nothing
    # unless more than 50 tracks are played before the next successful one.
    print(f"{time.strftime('%F %H:%M')}  skipped (HTTP {e.code})")
    raise SystemExit(0)
new = 0
with open('plays_incremental.jsonl', 'a') as f:
    for it in items:
        ts = it['played_at']
        if ts in seen: continue
        tr = it['track']
        f.write(json.dumps({
            'ts': ts,
            'master_metadata_track_name': tr['name'],
            'master_metadata_album_artist_name': (tr['artists'] or [{}])[0].get('name'),
            'master_metadata_album_album_name': (tr.get('album') or {}).get('name'),
            'spotify_track_uri': tr['uri'],
            'ms_played': tr.get('duration_ms'),   # ESTIMATE: API gives no true listen duration
            'est': 1,
            'platform': 'api-poll', 'skipped': None,
        }) + '\n')
        new += 1
print(f"{time.strftime('%F %H:%M')}  +{new} new plays (total window {len(items)})")
# Last.fm has unlimited history and scrobbles from the phone too, so it closes
# gaps the 50-play Spotify window cannot (see the 2026-08-09 dead-battery hole)
try:
    import subprocess
    subprocess.run(['python3', os.path.join(HERE, 'ingest_lastfm.py')], timeout=300)
except Exception as e:
    print(f'  lastfm ingest skipped: {e}')
