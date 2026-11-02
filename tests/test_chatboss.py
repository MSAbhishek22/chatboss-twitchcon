"""ChatBoss tests — stdlib unittest only. Run from the project folder:
  python3 run.py test        (or: python3 -m unittest discover -s tests)
"""

import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from chatboss.game import ChatBossGame
from chatboss.irc import parse_privmsg
from chatboss.server import make_handler


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestIrcParsing(unittest.TestCase):
    def test_privmsg_with_tags(self):
        line = (
            "@badge-info=;badges=;display-name=Alice;color=#FF0000 "
            ":alice!alice@alice.tmi.twitch.tv PRIVMSG #mychannel :!attack"
        )
        msg = parse_privmsg(line)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["user"], "alice")
        self.assertEqual(msg["display_name"], "Alice")
        self.assertEqual(msg["channel"], "mychannel")
        self.assertEqual(msg["text"], "!attack")

    def test_privmsg_without_tags(self):
        line = ":bob!bob@bob.tmi.twitch.tv PRIVMSG #mychannel :!heal"
        msg = parse_privmsg(line)
        self.assertEqual(msg["user"], "bob")
        self.assertEqual(msg["display_name"], "bob")
        self.assertEqual(msg["text"], "!heal")

    def test_non_privmsg_returns_none(self):
        self.assertIsNone(parse_privmsg("PING :tmi.twitch.tv"))
        self.assertIsNone(parse_privmsg(""))
        self.assertIsNone(parse_privmsg(":alice!alice@alice.tmi.twitch.tv JOIN #mychannel"))

    def test_irc_message_feeds_same_parser(self):
        clock = FakeClock()
        game = ChatBossGame(clock=clock)
        msg = parse_privmsg(
            ":carol!carol@carol.tmi.twitch.tv PRIVMSG #x :!attack"
        )
        reply = game.handle_chat(msg["user"], msg["text"])
        self.assertIn("5 damage", reply)
        self.assertEqual(game.boss_hp, 95)


