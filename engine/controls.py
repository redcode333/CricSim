"""
controls.py
Non-blocking keyboard input and live speed control during simulation.

Keys during a live match:
  1  ->  1x   (2.0 sec / ball)
  2  ->  2x   (1.0 sec / ball)
  3  ->  4x   (0.4 sec / ball)
  4  ->  Instant (no delay)
  p  ->  Pause / Resume
  q  ->  Quit match early
"""

import sys
import time

# ---------------------------------------------------------------------------
# Platform-specific non-blocking key reader
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import msvcrt

    def _kbhit() -> bool:
        return msvcrt.kbhit()

    def _getch() -> str:
        return msvcrt.getch().decode("utf-8", errors="ignore")

else:
    import select
    import tty
    import termios

    def _kbhit() -> bool:
        return bool(select.select([sys.stdin], [], [], 0)[0])

    def _getch() -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def poll_key() -> str:
    """Return the pressed key (lowercase) or '' if nothing pressed."""
    if _kbhit():
        return _getch().lower()
    return ""


# ---------------------------------------------------------------------------
# Speed map
# ---------------------------------------------------------------------------

SPEEDS = {
    "1": ("1x",      2.0),
    "2": ("2x",      1.0),
    "3": ("4x",      0.4),
    "4": ("Instant", 0.0),
}


# ---------------------------------------------------------------------------
# SpeedControl — shared mutable state passed into the simulator
# ---------------------------------------------------------------------------

class SpeedControl:
    def __init__(self, initial_key: str = "2"):
        label, delay = SPEEDS.get(initial_key, ("2x", 1.0))
        self.label   = label
        self.delay   = delay
        self.paused  = False
        self.quit    = False

    def apply_key(self, key: str):
        if key in SPEEDS:
            self.label, self.delay = SPEEDS[key]
            print(f"\n  [Speed changed -> {self.label}]", flush=True)
        elif key in ("p", " "):
            self.paused = not self.paused
            if self.paused:
                print("\n  [PAUSED] Press P to resume...", flush=True)
            else:
                print("\n  [RESUMED]", flush=True)
        elif key == "q":
            self.quit = True
            print("\n  [Quit requested — ending innings early]", flush=True)

    def status_bar(self) -> str:
        state = "PAUSED" if self.paused else f"Speed: {self.label}"
        return f"  [{state}]  Controls: 1=1x  2=2x  3=4x  4=Instant  P=Pause  Q=Quit"


# ---------------------------------------------------------------------------
# Smart sleep — checks for keypresses every 50 ms during the delay
# ---------------------------------------------------------------------------

def smart_sleep(sc: SpeedControl):
    """
    Sleep for sc.delay seconds but poll for keypresses every 50 ms
    so controls feel instant. Also handles pause loop.
    """
    # Handle pause: spin until unpaused
    while sc.paused and not sc.quit:
        time.sleep(0.05)
        key = poll_key()
        if key:
            sc.apply_key(key)

    if sc.quit:
        return

    # Sleep in 50 ms chunks, checking keys throughout
    remaining = sc.delay
    chunk = 0.05
    while remaining > 0 and not sc.quit:
        time.sleep(min(chunk, remaining))
        remaining -= chunk
        key = poll_key()
        if key:
            sc.apply_key(key)
            # If speed changed, use new delay for remaining sleep
            # (just break — next ball uses new delay from scratch)
            break
        # Re-enter pause loop if user paused mid-sleep
        while sc.paused and not sc.quit:
            time.sleep(0.05)
            key = poll_key()
            if key:
                sc.apply_key(key)
