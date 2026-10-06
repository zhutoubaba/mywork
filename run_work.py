"""
Virtual Key Sender & Mouse Movement Automation Script
------------------------------------------------------
Requirements Met:
1. Key press speed, send contents, and interval are fully configurable.
2. Uses ONLY standard Python packages (ctypes, time, json, tkinter, threading, random). Zero external dependencies.
3. Removes argparse; all arguments and scenarios are loaded directly from config.json.
4. Includes full office worker behavior simulation engine and scenario runner.

Usage:
  - CLI: python run_work.py (loads config.json directly)
  - Custom Config: python run_work.py custom_config.json
  - GUI Mode: python run_work.py --gui (or set "gui": true in config.json)
  - Module import: from run_work import AutoInput
"""

import sys
import os
import time
import json
import math
import ctypes
from ctypes import wintypes
import threading
import random

# ---------------------------------------------------------------------------
# Windows API Data Types & Input Structs via ctypes (Zero dependencies)
# ---------------------------------------------------------------------------
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("dwMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION),
    ]

# Win32 Flags
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

# Virtual Key Mapping
VK_MAP = {
    "BACKSPACE": 0x08, "BACK": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D, "RETURN": 0x0D,
    "SHIFT": 0x10,
    "CTRL": 0x11, "CONTROL": 0x11,
    "ALT": 0x12, "MENU": 0x12,
    "PAUSE": 0x13, "CAPSLOCK": 0x14,
    "ESC": 0x1B, "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "END": 0x23, "HOME": 0x24,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "INSERT": 0x2D, "DELETE": 0x2E,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "WIN": 0x5B, "LWIN": 0x5B, "RWIN": 0x5C,
}


