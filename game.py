"""
game.py -- runs Tech With Tim's aim trainer with the study's cheats and logging.

Tim's game is NOT included in this repository. Clone it next to this file
(see README.md). We import his tutorial.py and reuse his Target class (targets
that grow, then shrink) and his drawing code. We only replace his main loop, so
that we can:

  1. read raw mouse movement and let an aim cheat rewrite it   -> CHEAT HOOK 1
  2. draw the wallhack on the cheater's screen                 -> CHEAT HOOK 2
  3. show ONE target at a time: after a target is hit (or shrinks away), the
     next one's position is decided right away, but it only appears after a
     random gap -- so during the gap a wallhack has something to reveal
  4. play fixed-length sessions instead of "3 lives"
  5. give each cheat a random, hidden strength every session (cheats.py)
  6. log every frame for the study (logger.py)

Run:  python game.py      (opens the settings menu)
"""
import math
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ folders syncing between computers via Drive

TIM_DIR = Path(__file__).resolve().parent / "Python-Aim-Trainer"
if not (TIM_DIR / "tutorial.py").exists():
    raise SystemExit(f"Tim's aim trainer not found at {TIM_DIR}\n"
                     "Clone it first:  git clone https://github.com/techwithtim/Python-Aim-Trainer")
sys.path.insert(0, str(TIM_DIR))

import pygame  # noqa: E402
import tutorial as tim  # noqa: E402  Tim's game: opens the window, defines Target and draw()

import cheats  # noqa: E402
from logger import SessionLog  # noqa: E402
from menu import NEEDS_MOUSE, cheat_name, load_settings, menu, save_settings  # noqa: E402

# Fixed for every session, so all sessions are comparable.
SESSION_LENGTH_S = 60
SPAWN_GAP_MS = (300, 1200)     # random gap between one target ending and the next appearing

# Tim's targets grow/shrink a fixed amount *per frame*, so his game is designed
# to run at 60 FPS. Running faster would make targets disappear sooner.
FPS = 60
PLAY_TOP = tim.TOP_BAR_HEIGHT  # the play area is below Tim's top bar


@dataclass
class UpcomingTarget:
    """The next target. Its position is decided as soon as the previous target
    is gone, but it only becomes visible at spawn_t."""
    id: int
    x: int
    y: int
    decided_t: float
    spawn_t: float


def decide_next_target(rng, now, target_id):
    # Same spawn area as Tim's game; the gap before it appears is random.
    x = rng.randint(tim.TARGET_PADDING, tim.WIDTH - tim.TARGET_PADDING)
    y = rng.randint(tim.TARGET_PADDING + PLAY_TOP, tim.HEIGHT - tim.TARGET_PADDING)
    return UpcomingTarget(target_id, x, y, now, now + rng.uniform(*SPAWN_GAP_MS) / 1000)


def draw_crosshair(win, cross, scale=1.0):
    cx, cy = cross[0] * scale, cross[1] * scale
    a, b, w = 9 * scale, 3 * scale, max(1, round(2 * scale))
    for p, q in (((cx - a, cy), (cx - b, cy)), ((cx + b, cy), (cx + a, cy)),
                 ((cx, cy - a), (cx, cy - b)), ((cx, cy + b), (cx, cy + a))):
        pygame.draw.line(win, (80, 255, 120), p, q, w)


def draw_top_bar(win, name, time_left, hits, shots, missed):
    pygame.draw.rect(win, "grey", (0, 0, tim.WIDTH, PLAY_TOP))
    acc = hits / shots if shots else 0
    text = f"{name}   Time {time_left:4.1f}   Hits {hits}   Missed {missed}   Acc {acc:.0%}"
    win.blit(tim.LABEL_FONT.render(text, 1, "black"), (8, 5))


