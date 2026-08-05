"""One-time OAuth so the poller can read your recently-played tracks.
Run:  SPOTIFY_ID=... SPOTIFY_SECRET=... python3 spotify_auth.py
Requires redirect URI  http://127.0.0.1:8888/callback  registered on the Spotify app."""
import os, json, base64, hashlib, secrets, webbrowser, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

CID = os.environ['SPOTIFY_ID']; SEC = os.environ['SPOTIFY_SECRET']
REDIRECT = 'http://127.0.0.1:8888/callback'
SCOPE = 'user-read-recently-played'
verifier = secrets.token_urlsafe(64)[:96]
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
code_holder = {}

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        code_holder.update(urllib.parse.parse_qs(qs))
        self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers()
        ok = 'code' in code_holder
        self.wfile.write(b'<body style="background:#000302;color:#00ff41;font-family:monospace;padding:40px">'
                         + (b'<h2>&gt; AUTHORIZED</h2><p>You can close this tab.</p>' if ok
                            else b'<h2>&gt; FAILED</h2><p>Check the console.</p>') + b'</body>')
    def log_message(self, *a): pass

url = 'https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
    'client_id': CID, 'response_type': 'code', 'redirect_uri': REDIRECT,
    'scope': SCOPE, 'code_challenge_method': 'S256', 'code_challenge': challenge})
print('Opening browser for consent…\n', url)
webbrowser.open(url)
srv = HTTPServer(('127.0.0.1', 8888), H)
srv.handle_request()

if 'code' not in code_holder:
    raise SystemExit('no code returned: ' + json.dumps(code_holder))
data = urllib.parse.urlencode({
    'grant_type': 'authorization_code', 'code': code_holder['code'][0],
    'redirect_uri': REDIRECT, 'client_id': CID, 'code_verifier': verifier}).encode()
req = urllib.request.Request('https://accounts.spotify.com/api/token', data=data,
    headers={'Authorization': 'Basic ' + base64.b64encode(f'{CID}:{SEC}'.encode()).decode(),
             'Content-Type': 'application/x-www-form-urlencoded'})
tok = json.load(urllib.request.urlopen(req, timeout=20))
json.dump({'refresh_token': tok['refresh_token']}, open('.spotify_tokens.json', 'w'))
os.chmod('.spotify_tokens.json', 0o600)
print('saved .spotify_tokens.json — poller is ready')
