"""menu.py -- the settings menu shown before each session (plain UI code, no cheat logic).

Every setting is listed once in SETTINGS; the menu and the saved settings file
are both generated from that list.
"""
import getpass
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import pygame

# Menu choices are saved per person (in your user folder), not in the project
# folder -- the project may live in a Drive folder shared with a partner.
SETTINGS_FILE = Path.home() / ".aim-cheat-study-settings.json"


def _default_player():
    """Your computer's username, so two people don't both record as the same player."""
    try:
        name = re.sub(r"[^A-Za-z0-9_-]", "", getpass.getuser())[:20]
    except Exception:
        name = ""
    return name or "player1"

MODES = ("human", "soft_aim", "strong_aim", "snap")
NEEDS_MOUSE = ("human", "soft_aim", "strong_aim")  # modes where you play; snap plays itself

MODE_HELP = {
    "human": "You play with no aim help. Turn the wallhack on to cheat with it alone.",
    "soft_aim": "Soft aim: you aim and click; the crosshair is gently pulled onto nearby targets.",
    "strong_aim": "Strong aim: while you move the mouse, the crosshair is steered onto the target. "
                  "You still have to move and click.",
    "snap": "Snap: the bot plays by itself, jumping onto each target and clicking.",
}


def cheat_name(mode, wallhack):
    """Name of the cheat combination, e.g. 'clean', 'soft_aim', 'strong_aim+wallhack'."""
    parts = [] if mode == "human" else [mode]
    if wallhack and mode in NEEDS_MOUSE:
        parts.append("wallhack")
    return "+".join(parts) or "clean"


@dataclass
class Setting:
    key: str
    label: str
    default: object
    lo: float = 0
    hi: float = 0
    step: float = 1
    modes: tuple = ()  # empty = shown for every mode
    help: str = ""
    kind: str = "num"  # num | choice | text | bool


SETTINGS = [
    Setting("mode", "Mode", "human", kind="choice"),
    Setting("wallhack", "Wallhack", False, kind="bool", modes=NEEDS_MOUSE,
            help="Shows where the next target will appear (cyan ring) before it appears. "
                 "Works on top of any aim mode. Its strength is random each session."),
    Setting("player", "Player name", _default_player(), kind="text", modes=NEEDS_MOUSE,
            help="Type to edit. Use a different name for each person who plays."),
    Setting("sensitivity_px_per_count", "Sensitivity", 1.0, 0.1, 5.0, 0.1,
            help="Crosshair pixels moved per mouse count. Higher = faster crosshair."),
]
# Cheat strengths are not settings: each session draws a random strength level
# for each cheat in use (see cheats.py, "CHEAT STRENGTH"). Session length and
# spawn timing are fixed (see game.py).


def defaults():
    return {s.key: s.default for s in SETTINGS}


def load_settings():
    cfg = defaults()
    try:
        saved = json.loads(SETTINGS_FILE.read_text())
        cfg.update({k: v for k, v in saved.items() if k in cfg})
    except (OSError, ValueError):
        pass
    if cfg["mode"] not in MODES:
        cfg["mode"] = "human"
    return cfg


def save_settings(cfg):
    try:
        SETTINGS_FILE.write_text(json.dumps({s.key: cfg[s.key] for s in SETTINGS}, indent=2))
    except OSError:
        pass


def _format(s, v):
    if s.kind == "bool":
        return "ON" if v else "OFF"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def _adjust(cfg, s, direction):
    if s.kind == "choice":
        cfg[s.key] = MODES[(MODES.index(cfg[s.key]) + direction) % len(MODES)]
    elif s.kind == "bool":
        cfg[s.key] = not cfg[s.key]
    elif s.kind == "num":
        v = min(max(cfg[s.key] + direction * s.step, s.lo), s.hi)
        cfg[s.key] = round(v, 4) if isinstance(s.default, float) else int(round(v))


def _wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


def menu(win, cfg, message=""):
    """Show the settings screen. Returns True to start a session, False to quit."""
    width, height = win.get_size()
    title = pygame.font.SysFont("consolas", 32, bold=True)
    font = pygame.font.SysFont("consolas", 19)
    small = pygame.font.SysFont("consolas", 15)
    clock = pygame.time.Clock()
    sel = 0

    def rows():
        return [s for s in SETTINGS if not s.modes or cfg["mode"] in s.modes]

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type != pygame.KEYDOWN:
                continue
            visible = rows()                      # changes when the mode changes
            sel = min(sel, len(visible) - 1)
            s = visible[sel]
            repeat = 10 if e.mod & pygame.KMOD_SHIFT else 1
            if e.key == pygame.K_ESCAPE:
                return False
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return True
            elif e.key == pygame.K_UP:
                sel = (sel - 1) % len(visible)
            elif e.key == pygame.K_DOWN:
                sel = (sel + 1) % len(visible)
            elif e.key in (pygame.K_LEFT, pygame.K_RIGHT) and s.kind != "text":
                for _ in range(repeat):
                    _adjust(cfg, s, -1 if e.key == pygame.K_LEFT else 1)
            elif s.kind == "text":
                if e.key == pygame.K_BACKSPACE:
                    cfg[s.key] = cfg[s.key][:-1]
                elif e.unicode and (e.unicode.isalnum() or e.unicode in "-_") and len(cfg[s.key]) < 20:
                    cfg[s.key] += e.unicode

        visible = rows()
        sel = min(sel, len(visible) - 1)
        win.fill((0, 25, 40))
        win.blit(title.render("Aim cheat study", True, (240, 240, 245)), (40, 18))
        if message:
            win.blit(small.render(message, True, (120, 220, 140)), (40, 60))

        y = 88
        for i, s in enumerate(visible):
            active = i == sel
            color = (255, 210, 90) if active else (200, 200, 210)
            if active:
                pygame.draw.rect(win, (30, 55, 75), (32, y - 4, 560, 28), border_radius=5)
            win.blit(font.render(s.label, True, color), (44, y))
            val = _format(s, cfg[s.key])
            if s.kind == "text":
                val += "_" if active and (time.time() * 2) % 2 < 1 else " "
            elif active:
                val = f"<  {val}  >"
            win.blit(font.render(val, True, color), (340, y))
            y += 30

        cheat = cheat_name(cfg["mode"], cfg["wallhack"])
        records = "CLEAN (label 0)" if cheat == "clean" else f"CHEAT: {cheat} (label 1)"
        lines = _wrap(MODE_HELP[cfg["mode"]], 82) + [f"Records as: {records}"]
        if visible[sel].help:
            lines += [""] + _wrap(visible[sel].help, 82)
        hy = height - 30 - 18 * len(lines) - 10
        for line in lines:
            win.blit(small.render(line, True, (150, 175, 200)), (40, hy))
            hy += 18
        keys = "Up/Down select   Left/Right change (Shift = x10)   Enter start   Esc quit"
        win.blit(small.render(keys, True, (110, 120, 135)), (40, height - 26))
        pygame.display.flip()
        clock.tick(60)
