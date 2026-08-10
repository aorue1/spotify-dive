# 🎧 Spotify Dive

A private dashboard for your own listening history — every play since you joined
Spotify, cross-referenced with Discogs, MusicBrainz, Deezer and Last.fm so you
can actually see **what you listen to, how it changed, and what you've forgotten**.

Built for digging: real record labels, real subgenres (not Spotify's vague
"genres"), where artists are from, and suggestions for music you've never played.

> Everything runs on your own machine. Nothing is uploaded anywhere. The result
> is one HTML file you double-click.

---

## What you get

| Tab | What it's for |
|---|---|
| **Overview** | hours listened, monthly intensity, top artists |
| **Trends** | how your genres, subgenres and labels shifted year by year |
| **World** | a spinning globe of where your artists come from |
| **Rediscover** | tracks you loved and haven't played in years |
| **Explorer** | every track, sortable, with genre / subgenre / label |
| **Dig** | artists and records you've *never* played, based on what you love |

Click any track name for artwork, a playable Spotify player, and lyrics.

---

## Setup

**You do not need to know how to code.** If you have Claude Code, just open this
folder and say *"help me set up Spotify Dive"* — it reads `CLAUDE.md` and walks
you through all of it. Otherwise, follow along:

### 1. Ask Spotify for your data — do this first, it takes weeks

1. Go to **<https://www.spotify.com/account/privacy/>**
2. Scroll to "Download your data" and tick **Extended streaming history**
   *(this is the important one — the "Account data" box only gives you a
   shallow slice)*
3. **Check your email and click Spotify's confirmation link**, or the request
   is never actually queued
4. Wait. It's usually ~2 weeks, officially up to 30 days.

While you wait, do step 2.

### 2. Get free API keys (~10 minutes, all free, none need approval)

These are optional. **Skip them entirely and you still get a full dashboard** of
what you listened to and when — you just won't get genres, record labels, artist
origins or recommendations.

Copy `.env.example` to `.env` (a plain text file) and paste each key in as you go.

