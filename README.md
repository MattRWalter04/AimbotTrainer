# Aim cheat study

We added cheats (soft aim, strong aim, a snap aimbot and a wallhack) and
per-frame recording to a simple 2D aim trainer, to compare two ways of catching
cheaters:

1. **Frame data**: a model trained on the per-frame recordings.
2. **Video**: a model trained only on videos of the gameplay.

## What's where

```
aim-cheat-study/
  README.md            you are here
  DATA_FORMAT.md       what every recorded file and column means

  cheats.py            THE CHEATS: all four, one commented function each. Start here.
  game.py              run this to play and record (look for "CHEAT HOOK")
  menu.py                settings menu, used by game.py
  logger.py              saves each session to data/, used by game.py
  tally.py               pop-up counting sessions per cheat type, opened by game.py

  processing/          everything done AFTER recording
    sessions.py          what has been recorded so far -> data/sessions.csv
    render_video.py      turns each session into a video -> videos/
    make_splits.py       train/val/test split -> data/splits.json
    common.py            shared loading code
    process_data.ipynb   runs the three scripts above in Google Colab

  data/                recordings: one folder per session (see DATA_FORMAT.md)
  videos/              rendered videos (created by processing/render_video.py)
  Python-Aim-Trainer/  Tech With Tim's game, which this runs on (not our code)
```

## Recording

```bash
python game.py
```

A menu opens with four choices: **Mode**, **Wallhack** on/off, **Player name**
and **Sensitivity**. **Up/Down** picks one, **Left/Right** changes it, **Enter**
starts a 60-second session and **Esc** quits. Each session saves to its own
folder in `data/`.

A small **Sessions recorded** window opens next to the game. It counts the
sessions in `data/` for each cheat type (yours and your partner's) and updates
every few seconds, so you can see which types still need recording.

| Mode | Who plays | Recorded as |
|---|---|---|
| `human` | you | `clean`, or `wallhack` if the wallhack is on |
| `soft_aim` | you, with a gentle pull near targets | cheat |
| `strong_aim` | you move the mouse, the cheat steers | cheat |
| `snap` | the bot plays by itself | cheat |

The wallhack can be turned on with `human`, `soft_aim` or `strong_aim`.

**Cheat strength is random.** You choose *whether* to cheat, not how much. Each
session gives every cheat in use a random, hidden strength level from 0.0
(weakest) to 1.0 (strongest), and records it with the session. The ranges are in
`STRENGTH_RANGES` at the bottom of `cheats.py`.

**Use your own player name.** It defaults to your computer's username, so check
it in the menu.

## Processing

Run these from the project folder after recording:

```bash
python processing/sessions.py        # what's been recorded -> data/sessions.csv
python processing/render_video.py    # videos -> videos/60fps and videos/30fps
python processing/make_splits.py     # train/val/test split -> data/splits.json (run once, at the end)
```

Or open `processing/process_data.ipynb` in Google Colab, which runs the same
three scripts on the shared Drive folder.

## Setup (once per computer)

1. Install Python, then run `pip install -r requirements.txt`.
2. Tim's game must be in `Python-Aim-Trainer/` inside this folder. If it's
   missing, run:
   ```bash
   git clone https://github.com/techwithtim/Python-Aim-Trainer
   git -C Python-Aim-Trainer checkout 12d853abca793b1e7c7022068544019228b62cac
   ```

### Sharing with a partner (Google Drive)

The game runs on your own computers (Colab has no screen or mouse). Put this
whole folder in a shared Google Drive folder, and both of you will record into
the same `data/`.

- **Owner:** install [Google Drive for desktop](https://www.google.com/drive/download/),
  put this folder (with `Python-Aim-Trainer/`) inside a Drive folder called
  `AimCheatStudy`, and share that folder with your partner as an **Editor**.
- **Partner:** install Google Drive for desktop. On drive.google.com, right-click
  the shared folder → **Organize → Add shortcut** → **My Drive**. Then open a
  terminal in the folder (usually `G:\My Drive\AimCheatStudy\aim-cheat-study`)
  and run `python game.py`.

Each session writes only its own new folder, so you can both record at the
same time. Menu settings are saved per person, in your own user folder.

## Changes to Tim's game

All of these are in `game.py`. Tim's `tutorial.py` itself is untouched.

- **One target at a time**, instead of a new one every 400 ms. After a target
  is hit or shrinks away, the next appears after a random gap (300–1200 ms by
  default). Its position is decided at the start of the gap, so the wallhack
  has something to reveal.
- **Fixed-length sessions** instead of 3 lives.
- **A crosshair moved by raw mouse input** instead of the Windows cursor, so the
  cheats can rewrite your input and the recording holds real mouse counts.

## Credit

Game: [Tech With Tim, *Python-Aim-Trainer*](https://github.com/techwithtim/Python-Aim-Trainer).
His repository has no license, so his code isn't redistributed with this
project. Clone it as shown above. Everything else here is original work for
this study.

<!-- Before publishing, choose a license for YOUR code (e.g. MIT) and add a LICENSE file. -->
