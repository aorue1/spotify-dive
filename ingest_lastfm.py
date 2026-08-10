"""Pull scrobbles from Last.fm into plays_incremental.jsonl.

Why this exists: the Spotify poller can only see the last 50 plays, so any gap
longer than your listening rate loses data permanently - a dead battery on
2026-08-09 opened a 26h hole that only luck kept empty. Last.fm keeps unlimited
history, scrobbles from the phone as well as the laptop, and is paginated, so it
closes that class of gap for good and can backfill retroactively.
"""
import json, os, time, urllib.parse, urllib.request

KEY  = os.environ['LASTFM_KEY']
USER = os.environ['LASTFM_USER']   # your Last.fm username
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)

seen = set()
if os.path.exists('plays_incremental.jsonl'):
    for line in open('plays_incremental.jsonl'):
        try: seen.add(json.loads(line)['ts'])
        except Exception: pass

def get(page):
    u = 'https://ws.audioscrobbler.com/2.0/?' + urllib.parse.urlencode(
        {'method': 'user.getrecenttracks', 'user': USER, 'api_key': KEY,
         'format': 'json', 'limit': 200, 'page': page})
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'SpotifyDive/1.0'}), timeout=20) as r:
                return json.load(r)
        except Exception:
            time.sleep(3)
    return None

first = get(1)
if not first or 'recenttracks' not in first:
    print('lastfm: no data (is scrobbling connected?)'); raise SystemExit(0)
pages = int(first['recenttracks']['@attr']['totalPages'] or 0)
total = int(first['recenttracks']['@attr']['total'] or 0)
print(f'lastfm: {total:,} scrobbles across {pages} pages', flush=True)

added = 0
with open('plays_incremental.jsonl', 'a') as f:
    for p in range(1, pages + 1):
        d = first if p == 1 else get(p)
        if not d: break
        tracks = d['recenttracks'].get('track') or []
        if isinstance(tracks, dict): tracks = [tracks]
        stop = True
        for t in tracks:
            if t.get('@attr', {}).get('nowplaying'): continue      # not finished yet
            uts = t.get('date', {}).get('uts')
            if not uts: continue
            ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(int(uts)))
            if ts in seen: continue
            seen.add(ts); stop = False
            f.write(json.dumps({
                'ts': ts,
                'master_metadata_track_name': t.get('name'),
                'master_metadata_album_artist_name': (t.get('artist') or {}).get('#text'),
                'master_metadata_album_album_name': (t.get('album') or {}).get('#text'),
                'spotify_track_uri': None,      # Last.fm has no Spotify id
                'ms_played': None,              # nor a listen duration
                'est': 1, 'platform': 'lastfm', 'skipped': None,
            }) + '\n')
            added += 1
        if p > 1 and stop: break                # whole page already known: caught up
        time.sleep(0.3)
print(f'lastfm: +{added} new plays', flush=True)
