"""ChatBoss game state and command parser.

Pure logic, no I/O, no network. The same parser is fed by:
- sim mode: POST /sim
- Twitch mode: parsed IRC PRIVMSG lines (see twitch_irc.py)

Design decisions (documented, not hidden):
- On VICTORY: victories += 1, boss number += 1, next boss max HP += 20,
  party HP resets to 100, per-boss !fire set clears, shield clears.
- On DEFEAT: defeats += 1, boss number += 1, next boss resets to 100 max HP,
  party HP resets to 100, per-boss !fire set clears, shield clears.
  (A defeat is a fresh run, not a harder boss.)
- !heal caps party HP at 100.
- Cooldowns and counterattack timing use an injectable clock so tests
  can control time without sleeping.
"""

import time

ATTACK_DAMAGE = 5
FIRE_DAMAGE = 10
HEAL_AMOUNT = 5
COUNTERATTACK_DAMAGE = 8
COUNTERATTACK_INTERVAL = 30.0
ATTACK_COOLDOWN = 10.0
BOSS_HP_GROWTH = 20


class ChatBossGame:
    def __init__(self, clock=None):
        self.clock = clock or time.time
        now = self.clock()
        self.boss_number = 1
        self.boss_max_hp = 100
        self.boss_hp = 100
        self.party_max_hp = 100
        self.party_hp = 100
        self.victories = 0
        self.defeats = 0
        self.shield_active = False
        self.damage_by_user = {}
        self._last_attack_by_user = {}
        self._fired_users = set()
        self._last_counterattack = now
        self.last_event = "Boss 1 appeared with 100 HP. Type !attack in chat!"
        self.events = [self.last_event]

    # -- helpers ---------------------------------------------------------
    def _log(self, message):
        self.last_event = message
        self.events.append(message)
        self.events = self.events[-20:]

    def _deal_damage(self, user, amount, label):
        self.boss_hp -= amount
        self.damage_by_user[user] = self.damage_by_user.get(user, 0) + amount
        if self.boss_hp <= 0:
            self.boss_hp = 0
            self.victories += 1
            msg = (
                f"VICTORY! {user} dealt the final blow ({label}). "
                f"Boss {self.boss_number} defeated."
            )
            self._log(msg)
            self._new_boss(victory=True)
            return f"{msg} New boss {self.boss_number} appeared with {self.boss_max_hp} HP!"
        return f"{user} dealt {amount} damage ({label}). Boss HP: {self.boss_hp}/{self.boss_max_hp}."

    def _new_boss(self, victory):
        self.boss_number += 1
        if victory:
            self.boss_max_hp += BOSS_HP_GROWTH
        else:
            self.boss_max_hp = 100
        self.boss_hp = self.boss_max_hp
        self.party_hp = self.party_max_hp
        self.shield_active = False
        self._fired_users = set()
        self._last_counterattack = self.clock()

    def _check_defeat(self):
        if self.party_hp <= 0:
            self.party_hp = 0
            self.defeats += 1
            self._log(f"DEFEAT! Boss {self.boss_number} wiped the party.")
            self._new_boss(victory=False)
            return True
        return False

    # -- boss counterattack ---------------------------------------------
    def tick(self, now=None):
        """Apply a boss counterattack if 30s elapsed since the last one.

        Called on every /state and /sim request, and by the server's
        1-second background thread. Returns a message or None.
        """
        now = self.clock() if now is None else now
        if now - self._last_counterattack < COUNTERATTACK_INTERVAL:
            return None
        self._last_counterattack = now
        if self.shield_active:
            self.shield_active = False
            msg = "Boss counterattacks, but the party shield blocks it!"
            self._log(msg)
            return msg
        self.party_hp -= COUNTERATTACK_DAMAGE
        msg = f"Boss counterattacks for {COUNTERATTACK_DAMAGE} damage! Party HP: {max(self.party_hp, 0)}/{self.party_max_hp}."
        self._log(msg)
        if self._check_defeat():
            msg += f" DEFEAT! New boss {self.boss_number} appeared with {self.boss_max_hp} HP!"
        return msg

    # -- command parser (the single entry point for chat) ---------------
    def handle_chat(self, user, text, now=None):
        """Parse one chat message. Returns a reply string, or None if
        the message is not a ChatBoss command."""
        if not user or not text:
            return None
        now = self.clock() if now is None else now
        user = str(user).strip().lower()
        if not user:
            return None
        parts = str(text).strip().split()
        if not parts:
            return None
        cmd = parts[0].lower()

        if cmd == "!attack":
            last = self._last_attack_by_user.get(user)
            if last is not None and now - last < ATTACK_COOLDOWN:
                remaining = ATTACK_COOLDOWN - (now - last)
                return f"{user}: !attack is on cooldown ({remaining:.0f}s left)."
            self._last_attack_by_user[user] = now
            msg = self._deal_damage(user, ATTACK_DAMAGE, "!attack")
            self._log(msg)
            return msg

        if cmd == "!fire":
            if user in self._fired_users:
                return f"{user}: !fire can only be used once per boss."
            self._fired_users.add(user)
            msg = self._deal_damage(user, FIRE_DAMAGE, "!fire")
            self._log(msg)
            return msg

        if cmd == "!heal":
            before = self.party_hp
            self.party_hp = min(self.party_max_hp, self.party_hp + HEAL_AMOUNT)
            healed = self.party_hp - before
            msg = f"{user} heals the party for {healed} HP. Party HP: {self.party_hp}/{self.party_max_hp}."
            self._log(msg)
            return msg

        if cmd == "!shield":
            self.shield_active = True
            msg = f"{user} raises a shield! It will block the next boss counterattack."
            self._log(msg)
            return msg

        if cmd == "!boss":
            return (
                f"Boss {self.boss_number}: {self.boss_hp}/{self.boss_max_hp} HP | "
                f"Party: {self.party_hp}/{self.party_max_hp} HP | "
                f"Victories: {self.victories} | Defeats: {self.defeats} | "
                f"Shield: {'UP' if self.shield_active else 'down'}"
            )

        if cmd == "!score":
            board = self.leaderboard()
            if not board:
                return "No damage dealt yet. Type !attack!"
            lines = ", ".join(f"{u}: {d}" for u, d in board[:5])
            return f"Leaderboard: {lines}"

        return None

    def leaderboard(self):
        return sorted(self.damage_by_user.items(), key=lambda kv: -kv[1])

    def state(self):
        return {
            "boss": {
                "number": self.boss_number,
                "hp": self.boss_hp,
                "max_hp": self.boss_max_hp,
            },
            "party": {"hp": self.party_hp, "max_hp": self.party_max_hp},
            "victories": self.victories,
            "defeats": self.defeats,
            "shield_active": self.shield_active,
            "leaderboard": [
                {"user": u, "damage": d} for u, d in self.leaderboard()
            ],
            "last_event": self.last_event,
            "events": list(self.events[-10:]),
        }
