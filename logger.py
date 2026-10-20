"""logger.py -- records each session into its own folder in data/.

  data/
    sessions.csv                one line per session (made by `python processing/sessions.py`)
    <date>_<time>_<player>_<cheat>_<id>/
      summary.json              who played, cheat + label, cheat strength, settings, results
      frames.csv                one row per frame: aim, shots, the target       (for analysis)
      targets.csv               one row per target: where, when, hit or not     (for analysis)
      replay/                   exact data to re-create the session (used by processing/render_video.py)
        frames.csv
        targets.csv

Every column is described in DATA_FORMAT.md.

Each session writes ONLY its own new folder -- nothing shared is ever appended
to -- so two people can record into the same synced Drive folder at once.
"""
import csv
import json
import math
import statistics
import time
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

# ---- analysis files: plain-English names, units in the name ------------------
FRAME_COLUMNS = [
    "frame", "time_s",
    "move_x_px", "move_y_px",                 # how far the crosshair moved this frame (after any cheat)
    "crosshair_x_px", "crosshair_y_px",
    "shot",                                   # blank, "hit" or "miss"
    # the one target -- either on screen, or still hidden in the gap before it appears
    "target_id", "target_visible",            # target_visible: 1 = on screen, 0 = hidden
    "target_x_px", "target_y_px", "target_distance_px",
    "target_size_px", "target_age_ms",        # only while visible
    "target_appears_in_ms",                   # only while hidden
]
TARGET_COLUMNS = [
    "target_id", "x_px", "y_px", "appeared_at_s", "ended_at_s", "outcome",
    "time_to_kill_ms",                        # only for hits: appeared -> shot
    "time_on_screen_ms", "size_when_ended_px", "crosshair_distance_when_appeared_px",
]

# ---- replay files: exact values needed to re-create the session --------------
REPLAY_FRAME_COLUMNS = [
    "frame", "time_s", "frame_length_s",
    "mouse_counts_x", "mouse_counts_y",       # whole mouse counts actually applied
    "crosshair_x", "crosshair_y", "clicked",
]
REPLAY_TARGET_COLUMNS = [
    "target_id", "x", "y",
    "decided_frame", "decided_time_s",        # when its position was picked (wallhack can see it from here)
    "scheduled_spawn_time_s",
    "spawn_frame", "end_frame", "outcome",    # visible on frames spawn_frame .. end_frame-1
]


def _round(value, digits=1):
    """Round for the CSV; blank for missing values; whole numbers when digits=0."""
    if value is None:
        return ""
    return int(round(value)) if digits == 0 else round(value, digits)


