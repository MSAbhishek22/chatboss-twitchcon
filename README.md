# ChatBoss — chat vs boss battle overlay for Twitch streamers

Viewers fight a boss from Twitch chat. The streamer runs an overlay
(OBS browser source); chat does the rest. No database, no keys in
this repo, Python 3 standard library only.

**Hackathon:** Codex x TwitchCon — deadline **Nov 2, 2026, 2:00 PM PT**
(= Nov 3, ~02:30–03:30 IST; PT is UTC−7 in daylight time, UTC−8 after
the Nov 1 DST change — submit by the earlier IST time to be safe).

## Do X, see Y

### 1. Run it

```bash
cd ~/workspace/hackathons/codex-twitchcon
python3 run.py serve
```

You should see:

```
ChatBoss mode: sim (no TWITCH_CHANNEL set; use POST /sim or the overlay form)
ChatBoss overlay: http://127.0.0.1:8768/overlay
ChatBoss state:   http://127.0.0.1:8768/state
```

### 2. Open the overlay

Open http://127.0.0.1:8768/overlay in a browser. You should see
Boss 1 at 100/100 HP, Party at 100/100 HP, Victories 0, Defeats 0,
and a note that the mode is **sim**.

**OBS:** add a Browser Source with URL
`http://localhost:8768/overlay` (width ~600, height ~400).
The overlay polls `/state` every 500 ms.

### 3. Play it in sim mode (no live stream needed)

In the overlay's sim form, or with curl:

```bash
curl -s -X POST http://127.0.0.1:8768/sim \
  -H 'Content-Type: application/json' \
  -d '{"user": "alice", "text": "!attack"}'
# -> boss HP drops to 95, leaderboard shows alice: 5
```

Try the full command set:

| Command | Effect |
|---|---|
| `!attack` | 5 damage. Per-user cooldown 10s (enforced). |
| `!fire` | 10 damage, but only once per user per boss. |
| `!heal` | Restores 5 party HP (capped at 100). |
| `!shield` | Blocks the next boss counterattack (consumed on use). |
| `!boss` | Status: boss HP, party HP, victories, defeats, shield. |
| `!score` | Leaderboard by damage dealt (top 5). |

Boss rules:

- Boss counterattacks every 30s for 8 damage, unless shielded.
- Boss HP 0 = **VICTORY**: victories++, new boss with **+20 HP**
  (boss 2 = 120 HP, boss 3 = 140 HP, …), party HP resets to 100,
  per-boss `!fire` set clears.
- Party HP 0 = **DEFEAT**: defeats++, new boss at 100 HP (a fresh
  run, not a harder boss), party HP resets to 100.

### 4. Run the scripted demo

```bash
python3 run.py demo
```

You should see attacks, a fire, a heal, a shield, a cooldown refusal,
`!boss` / `!score` output, and a shielded counterattack.

### 5. Run the tests

```bash
python3 run.py test
# 21 tests, all passing (verified 2026-11-02, from the project folder)
```

### 6. Twitch IRC path (real chat, no token for reading)

`chatboss/twitch_irc.py` parses real Twitch IRC PRIVMSG lines
(`irc.chat.twitch.tv` format, with or without tags) and feeds them
into the **same** `ChatBossGame.handle_chat()` parser used by sim
mode, so live and sim behaviour cannot drift.

To use it, set the channel and restart:

```bash
TWITCH_CHANNEL=mychannel python3 run.py serve
```

The server then starts an anonymous read-only IRC reader
(`justinfan` nickname, **no OAuth token, no keys**) that joins
`#mychannel` and feeds chat commands into the game. If no channel
is set, the server runs in sim mode and says so on the overlay.
Writing to chat / posting as a user is out of scope — this project
only reads public chat and never posts to Twitch.

## Codex step (placeholder — do not invent)

This project was built with Codex assistance. The Codex session ID
for the submission form is:

```
[CODEX_SESSION_ID_FROM_USER_THREAD]
```

Fill this in from the user's own Codex thread before submitting.
No session ID is claimed anywhere else in this repo.

## Files

```
run.py                    serve / demo / test entry point
chatboss/game.py          game state + the one command parser
chatboss/irc.py           Twitch IRC PRIVMSG parser + anonymous reader
chatboss/server.py        stdlib HTTP server: /overlay, /state, /health, /sim
tests/test_chatboss.py    21 unittest tests (IRC, commands, rollover, server)
README.md                 this file
SUBMISSION_CHECKLIST.md   Devpost fields + remaining user taps
```

## Honest limits

- All state is in memory. Restarting the server resets the battle.
- Sim mode is a local stand-in for testing/video; it is not a live
  Twitch stream and must not be presented as one.
- The Twitch reader is anonymous read-only; it cannot post messages,
  and it has not been run against a live channel in this build
  (no live stream was available). The parser is fully unit-tested
  against real IRC line formats.
- No database, no pip dependencies, no keys, tokens, or passwords
  in this repo. The only env var is the optional `TWITCH_CHANNEL`.
