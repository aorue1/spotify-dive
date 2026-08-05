import os, json, time, urllib.parse, urllib.request, os

targets = json.load(open('enrich_targets.json'))
out = json.load(open('artist_country_mb.json')) if os.path.exists('artist_country_mb.json') else {}

def q(artist):
    url = 'https://musicbrainz.org/ws/2/artist/?' + urllib.parse.urlencode(
        {'query': f'artist:"{artist}"', 'fmt': 'json', 'limit': 3})
    req = urllib.request.Request(url, headers={'User-Agent': f"SpotifyDive/1.0 ({os.environ.get('CONTACT_EMAIL','anonymous@example.com')})"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

for i, a in enumerate(targets):
    if a in out: continue
    try:
        res = q(a).get('artists', [])
        c = None
        for r in res:
            if int(r.get('score', 0)) < 90: break
            c = r.get('country') or (r.get('area') or {}).get('iso-3166-1-codes', [None])[0]
            if not c:
                ba = r.get('begin-area') or {}
                c = (ba.get('iso-3166-1-codes') or [None])[0]
            if c: break
        out[a] = c
    except Exception as e:
        out[a] = None
    if i % 25 == 0:
        json.dump(out, open('artist_country_mb.json', 'w'))
        print(f'{i+1}/{len(targets)}', flush=True)
    time.sleep(1.1)
json.dump(out, open('artist_country_mb.json', 'w'))
found = sum(1 for v in out.values() if v)
print(f'DONE {len(out)} ({found} with country)', flush=True)
