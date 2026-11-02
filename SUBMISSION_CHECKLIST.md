# ChatBoss — Submission checklist (Codex x TwitchCon)

**Deadline: Nov 2, 2026, 2:00 PM PT = Nov 3, ~02:30–03:30 IST.**
PT is UTC−7 in daylight time and UTC−8 after the Nov 1 DST change,
so aim to submit by **Nov 3, 02:30 IST** at the latest. Do NOT rely
on the later end of that range.

**Status: BUILT AND TESTED LOCALLY. NOT SUBMITTED.**
No Devpost submission has been made by this build. Do not record
this project as submitted without a Devpost confirmation link.

## Devpost fields (draft — review before sending)

- **Project name:** ChatBoss — Chat vs Boss Battle Overlay
- **One-liner:** Viewers fight a boss from Twitch chat: !attack,
  !fire, !heal, !shield — the streamer just runs an OBS overlay.
- **Description draft (~for the form, edit to fit):**
  > ChatBoss turns Twitch chat into a boss battle. The streamer runs
  > an OBS browser-source overlay; viewers type !attack (5 damage,
  > 10s cooldown), !fire (10 damage, once per user per boss),
  > !heal (5 party HP), and !shield (blocks the next counterattack).
  > The boss counterattacks every 30 seconds for 8 damage. Boss HP 0
  > is a victory and the next boss has +20 HP; party HP 0 is a
  > defeat and a fresh boss spawns. A live leaderboard ranks viewers
  > by damage dealt. Built in Python 3 with the standard library
  > only — no database, no keys. Sim mode lets anyone test it
  > without a live stream; with TWITCH_CHANNEL set, an anonymous
  > read-only IRC reader feeds real public chat into the same
  > command parser. State is in memory, so restarting resets the
  > battle. Built with Codex assistance (session ID below).
- **Public repo:** [GITHUB LINK AFTER USER CREATES PUBLIC REPO]
  - Repo must contain only this project folder's contents.
  - Never commit keys, tokens, or a TWITCH_CHANNEL value that is
    private (a public channel name is fine; none is committed here).
- **Demo video:** [YOUTUBE LINK AFTER VIDEO AGENT FINISHES]
  - **Video must be < 3 minutes** and must show the project
    actually running (overlay + sim commands + boss/party HP
    changing + a victory or shielded counterattack if possible).
  - Video is NOT made by this build — a separate agent does it.
    Do not submit with a placeholder video link.
- **Codex session ID:** [CODEX_SESSION_ID_FROM_USER_THREAD]
  - Do NOT invent a session ID. Fill it in from the user's own
    Codex thread before submitting.

## Verified in this build (do not overclaim)

- [x] `python3 run.py test` — **21/21 tests pass** (from project folder)
- [x] `python3 run.py serve` smoke test — /health ok (sim mode),
      POST /sim !attack drops boss HP 100 -> 95, /state shape correct,
      /overlay serves HTML
- [x] `python3 run.py demo` — scripted battle incl. cooldown refusal
      and shielded counterattack
- [x] IRC parser unit-tested on tagged + untagged PRIVMSG lines
- [x] No pip deps, no DB, no keys in repo
- [ ] Live Twitch channel run — NOT done (no live stream available
      in this build; parser tested, socket loop not run live)
- [ ] Public repo created — user tap
- [ ] Demo video (< 3 min, project running) — separate video agent
- [ ] Devpost submission sent — user/parent browser tap only

## User taps left (in order)

1. Create a public GitHub repo for this project only, push this
   folder's contents (no secrets — there are none to remove).
2. Get the demo video link from the video agent; check it is
   < 3 min and shows the overlay running.
3. Fill in the Codex session ID from the user's own Codex thread.
4. Submit on Devpost before Nov 3, 02:30 IST. Review every field
   before sending — Devpost forms may not be editable after submit.
5. Optional, only if a live stream is available: run with
   `TWITCH_CHANNEL=<channel>` and verify real chat commands move
   the overlay before claiming a live run in the submission text.

## Update 2026-11-02 ~10:56 IST (verified)
- Demo video (real footage, 125.8s): local ~/workspace/your_files/chatboss-twitchcon-demo.mp4
- YouTube Unlisted: https://youtu.be/bWRjgOj8q3I (YouTube shows 2:06, Not made for kids)
- Public repo: creation in progress via browser (chatboss-twitchcon) — link to be added when confirmed, do NOT paste a guessed URL
- Codex session ID: STILL PENDING from user's own Codex thread — do NOT invent
- Devpost submit: STILL PENDING, user's own browser (Cloudflare blocks assistant browser)
