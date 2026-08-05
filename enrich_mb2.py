import os, json, os, time, urllib.parse, urllib.request, urllib.error

UA = {'User-Agent': f"SpotifyDive/1.0 ({os.environ.get('CONTACT_EMAIL','anonymous@example.com')})"}
targets = json.load(open('enrich_targets.json'))
mb = json.load(open('artist_country_mb.json'))
acache = json.load(open('area_cache.json')) if os.path.exists('area_cache.json') else {}

def get(url):
    for _ in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (503, 429): time.sleep(4); continue
            return None
        except Exception:
            time.sleep(2); continue
    return None

def area_country(aid, depth=0):
    """walk area parents until an ISO-3166-1 code appears"""
    if not aid or depth > 4: return None
    if aid in acache: return acache[aid]
    j = get(f'https://musicbrainz.org/ws/2/area/{aid}?inc=area-rels&fmt=json')
    time.sleep(1.1)
    if not j:
        acache[aid] = None; return None
    iso = (j.get('iso-3166-1-codes') or [None])[0]
    if iso:
        acache[aid] = iso; return iso
    for rel in j.get('relations', []):
        if rel.get('type') == 'part of' and rel.get('direction') == 'backward':
            par = rel.get('area') or {}
            piso = (par.get('iso-3166-1-codes') or [None])[0] or area_country(par.get('id'), depth + 1)
            if piso:
                acache[aid] = piso; return piso
    acache[aid] = None
    return None

todo = [a for a in targets if not mb.get(a)]
print(f'pass2: {len(todo)} artists without country', flush=True)
for i, a in enumerate(todo):
    j = get('https://musicbrainz.org/ws/2/artist/?' + urllib.parse.urlencode(
        {'query': f'artist:"{a}"', 'fmt': 'json', 'limit': 3}))
    time.sleep(1.1)
    c = None
    for r in (j or {}).get('artists', []):
        if int(r.get('score', 0)) < 85: break
        c = r.get('country')
        if not c:
            for key in ('area', 'begin-area'):
                ar = r.get(key) or {}
                c = (ar.get('iso-3166-1-codes') or [None])[0] or area_country(ar.get('id'))
                if c: break
        if c: break
    if c: mb[a] = c
    if i % 20 == 0:
        json.dump(mb, open('artist_country_mb.json', 'w'))
        json.dump(acache, open('area_cache.json', 'w'))
        got = sum(1 for v in mb.values() if v)
        print(f'{i+1}/{len(todo)} · resolved total {got} · areas cached {len(acache)}', flush=True)
json.dump(mb, open('artist_country_mb.json', 'w'))
json.dump(acache, open('area_cache.json', 'w'))
got = sum(1 for v in mb.values() if v)
print(f'DONE pass2 · {got}/{len(mb)} artists with country', flush=True)