class AutoInput:
    """Core automation engine for virtual key typing, mouse movement, and office worker scenario execution."""

    def __init__(self, key_press_speed=0.025, interval=0.035, human_jitter=False):
        """
        :param key_press_speed: Duration (in seconds) key is held down.
        :param interval: Delay (in seconds) between characters / actions.
        :param human_jitter: Add natural timing variations to simulate human typing.
        """
        self.key_press_speed = float(key_press_speed)
        self.interval = float(interval)
        self.human_jitter = bool(human_jitter)
        self.stop_requested = False

    def _send(self, inp):
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    # --- Mouse API ---
    def get_mouse_pos(self):
        """Return current mouse cursor position (x, y)."""
        pt = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)

    def set_mouse_pos(self, x, y):
        """Move cursor instantly to (x, y)."""
        ctypes.windll.user32.SetCursorPos(int(x), int(y))

    def move_mouse(self, target_x, target_y, smooth=True, duration=0.3, steps=25):
        """Move cursor to target (x, y) with optional smooth interpolation."""
        if not smooth or duration <= 0:
            self.set_mouse_pos(target_x, target_y)
            return

        start_x, start_y = self.get_mouse_pos()
        dx = target_x - start_x
        dy = target_y - start_y
        step_delay = float(duration) / steps

        for i in range(1, steps + 1):
            if self.stop_requested:
                break
            t = i / steps
            ease = t * t * (3 - 2 * t)  # Smooth ease-in-out
            self.set_mouse_pos(start_x + dx * ease, start_y + dy * ease)
            time.sleep(step_delay)

        self.set_mouse_pos(target_x, target_y)

    def click_mouse(self, button="left", count=1, click_interval=0.05):
        """Perform mouse click(s). button='left'|'right'|'middle'"""
        btn = button.lower()
        if btn == "left":
            down_f, up_f = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
        elif btn == "right":
            down_f, up_f = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            down_f, up_f = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
        else:
            raise ValueError(f"Unknown button: {button}")

        for _ in range(count):
            if self.stop_requested:
                break
            self._send(INPUT(type=INPUT_MOUSE, u=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=down_f))))
            time.sleep(self.key_press_speed)
            self._send(INPUT(type=INPUT_MOUSE, u=_INPUT_UNION(mi=MOUSEINPUT(dwFlags=up_f))))
            time.sleep(click_interval)

    def scroll_mouse(self, amount):
        """Scroll mouse wheel. Positive amount scrolls up, negative scrolls down."""
        delta = int(amount * 120)
        dw_data = wintypes.DWORD(delta & 0xFFFFFFFF)
        inp = INPUT(
            type=INPUT_MOUSE,
            u=_INPUT_UNION(mi=MOUSEINPUT(dx=0, dy=0, mouseData=dw_data, dwFlags=MOUSEEVENTF_WHEEL, time=0, dwExtraInfo=0))
        )
        self._send(inp)

    # --- Keyboard API ---
    def press_vk(self, vk_code, down=True):
        """Press or release a virtual key code."""
        flags = 0 if down else KEYEVENTF_KEYUP
        inp = INPUT(
            type=INPUT_KEYBOARD,
            u=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk_code, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0))
        )
        self._send(inp)

    def send_vk(self, vk_code, press_speed=None):
        """Send virtual key press down & up."""
        speed = self.key_press_speed if press_speed is None else float(press_speed)
        self.press_vk(vk_code, down=True)
        time.sleep(speed)
        self.press_vk(vk_code, down=False)

    def send_hotkey(self, key_combo, press_speed=None):
        """Send key combination like 'CTRL+S', 'ALT+TAB', 'CTRL+SHIFT+ESC'."""
        speed = self.key_press_speed if press_speed is None else float(press_speed)
        parts = [p.strip().upper() for p in key_combo.split("+")]
        vk_codes = []
        for p in parts:
            if p in VK_MAP:
                vk_codes.append(VK_MAP[p])
            elif len(p) == 1 and p.isalnum():
                vk_codes.append(ord(p))

        if not vk_codes:
            return

        # Press all keys down in order
        for vk in vk_codes:
            self.press_vk(vk, down=True)
            time.sleep(0.01)

        time.sleep(speed)

        # Release all keys in reverse order
        for vk in reversed(vk_codes):
            self.press_vk(vk, down=False)
            time.sleep(0.01)

    def send_char(self, char, press_speed=None):
        """Send a single character using Unicode input event."""
        speed = self.key_press_speed if press_speed is None else float(press_speed)
        if self.human_jitter:
            speed = max(0.005, speed + random.uniform(-0.005, 0.01))

        if char == '\n':
            self.send_vk(VK_MAP["ENTER"], speed)
            return
        elif char == '\t':
            self.send_vk(VK_MAP["TAB"], speed)
            return

        code = ord(char)
        inp_down = INPUT(
            type=INPUT_KEYBOARD,
            u=_INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0))
        )
        inp_up = INPUT(
            type=INPUT_KEYBOARD,
            u=_INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))
        )
        self._send(inp_down)
        time.sleep(speed)
        self._send(inp_up)

    def send_contents(self, contents, key_press_speed=None, interval=None):
        """
        Send text/contents with token parsing (e.g. {ENTER}, {TAB}, {SLEEP:1.5}, {CLICK}, {MOVE:X,Y}).
        :param contents: String to send or list of character/token strings.
        :param key_press_speed: Override key press duration.
        :param interval: Override inter-character delay.
        """
        k_speed = self.key_press_speed if key_press_speed is None else float(key_press_speed)
        k_interval = self.interval if interval is None else float(interval)

        if isinstance(contents, (list, tuple)):
            contents = "".join(contents)

        i = 0
        n = len(contents)
        while i < n and not self.stop_requested:
            # Check for special tokens like {ENTER}, {SLEEP:1.0}, {MOVE:500,400}, {CTRL+S}
            if contents[i] == '{':
                end = contents.find('}', i)
                if end != -1:
                    token = contents[i+1:end].strip()
                    if self._handle_token(token, k_speed):
                        i = end + 1
                        delay = k_interval
                        if self.human_jitter:
                            delay = max(0.005, delay + random.uniform(-0.01, 0.015))
                        time.sleep(delay)
                        continue

            self.send_char(contents[i], press_speed=k_speed)
            delay = k_interval
            if self.human_jitter:
                delay = max(0.005, delay + random.uniform(-0.01, 0.015))
            time.sleep(delay)
            i += 1

    def _handle_token(self, token, press_speed):
        """Parse special action token inside curly braces."""
        upper = token.upper()
        if "+" in token:
            self.send_hotkey(token, press_speed)
            return True
        elif upper in VK_MAP:
            self.send_vk(VK_MAP[upper], press_speed)
            return True
        elif upper.startswith("SLEEP:"):
            try:
                time.sleep(float(token.split(":")[1]))
                return True
            except ValueError:
                pass
        elif upper.startswith("MOVE:"):
            try:
                parts = token.split(":")[1].split(",")
                self.move_mouse(int(parts[0]), int(parts[1]), smooth=True)
                return True
            except (ValueError, IndexError):
                pass
        elif upper.startswith("SCROLL:"):
            try:
                amount = float(token.split(":")[1])
                self.scroll_mouse(amount)
                return True
            except ValueError:
                pass
        elif upper == "CLICK":
            self.click_mouse("left")
            return True
        elif upper == "RIGHT_CLICK":
            self.click_mouse("right")
            return True
        return False

    def execute_scenario_step(self, step, base_speed, base_interval):
        """Execute a single scenario step dictionary."""
        action = step.get("action", "").lower()

        if action == "log":
            msg = step.get("message", step.get("text", ""))
            print(f"[Office Worker] {msg}")

        elif action in ("send_keys", "type", "input"):
            contents = step.get("contents", step.get("text", ""))
            speed = float(step.get("key_press_speed", base_speed))
            interval = float(step.get("interval", base_interval))
            self.send_contents(contents, key_press_speed=speed, interval=interval)

        elif action == "move_mouse":
            x = int(step.get("x", 0))
            y = int(step.get("y", 0))
            smooth = step.get("smooth", True)
            duration = float(step.get("duration", step.get("mouse_speed", 0.3)))
            self.move_mouse(x, y, smooth=smooth, duration=duration)

        elif action == "click":
            btn = step.get("button", "left")
            count = int(step.get("count", 1))
            self.click_mouse(btn, count=count)

        elif action == "scroll":
            amount = float(step.get("amount", -3))
            self.scroll_mouse(amount)

        elif action in ("sleep", "pause"):
            dur = float(step.get("duration", step.get("seconds", 1.0)))
            time.sleep(dur)

        elif action == "hotkey":
            combo = step.get("combo", step.get("keys", ""))
            if combo:
                self.send_hotkey(combo, press_speed=base_speed)

    def execute_workflow(self, config):
        """
        Run a full automation workflow or scenario sequence from a configuration dictionary.
        Supports both structured scenario steps ('scenario' list) and legacy single workflow parameters.
        """
        self.stop_requested = False
        k_speed = float(config.get("key_press_speed", self.key_press_speed))
        k_interval = float(config.get("interval", self.interval))
        self.human_jitter = bool(config.get("human_jitter", self.human_jitter))

        scenario = config.get("scenario")
        repeat_count = int(config.get("repeat_count", 1))
        repeat_interval = float(config.get("repeat_interval", 1.0))

        current_run = 0
        while not self.stop_requested:
            current_run += 1

            if scenario and isinstance(scenario, list):
                scenario_name = config.get("scenario_name", "Office Worker Scenario")
                run_label = f"Run {current_run}/{repeat_count}" if repeat_count > 0 else f"Run {current_run} (Infinite)"
                print(f"\n--- Running Scenario: '{scenario_name}' ({run_label}) ---")
                for step in scenario:
                    if self.stop_requested:
                        break
                    self.execute_scenario_step(step, k_speed, k_interval)
            else:
                # 1. Mouse movement (if specified)
                mx = config.get("mouse_x")
                my = config.get("mouse_y")
                if mx is not None and my is not None:
                    smooth = config.get("mouse_smooth", True)
                    m_speed = float(config.get("mouse_speed", 0.3))
                    self.move_mouse(int(mx), int(my), smooth=smooth, duration=m_speed)

                    click_btn = config.get("click_at_target")
                    if click_btn:
                        btn_type = "left" if click_btn is True else str(click_btn)
                        self.click_mouse(btn_type)

                # 2. Key/Text Sending
                contents = config.get("send_contents", "")
                if contents:
                    self.send_contents(contents, key_press_speed=k_speed, interval=k_interval)

            if repeat_count > 0 and current_run >= repeat_count:
                break

            if not self.stop_requested:
                time.sleep(repeat_interval)


