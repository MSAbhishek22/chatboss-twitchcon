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
*{box-sizing:border-box}
body{background:transparent;color:#f5f3ff;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;margin:0;padding:14px}
.shell{max-width:980px;margin:0 auto;background:linear-gradient(160deg,#17111f 0%,#0d0a14 55%,#131a2e 100%);border:1px solid #3b2d5e;border-radius:20px;padding:18px 20px 14px;box-shadow:0 18px 50px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.08)}
.shell.victory-glow{box-shadow:0 0 0 3px #f5c518,0 0 44px rgba(245,197,24,.55),0 18px 50px rgba(0,0,0,.55)}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.brand{font-size:28px;line-height:1;font-weight:900;letter-spacing:.06em}
.brand span{color:#b78cff}
.sub{color:#b8b0cc;font-size:13px;margin-top:5px;letter-spacing:.04em}
.pill{font-size:12px;font-weight:800;letter-spacing:.08em;padding:6px 10px;border-radius:999px;border:1px solid #4b3a75;background:#241b38;color:#d8ccf5;white-space:nowrap}
.pill.sim{color:#ffd479;border-color:#6b5220;background:#2c2210}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:14px 16px 12px}
.card.boss{border-top:4px solid #e5484d}
.card.party{border-top:4px solid #46a758}
.kicker{font-size:11px;font-weight:800;letter-spacing:.14em;color:#b8b0cc}
.big{font-size:clamp(26px,4vw,40px);font-weight:900;line-height:1.05;margin:4px 0 2px}
.big small{font-size:.5em;color:#b8b0cc;font-weight:700}
.hp-row{display:flex;justify-content:space-between;align-items:baseline;font-weight:800;margin:8px 0 6px}
.hp-num{font-size:22px}
.bar{height:30px;background:#241f33;border-radius:999px;overflow:hidden;border:1px solid rgba(255,255,255,.14);box-shadow:inset 0 2px 6px rgba(0,0,0,.5)}
.fill{height:100%;border-radius:999px;transition:width .6s cubic-bezier(.2,.8,.2,1)}
#bossFill{background:linear-gradient(90deg,#ff5a5f,#c81e2b);box-shadow:0 0 18px rgba(229,72,77,.75)}
#partyFill{background:linear-gradient(90deg,#5ee07a,#1f9d4d);box-shadow:0 0 18px rgba(70,167,88,.7)}
.bar.low #bossFill{animation:pulse 1s infinite}
@keyframes pulse{50%{filter:brightness(1.6)}}
.shield{margin-top:10px;font-weight:900;letter-spacing:.06em;font-size:14px;padding:8px 10px;border-radius:10px;text-align:center}
.shield.up{background:#0e3a4a;color:#7fe7ff;border:1px solid #38c8f0;box-shadow:0 0 18px rgba(56,200,240,.6)}
.shield.down{background:rgba(255,255,255,.05);color:#8f87a3;border:1px dashed rgba(255,255,255,.18)}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.stat{flex:1;min-width:110px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:10px 12px}
.stat b{display:block;font-size:22px}
.stat span{font-size:11px;letter-spacing:.1em;color:#b8b0cc;font-weight:700}
.banner{display:none;margin-top:14px;padding:12px 14px;border-radius:12px;font-weight:900;font-size:18px;text-align:center;letter-spacing:.02em}
.banner.victory{display:block;background:#f5c518;color:#1a1200;box-shadow:0 0 24px rgba(245,197,24,.5)}
.banner.defeat{display:block;background:#e5484d;color:#fff;box-shadow:0 0 24px rgba(229,72,77,.5)}
.panels{display:grid;grid-template-columns:1.25fr .75fr;gap:14px;margin-top:14px}
.panel{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);border-radius:14px;padding:12px 14px}
.panel h3{margin:0 0 8px;font-size:13px;letter-spacing:.12em;color:#d8ccf5}
.feed{list-style:none;margin:0;padding:0;font-size:14px;line-height:1.45}
.feed li{padding:6px 0;border-top:1px solid rgba(255,255,255,.08);color:#ddd6ee}
.feed li:first-child{border-top:0;color:#fff;font-weight:600}
.board{list-style:none;margin:0;padding:0}
.board li{display:flex;gap:10px;align-items:center;padding:7px 0;border-top:1px solid rgba(255,255,255,.08);font-size:15px}
.board li:first-child{border-top:0}
.rank{width:28px;text-align:center;font-weight:900}
.board .dmg{margin-left:auto;font-weight:900;color:#ffd479}
.mini-bar{height:6px;background:#241f33;border-radius:999px;flex:1;overflow:hidden}
.mini-bar i{display:block;height:100%;background:#b78cff}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
.chips span{background:#241b38;border:1px solid #4b3a75;color:#e6dcff;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:700}
.small{color:#9d94b5;font-size:12px;line-height:1.5}
details{margin-top:12px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:10px 12px}
summary{cursor:pointer;font-weight:800;font-size:14px}
input,button{font-size:15px;padding:8px 10px;margin:4px 2px;border-radius:9px;border:1px solid #4b3a75;background:#1d1730;color:#fff}
button{background:#9146ff;font-weight:800;cursor:pointer}
.flash-red{animation:flashred .6s}
.flash-green{animation:flashgreen .6s}
@keyframes flashred{0%{box-shadow:0 0 0 3px rgba(229,72,77,.9)}100%{box-shadow:0 0 0 0 transparent}}
@keyframes flashgreen{0%{box-shadow:0 0 0 3px rgba(70,167,88,.9)}100%{box-shadow:0 0 0 0 transparent}}
@media(max-width:640px){.brand{font-size:22px}body{padding:8px}.shell{padding:12px}.card{padding:10px 12px}.big{font-size:24px}.hp-num{font-size:18px}.bar{height:24px}.stat{min-width:0}.stat b{font-size:18px}.feed{font-size:13px}}
@media(max-width:420px){.grid,.panels{grid-template-columns:1fr}}
</style></head><body><div class="shell" id="shell">
<header>
<div><div class="brand">CHAT<span>BOSS</span></div><div class="sub">Chat vs boss &mdash; streamers play together, chat does the damage</div></div>
<div class="pill sim" id="modePill">LOCAL DEMO &middot; SIM MODE</div>
</header>
<div class="grid">
<section class="card boss">
<div class="kicker">BOSS</div>
<div class="big">Boss <span id="bossNum"></span></div>
<div class="hp-row"><span>HP</span><span class="hp-num" id="bossHp"></span></div>
<div class="bar" id="bossBar"><div class="fill" id="bossFill"></div></div>
</section>
<section class="card party">
<div class="kicker">PARTY &mdash; CHAT</div>
<div class="big">Party</div>
<div class="hp-row"><span>HP</span><span class="hp-num" id="partyHp"></span></div>
<div class="bar" id="partyBar"><div class="fill" id="partyFill"></div></div>
<div class="shield down" id="shieldPill">SHIELD: DOWN</div>
</section>
</div>
<div class="stats">
<div class="stat"><b id="statVictories">0</b><span>VICTORIES</span></div>
<div class="stat"><b id="statDefeats">0</b><span>DEFEATS</span></div>
<div class="stat"><b id="statBoss">1</b><span>CURRENT BOSS</span></div>
</div>
<div class="banner" id="banner"></div>
<div class="panels">
<section class="panel"><h3>LIVE EVENT FEED</h3><ul class="feed" id="feed"></ul></section>
<section class="panel"><h3>LEADERBOARD</h3><ul class="board" id="boardList"></ul></section>
</div>
<div class="chips"><span>!attack &minus;5</span><span>!fire &minus;10</span><span>!heal +5</span><span>!shield block</span><span>!boss</span><span>!score</span></div>
<div class="small" id="meta"></div>
<details><summary>Sim controls (local test only)</summary>
<div class="small">Sim test (local only): user + command, e.g. !attack !fire !heal !shield !boss !score</div>
<input id="user" placeholder="user" value="viewer1">
<input id="cmd" placeholder="!attack" value="!attack">
<button onclick="sendSim()">Send</button>
<div class="small" id="simReply"></div>
</details>
</div>
<script>
let prevBoss = null, prevParty = null, prevVictories = 0, prevDefeats = 0;
const medals = ['🥇', '🥈', '🥉'];
function esc(t){ return String(t).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
async function refresh(){
  const r = await fetch('/state'); const s = await r.json();
  const shell = document.getElementById('shell');
  if (prevBoss !== null && s.boss.hp < prevBoss) { const b = document.getElementById('bossBar'); b.classList.remove('flash-red'); void b.offsetWidth; b.classList.add('flash-red'); }
  if (prevParty !== null && s.party.hp < prevParty) { const b = document.getElementById('partyBar'); b.classList.remove('flash-red'); void b.offsetWidth; b.classList.add('flash-red'); }
  if (prevParty !== null && s.party.hp > prevParty) { const b = document.getElementById('partyBar'); b.classList.remove('flash-green'); void b.offsetWidth; b.classList.add('flash-green'); }
  if (s.victories > prevVictories) { shell.classList.add('victory-glow'); setTimeout(() => shell.classList.remove('victory-glow'), 2500); }
  prevBoss = s.boss.hp; prevParty = s.party.hp; prevVictories = s.victories; prevDefeats = s.defeats;
  document.getElementById('bossNum').textContent = s.boss.number;
  document.getElementById('bossHp').textContent = s.boss.hp + '/' + s.boss.max_hp;
  document.getElementById('bossFill').style.width = (100*s.boss.hp/s.boss.max_hp) + '%';
  document.getElementById('bossBar').classList.toggle('low', s.boss.hp <= 0.3*s.boss.max_hp);
  document.getElementById('partyHp').textContent = s.party.hp + '/' + s.party.max_hp;
  document.getElementById('partyFill').style.width = (100*s.party.hp/s.party.max_hp) + '%';
  document.getElementById('meta').textContent = 'Victories: ' + s.victories + ' | Defeats: ' + s.defeats + ' | Shield: ' + (s.shield_active ? 'UP' : 'down') + ' | Mode: ' + s.mode;
  document.getElementById('statVictories').textContent = s.victories;
  document.getElementById('statDefeats').textContent = s.defeats;
  document.getElementById('statBoss').textContent = s.boss.number;
  const pill = document.getElementById('shieldPill');
  pill.textContent = s.shield_active ? 'SHIELD: UP \u2014 NEXT HIT BLOCKED' : 'SHIELD: DOWN';
  pill.className = 'shield ' + (s.shield_active ? 'up' : 'down');
  document.getElementById('modePill').textContent = (s.mode === 'sim' ? 'LOCAL DEMO \u00b7 SIM MODE' : 'MODE: ' + s.mode.toUpperCase());
  const banner = document.getElementById('banner');
  if (s.last_event && s.last_event.includes('VICTORY')) { banner.textContent = '🎉 ' + s.last_event; banner.className = 'banner victory'; }
  else if (s.last_event && s.last_event.includes('DEFEAT')) { banner.textContent = s.last_event; banner.className = 'banner defeat'; }
  else { banner.textContent = ''; banner.className = 'banner'; }
  const feed = document.getElementById('feed');
  const events = (s.events || []).slice(-6).reverse();
  feed.innerHTML = events.map(e => '<li>' + esc(e) + '</li>').join('') || '<li>Waiting for chat&hellip;</li>';
  const list = document.getElementById('boardList');
  const top = s.leaderboard.slice(0, 5);
  const maxDmg = top.length ? top[0].damage : 1;
  list.innerHTML = top.map((e, i) => '<li><span class="rank">' + (medals[i] || (i+1)) + '</span><span>' + esc(e.user) + '</span><span class="mini-bar"><i style="width:' + Math.round(100*e.damage/maxDmg) + '%"></i></span><span class="dmg">' + e.damage + '</span></li>').join('') || '<li>No damage yet &mdash; type !attack</li>';
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
