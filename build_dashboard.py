"""Render listening_base.json + all enrichment caches into one self-contained
Spotify Dive.html (data, d3-geo and the globe geometry are all inlined, so the
file works from file:// with no server).

Precedence rules encoded here, in order, each learned the hard way:

* LABEL   Discogs release imprint > Deezer > Spotify P-line. Discogs names the
          label on the record; the P-line often names the parent ("Elektra
          Entertainment Group" vs "Elektra") and is sometimes prose, not a label.
* GENRE   The release's own tags first, then the artist profile, then a coarse
          Deezer genre mapped onto Discogs' taxonomy. Genre belongs to a record,
          not a person - one artist's releases genuinely differ.
* ORIGIN  MusicBrainz only. Discogs "country" is the pressing country, which put
          The Doors in Russia; unverified artists get no country at all.
* Artists that could not be verified against a known release carry NO genre
          rather than a guessed one (see enrich_v3.py).

Cheap and idempotent: ~0.2s, zero API calls. Re-run it freely.
"""
import json, re, os

base = json.load(open('listening_base.json'))
if os.path.exists('track_labels.json'):
    _tl = json.load(open('track_labels.json'))
    n_lb = 0
    for _t in base['tracks']:
        _lb = _tl.get(_t['id'])
        if _lb:
            _lb = re.sub(r'^(\((?:P|C)\)|℗|©)\s*', '', _lb).strip()
            # some P-lines are prose, not a label ("The copyright in this sound...")
            if len(_lb) > 48 or re.search(r'copyright|all rights|under (exclusive )?licen', _lb, re.I):
                _lb = ''
            if _lb: _t['lb'] = _lb; n_lb += 1
    print(f'spotify labels on {n_lb} tracks')
# v3 = title-anchored (verified) matching; v2 = legacy name-only, kept only as a
# last resort for artists v3 never reached. v3 entries with v==0 are deliberately
# empty: no genre beats a wrong genre.
meta_v3 = json.load(open('artist_meta_v3.json')) if os.path.exists('artist_meta_v3.json') else {}
meta_v2 = json.load(open('artist_meta_v2.json')) if os.path.exists('artist_meta_v2.json') else {}
if meta_v3:
    n0 = sum(1 for v in meta_v3.values() if not v.get('v'))
    print(f'using v3 for {len(meta_v3)} artists ({n0} unverified -> no genre)')
    for a, m in meta_v3.items():
        meta_v2[a] = m if m.get('v') else {'g': [], 's': [], 'l': [], 'c': None}
    # v3b widens style/label sampling for verified artists (single-anchor bias fix)
    if os.path.exists('artist_meta_v3b.json'):
        wide = json.load(open('artist_meta_v3b.json'))
        n_w = 0
        for a, w in wide.items():
            if not w or a not in meta_v2 or not meta_v2[a].get('v'): continue
            meta_v2[a] = {**meta_v2[a], 'g': w['g'] or meta_v2[a].get('g', []),
                          's': w['s'] or meta_v2[a].get('s', []),
                          'l': w['l'] or meta_v2[a].get('l', [])}
            n_w += 1
        print(f'style profile broadened for {n_w} artists')
# fallback: older playlist enrichment (no country)
old = {}
oldp = os.path.expanduser('~/Downloads/artist_meta.json')
if os.path.exists(oldp):
    for a, m in json.load(open(oldp)).items():
        old[a] = {'g': (m.get('genre') or [])[:2], 's': (m.get('style') or [])[:3],
                  'l': (m.get('label') or [])[:3], 'c': None}
META = dict(old); META.update({k: v for k, v in meta_v2.items() if not v.get('err')})
META = {k: v for k, v in META.items() if k in base['artists'] and (v['g'] or v['s'] or v['l'] or v.get('c'))}
enriched_h = sum(base['artists'][a]['h'] for a in META)
total_h = sum(v['h'] for v in base['artists'].values())
print(f'meta for {len(META)} artists = {enriched_h/total_h*100:.0f}% of kept hours')

mp = json.load(open('map_paths.json'))
name2iso = {p['n'].lower(): p['id'] for p in mp}
GEO = json.load(open('globe_geo.json'))
for f in GEO['features']:
    name2iso.setdefault(f['properties']['n'].lower(), f['id'])
d3js = open('d3-array.min.js').read() + '\n' + open('d3-geo.min.js').read()

# MusicBrainz artist-origin override (Discogs release-country is bootleg-skewed for big acts)
if os.path.exists('artist_country_mb.json'):
    mb = json.load(open('artist_country_mb.json'))
    iso2name = {f['id']: f['properties']['n'] for f in GEO['features']}
    n_ok = n_drop = 0
    for a, m in META.items():
        iso = mb.get(a)
        if iso and iso in iso2name:
            m['c'] = iso2name[iso]; n_ok += 1
        else:
            # Discogs 'country' is release/pressing country, not artist origin
            # (it made The Doors "Russian"). Accuracy over coverage: drop it.
            if m.get('c'): n_drop += 1
            m['c'] = None
    print(f'origins: {n_ok} verified via MusicBrainz, {n_drop} unreliable Discogs values dropped')

