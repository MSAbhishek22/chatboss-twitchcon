#!/usr/bin/env python3
"""ChatBoss runner — stdlib only.

Usage:
  python3 run.py serve [--port 8768]   Start overlay + API server
  python3 run.py demo                   Scripted sim battle, printed to stdout
  python3 run.py test                   Run the unittest suite
"""

import argparse
import sys
import unittest

from chatboss.game import ChatBossGame
from chatboss.server import serve


def demo():
    game = ChatBossGame()
    script = [
        ("alice", "!attack"), ("bob", "!attack"), ("alice", "!fire"),
        ("carol", "!heal"), ("dave", "!shield"), ("bob", "!fire"),
        ("alice", "!attack"),  # within 10s cooldown -> refused (demo clock is real time)
        ("eve", "!boss"), ("frank", "!score"),
    ]
    for user, text in script:
        reply = game.handle_chat(user, text)
        print(f"{user} {text} -> {reply}")
    print("Boss counterattack after 30s (simulated tick):")
    print(" ", game.tick(now=game.clock() + 31))
    print("Final state:", game.state())


def main(argv=None):
    parser = argparse.ArgumentParser(prog="run.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--port", type=int, default=8768)
    sub.add_parser("demo")
    sub.add_parser("test")
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        serve(args.port)
    elif args.cmd == "demo":
        demo()
    elif args.cmd == "test":
        loader = unittest.TestLoader()
        suite = loader.discover("tests")
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        return 0 if result.wasSuccessful() else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
