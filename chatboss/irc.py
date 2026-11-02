"""Real Twitch IRC parsing (read-only, anonymous, no token).

Twitch IRC format (irc.chat.twitch.tv):
  With tags:
    @badge-info=;badges=;display-name=Alice;color=#FF0000;... \
    :alice!alice@alice.tmi.twitch.tv PRIVMSG #channel :!attack
  Without tags:
    :alice!alice@alice.tmi.twitch.tv PRIVMSG #channel :!attack

Reading public chat anonymously uses a justinfan nickname and no
OAuth token. This module only PARSES lines; the live socket loop is
connect_and_run() and is only started by the server when the
TWITCH_CHANNEL env var is set. No keys, tokens, or passwords appear
anywhere in this repo.

Parsed messages are fed into the SAME ChatBossGame.handle_chat()
parser used by sim mode, so sim and live behaviour cannot drift.
"""

import random
import socket
import threading


def parse_privmsg(line):
    """Parse one raw IRC line. Returns a dict for PRIVMSG, else None.

    Dict keys: user, display_name, channel, text, raw.
    display_name falls back to the IRC username when no tag is present.
    """
    if not line:
        return None
    raw = line.rstrip("\r\n")
    rest = raw
    tags = {}
    if rest.startswith("@"):
        tag_part, _, rest = rest.partition(" ")
        for item in tag_part[1:].split(";"):
            if "=" in item:
                key, value = item.split("=", 1)
                tags[key] = value
    if not rest.startswith(":"):
        return None
    prefix, _, rest = rest[1:].partition(" ")
    if " PRIVMSG " not in f" {rest} " and not rest.startswith("PRIVMSG "):
        return None
    # rest is now: "PRIVMSG #channel :message"
    _, _, after = rest.partition(" ")
    channel, _, message = after.partition(" :")
    if not message and ":" in after:
        # Fallback for a message without the usual " :" separator.
        channel, _, message = after.partition(":")
    if not channel.startswith("#"):
        return None
    username = prefix.split("!", 1)[0] if "!" in prefix else prefix
    display_name = tags.get("display-name") or username
    return {
        "user": username.lower(),
        "display_name": display_name,
        "channel": channel[1:],
        "text": message,
        "raw": raw,
    }


def connect_and_run(game, channel, stop_event=None, on_message=None):
    """Connect anonymously to Twitch IRC and feed chat into game.

    Runs until stop_event is set or the socket closes. Any socket error
    is raised to the caller (the server logs it and keeps serving sim
    mode); this function never writes a token anywhere.
    """
    stop_event = stop_event or threading.Event()
    nick = f"justinfan{random.randint(10000, 99999)}"
    sock = socket.create_connection(("irc.chat.twitch.tv", 6667), timeout=15)
    try:
        sock.sendall(f"NICK {nick}\r\n".encode())
        sock.sendall(f"JOIN #{channel}\r\n".encode())
        buf = ""
        while not stop_event.is_set():
            data = sock.recv(4096)
            if not data:
                break
            buf += data.decode("utf-8", errors="replace")
            while "\r\n" in buf:
                line, buf = buf.split("\r\n", 1)
                if line.startswith("PING"):
                    sock.sendall(b"PONG :tmi.twitch.tv\r\n")
                    continue
                parsed = parse_privmsg(line)
                if parsed is None:
                    continue
                reply = game.handle_chat(parsed["user"], parsed["text"])
                if on_message is not None:
                    on_message(parsed, reply)
    finally:
        try:
            sock.close()
        except OSError:
            pass
