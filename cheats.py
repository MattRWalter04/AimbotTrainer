"""
cheats.py -- every cheat used in the study, in one file.

HOW CHEATS PLUG INTO THE GAME
-----------------------------
Every frame, game.py reads what your real mouse did (how far it moved, and
whether you clicked). If an aim cheat is switched on, the game hands that input
to the cheat first, and the cheat hands back the movement/click the game should
use instead. That is exactly what a real aimbot does: it sits between your mouse
and the game and quietly rewrites your input.

  your mouse --> [ aim cheat ] --> crosshair moves

The wallhack is different: it never touches the mouse. It only draws extra
information on the cheater's screen (where the next target will appear).

WHAT THE CHEATS ARE ALLOWED TO KNOW
-----------------------------------
The same things a real cheat reads out of a game's memory:
  * where the crosshair is
  * where the target is (the game shows one target at a time), and how big it is
  * (wallhack only) where the next target will appear, before it is visible

`target` is None during the gap before the next target appears, so the aim
cheats do nothing then -- seeing hidden targets is the wallhack's job.

UNITS
-----
All movement is in screen pixels: (x, y), where +x is right and +y is down.
`dt` is the length of the current frame in seconds.

THE CHEATS (each one is self-contained -- read any of them on its own)
----------
  soft_aim()       you aim; a gentle pull toward the target once you're close
  strong_aim()     while you move the mouse, the cheat steers for you
  SnapBot          plays by itself: jumps onto targets and clicks
  draw_wallhack()  shows where and when the next target will appear

plus MouseOutput, a helper the game uses to turn any movement into whole mouse counts.

HOW STRONG EACH CHEAT IS -- random every session (bottom of this file)
------------------------
The player can't choose a cheat's strength. When a session starts, each cheat in
use gets a random strength LEVEL from 0.0 (weakest) to 1.0 (strongest), which
sets all of that cheat's knobs (see STRENGTH_RANGES). The level is hidden while
playing and saved with the session.
"""
import math

import pygame


# =============================================================================
# HELPER
# =============================================================================

class MouseOutput:
    """Turns the movement a cheat wants into whole mouse "counts".

    A real mouse only reports whole numbers of counts, and a real cheat that
    fakes mouse input (e.g. with Windows' SendInput) can only send whole numbers
    too. So the cheat's pixel movement is converted to whole counts, and any
    leftover fraction is carried over to the next frame so nothing is lost.

    Why this matters for the study: without it, cheated sessions would contain
    fractional movements no real mouse can produce, and a detector could catch
    every cheat by that alone -- which says nothing about how the cheat aims.

    For a clean player this changes nothing: their movement is already whole counts.
    """

    def __init__(self, sensitivity):
        self.sensitivity = sensitivity  # pixels per count
        self.leftover_x = 0.0
        self.leftover_y = 0.0

    def to_counts(self, move_x, move_y):
        exact_x = move_x / self.sensitivity + self.leftover_x
        exact_y = move_y / self.sensitivity + self.leftover_y
        counts_x, counts_y = round(exact_x), round(exact_y)
        self.leftover_x = exact_x - counts_x
        self.leftover_y = exact_y - counts_y
        return counts_x, counts_y


# =============================================================================
# CHEAT 1: SOFT AIM  (subtle aim assist -- the "closet cheater")
# =============================================================================

def soft_aim(cross, target, move, dt, strength, radius):
    """You aim and click yourself. Once the crosshair is within `radius` pixels
    of the target, it gets nudged a little toward it every frame. The
    nudge is strongest right next to the target and fades to nothing at the edge
    of the radius, so it feels like "sticky" aim rather than a lock.

    move:      (x, y) pixels your real mouse moved this frame
    strength:  how hard it pulls (roughly: fraction of the gap closed per second)
    radius:    how close you must be before it kicks in (pixels)
    returns:   (x, y) pixels the crosshair should actually move
    """
    if target is None:
        return move                      # nothing to aim at: your input untouched
    gap_x, gap_y = target.x - cross[0], target.y - cross[1]   # crosshair -> target
    distance = math.hypot(gap_x, gap_y)
    if distance >= radius:
        return move                      # too far away: your input untouched

    # Step 1: how much of the gap to close this frame.
    #   strength * dt     -> the per-second strength scaled to this frame
    #   (1 - d / radius)  -> 1.0 right at the target, 0.0 at the edge of the radius
    pull = min(1.0, strength * dt) * (1 - distance / radius)

    # Step 2: your movement, plus a small step toward the target.
    return (move[0] + gap_x * pull,
            move[1] + gap_y * pull)


