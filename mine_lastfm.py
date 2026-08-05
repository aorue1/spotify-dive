"""Last.fm similar-artists for the user's top artists.
Scrobble-based collaborative filtering - unlike ListenBrainz it has real depth
in underground house/techno, which is most of this library."""
import json, os, time, collections, urllib.parse, urllib.request

KEY = os.environ['LASTFM_KEY']
base = json.load(open('listening_base.json'))
out = json.load(open('similar_artists.json')) if os.path.exists('similar_artists.json') else {}

hours = collections.Counter()
for t in base['tracks']: hours[t['a']] += t['h']
targets = [a for a, _ in hours.most_common(900)]

def get(params):
    u = 'https://ws.audioscrobbler.com/2.0/?' + urllib.parse.urlencode(
        {**params, 'api_key': KEY, 'format': 'json'})
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'SpotifyDive/1.0'}), timeout=20) as r:
                return json.load(r)
        except Exception:
            time.sleep(2)
    return {}

for i, a in enumerate(targets):
    if a in out: continue
    d = get({'method': 'artist.getsimilar', 'artist': a, 'limit': 30, 'autocorrect': 1})
    arts = (d.get('similarartists') or {}).get('artist', [])
    out[a] = [{'n': x['name'], 'm': round(float(x.get('match') or 0), 4)} for x in arts if x.get('name')]
    time.sleep(0.28)
    if i % 50 == 0:
        json.dump(out, open('similar_artists.json', 'w'))
        got = sum(1 for v in out.values() if v)
        print(f'{i+1}/{len(targets)} · with peers {got}', flush=True)
json.dump(out, open('similar_artists.json', 'w'))
got = sum(1 for v in out.values() if v)
print(f'DONE {len(out)} artists · {got} with peers', flush=True)
