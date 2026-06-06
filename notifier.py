"""
notifier.py â€” Multi-channel notification dispatcher.

Sends alerts through:
  1. Console   â€” always active
  2. Email     â€” SMTP (Gmail / Outlook / custom), enable in config.py
  3. Signal    â€” via signal-cli CLI tool, enable in config.py

Throttling: at most one alert per 5 seconds for any given subject prefix,
            EXCEPT priority="high" (2FA codes) â€” those always fire immediately.

College cybersecurity assignment â€” run only on systems you own.
"""

import smtplib
import ssl
import subprocess
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

_last_sent: dict[str, datetime] = {}
_THROTTLE_SECS = 5


def send_notification(subject: str, body: str, priority: str = "normal") -> None:
    """Send through all enabled channels (non-blocking for email / Signal)."""
    now = datetime.now()
    key = subject[:40]

    if priority != "high":
        last = _last_sent.get(key)
        if last and (now - last).total_seconds() < _THROTTLE_SECS:
            return

    _last_sent[key] = now

    # Console (synchronous â€” always)
    _console(subject, body, priority)

    # Email (background thread)
    if config.EMAIL_ENABLED:
        threading.Thread(target=_email, args=(subject, body, priority),
                         daemon=True).start()

    # Signal (background thread)
    if config.SIGNAL_ENABLED:
        threading.Thread(target=_signal, args=(subject, body),
                         daemon=True).start()


# â”€â”€ Console â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _console(subject: str, body: str, priority: str) -> None:
    border = "!" * 60 if priority == "high" else "=" * 60
    print(f"\n{border}")
    print(f"  [ALERT] {subject}")
    print(f"  Priority: {priority.upper()}")
    for line in body.splitlines()[:8]:
        print(f"  {line}")
    print(f"{border}\n")


# â”€â”€ Email â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _email(subject: str, body: str, priority: str) -> None:
    try:
        msg = MIMEMultipart()
        msg["From"]    = config.SENDER_EMAIL
        msg["To"]      = config.RECIPIENT_EMAIL
        msg["Subject"] = f"[SentinelKey | {priority.upper()}] {subject}"

        full_body = (
            f"SentinelKey Alert\n"
            f"Priority  : {priority.upper()}\n"
            f"Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'â”€' * 40}\n\n"
            f"{body}\n"
        )
        msg.attach(MIMEText(full_body, "plain", "utf-8"))

        if config.SMTP_USE_TLS:
            with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as s:
                s.login(config.SENDER_EMAIL, config.SENDER_PASSWORD)
                s.send_message(msg)

        print(f"[EMAIL] Sent to {config.RECIPIENT_EMAIL}")

    except Exception as exc:
        print(f"[EMAIL] Failed: {exc}")


# â”€â”€ Signal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _signal(subject: str, body: str) -> None:
    msg = f"[SentinelKey]\n{subject}\n\n{body[:400]}"
    try:
        result = subprocess.run(
            ["signal-cli", "-u", config.SIGNAL_PHONE, "send",
             "-m", msg, config.RECIPIENT_EMAIL],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            print("[SIGNAL] Sent successfully")
        else:
            print(f"[SIGNAL] Error: {result.stderr[:150]}")
    except FileNotFoundError:
        print("[SIGNAL] signal-cli not found â€” install from https://github.com/AsamK/signal-cli")
    except subprocess.TimeoutExpired:
        print("[SIGNAL] Timed out")
    except Exception as exc:
        print(f"[SIGNAL] Failed: {exc}")