#### Discogs — adds subgenres and record labels
1. Go to [discogs.com/settings/developers](https://www.discogs.com/settings/developers) (sign in / make a free account).
2. Click **Generate new token**.
3. Copy the long string it shows you into `DISCOGS_TOKEN=` in your `.env`.

#### Last.fm — adds "artists you've never played" recommendations
1. Go to [last.fm/api/account/create](https://www.last.fm/api/account/create).
2. Fill in any name and description — "Spotify Dive", "personal dashboard" is fine.
   Leave the callback URL blank.
3. Copy **API key** into `LASTFM_KEY=`.
4. If you scrobble, also put your Last.fm username in `LASTFM_USER=`.
   Worth doing: scrobbling records plays from your phone too, so nothing is lost
   when your laptop is asleep or flat.

#### Spotify — adds playable previews in the Dig tab, and live updates
This one is the fiddliest, because Spotify's page is built for developers. It is
still just a form. Step by step:

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
   and log in with your normal Spotify account.
2. Click **Create app**.
3. Fill the form in:
   - **App name** — anything, e.g. `Spotify Dive`
   - **App description** — anything, e.g. `personal listening dashboard`
   - **Redirect URI** — type `http://127.0.0.1:8888/callback` then click **Add**.
     It must be that exactly. Spotify rejects the word `localhost`, and it will
     not let you save until you have clicked Add.
   - **Which API/SDKs are you planning to use?** — tick **Web API** only.
4. Accept the terms and click **Save**.
5. You now land on the app's page. Click **Settings** (top right).
6. Copy **Client ID** into `SPOTIFY_ID=`.
7. Click **View client secret**, and copy that into `SPOTIFY_SECRET=`.

Treat the client secret like a password — it goes in `.env`, which is already
listed in `.gitignore` so it never reaches GitHub.

#### Your email
Put your own address in `CONTACT_EMAIL=`. MusicBrainz asks callers to identify
themselves; it is never shown anywhere or sent to anyone else.

### 3. Unzip the export

When the email arrives, unzip it so you have:

```
~/Downloads/spotify_export/
└── Spotify Extended Streaming History/
    ├── Streaming_History_Audio_2015.json
    └── …
```

### 4. Build it

```bash
python3 build_data.py         # reads your export
python3 build_dashboard.py    # makes the dashboard
open "Spotify Dive.html"      # done
```

That's it — you have a working dashboard.

### 5. Add the good stuff (optional, runs in the background)

These fill in genres, labels, artist origins and recommendations. **Run them one
at a time**, not together — the APIs will temporarily ban you for hammering them.

```bash
source .env
python3 enrich_releases.py    # genres + labels        (~3h)
python3 enrich_deezer.py      # labels Discogs missed  (~1h)
python3 enrich_mb.py && python3 enrich_mb2.py   # artist origins (~45m)
python3 mine_lastfm.py        # similar artists        (~5m)
python3 mine_recs.py          # unheard records        (~10m)
python3 build_dashboard.py    # re-render
```

They're slow because they're polite — one request per second. They're also
**resumable**: stop any of them and re-run later, they pick up where they left
off. Shipped caches mean much of this is already done for you.

### 6. Keep it up to date (optional)

Spotify's export is a snapshot, and only keeps the last 50 plays available live.
To stop a gap forming:

```bash
python3 spotify_auth.py    # one browser click, once
launchctl load ~/Library/LaunchAgents/com.<you>.spotifydive.poll.plist
```

Now new plays are captured every 4 hours. `weekly_refresh.sh` can re-render
everything on a schedule.

---

## Honest limitations

- **Genre/label coverage isn't 100%.** Around half of modern streaming-only
  singles simply aren't in Discogs. Where we can't verify something, we show
  **nothing** rather than a confident guess.
- **Beatport and Traxsource are not available.** Beatport's API needs an approved
  partnership; Traxsource has none. Discogs + Deezer are the best open sources.
- **Lyrics only exist for vocal tracks** (via LRCLIB) — most house and techno
  genuinely has none.
- **Shared accounts distort everything.** If a partner or parent used your login,
  their listening is in your data. See `CLAUDE.md` for how to filter it out.
- **Play counts lie, hours don't.** A skipped track counts as a play, which is
  why this dashboard ranks by listening time.

## Privacy

Your listening history never leaves your machine. `.gitignore` excludes your
data, your built dashboard and your `.env` — so if you push this to your own
repo, you're publishing code, not your taste in music.

## Credits

Data from [Discogs](https://www.discogs.com/developers),
[MusicBrainz](https://musicbrainz.org/doc/MusicBrainz_API),
[Deezer](https://developers.deezer.com/api),
[Last.fm](https://www.last.fm/api) and [LRCLIB](https://lrclib.net).
Globe geometry from [Natural Earth](https://www.naturalearthdata.com/).

## Keeping it running (things that only show up in practice)

**Plug the laptop in.** macOS defers scheduled jobs when you're on battery with
the lid closed, and stops entirely if it goes flat. A dead battery here opened a
26-hour hole in collection. Lid open or closed doesn't matter — power does.

**Turn on Last.fm scrobbling if you can.** Spotify's API only exposes your last
50 plays, so any gap longer than your listening rate loses data permanently and
silently. Last.fm keeps unlimited history and scrobbles from your phone, so it
survives the laptop being asleep, flat, or shut. With it connected, a missed
refresh costs you nothing — the data waits and gets backfilled.

**Re-request the export occasionally.** It is only current up to the day it was
generated, and takes up to 30 days to arrive. `build_data.py` merges and
de-duplicates by timestamp, so dropping a newer export in is always safe.

**Never run two crawlers at once.** Rate limits are per endpoint and unforgiving —
running three in parallel earned a 23-hour ban during development. The scripts
are all resumable, so one at a time costs nothing but patience.
