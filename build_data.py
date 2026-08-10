import json, glob, collections, os

SRC = os.path.expanduser('~/Downloads/spotify_export/Spotify Extended Streaming History/Streaming_History_Audio_*.json')

def is_ios(p):
    p = (p or '').lower()
    return ('ios' in p) or ('iphone' in p) or ('ipad' in p)

recs = []
for f in glob.glob(SRC):
    recs += json.load(open(f))

# merge incremental plays captured by poll_recent.py (dedup by timestamp)
INC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plays_incremental.jsonl')
if os.path.exists(INC):
    have = {r['ts'] for r in recs}
    n_inc = 0
    for line in open(INC):
        try: r = json.loads(line)
        except Exception: continue
        if r.get('ts') in have: continue
        have.add(r['ts']); recs.append(r); n_inc += 1
    print(f'merged {n_inc} incremental plays from poller')

kept = []
for r in recs:
    if not r.get('master_metadata_track_name'): continue
    yr = int(r['ts'][:4])
    if is_ios(r['platform']) and yr < 2024: continue   # permanent exclusion
    kept.append(r)

print(f'plays kept: {len(kept):,}')

# track-level aggregate: uri -> stats + per-year plays
tracks = {}
art_ms = collections.Counter()
art_year_ms = collections.defaultdict(collections.Counter)   # artist -> year -> ms
month_ms = collections.Counter()                              # 'YYYY-MM' -> ms
# Last.fm scrobbles carry no Spotify id, so key them to the same track by
# name+artist where we already know it, else to a stable synthetic key. Without
# this a single scrobble would crash the build on uri.split(':').
name_key = {}
for r in kept:
    if r.get('spotify_track_uri'):
        k = ((r.get('master_metadata_track_name') or '').lower().strip(),
             (r.get('master_metadata_album_artist_name') or '').lower().strip())
        name_key.setdefault(k, r['spotify_track_uri'])

n_lfm = 0
for r in kept:
    uri = r.get('spotify_track_uri')
    if not uri:
        k = ((r.get('master_metadata_track_name') or '').lower().strip(),
             (r.get('master_metadata_album_artist_name') or '').lower().strip())
        uri = name_key.get(k) or ('lfm:' + k[1] + '|' + k[0])
        n_lfm += 1
    if r.get('ms_played') is None:   # Last.fm gives no duration; assume a full listen
        r['ms_played'] = 210000
    yr = r['ts'][:4]
    a = r['master_metadata_album_artist_name']
    t = tracks.setdefault(uri, {'n': r['master_metadata_track_name'], 'a': a,
                                'al': r['master_metadata_album_album_name'],
                                'p': 0, 'ms': 0, 'sk': 0, 'f': r['ts'], 'l': r['ts'],
                                'y': collections.Counter()})
    t['p'] += 1; t['ms'] += r['ms_played']; t['y'][yr] += 1
    if r.get('skipped'): t['sk'] += 1
    t['f'] = min(t['f'], r['ts']); t['l'] = max(t['l'], r['ts'])
    art_ms[a] += r['ms_played']
    art_year_ms[a][yr] += r['ms_played']
    month_ms[r['ts'][:7]] += r['ms_played']

# keep tracks with >=2 plays OR >=4 min listened (drop one-shot noise)
tl = []
for uri, t in tracks.items():
    if t['p'] < 2 and t['ms'] < 240000: continue
    tl.append({'id': (uri.split(':')[-1] if not uri.startswith('lfm:') else uri), 'n': t['n'], 'a': t['a'], 'al': t['al'],
               'p': t['p'], 'h': round(t['ms']/3600000, 2), 'sk': t['sk'],
               'f': t['f'][:7], 'l': t['l'][:7], 'y': dict(t['y'])})
tl.sort(key=lambda x: -x['h'])
if n_lfm: print(f'  ({n_lfm} of them Last.fm scrobbles with no Spotify id)')
print(f'tracks kept (>=2 plays or >=4min): {len(tl):,} of {len(tracks):,}')

# artist aggregates (only artists appearing in kept tracks or with >=10min)
arts = {}
for a, ms in art_ms.items():
    if ms < 600000: continue    # >=10 min total
    arts[a] = {'h': round(ms/3600000, 2),
               'y': {y: round(m/3600000, 2) for y, m in art_year_ms[a].items()}}
print(f'artists kept (>=10min): {len(arts):,}')

# enrichment target: artists by ms until 88% cumulative coverage (cap 1400)
total = sum(art_ms.values()); cum = 0; targets = []
for a, ms in art_ms.most_common():
    cum += ms; targets.append(a)
    if cum / total >= 0.88 or len(targets) >= 1400: break
print(f'enrichment targets: {len(targets)} artists = {cum/total*100:.1f}% of listening time')

json.dump({'tracks': tl, 'artists': arts,
           'months': dict(sorted(month_ms.items())),
           'totalHours': round(total/3600000)}, open('listening_base.json', 'w'))
json.dump(targets, open('enrich_targets.json', 'w'))
print('written listening_base.json,', os.path.getsize('listening_base.json')//1024, 'KB')
