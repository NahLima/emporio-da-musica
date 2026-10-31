"""CLI for Mel, the Empório da Música attendant.

Usage:
    python -m src.main                       # interactive chat
    python -m src.main --today 2026-02-20   # simulate a reference date
    python -m src.main --message "Olá"      # one message, then exit
    python -m src.main --session-id leticia  # resume/persist a session

The API key is read from GEMINI_API_KEY (see .env.example). It is never
printed, logged or written to any file by this program.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from dotenv import load_dotenv

from src.agent import GeminiAgent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mel — Empório da Música customer-service agent."
    )
    parser.add_argument(
        "--today",
        default=None,
        help="Reference date (YYYY-MM-DD) for deadline calculations. "
        "Default: the system date.",
    )
    parser.add_argument(
        "--session-id",
        default="default",
        help="Session id; history is persisted to sessions/<id>.json.",
    )
    parser.add_argument(
        "--message",
        default=None,
        help="Send a single message and exit (used by scripts/run_examples.py).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Gemini model id. Default: GEMINI_MODEL or gemini-3.8-flash.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)
    today = args.today or date.today().isoformat()
    try:
        agent = GeminiAgent(
            model=args.model or os.environ.get("GEMINI_MODEL"),
            today=today,
            session_id=args.session_id,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("Mel — Empório da Música 🎵")
    print(f"Reference date: {agent.today.isoformat()} | Session: {agent.session_id}")
    print("Type 'sair' to quit.\n")

    if args.message is not None:
        result = agent.chat(args.message)
        print(result["reply"])
        return 0

    while True:
        try:
            user_text = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté mais! 🎵")
            return 0
        if user_text.lower() in ("sair", "exit", "quit"):
            print("Mel: Até mais! Qualquer coisa, é só chamar. 🎵")
            return 0
        if not user_text:
            continue
        result = agent.chat(user_text)
        print(f"\nMel: {result['reply']}\n")


if __name__ == "__main__":
    raise SystemExit(main())
