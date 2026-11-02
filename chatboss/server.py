"""ChatBoss HTTP server — Python 3 stdlib only.

Routes:
  GET  /overlay  -> OBS browser-source overlay HTML (polls /state every 500ms)
  GET  /state    -> JSON game state (tick() applied first, so the boss
                   counterattack fires even without a background thread)
  GET  /health   -> {"status": "ok", "mode": "sim"|"twitch", ...}
  POST /sim      -> {"user": "...", "text": "!attack"} feeds the SAME
                   parser as Twitch IRC. Local testing / video only.

Mode:
  TWITCH_CHANNEL env var set   -> mode "twitch", anonymous IRC reader
                                  thread started (no token, no keys).
  TWITCH_CHANNEL unset         -> mode "sim", overlay says so plainly.

Run:  python3 run.py serve [--port 8768]
OBS:  add a Browser Source pointing at http://localhost:8768/overlay
"""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .game import ChatBossGame
from .irc import connect_and_run

OVERLAY_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>ChatBoss Overlay</title>
<style>
body{background:transparent;color:#fff;font-family:Arial,sans-serif;margin:0;padding:16px}
.card{background:rgba(0,0,0,.75);border:2px solid #9146ff;border-radius:12px;padding:16px;max-width:560px}
.bar{height:24px;background:#333;border-radius:6px;overflow:hidden}
.fill{height:100%}
#bossFill{background:#e5484d}
#partyFill{background:#46a758}
h2{margin:0 0 8px}.small{color:#ccc;font-size:14px}
input,button{font-size:16px;padding:6px;margin:2px}
</style></head><body><div class="card">
<h2 id="title">ChatBoss</h2>
<div>Boss <span id="bossNum"></span> HP: <span id="bossHp"></span></div>
<div class="bar"><div class="fill" id="bossFill"></div></div>
<div>Party HP: <span id="partyHp"></span></div>
<div class="bar"><div class="fill" id="partyFill"></div></div>
<div class="small" id="meta"></div>
<div class="small" id="event"></div>
<div class="small" id="board"></div>
<hr>
<div class="small">Sim test (local only): user + command, e.g. !attack !fire !heal !shield !boss !score</div>
<input id="user" placeholder="user" value="viewer1">
<input id="cmd" placeholder="!attack" value="!attack">
<button onclick="sendSim()">Send</button>
<div class="small" id="simReply"></div>
</div>
<script>
async function refresh(){
  const r = await fetch('/state'); const s = await r.json();
  document.getElementById('bossNum').textContent = s.boss.number;
  document.getElementById('bossHp').textContent = s.boss.hp + '/' + s.boss.max_hp;
  document.getElementById('bossFill').style.width = (100*s.boss.hp/s.boss.max_hp) + '%';
  document.getElementById('partyHp').textContent = s.party.hp + '/' + s.party.max_hp;
  document.getElementById('partyFill').style.width = (100*s.party.hp/s.party.max_hp) + '%';
  document.getElementById('meta').textContent = 'Victories: ' + s.victories + ' | Defeats: ' + s.defeats + ' | Shield: ' + (s.shield_active ? 'UP' : 'down') + ' | Mode: ' + s.mode;
  document.getElementById('event').textContent = s.last_event;
  document.getElementById('board').textContent = 'Leaderboard: ' + s.leaderboard.map(e => e.user + ': ' + e.damage).join(', ');
}
async function sendSim(){
  const r = await fetch('/sim', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({user: document.getElementById('user').value, text: document.getElementById('cmd').value})});
  const j = await r.json();
  document.getElementById('simReply').textContent = j.reply || '';
  refresh();
}
setInterval(refresh, 500); refresh();
</script></body></html>
"""


def make_handler(game, mode):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep stdout clean
            pass

        def _json(self, obj, status=200):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/overlay":
                body = OVERLAY_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/state":
                game.tick()
                state = game.state()
                state["mode"] = mode
                self._json(state)
            elif self.path == "/health":
                self._json({"status": "ok", "mode": mode})
            else:
                self._json({"error": "not found"}, status=404)

        def do_POST(self):
            if self.path != "/sim":
                self._json({"error": "not found"}, status=404)
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, UnicodeDecodeError):
                self._json({"error": "bad json"}, status=400)
                return
            game.tick()
            reply = game.handle_chat(payload.get("user", ""), payload.get("text", ""))
            state = game.state()
            state["mode"] = mode
            state["reply"] = reply
            self._json(state)

    return Handler


def build_server(port=8768, channel=None):
    game = ChatBossGame()
    mode = "twitch" if channel else "sim"
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(game, mode))
    return server, game, mode


def serve(port=8768):
    channel = os.environ.get("TWITCH_CHANNEL") or None
    server, game, mode = build_server(port, channel)
    stop = threading.Event()

    def ticker():
        while not stop.is_set():
            time.sleep(1)
            try:
                game.tick()
            except Exception:
                pass

    threading.Thread(target=ticker, daemon=True).start()
    if channel:
        def irc_loop():
            try:
                connect_and_run(game, channel, stop_event=stop)
            except Exception as exc:  # keep serving sim/overlay on IRC failure
                print(f"Twitch IRC disconnected (continuing in overlay/sim mode): {exc}")

        threading.Thread(target=irc_loop, daemon=True).start()
        print(f"ChatBoss mode: twitch (channel: {channel}, anonymous read, no token)")
    else:
        print("ChatBoss mode: sim (no TWITCH_CHANNEL set; use POST /sim or the overlay form)")
    print(f"ChatBoss overlay: http://127.0.0.1:{port}/overlay")
    print(f"ChatBoss state:   http://127.0.0.1:{port}/state")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