# =============================================================================
# CHEAT 2: STRONG AIM  (aimbot that still needs you to move the mouse)
# =============================================================================

def strong_aim(cross, target, move, dt, strength, radius, your_direction_pct):
    """While your mouse is moving, the cheat takes over the *direction*: the
    crosshair heads straight for the target, and your mouse speed acts
    like a throttle. Stop moving and it stops too. You still click yourself.

    move:                (x, y) pixels your real mouse moved this frame
    strength:            how fast it locks on (fraction of the gap per second)
    radius:              how far away it can grab a target (pixels)
    your_direction_pct:  0-100. How much of YOUR direction is kept.
                           0   = perfectly straight, bot-steered paths (obvious)
                           100 = your own movement plus a pull (looks human)
    returns:             (x, y) pixels the crosshair should actually move
    """
    if move == (0, 0) or target is None:
        return move                      # you're not moving, or nothing to aim at
    gap_x, gap_y = target.x - cross[0], target.y - cross[1]   # crosshair -> target
    distance = math.hypot(gap_x, gap_y)
    if distance >= radius:
        return move
    if distance < 0.5:
        return (0.0, 0.0)                # already dead-on: swallow the wiggle, stay locked

    # Unit vector pointing from the crosshair to the target.
    dir_x, dir_y = gap_x / distance, gap_y / distance
    lock = min(1.0, strength * dt)       # fraction of the gap closed this frame

    # A) The cheat's own path: straight at the target, at your speed plus the
    #    lock speed -- but never further than the target itself.
    your_speed = math.hypot(move[0], move[1])
    step = min(distance, your_speed + distance * lock)
    cheat_x, cheat_y = dir_x * step, dir_y * step

    # B) "Your direction": your real movement plus a pull toward the target.
    yours_x = move[0] + gap_x * lock
    yours_y = move[1] + gap_y * lock

    # C) Blend A and B using the slider.
    keep = your_direction_pct / 100
    out_x = (1 - keep) * cheat_x + keep * yours_x
    out_y = (1 - keep) * cheat_y + keep * yours_y

    # D) Anti-overshoot: never carry the crosshair past the target along the
    #    line toward it. Without this, a fast flick flies past the target, gets
    #    pulled back, flies past again... which shows up as jitter.
    forward = out_x * dir_x + out_y * dir_y          # how far we'd move toward the target
    if forward > distance:
        out_x -= (forward - distance) * dir_x
        out_y -= (forward - distance) * dir_y
    return out_x, out_y


# =============================================================================
# CHEAT 3: SNAP  (full aimbot -- plays by itself, no human input)
# =============================================================================

class SnapBot:
    """Once the target appears, waits `delay` seconds (a fake reaction
    time), teleports the crosshair onto it, and clicks on the next frame.

    It's a class rather than a function because it has to remember which target
    it already jumped to between frames.
    """

    def __init__(self, delay):
        self.delay = delay               # seconds a target must be visible before snapping
        self.locked_id = None            # the target we've already jumped onto

    def step(self, cross, target, now):
        """Returns ((x, y) pixels to move, click?)."""
        if target is None:
            return (0, 0), False
        gap_x, gap_y = target.x - cross[0], target.y - cross[1]   # crosshair -> target
        if now - target.spawn_t < self.delay:
            return (0, 0), False         # still "reacting"

        if self.locked_id != target.id:
            self.locked_id = target.id
            return (gap_x, gap_y), False # frame 1: jump onto the target
        return (gap_x, gap_y), True      # frame 2: stay on it and fire


# =============================================================================
# CHEAT 4: WALLHACK  (information cheat -- never touches the mouse)
# =============================================================================

WALLHACK_RING = (60, 220, 255)
WALLHACK_FILL = (30, 110, 130)
WALLHACK_RADIUS = 30                     # Tim's Target.MAX_SIZE: the size the target will grow to