# ---------------------------------------------------------------------------
# Config File Manager (JSON)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "scenario_name": "Normal Office Worker Behavior Simulation",
    "key_press_speed": 0.025,
    "interval": 0.035,
    "human_jitter": True,
    "repeat_count": 0,
    "repeat_interval": 2.0,
    "send_contents": "Hello World! {ENTER}Automation test successful.{ENTER}",
    "mouse_x": None,
    "mouse_y": None,
    "mouse_smooth": True,
    "mouse_speed": 0.3,
    "click_at_target": False
}

def get_config_path(filepath="config.json"):
    if not os.path.isabs(filepath):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(script_dir, filepath)
    return filepath

def load_config(filepath="config.json"):
    full_path = get_config_path(filepath)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            full_cfg = DEFAULT_CONFIG.copy()
            full_cfg.update(cfg)
            return full_cfg
    return DEFAULT_CONFIG.copy()

def save_config(filepath, config_dict):
    full_path = get_config_path(filepath)
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(config_dict, f, indent=4)



# ---------------------------------------------------------------------------
# Simple Graphical User Interface (Tkinter - Standard Library)
# ---------------------------------------------------------------------------
def launch_gui(config_path="config.json"):
    import tkinter as tk
    from tkinter import ttk, messagebox

    cfg = load_config(config_path)

    root = tk.Tk()
    root.title("Virtual Key & Mouse Automation")
    root.geometry("520x640")
    root.resizable(False, False)

    # Style
    style = ttk.Style()
    style.theme_use("clam")

    # Engine instance
    engine = AutoInput()
    worker_thread = None

    # Title
    header = ttk.Label(root, text="Virtual Key & Mouse Automation", font=("Segoe UI", 14, "bold"))
    header.pack(pady=10)

    frame = ttk.Frame(root, padding=15)
    frame.pack(fill="both", expand=True)

    # 1. Send Contents
    ttk.Label(frame, text="Send Contents (supports {ENTER}, {TAB}, {SLEEP:1.0}, {ALT+TAB}, {CTRL+S}):", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    text_area = tk.Text(frame, height=5, width=55, font=("Consolas", 10))
    text_area.grid(row=1, column=0, columnspan=2, pady=(0, 10))
    text_area.insert("1.0", cfg.get("send_contents", ""))

    # 2. Key Press Speed
    ttk.Label(frame, text="Key Press Speed (seconds hold down):").grid(row=2, column=0, sticky="w", pady=5)
    entry_speed = ttk.Entry(frame, width=15)
    entry_speed.grid(row=2, column=1, sticky="e", pady=5)
    entry_speed.insert(0, str(cfg.get("key_press_speed", 0.025)))

    # 3. Interval
    ttk.Label(frame, text="Interval between Keys/Actions (seconds):").grid(row=3, column=0, sticky="w", pady=5)
    entry_interval = ttk.Entry(frame, width=15)
    entry_interval.grid(row=3, column=1, sticky="e", pady=5)
    entry_interval.insert(0, str(cfg.get("interval", 0.035)))

    # 4. Mouse Coordinates
    ttk.Label(frame, text="Mouse Target (X, Y) [Optional]:").grid(row=4, column=0, sticky="w", pady=5)
    mouse_frame = ttk.Frame(frame)
    mouse_frame.grid(row=4, column=1, sticky="e", pady=5)

    entry_mx = ttk.Entry(mouse_frame, width=6)
    entry_mx.pack(side="left", padx=2)
    if cfg.get("mouse_x") is not None:
        entry_mx.insert(0, str(cfg["mouse_x"]))

    entry_my = ttk.Entry(mouse_frame, width=6)
    entry_my.pack(side="left", padx=2)
    if cfg.get("mouse_y") is not None:
        entry_my.insert(0, str(cfg["mouse_y"]))

    def pick_coords():
        def update_pos():
            x, y = engine.get_mouse_pos()
            lbl_pos.config(text=f"Mouse Pos: ({x}, {y}) - Press ESC to lock")
            if not top.done:
                top.after(50, update_pos)

        top = tk.Toplevel(root)
        top.title("Coordinate Picker")
        top.geometry("300x100")
        top.done = False
        lbl_pos = ttk.Label(top, text="Hover over target location...", font=("Segoe UI", 11))
        lbl_pos.pack(expand=True)

        def on_esc(event):
            top.done = True
            x, y = engine.get_mouse_pos()
            entry_mx.delete(0, tk.END)
            entry_mx.insert(0, str(x))
            entry_my.delete(0, tk.END)
            entry_my.insert(0, str(y))
            top.destroy()

        top.bind("<Escape>", on_esc)
        top.after(50, update_pos)

    btn_pick = ttk.Button(frame, text="Pick Position", command=pick_coords)
    btn_pick.grid(row=5, column=1, sticky="e", pady=(0, 5))

    # 5. Options
    var_smooth = tk.BooleanVar(value=cfg.get("mouse_smooth", True))
    chk_smooth = ttk.Checkbutton(frame, text="Smooth Mouse Glide", variable=var_smooth)
    chk_smooth.grid(row=5, column=0, sticky="w", pady=5)

    var_click = tk.BooleanVar(value=bool(cfg.get("click_at_target")))
    chk_click = ttk.Checkbutton(frame, text="Click at Target Mouse Position", variable=var_click)
    chk_click.grid(row=6, column=0, sticky="w", pady=5)

    # 6. Repeat Loop
    ttk.Label(frame, text="Repeat Count (1 = once, 0 = infinite):").grid(row=7, column=0, sticky="w", pady=5)
    entry_repeat = ttk.Entry(frame, width=15)
    entry_repeat.grid(row=7, column=1, sticky="e", pady=5)
    entry_repeat.insert(0, str(cfg.get("repeat_count", 1)))

    ttk.Label(frame, text="Repeat Delay (seconds):").grid(row=8, column=0, sticky="w", pady=5)
    entry_rep_delay = ttk.Entry(frame, width=15)
    entry_rep_delay.grid(row=8, column=1, sticky="e", pady=5)
    entry_rep_delay.insert(0, str(cfg.get("repeat_interval", 2.0)))

    # Status & Control Buttons
    lbl_status = ttk.Label(root, text="Status: Ready", font=("Segoe UI", 10, "italic"), foreground="gray")
    lbl_status.pack(pady=5)

    def get_ui_config():
        contents = text_area.get("1.0", tk.END).rstrip("\n")
        try:
            speed = float(entry_speed.get())
            interval = float(entry_interval.get())
            repeat = int(entry_repeat.get())
            rep_delay = float(entry_rep_delay.get())
        except ValueError:
            messagebox.showerror("Error", "Numeric values required for speeds/intervals.")
            return None

        mx_str = entry_mx.get().strip()
        my_str = entry_my.get().strip()
        mx = int(mx_str) if mx_str else None
        my = int(my_str) if my_str else None

        updated_cfg = cfg.copy()
        updated_cfg.update({
            "send_contents": contents,
            "key_press_speed": speed,
            "interval": interval,
            "mouse_x": mx,
            "mouse_y": my,
            "mouse_smooth": var_smooth.get(),
            "mouse_speed": 0.3,
            "click_at_target": var_click.get(),
            "repeat_count": repeat,
            "repeat_interval": rep_delay
        })
        return updated_cfg

    def start_automation():
        nonlocal worker_thread
        current_cfg = get_ui_config()
        if not current_cfg:
            return

        save_config(config_path, current_cfg)
        btn_start.config(state="disabled")
        btn_stop.config(state="normal")
        lbl_status.config(text="Status: Running (Countdown 3s)...", foreground="blue")

        def run_thread():
            time.sleep(3.0)  # Countdown focus delay
            lbl_status.config(text="Status: Executing Automation...", foreground="green")
            engine.execute_workflow(current_cfg)
            lbl_status.config(text="Status: Completed", foreground="gray")
            btn_start.config(state="normal")
            btn_stop.config(state="disabled")

        worker_thread = threading.Thread(target=run_thread, daemon=True)
        worker_thread.start()

    def stop_automation():
        engine.stop_requested = True
        lbl_status.config(text="Status: Stopping...", foreground="red")
        btn_start.config(state="normal")
        btn_stop.config(state="disabled")

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=10)

    btn_start = ttk.Button(btn_frame, text="▶ Start Automation (3s delay)", command=start_automation, width=28)
    btn_start.pack(side="left", padx=5)

    btn_stop = ttk.Button(btn_frame, text="⏹ Stop", command=stop_automation, state="disabled", width=15)
    btn_stop.pack(side="left", padx=5)

    root.mainloop()