def play_session(win, cfg, seed):
    """Play one session. Returns a one-line summary, or None if it was aborted."""
    mode = cfg["mode"]
    needs_mouse = mode in NEEDS_MOUSE
    wallhack = bool(cfg["wallhack"]) and needs_mouse
    cheat = cheat_name(mode, wallhack)
    sens = cfg["sensitivity_px_per_count"]

    rng = random.Random(seed)
    # Random, hidden strength for each cheat in use (see cheats.py, "CHEAT STRENGTH")
    strength_rng = random.Random(seed + 1)
    aim = cheats.random_strength(mode, strength_rng) if mode != "human" else None
    wall = cheats.random_strength("wallhack", strength_rng) if wallhack else None

    log = SessionLog(sens)
    mouse_out = cheats.MouseOutput(sens)
    snap_bot = cheats.SnapBot(aim["delay_ms"] / 1000) if mode == "snap" else None
    clock = pygame.time.Clock()

    # Exactly one of these is set at any moment:
    target = None                                        # the visible target (Tim's Target)
    upcoming = decide_next_target(rng, 0.0, target_id=0)  # the next one, still hidden
    log.target_decided(upcoming, frame=0)
    cross = [tim.WIDTH / 2, (tim.HEIGHT + PLAY_TOP) / 2]
    hits = shots = missed = 0

    if needs_mouse and not countdown(win, clock, cheat):
        return None

    t, frame = 0.0, 0
    while t < SESSION_LENGTH_S:
        # ---- time and raw input ------------------------------------------------
        dt = clock.tick(FPS) / 1000
        abort, click = poll_events()
        if abort:
            release_mouse()
            return None
        raw = pygame.mouse.get_rel() if needs_mouse else (0, 0)   # snap plays itself
        t += dt

        # ---- the target: appear after the gap, then Tim's grow/shrink -----------
        if upcoming and t >= upcoming.spawn_t:
            target = tim.Target(upcoming.x, upcoming.y)
            target.id, target.spawn_t = upcoming.id, t   # extra fields for the cheats/log
            log.target_spawned(target.id, frame, t, cross)
            upcoming = None
        if target:
            target.update()
            if target.size <= 0:                         # shrank away before being hit
                log.target_ended(target.id, frame, t, "expired", 0.0)
                missed += 1
                target = None
                upcoming = decide_next_target(rng, t, target_id=next_target_id(log))
                log.target_decided(upcoming, frame)

        # ==== CHEAT HOOK 1: aim cheats rewrite the mouse input ====================
        move = (raw[0] * sens, raw[1] * sens)            # your real movement, in pixels
        if mode == "soft_aim":
            move = cheats.soft_aim(cross, target, move, dt, aim["strength"], aim["radius_px"])
        elif mode == "strong_aim":
            move = cheats.strong_aim(cross, target, move, dt, aim["strength"],
                                     aim["radius_px"], aim["your_direction_pct"])
        elif mode == "snap":
            move, click = snap_bot.step(cross, target, t)
        dx, dy = mouse_out.to_counts(*move)              # whole counts, like a real mouse
        # ==========================================================================

        cross[0] = min(max(cross[0] + dx * sens, 0), tim.WIDTH)
        cross[1] = min(max(cross[1] + dy * sens, PLAY_TOP), tim.HEIGHT)

        # ---- shooting (Tim's collide) ------------------------------------------
        shown, visible = (target, True) if target else (upcoming, False)   # for the log
        hit = False
        if click:
            shots += 1
            if target and target.collide(*cross):
                hit = True
                hits += 1
                log.target_ended(target.id, frame, t, "hit", target.size)
                target = None
                upcoming = decide_next_target(rng, t, target_id=next_target_id(log))
                log.target_decided(upcoming, frame)

        log.frame(frame, t, dt, (dx, dy), cross, click, hit, shown, visible)
        frame += 1

        # ---- drawing -------------------------------------------------------------
        tim.draw(win, [target] if target else [])        # Tim's background + target
        if wallhack:                                     # ==== CHEAT HOOK 2 ====
            cheats.draw_wallhack(win, upcoming, target, t, wall["warning_ms"] / 1000,
                                 wall["linger_ms"] / 1000, tim.BG_COLOR)
        draw_crosshair(win, cross)
        draw_top_bar(win, cheat, max(0.0, SESSION_LENGTH_S - t), hits, shots, missed)
        pygame.display.update()

    release_mouse()
    player = cfg["player"] if needs_mouse else "bot"
    settings = {"sensitivity_px_per_count": sens, "session_length_s": SESSION_LENGTH_S,
                "spawn_gap_min_ms": SPAWN_GAP_MS[0], "spawn_gap_max_ms": SPAWN_GAP_MS[1]}
    strength = {}
    if aim:
        strength["aim_cheat"] = aim
    if wall:
        strength["wallhack"] = wall
    return log.save(player, "none" if mode == "human" else mode, wallhack, cheat,
                    int(cheat != "clean"), seed, settings, strength, target)


def next_target_id(log):
    """Targets are numbered 0, 1, 2, ... in the order they're decided."""
    return len(log.targets)


# ---- small input helpers -------------------------------------------------------

def poll_events():
    """Returns (abort, clicked)."""
    abort = clicked = False
    for e in pygame.event.get():
        if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            abort = True
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            clicked = True
    return abort, clicked


def release_mouse():
    pygame.event.set_grab(False)
    pygame.mouse.set_visible(True)


def countdown(win, clock, name):
    """3-2-1 before a played session. Locks the mouse so we get raw relative motion."""
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    big = pygame.font.SysFont("consolas", 64)
    start = time.perf_counter()
    while (left := 3 - (time.perf_counter() - start)) > 0:
        if poll_events()[0]:
            release_mouse()
            return False
        pygame.mouse.get_rel()                           # throw away movement during countdown
        win.fill(tim.BG_COLOR)
        draw_top_bar(win, name, 0, 0, 0, 0)
        s = big.render(str(math.ceil(left)), True, "white")
        win.blit(s, s.get_rect(center=(tim.WIDTH / 2, tim.HEIGHT / 2)))
        pygame.display.update()
        clock.tick(FPS)
    pygame.mouse.get_rel()
    return True


# ---- entry point -----------------------------------------------------------------

def main():
    # pop-up counting sessions per cheat type; its own process since tkinter and pygame don't share one
    tally = subprocess.Popen([sys.executable, str(Path(__file__).with_name("tally.py"))])
    try:
        cfg = load_settings()
        message = ""
        while menu(tim.WIN, cfg, message):
            save_settings(cfg)
            summary = play_session(tim.WIN, cfg, seed=random.randrange(1 << 30))
            message = "Session aborted - nothing saved." if summary is None else f"Saved  |  {summary}"
        save_settings(cfg)
        pygame.quit()
    finally:
        tally.terminate()


if __name__ == "__main__":
    main()
