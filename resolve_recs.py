"""Resolve DIG suggestions (plain name strings from Last.fm / Discogs) into Spotify
IDs, so the preview pane can show real artwork and a playable embed.
This is a ONE-TIME lookup per suggestion, cached forever - not a per-play cost.
Conservative pacing + hard abort on a long Retry-After: a greedy crawl is what
earned the 23h ban in the first place."""
import json, os, time, base64, collections, urllib.parse, urllib.request, urllib.error

CID = os.environ['SPOTIFY_ID']; SEC = os.environ['SPOTIFY_SECRET']
ART_N = int(os.environ.get('ART_N', '900'))
REL_N = int(os.environ.get('REL_N', '1600'))
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)

sim = json.load(open('similar_artists.json'))
recs = json.load(open('recs_raw.json'))
base = json.load(open('listening_base.json'))
out = json.load(open('rec_spotify_ids.json')) if os.path.exists('rec_spotify_ids.json') else {'artist': {}, 'album': {}}

heard = {t['a'].lower() for t in base['tracks']}
ac = collections.Counter()
for peers in sim.values():
    for p in peers:
        if p['n'].lower() not in heard: ac[p['n']] += p['m']
artists = [a for a, _ in ac.most_common(ART_N)]

rc = collections.Counter()
for bucket in recs.values():
    for rows in bucket.values():
        for r in rows: rc[(r['a'], r['n'])] += 1 + (0.5 if (r.get('y') or 0) >= 2022 else 0)
albums = [k for k, _ in rc.most_common(REL_N)]

TOK = {'v': None, 'exp': 0}
def token():
    if time.time() < TOK['exp'] - 60: return TOK['v']
    req = urllib.request.Request('https://accounts.spotify.com/api/token',
        data=b'grant_type=client_credentials',
        headers={'Authorization': 'Basic ' + base64.b64encode(f'{CID}:{SEC}'.encode()).decode(),
                 'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=20) as r: j = json.load(r)
    TOK['v'] = j['access_token']; TOK['exp'] = time.time() + j['expires_in']
    return TOK['v']

SLEEP = 0.5
def search(q, typ):
    global SLEEP
    url = 'https://api.spotify.com/v1/search?' + urllib.parse.urlencode({'q': q, 'type': typ, 'limit': 1})
    for _ in range(5):
        try:
            req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token()})
            with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get('Retry-After', '10'))
                if wait > 300:
                    print(f'RATE LIMITED {wait}s - aborting, rerun later', flush=True)
                    flush(); raise SystemExit(2)
                SLEEP = min(2.0, SLEEP * 1.4)
                time.sleep(wait + 2); continue
            if e.code in (500, 502, 503): time.sleep(4); continue
            return None
        except Exception: time.sleep(3); continue
    return None

def flush(): json.dump(out, open('rec_spotify_ids.json', 'w'))

for i, a in enumerate(artists):
    if a in out['artist']: continue
    j = search(f'artist:"{a}"', 'artist')
    items = ((j or {}).get('artists') or {}).get('items') or []
    hit = items[0] if items else None
    out['artist'][a] = {'id': hit['id'], 'n': hit['name']} if hit else None
    time.sleep(SLEEP)
    if i % 50 == 0:
        flush(); print(f"artists {i+1}/{len(artists)} · resolved {sum(1 for v in out['artist'].values() if v)}", flush=True)
flush()

for i, (art, alb) in enumerate(albums):
    k = art + '|' + alb
    if k in out['album']: continue
    j = search(f'artist:"{art}" album:"{alb}"', 'album')
    items = ((j or {}).get('albums') or {}).get('items') or []
    it = items[0] if items else None
    out['album'][k] = {'id': it['id'], 'n': it['name'],
                       'a': (it.get('artists') or [{}])[0].get('name', '')} if it else None
    time.sleep(SLEEP)
    if i % 50 == 0:
        flush(); print(f"albums {i+1}/{len(albums)} · resolved {sum(1 for v in out['album'].values() if v)}", flush=True)
flush()
print(f"DONE artists={sum(1 for v in out['artist'].values() if v)}/{len(out['artist'])} "
      f"albums={sum(1 for v in out['album'].values() if v)}/{len(out['album'])}", flush=True)
