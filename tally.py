"""tally.py -- small pop-up window counting recorded sessions per cheat type.

game.py opens it automatically (or run it on its own: python tally.py). It
re-counts the session folders in data/ every few seconds, so it also picks up
sessions your partner records into the shared folder.
"""
import json
import sys
import tkinter as tk
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True

from logger import DATA_DIR  # noqa: E402
from menu import MODES, cheat_name  # noqa: E402

# every cheat type the game can record, in menu order (snap has no wallhack, so dedupe)
CHEATS = list(dict.fromkeys(cheat_name(mode, wallhack) for mode in MODES for wallhack in (False, True)))
REFRESH_MS = 3000


def refresh():
    counts, unreadable = Counter(), 0
    for path in DATA_DIR.glob("*/summary.json"):
        try:
            counts[json.loads(path.read_text())["session"]["cheat"]] += 1
        except (OSError, ValueError, KeyError):  # still syncing from the shared folder, or broken
            unreadable += 1
    rows = CHEATS + sorted(set(counts) - set(CHEATS))
    lines = [f"{c:<22}{counts[c]:>4}" for c in rows] + ["-" * 26, f"{'total':<22}{sum(counts.values()):>4}"]
    if unreadable:
        lines.append(f"({unreadable} not readable yet)")
    text.set("\n".join(lines))
    root.after(REFRESH_MS, refresh)


root = tk.Tk()
root.title("Sessions recorded")
text = tk.StringVar()
tk.Label(root, textvariable=text, font=("Consolas", 12), justify="left", padx=14, pady=10).pack()
refresh()
root.mainloop()