def draw_wallhack(win, upcoming, target, now, warning, linger, background):
    """The game decides where the next target will appear *before* it appears
    (just like a real game server knows where enemies are before you can see
    them). The wallhack reads that and draws it on the cheater's screen.

    Only one target exists at a time, so at any moment either the next target
    is still hidden (Part 1) or it is on screen (Part 2).

    Part 1 -- the target is still HIDDEN (the gap after the last one):
      `warning` seconds before the target appears (or as soon as its position
      is decided, if the gap is shorter than that), the wallhack shows:
      * a cyan ring    = where it will appear
      * a filled disc  = grows as the appear time approaches; when it fills the
                         ring, the target appears
      So the cheater knows both WHERE and WHEN, and can be waiting on the spot.
      A longer warning gives the cheater more time to get there.

    Part 2 -- the target just APPEARED:
      In Tim's game a new target starts as a tiny dot and grows. So the ring
      stays on it, fading out over `linger` seconds (outline only, no fill),
      to keep the cheater on it while it's still hard to see.

    upcoming:    the hidden next target (x, y, decided_t, spawn_t), or None
    target:      the visible target, or None
    now:         current time in seconds
    warning:     seconds before the target appears that the ring shows up
    linger:      seconds the ring stays on a target after it appears (0 = off)
    background:  the game's background color (the ring fades into it)
    """
    # Part 2: a fading ring on a target that just appeared
    if target is not None and linger > 0:
        age = now - target.spawn_t
        if age < linger:
            fade = 1 - age / linger                          # 1.0 just appeared -> 0.0 gone
            color = [b + (r - b) * fade for r, b in zip(WALLHACK_RING, background)]
            pygame.draw.circle(win, color, (target.x, target.y), WALLHACK_RADIUS, 2)

    if upcoming is None:
        return

    # Part 1: where (ring) and when (filling disc) the hidden target appears
    time_left = upcoming.spawn_t - now
    shown_for = min(warning, upcoming.spawn_t - upcoming.decided_t)   # how long the ring is up in total
    if time_left > shown_for:
        return                                           # too early: not revealed yet
    progress = 1 - time_left / max(1e-6, shown_for)
    center = (upcoming.x, upcoming.y)
    if progress > 0:
        pygame.draw.circle(win, WALLHACK_FILL, center, max(1, WALLHACK_RADIUS * progress))
    pygame.draw.circle(win, WALLHACK_RING, center, WALLHACK_RADIUS, 2)


# =============================================================================
# CHEAT STRENGTH  (random every session -- the player can't choose it)
# =============================================================================
# When a session starts, each cheat in use gets a random LEVEL between
# 0.0 (weakest) and 1.0 (strongest). The level places every knob of that cheat
# the same fraction of the way along its range below.
# Example: soft_aim at level 0.5 -> strength 7.0, radius 130 px.
#
#                       (value at level 0.0,  value at level 1.0)
STRENGTH_RANGES = {
    "soft_aim": {
        "strength":           (2.0, 12.0),  # how hard it pulls
        "radius_px":          (60, 200),    # how close you must be before it pulls
    },
    "strong_aim": {
        "strength":           (8.0, 45.0),  # how fast it locks on while you move
        "radius_px":          (250, 1000),  # how far away it can grab a target (1000 = whole screen)
        "your_direction_pct": (80, 0),      # how much of YOUR direction it keeps (less = more obvious)
    },
    "snap": {
        "delay_ms":           (300, 0),     # fake reaction time before it snaps
    },
    "wallhack": {
        "warning_ms":         (150, 1500),  # how early the ring shows where the next target will be
        "linger_ms":          (0, 2500),    # how long the ring stays on a target after it appears
    },
}


def random_strength(cheat, rng):
    """Draw a random level for one cheat and work out its knob values.
    Returns {"level": 0.0-1.0, <knob>: value, ...}."""
    level = rng.random()
    knobs = {"level": round(level, 3)}
    for knob, (weakest, strongest) in STRENGTH_RANGES[cheat].items():
        knobs[knob] = round(weakest + level * (strongest - weakest), 2)
    return knobs