class TestCommands(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.game = ChatBossGame(clock=self.clock)

    def test_attack_damage_and_cooldown(self):
        self.assertEqual(self.game.boss_hp, 100)
        self.game.handle_chat("alice", "!attack")
        self.assertEqual(self.game.boss_hp, 95)
        # Same user inside 10s cooldown: no damage.
        reply = self.game.handle_chat("alice", "!attack")
        self.assertIn("cooldown", reply)
        self.assertEqual(self.game.boss_hp, 95)
        # Different user is not on cooldown.
        self.game.handle_chat("bob", "!attack")
        self.assertEqual(self.game.boss_hp, 90)
        # After 10s, alice can attack again.
        self.clock.advance(10)
        self.game.handle_chat("alice", "!attack")
        self.assertEqual(self.game.boss_hp, 85)

    def test_fire_once_per_boss(self):
        self.game.handle_chat("alice", "!fire")
        self.assertEqual(self.game.boss_hp, 90)
        reply = self.game.handle_chat("alice", "!fire")
        self.assertIn("once per boss", reply)
        self.assertEqual(self.game.boss_hp, 90)
        # Another user may still fire.
        self.game.handle_chat("bob", "!fire")
        self.assertEqual(self.game.boss_hp, 80)

    def test_fire_resets_after_victory(self):
        self.game.boss_hp = 10
        self.game.handle_chat("alice", "!fire")  # victory, new boss 120 HP
        self.assertEqual(self.game.victories, 1)
        self.assertEqual(self.game.boss_hp, 120)
        reply = self.game.handle_chat("alice", "!fire")
        self.assertIn("10 damage", reply)  # allowed again on the new boss

    def test_heal_restores_and_caps(self):
        self.game.party_hp = 90
        self.game.handle_chat("alice", "!heal")
        self.assertEqual(self.game.party_hp, 95)
        self.game.handle_chat("alice", "!heal")
        self.assertEqual(self.game.party_hp, 100)
        self.game.handle_chat("alice", "!heal")
        self.assertEqual(self.game.party_hp, 100)  # capped, never above max

    def test_shield_blocks_counterattack(self):
        self.game.handle_chat("alice", "!shield")
        self.assertTrue(self.game.shield_active)
        msg = self.game.tick(now=self.clock.now + 31)
        self.assertIn("blocks", msg)
        self.assertEqual(self.game.party_hp, 100)
        self.assertFalse(self.game.shield_active)  # shield consumed

    def test_counterattack_unshielded(self):
        msg = self.game.tick(now=self.clock.now + 31)
        self.assertIn("8 damage", msg)
        self.assertEqual(self.game.party_hp, 92)

    def test_counterattack_not_before_30s(self):
        self.assertIsNone(self.game.tick(now=self.clock.now + 29))
        self.assertEqual(self.game.party_hp, 100)

    def test_victory_rollover(self):
        self.game.boss_hp = 5
        self.game.handle_chat("alice", "!attack")
        self.assertEqual(self.game.victories, 1)
        self.assertEqual(self.game.boss_number, 2)
        self.assertEqual(self.game.boss_max_hp, 120)
        self.assertEqual(self.game.boss_hp, 120)
        self.assertEqual(self.game.party_hp, 100)

    def test_defeat_rollover(self):
        self.game.party_hp = 8
        self.game.tick(now=self.clock.now + 31)  # counterattack wipes party
        self.assertEqual(self.game.defeats, 1)
        self.assertEqual(self.game.boss_number, 2)
        self.assertEqual(self.game.boss_max_hp, 100)  # fresh run, not harder
        self.assertEqual(self.game.boss_hp, 100)
        self.assertEqual(self.game.party_hp, 100)

    def test_leaderboard_ordering(self):
        self.game.handle_chat("alice", "!attack")   # 5
        self.game.handle_chat("bob", "!fire")      # 10
        self.clock.advance(11)
        self.game.handle_chat("alice", "!attack")  # alice total 10
        self.game.handle_chat("carol", "!fire")    # 10
        board = self.game.leaderboard()
        self.assertEqual([d for _, d in board], [10, 10, 10])
        self.assertEqual(set(u for u, _ in board), {"alice", "bob", "carol"})
        # Higher damage sorts first.
        self.game.handle_chat("bob", "!attack")    # bob total 15 (cooldown? bob never attacked)
        self.assertEqual(self.game.leaderboard()[0], ("bob", 15))

    def test_boss_and_score_commands(self):
        self.assertIn("Boss 1", self.game.handle_chat("alice", "!boss"))
        self.assertIn("No damage", self.game.handle_chat("alice", "!score"))
        self.game.handle_chat("alice", "!attack")
        self.assertIn("alice: 5", self.game.handle_chat("alice", "!score"))

    def test_unknown_and_empty_ignored(self):
        self.assertIsNone(self.game.handle_chat("alice", "hello"))
        self.assertIsNone(self.game.handle_chat("alice", ""))
        self.assertIsNone(self.game.handle_chat("", "!attack"))
        self.assertEqual(self.game.boss_hp, 100)

    def test_state_shape(self):
        state = self.game.state()
        self.assertEqual(state["boss"], {"number": 1, "hp": 100, "max_hp": 100})
        self.assertEqual(state["party"], {"hp": 100, "max_hp": 100})
        for key in ("victories", "defeats", "shield_active", "leaderboard",
                    "last_event", "events"):
            self.assertIn(key, state)


class TestServer(unittest.TestCase):
    def setUp(self):
        self.game = ChatBossGame()
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.game, "sim")
        )
        self.port = server.server_address[1]
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.thread.start()
        self.server = server

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read().decode()

    def _post_sim(self, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/sim",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode())

    def test_health_and_state_shape(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")
        status, body = self._get("/state")
        state = json.loads(body)
        self.assertEqual(state["mode"], "sim")
        self.assertEqual(state["boss"]["hp"], 100)
        self.assertIn("leaderboard", state)

    def test_overlay_serves_html(self):
        status, body = self._get("/overlay")
        self.assertEqual(status, 200)
        self.assertIn("ChatBoss", body)
        self.assertIn("/state", body)

    def test_sim_endpoint_uses_same_parser(self):
        status, data = self._post_sim({"user": "alice", "text": "!attack"})
        self.assertEqual(status, 200)
        self.assertIn("5 damage", data["reply"])
        self.assertEqual(data["boss"]["hp"], 95)
        # Cooldown enforced through the HTTP path too.
        _, data2 = self._post_sim({"user": "alice", "text": "!attack"})
        self.assertIn("cooldown", data2["reply"])
        self.assertEqual(data2["boss"]["hp"], 95)

    def test_sim_unknown_command(self):
        _, data = self._post_sim({"user": "alice", "text": "hi"})
        self.assertIsNone(data["reply"])
        self.assertEqual(data["boss"]["hp"], 100)


if __name__ == "__main__":
    unittest.main()