if os.path.exists('country_overrides.json'):
    ov = json.load(open('country_overrides.json'))
    iso2name = {f['id']: f['properties']['n'] for f in GEO['features']}
    n_ov = 0
    for a, iso in ov.items():
        if a.startswith('_') or a not in META: continue
        META[a]['c'] = iso2name.get(iso) if iso else None
        n_ov += 1
    print(f'manual overrides applied: {n_ov}')

# per-release genres/styles: a track inherits ITS OWN record's tags, not a
# flattened artist profile (artist->genre is many-to-many because of this)
if os.path.exists('release_meta.json'):
    rel = json.load(open('release_meta.json'))
    n_rel = 0
    for t in base['tracks']:
        r = rel.get(t['a'] + '|' + (t.get('al') or ''))
        if r and (r.get('g') or r.get('s')):
            t['rg'] = r.get('g') or []
            t['rs'] = r.get('s') or []
            # prefer the Discogs imprint: it is the label on the record, while the
            # Spotify P-line often names the parent/licensor ('Elektra Entertainment
            # Group' vs 'Elektra'). P-line stays as the fallback.
            if r.get('l'): t['lb'] = r['l'][0]
            n_rel += 1
    print(f'per-release genres on {n_rel} tracks')

RIDS = json.load(open('rec_spotify_ids.json')) if os.path.exists('rec_spotify_ids.json') else {'artist': {}, 'album': {}}
# entries are {'id','n'} (name kept so the UI can flag a bad match); keep ids only
RIDS = {k: {a: (i['id'] if isinstance(i, dict) else i) for a, i in v.items() if i}
        for k, v in RIDS.items()}
if RIDS['artist'] or RIDS['album']:
    print(f"suggestion IDs: {len(RIDS['artist'])} artists, {len(RIDS['album'])} albums")

# Deezer fills releases Discogs never had (Beatport needs partner OAuth,
# Traxsource has no API). Labels only - Deezer genres are too coarse.
if os.path.exists('deezer_meta.json'):
    dz = json.load(open('deezer_meta.json'))
    n_dz = 0
    # Deezer's taxonomy is coarser and differently named than Discogs'. Map it
    # onto the Discogs genre names so a fallback does not fragment the genre list
    # (Dance/Electro are both Discogs' "Electronic"). Used ONLY when a track has
    # no genre at all, and never for subgenres - Deezer has nothing that granular.
    DZ2DISCOGS = {'Dance': 'Electronic', 'Electro': 'Electronic',
                  'Reggae': 'Reggae', 'Rock': 'Rock', 'Pop': 'Pop', 'Jazz': 'Jazz',
                  'Rap/Hip Hop': 'Hip Hop', 'R&B': 'Funk / Soul', 'Soul & Funk': 'Funk / Soul',
                  'Blues': 'Blues', 'Classical': 'Classical', 'Latin Music': 'Latin',
                  'Films/Games': 'Stage & Screen', 'Country': "Folk, World, & Country",
                  'Alternative': 'Rock', 'Metal': 'Rock', 'Folk': "Folk, World, & Country"}
    n_dzg = 0
    for t in base['tracks']:
        d = dz.get(t['a'] + '|' + (t.get('al') or ''))
        if not d: continue
        if not t.get('lb') and d.get('l'):
            t['lb'] = d['l']; n_dz += 1
        has_genre = t.get('rg') or t.get('rs') or (META.get(t['a'], {}).get('g') or META.get(t['a'], {}).get('s'))
        if not has_genre and d.get('g'):
            mapped = [DZ2DISCOGS.get(g) for g in d['g']]
            mapped = [m for m in dict.fromkeys(mapped) if m]
            if mapped: t['rg'] = mapped; n_dzg += 1
    print(f'deezer labels on {n_dz} further tracks, genres on {n_dzg}')

SIM = json.load(open('similar_artists.json')) if os.path.exists('similar_artists.json') else {}
SIM = {k: v[:20] for k, v in SIM.items() if v}
RECS = json.load(open('recs_raw.json')) if os.path.exists('recs_raw.json') else None
if RECS:   # thumbnails are never rendered and cost ~2 MB of payload
    for bucket in RECS.values():
        for rows in bucket.values():
            for r in rows: r.pop('th', None)
print(f'recs: {len(SIM)} artists with peers'
      + (f", {len(RECS.get('label', {}))} label + {len(RECS.get('artist', {}))} artist catalogues" if RECS else ', no release catalogues yet'))

payload = json.dumps({'T': base['tracks'], 'A': base['artists'], 'M': base['months'],
                      'META': META, 'N2I': name2iso, 'GEO': GEO,
                      'SIM': SIM, 'RECS': RECS, 'RIDS': RIDS}, ensure_ascii=False, separators=(',', ':'))

html = open('template.html').read()
html = html.replace('__LASTFM_KEY__', os.environ.get('LASTFM_KEY', ''))
html = html.replace('__D3__', d3js)
html = html.replace('__PAYLOAD__', payload)
open('Spotify Dive.html', 'w').write(html)
print('Spotify Dive.html written:', os.path.getsize('Spotify Dive.html')//1024, 'KB')