class SessionLog:
    def __init__(self, sensitivity):
        self.session_id = uuid.uuid4().hex[:6]
        self.sensitivity = sensitivity
        self.frame_rows = []
        self.replay_rows = []
        self.targets = {}                     # target_id -> everything we know about it

    # ---- target lifecycle events ---------------------------------------------------
    def target_decided(self, upcoming, frame):
        self.targets[upcoming.id] = {
            "id": upcoming.id, "x": upcoming.x, "y": upcoming.y,
            "decided_frame": frame, "decided_time": upcoming.decided_t,
            "scheduled_spawn_time": upcoming.spawn_t,
            "spawn_frame": None, "spawn_time": None, "end_frame": None, "end_time": None,
            "outcome": "not_spawned", "end_size": None, "distance_at_spawn": None,
        }

    def target_spawned(self, target_id, frame, t, cross):
        rec = self.targets[target_id]
        rec.update(spawn_frame=frame, spawn_time=t, outcome="on_screen_at_end",
                   distance_at_spawn=math.hypot(rec["x"] - cross[0], rec["y"] - cross[1]))

    def target_ended(self, target_id, frame, t, outcome, size):
        self.targets[target_id].update(end_frame=frame, end_time=t, outcome=outcome, end_size=size)

    # ---- one game frame --------------------------------------------------------------
    def frame(self, frame, t, dt, counts, cross, click, hit, target, visible):
        """target: the visible target (Tim's Target) if visible, else the hidden next one."""
        shot = "" if not click else ("hit" if hit else "miss")
        if visible:
            when = [_round(target.size), _round((t - target.spawn_t) * 1000, 0), ""]
        else:
            when = ["", "", _round(max(0.0, target.spawn_t - t) * 1000, 0)]
        self.frame_rows.append([
            frame, _round(t, 3),
            _round(counts[0] * self.sensitivity), _round(counts[1] * self.sensitivity),
            _round(cross[0]), _round(cross[1]),
            shot,
            target.id, int(visible), target.x, target.y,
            _round(math.hypot(target.x - cross[0], target.y - cross[1])), *when,
        ])
        self.replay_rows.append([frame, _round(t, 6), _round(dt, 6), counts[0], counts[1],
                                 _round(cross[0], 4), _round(cross[1], 4), int(click)])

    # ---- write everything ------------------------------------------------------------
    def save(self, player, aim_cheat, wallhack, cheat, label, seed, settings, strength, still_on_screen):
        if still_on_screen is not None:
            self.targets[still_on_screen.id]["end_size"] = still_on_screen.size

        appeared = [r for r in self.targets.values() if r["spawn_frame"] is not None]
        hit = [r for r in appeared if r["outcome"] == "hit"]
        shots = sum(1 for row in self.replay_rows if row[-1])
        ttk = [(r["end_time"] - r["spawn_time"]) * 1000 for r in hit]
        results = {
            "duration_s": _round(self.replay_rows[-1][1] if self.replay_rows else 0, 2),
            "targets_appeared": len(appeared),
            "targets_hit": len(hit),
            "targets_expired": sum(1 for r in appeared if r["outcome"] == "expired"),
            "shots": shots,
            "missed_shots": shots - len(hit),
            "accuracy_pct": _round(100 * len(hit) / shots if shots else 0),
            "median_time_to_kill_ms": _round(statistics.median(ttk), 0) if ttk else None,
        }

        recorded_at = time.strftime("%Y-%m-%d %H:%M:%S")
        folder_name = f"{time.strftime('%Y-%m-%d_%H-%M-%S')}_{player}_{cheat}_{self.session_id}"
        folder = DATA_DIR / folder_name
        (folder / "replay").mkdir(parents=True)

        summary = {
            "session": {
                "folder": folder_name, "recorded_at": recorded_at, "player": player,
                "cheat": cheat,
                "aim_cheat": aim_cheat,           # none, soft_aim, strong_aim or snap
                "wallhack": wallhack,
                "label": label, "label_meaning": "0 = clean, 1 = cheating",
            },
            "results": results,
            "cheat_strength": strength,           # random per session; level 0.0 weakest -> 1.0 strongest
            "settings": settings,
            "seed": seed,
            "files": {
                "frames.csv": "one row per frame: aim, shots, the target (see DATA_FORMAT.md)",
                "targets.csv": "one row per target: where, when, hit or expired",
                "replay/": "exact data to re-create the session; used to render videos",
            },
        }
        (folder / "summary.json").write_text(json.dumps(summary, indent=2))

        _write_csv(folder / "frames.csv", FRAME_COLUMNS, self.frame_rows)
        _write_csv(folder / "targets.csv", TARGET_COLUMNS, [
            [r["id"], r["x"], r["y"], _round(r["spawn_time"], 3), _round(r["end_time"], 3), r["outcome"],
             _round((r["end_time"] - r["spawn_time"]) * 1000, 0) if r["outcome"] == "hit" else "",
             _round(((r["end_time"] or self.replay_rows[-1][1]) - r["spawn_time"]) * 1000, 0),
             _round(r["end_size"]), _round(r["distance_at_spawn"])]
            for r in appeared])
        _write_csv(folder / "replay" / "frames.csv", REPLAY_FRAME_COLUMNS, self.replay_rows)
        _write_csv(folder / "replay" / "targets.csv", REPLAY_TARGET_COLUMNS, [
            [r["id"], r["x"], r["y"], r["decided_frame"], _round(r["decided_time"], 6),
             _round(r["scheduled_spawn_time"], 6), _round(r["spawn_frame"], 0), _round(r["end_frame"], 0),
             r["outcome"]]
            for r in self.targets.values()])

        line = (f"{cheat}: hit {len(hit)}/{len(appeared)} targets, accuracy {results['accuracy_pct']}%, "
                f"median time-to-kill {results['median_time_to_kill_ms']} ms")
        try:
            shown = folder.relative_to(Path.cwd())
        except ValueError:
            shown = folder
        print(f"Saved {shown}   ({line})")
        return line


def _write_csv(path, columns, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
