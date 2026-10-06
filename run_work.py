"""
Virtual Key Sender & Mouse Movement Automation Script
------------------------------------------------------
Core automation engine for virtual typing, hotkeys, mouse movements,
and scenario execution based on JSON configuration.
"""

import sys
import os
import time
from datetime import datetime
import json
import math
import ctypes
from ctypes import wintypes
import random


def log_msg(msg, end="\n", flush=False):
    """Log message prepended with current timestamp [YYYY-MM-DD HH:MM:SS]."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_str = str(msg)

    is_cr = False
    if msg_str.startswith("\r"):
        is_cr = True
        msg_str = msg_str[1:]

    leading_newlines = ""
    while msg_str.startswith("\n"):
        leading_newlines += "\n"
        msg_str = msg_str[1:]

    prefix = "\r" if is_cr else leading_newlines
    padding = "   " if is_cr else ""
    print(f"{prefix}[{timestamp}] {msg_str}{padding}", end=end, flush=flush)



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
    """Core automation engine for virtual key typing, mouse movement, and scenario execution."""

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

        for vk in vk_codes:
            self.press_vk(vk, down=True)
            time.sleep(0.01)

        time.sleep(speed)

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
        """Send text/contents with token parsing (e.g. {ENTER}, {TAB}, {SLEEP:1.5}, {CLICK}, {MOVE:X,Y})."""
        k_speed = self.key_press_speed if key_press_speed is None else float(key_press_speed)
        k_interval = self.interval if interval is None else float(interval)

        if isinstance(contents, (list, tuple)):
            contents = "".join(contents)

        i = 0
        n = len(contents)
        while i < n and not self.stop_requested:
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
            log_msg(f"[Office Worker] {msg}")

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
        """Run automation workflow or scenario sequence from config dictionary."""
        self.stop_requested = False
        k_speed = float(config.get("key_press_speed", self.key_press_speed))
        k_interval = float(config.get("interval", self.interval))
        self.human_jitter = bool(config.get("human_jitter", self.human_jitter))

        scenario = config.get("scenario")
        repeat_count = int(config.get("repeat_count", 1))
        repeat_interval = float(config.get("repeat_interval", 1.0))

        log_msg("[Workflow] Loaded Arguments / Configuration:")
        for k, v in config.items():
            if k == "scenario" and isinstance(v, list):
                log_msg(f"  - {k}: [{len(v)} steps defined]")
            else:
                log_msg(f"  - {k}: {v}")

        current_run = 0
        while not self.stop_requested:
            current_run += 1

            if scenario and isinstance(scenario, list):
                scenario_name = config.get("scenario_name", "Office Worker Scenario")
                run_label = f"Run {current_run}/{repeat_count}" if repeat_count > 0 else f"Run {current_run} (Infinite)"
                log_msg(f"\n--- Running Scenario: '{scenario_name}' ({run_label}) ---")
                for step in scenario:
                    if self.stop_requested:
                        break
                    self.execute_scenario_step(step, k_speed, k_interval)
            else:
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

                contents = config.get("send_contents", "")
                if contents:
                    self.send_contents(contents, key_press_speed=k_speed, interval=k_interval)

            if repeat_count > 0 and current_run >= repeat_count:
                break

            if not self.stop_requested:
                rem = repeat_interval
                while rem > 0 and not self.stop_requested:
                    display_sec = int(math.ceil(rem)) if rem >= 1 else round(rem, 1)
                    log_msg(f"\r[Office Worker] Waiting for next run... {display_sec}s remaining", end="", flush=True)
                    sleep_time = min(1.0, rem)
                    time.sleep(sleep_time)
                    rem -= sleep_time
                print()



# ---------------------------------------------------------------------------
# Config File Manager (JSON)
# ---------------------------------------------------------------------------
def load_config(filepath="config.json"):
    """Load JSON configuration file."""
    if not os.path.isabs(filepath):
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------
def main():
    log_msg(f"[Init] CLI Arguments: {sys.argv}")
    config_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "config.json"

    log_msg(f"[Init] Loading configuration from '{config_path}'...")
    cfg = load_config(config_path)

    scenario_name = cfg.get("scenario_name", "Office Worker Automation")
    sec_init = 5
    log_msg(f"\n[Init] Starting Virtual Key & Mouse Automation ({scenario_name})")
    log_msg("Press Ctrl+C at any time to stop.")
    for i in range(sec_init, 0, -1):
        log_msg(f"\r[Init] Starting in {i}s...", end="", flush=True)
        time.sleep(1)
    print()


    engine = AutoInput(
        key_press_speed=cfg.get("key_press_speed", 0.025),
        interval=cfg.get("interval", 0.035),
        human_jitter=cfg.get("human_jitter", True)
    )
    try:
        engine.execute_workflow(cfg)
        log_msg("Automation finished successfully.")
    except KeyboardInterrupt:
        log_msg("\n[!] Automation stopped by user (Ctrl+C). Exiting.")


if __name__ == "__main__":
    main()
