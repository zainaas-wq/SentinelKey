# SentinelKey

> College cybersecurity assignment — keystroke & credential-capture framework.  
> Run **only on systems you own** or have explicit written permission to test.

---

## Overview

SentinelKey is a two-part Python keylogger built for a university cybersecurity course.  
It demonstrates how input-capture attacks work at the OS level, why strong authentication matters, and how defenders can detect them.

| Part | What it does | Output file |
|------|-------------|-------------|
| **Part 1** | Captures every keystroke, mouse event and **active window** (which app you're typing in) with millisecond timestamps | `keylog_output.txt` |
| **Part 2** | Detects password submissions across 5 scenarios and fires instant alerts | `passwords_captured.txt` |

---

## Features

### Part 1 — Input Logger
- **Window tracking** — logs the active application title on every keystroke  
  `[21:14:21.493] KEY_PRESS   p  | window=Google Chrome — Gmail`
- Every key press **and** release with timestamp
- Every mouse move (x, y coordinates)
- Every mouse click — button, press/release, coordinates
- Every scroll tick — direction, position, delta
- Real-time **dark-themed tkinter GUI** with live feed
- Pause / Resume / Stop controls
- Stats bar — live key count + mouse event count

### Part 2 — Password Detector
| # | Scenario | How detected |
|---|----------|-------------|
| 1 | **Mouse → click → type → Enter** | Mouse-click event in buffer before Enter |
| 2 | **Username → Tab → Password → Enter** | Tab timestamp within 2 s of Enter |
| 3 | **Ctrl+C → Ctrl+V → Enter** | Clipboard daemon + paste correlation |
| 4 | **2FA numeric code** | 4–8 digit-only string → Enter → HIGH priority |
| 5 | **Complex string heuristic** | 3+ character classes + length ≥ 8 |

Each detection includes:
- Confidence score (0–100 %)
- Detection reasons
- Flow type (Tab-Type-Enter / Mouse-Type-Enter / Heuristic)
- Clipboard content (if applicable)

### Notifications
- **Console** — always active, `!!!!` border for HIGH priority (2FA)
- **Email** — Gmail SMTP with App Password (configure in `config.py`)
- **Signal** — via `signal-cli` (configure in `config.py`)

---

## Project Structure

```
SentinelKey/
├── main.py               # Combined launcher (Part 1 + Part 2)
├── sentinel_key.py       # Part 1 — global input logger + GUI
├── password_sniffer.py   # Part 2 — PasswordDetector (5 scenarios)
├── clipboard_monitor.py  # Clipboard daemon thread (pyperclip)
├── notifier.py           # Email + Signal + console alerts
├── config.py             # All settings
├── Help.txt              # Full documentation
└── requirements.txt
```

**Runtime output files** (created automatically):

| File | Contents |
|------|----------|
| `keylog_output.txt` | Part 1 — every event with window context |
| `passwords_captured.txt` | Part 2 — captured credentials only |
| `clipboard_log.txt` | Clipboard change history |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run (Part 1 + Part 2 together)
python main.py

# 3. Run Part 1 only
python sentinel_key.py
```

Press **ESC** to stop, or click **STOP** in the GUI window.

---

## Log Format

### keylog_output.txt
```
SENTINELKEY — PART 1: COMPLETE INPUT LOG
Started : 2026-06-06 21:00:00
========================================================================
[2026-06-06 21:00:01.234] [WINDOW] ▶ Google Chrome — Gmail
[2026-06-06 21:00:01.500] KEY_PRESS   h                    | window=Google Chrome — Gmail
[2026-06-06 21:00:01.510] KEY_PRESS   e                    | window=Google Chrome — Gmail
[2026-06-06 21:00:02.100] MOUSE_CLICK  PRESS   btn=left  x=540  y=380  | window=Notepad
[2026-06-06 21:00:02.110] [WINDOW] ▶ Notepad — untitled.txt
[2026-06-06 21:00:05.000] MOUSE_SCROLL DOWN  x=540  y=380
```

### passwords_captured.txt
```
════════════════════════════════════════════════════════════
  *** PASSWORD CAPTURED ***
  Timestamp  : 2026-06-06 21:14:21.495
  Password   : MyP@ssword99
  Confidence : 90%
  Reasons    : Tab-to-password flow (Sc2); Complex string: 4 char-classes (Sc5)
  Flow       : Tab-Type-Enter, Heuristic
════════════════════════════════════════════════════════════

════════════════════════════════════════════════════════════
  [2FA CODE DETECTED — HIGH PRIORITY]
  Code       : 482917
  Note       : Code expires in ~5 minutes — act immediately!
════════════════════════════════════════════════════════════
```

---

## Configuration

All settings live in `config.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `START_ON_ESC` | `False` | `True` = wait for ESC before logging starts |
| `STOP_KEY` | `"esc"` | Key that stops the logger |
| `EMAIL_ENABLED` | `False` | Enable Gmail SMTP alerts |
| `SENDER_EMAIL` | — | Your Gmail address |
| `SENDER_PASSWORD` | — | Gmail App Password |
| `RECIPIENT_EMAIL` | — | Where alerts go |
| `SIGNAL_ENABLED` | `False` | Enable Signal alerts via signal-cli |
| `USE_GUI` | `True` | Show tkinter window |

### Enable email alerts
1. Enable 2FA on Gmail → generate an **App Password** at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Edit `config.py`:
```python
EMAIL_ENABLED   = True
SENDER_EMAIL    = "you@gmail.com"
SENDER_PASSWORD = "xxxx xxxx xxxx xxxx"   # App Password
RECIPIENT_EMAIL = "alerts@example.com"
```

---

## How the Window Tracker Works

`sentinel_key.py` runs a background thread (`WindowWatcher`) that calls the Windows API `GetForegroundWindow` + `GetWindowTextW` every 200 ms.

When the active window title changes:
1. A `[WINDOW] ▶ <title>` line is written to the log
2. The GUI banner updates in real time
3. Every subsequent key/mouse line includes `| window=<title>`

This means the log shows **exactly which app and page** a user was typing in — Chrome → Google, Notepad, VS Code, password managers, etc.

---

## Requirements

```
pynput>=1.7.6
pyperclip>=1.8.2
```

Python 3.8+ required. tkinter is included with the standard Windows Python installer.

---

## Legal

This project is for **educational use only** on systems you own or have explicit written permission to test.  
Unauthorised use may violate the Computer Fraud and Abuse Act (CFAA) and equivalent laws in your jurisdiction.
