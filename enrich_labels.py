import json, os, re, time, base64, urllib.request, urllib.error

CID = os.environ['SPOTIFY_ID']; SEC = os.environ['SPOTIFY_SECRET']
base = json.load(open('listening_base.json'))
# priority: most-listened first
LIMIT = int(os.environ.get('LABEL_LIMIT', '5000'))
tracks = sorted(base['tracks'], key=lambda t: -t['h'])[:LIMIT]
t2a = json.load(open('track_albums.json')) if os.path.exists('track_albums.json') else {}
a2l = json.load(open('album_labels.json')) if os.path.exists('album_labels.json') else {}
a2l = {k: v for k, v in a2l.items() if v}  # refetch albums that came back empty

def label_from(al):
    if not al: return None
    lab = (al.get('label') or '').strip()
    if lab: return lab
    crs = sorted(al.get('copyrights') or [], key=lambda c: 0 if c.get('type') == 'P' else 1)
    for c in crs:
        t = (c.get('text') or '').strip()
        t = re.sub(r'^[℗©(P)(C)\s]+', '', t)
        t = re.sub(r'^(19|20)\d\d[\s,.-]*', '', t)
        t = re.sub(r'\s+(under exclusive license.*|under license.*|a division of.*|distributed by.*|marketed by.*|licen[cs]ed.*)$', '', t, flags=re.I)
        t = t.strip(' .,-')
        if t and len(t) > 1: return t[:60]
    return None

TOK = {'v': None, 'exp': 0}
def token():
    if time.time() < TOK['exp'] - 60: return TOK['v']
    req = urllib.request.Request('https://accounts.spotify.com/api/token',
        data=b'grant_type=client_credentials',
        headers={'Authorization': 'Basic ' + base64.b64encode(f'{CID}:{SEC}'.encode()).decode(),
                 'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(req, timeout=20) as r:
        j = json.load(r)
    TOK['v'] = j['access_token']; TOK['exp'] = time.time() + j['expires_in']
    return TOK['v']

SLEEP = 1.0
def get(url):
    global SLEEP
    for _ in range(6):
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token()})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get('Retry-After', '10'))
                if wait > 300:
                    print(f'RATE LIMITED for {wait}s ({wait/3600:.1f}h) - stopping, rerun later', flush=True)
                    flush(); raise SystemExit(2)
                SLEEP = min(3.0, SLEEP * 1.4)
                print(f'429 - backoff {wait}s, sleep now {SLEEP:.1f}', flush=True)
                time.sleep(wait + 2); continue
            if e.code in (500, 502, 503): time.sleep(4); continue
            if e.code in (400, 404): return None
            raise
    return None

def flush():
    json.dump(t2a, open('track_albums.json', 'w'))
    json.dump(a2l, open('album_labels.json', 'w'))
    out = {}
    for t in base['tracks']:
        aid = t2a.get(t['id'])
        out[t['id']] = a2l.get(aid) if aid else None
    json.dump(out, open('track_labels.json', 'w'))

n = 0
for t in tracks:
    tid = t['id']
    if tid not in t2a:
        j = get(f'https://api.spotify.com/v1/tracks/{tid}')
        t2a[tid] = (j.get('album') or {}).get('id') if j else None
        time.sleep(SLEEP)
    aid = t2a[tid]
    if aid and aid not in a2l:
        j = get(f'https://api.spotify.com/v1/albums/{aid}')
        a2l[aid] = label_from(j)
        time.sleep(SLEEP)
    n += 1
    if n % 100 == 0:
        flush(); print(f'{n}/{len(tracks)} tracks · {len(a2l)} albums · sleep {SLEEP:.2f}', flush=True)
flush()
have = sum(1 for t in base['tracks'] if a2l.get(t2a.get(t['id']) or ''))
print(f'DONE: {have}/{len(tracks)} tracks labeled', flush=True)