# ---------------------------------------------------------------------------
# CLI Entrypoint (Argparse removed - configuration loaded from JSON)
# ---------------------------------------------------------------------------
def main():
    # Path to config file (default: config.json in current directory or specified as 1st arg)
    config_path = "config.json"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        config_path = sys.argv[1]

    # Load configuration strictly from config.json (or specified config file)
    print(f"Loading configuration from '{config_path}'...")
    cfg = load_config(config_path)

    # Check if GUI launch is requested in config or via --gui flag
    if cfg.get("gui", False) or "--gui" in sys.argv:
        launch_gui(config_path)
        return

    scenario_name = cfg.get("scenario_name", "Office Worker Automation")
    sec_init = 5
    print(f"Starting Virtual Key & Mouse Automation ({scenario_name}) in {sec_init} seconds...")
    print("Looping scenario infinitely. Press Ctrl+C to stop.")
    time.sleep(sec_init)

    engine = AutoInput(
        key_press_speed=cfg.get("key_press_speed", 0.025),
        interval=cfg.get("interval", 0.035),
        human_jitter=cfg.get("human_jitter", True)
    )
    try:
        engine.execute_workflow(cfg)
        print("Automation finished successfully.")
    except KeyboardInterrupt:
        print("\n[!] Automation stopped by user (Ctrl+C). Exiting.")


if __name__ == "__main__":
    main()
