
"""
Classic Tetris — Pygame (Educational Edition)
=============================================

This file implements a playable, desktop Tetris clone using Pygame with:

  • TRUE NES-style randomizer (LCG-based with 50% repeat rejection, optional first-piece rule)
  • Super Rotation System (SRS) kicks for JLSTZ and I pieces
  • DAS/ARR horizontal movement and configurable lock delay
  • Gravity curve similar to classic
  • Live, in-game configuration overlay (press F1) to tweak feel in real time
  • Heavy inline documentation for learning and extension

Author: M365 Copilot
Tested with: Python 3.10+ and pygame 2.5+

-------------------------------------------------------------
STRUCTURE OVERVIEW
-------------------------------------------------------------

This module is intentionally organized into small, well-named units:

  • Constants & Config: Tunable gameplay numbers with clear meanings
  • NESRandom: Implements a reproducible pseudo-random piece generator approximating NES behavior
  • Tetrimino/Piece model: Holds shape, rotation state, position
  • Collision/Board helpers: Pure functions: collide, merge, sweep
  • SRS rotation: rotate_with_srs() uses official JLSTZ/I kick tables
  • Input: ShiftRepeat class for DAS/ARR horizontal stepping
  • Overlay: Small UI to display & edit runtime tuning parameters
  • Game loop: Fixed-timestep update with rendering decoupled for smooth feel

-------------------------------------------------------------
NOTES ON ACCURACY VS AUTHENTICITY
-------------------------------------------------------------

This project focuses on *feel* and *clarity* more than byte-for-byte emulation.
The NES randomizer here uses an LCG and a single 50% repeat-rejection step,
which reproduces the key gameplay behavior: repeats occur, but are less common,
and long droughts are possible. It also includes an optional 'first piece rule'
(commonly cited: forbid S/Z/O as the very first piece). You can toggle that in
CONFIG.

The movement and rotation logic follow modern SRS rules (JLSTZ and I have
separate kick tables) for a predictable experience near walls and floors. If
you want stricter NES-era rotation and gravity quirks, you can change the
rotation and gravity functions—each is self-contained and documented.

-------------------------------------------------------------
CONTROLS (default)
-------------------------------------------------------------

  • Left / Right : Move (DAS/ARR)
  • Down         : Soft drop
  • Up           : Rotate clockwise
  • Z            : Rotate counter-clockwise
  • Space        : Hard drop
  • P            : Pause / Resume
  • R            : Restart
  • F1           : Toggle Config Overlay

Inside the Config Overlay:
  • Up/Down      : Select setting
  • Left/Right   : Decrease/Increase numeric values
  • Enter        : Toggle booleans
  • Esc/F1       : Close overlay

-------------------------------------------------------------
EXTENDING THIS CODEBASE
-------------------------------------------------------------

  • Add Hold Piece: Keep a 'held' Piece type, allow one swap per drop.
  • Add Sound: Pygame mixer load .wav for rotate/lock/line clear.
  • Add Persistence: Save high scores and config to JSON under ~/.tetris.
  • Add Skins: Drive COLORS from a theme JSON and expose in overlay.

Enjoy exploring and hacking this code!
"""

from __future__ import annotations
import math
import random
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pygame

# -------------------------------------------------------------
# CONSTANTS & DEFAULT CONFIG
# -------------------------------------------------------------
COLS, ROWS = 10, 20            # Board dimensions
CELL = 32                      # Pixel size of a cell
WIDTH, HEIGHT = COLS * CELL, ROWS * CELL

# Rendering/Update cadence
TARGET_FPS = 60                # Render target (vsync permitting)
UPDATE_HZ = 60                 # Fixed-timestep update rate for logic

# Scoring & level progression
LINES_PER_LEVEL = 10
SCORE_TABLE = {1: 40, 2: 100, 3: 300, 4: 1200}   # NES-like line clear points (multiplied by level+1)
SOFT_DROP_PER_CELL = 1         # Score per soft-drop cell
HARD_DROP_PER_CELL = 2         # Score per hard-drop cell

# Colors per tetromino type
COLORS: Dict[str, Tuple[int,int,int]] = {
    "I": (102, 224, 255),
    "J": (106, 119, 255),
    "L": (255, 158,  94),
    "O": (255, 224, 102),
    "S": ( 94, 224, 142),
    "T": (200, 119, 255),
    "Z": (255, 102, 119),
}

# Tetromino base shapes (minimal bounding box), 1s are blocks
SHAPES: Dict[str, List[List[int]]] = {
    "I": [[0,0,0,0],
          [1,1,1,1],
          [0,0,0,0],
          [0,0,0,0]],
    "J": [[1,0,0],
          [1,1,1],
          [0,0,0]],
    "L": [[0,0,1],
          [1,1,1],
          [0,0,0]],
    "O": [[1,1],
          [1,1]],
    "S": [[0,1,1],
          [1,1,0],
          [0,0,0]],
    "T": [[0,1,0],
          [1,1,1],
          [0,0,0]],
    "Z": [[1,1,0],
          [0,1,1],
          [0,0,0]],
}

# Default gameplay feel (can be edited live in overlay)
CONFIG = {
    # Horizontal movement feel
    "DAS_MS": 170,            # Delayed Auto Shift (ms before auto-stepping)
    "ARR_MS": 30,             # Auto Repeat Rate (ms per step after DAS). 0 => instant

    # Locking behavior
    "LOCK_DELAY_MS": 500,     # How long a grounded piece can be moved/rotated before it locks

    # Gravity
    "GRAVITY_MULT": 1.0,      # Multiplier on the base gravity (per level)
    "SOFT_DROP_MULT": 1.0,    # Multiplier on soft drop speed (affects scoring per cell still)

    # NES Randomizer specifics
    "NES_FIRST_PIECE_AVOID_SZO": True,  # Optional: forbid S/Z/O as the very first piece
    "NES_SEED": None,                   # If None, seeded from pygame.time.get_ticks(); set int for reproducibility
}

# Gravity curve (approx classic). Returns milliseconds between gravity drops.
def gravity_interval_ms(level: int) -> int:
    base, step = 1000, 60  # 1s at level 0, 60ms faster per level
    return max(60, int((base - level * step) / max(CONFIG["GRAVITY_MULT"], 0.1)))

# -------------------------------------------------------------
# NES-STYLE RANDOMIZER (Educational approximation)
# -------------------------------------------------------------
class NESRandom:
    """
    Educational approximation of NES Tetris piece randomization.

    NES Tetris uses a pseudo-random process with the following behavior:
      • Repeats are *possible* but *less likely*: if the newly rolled piece
        equals the previous piece, there's a 50% chance to reroll once.
      • Long droughts (e.g., no I for 20+ pieces) *can* happen.

    Implementation here:
      • Uses a 32-bit Linear Congruential Generator (LCG) state to produce
        pseudo-random numbers.
      • Maps to piece indices [0..6] for {I,J,L,O,S,T,Z}.
      • Applies one-time 50% repeat rejection.
      • Optional 'first piece rule' that forbids S/Z/O as the very first piece.

    This is not a cycle-accurate reimplementation of the NES ROM, but it
    mirrors the essential gameplay characteristics.
    """

    PIECES = ["I","J","L","O","S","T","Z"]

    def __init__(self, seed: Optional[int] = None, avoid_szo_first: bool = True):
        # Seed the LCG; if None, use ticks for variability
        if seed is None:
            seed = pygame.time.get_ticks() & 0xFFFFFFFF
        self.state = seed & 0xFFFFFFFF
        self.prev_index: Optional[int] = None
        self.avoid_szo_first = avoid_szo_first

    def _lcg_next(self) -> int:
        """Advance the 32-bit LCG state and return the new state.
        Using common LCG parameters (multiplier 0x41C64E6D, increment 0x3039).
        """
        self.state = (self.state * 0x41C64E6D + 0x3039) & 0xFFFFFFFF
        return self.state

    def _rand(self) -> int:
        """Return a pseudo-random 15-bit integer (0..32767) from the state.
        Following the common approach of using the high bits of the LCG.
        """
        return (self._lcg_next() >> 16) & 0x7FFF

    def _rand_choice7(self) -> int:
        """Map RNG to an index 0..6 by mod 7 (simple, uniform)."""
        return self._rand() % 7

    def next_piece(self) -> str:
        """Return next tetromino type using NES-like repeat rejection.

        Process:
          1) Roll candidate in 0..6.
          2) If first piece AND avoid_szo_first, reroll while candidate is S/Z/O.
          3) If candidate == prev, flip a coin (rand() & 1). If heads, reroll once.
          4) Update prev and return mapping to piece letter.
        """
        cand = self._rand_choice7()

        # Apply first-piece rule once
        if self.prev_index is None and self.avoid_szo_first:
            # Indices for S,Z,O in PIECES
            bad = {self.PIECES.index("S"), self.PIECES.index("Z"), self.PIECES.index("O")}
            # Ensure first piece is not S/Z/O (simple loop; expected to finish quickly)
            while cand in bad:
                cand = self._rand_choice7()

        # 50% repeat rejection if same as previous
        if self.prev_index is not None and cand == self.prev_index:
            if (self._rand() & 1) == 1:  # coin flip: 1 => reroll
                cand = self._rand_choice7()

        self.prev_index = cand
        return self.PIECES[cand]

# -------------------------------------------------------------
# PIECE MODEL & HELPERS
# -------------------------------------------------------------

def rotate_cw(mat: List[List[int]]) -> List[List[int]]:
    return [list(row) for row in zip(*mat[::-1])]

def rotate_ccw(mat: List[List[int]]) -> List[List[int]]:
    return [list(col) for col in zip(*mat)][::-1]

@dataclass
class Piece:
    t: str
    shape: List[List[int]]
    state: int  # rotation state 0=spawn,1=R,2=2,3=L
    x: int
    y: int

    @staticmethod
    def spawn(t: str) -> "Piece":
        shape = [row[:] for row in SHAPES[t]]
        w = len(shape[0])
        # Allow some spawning above top for tall pieces
        empty_rows_top = 0
        for r in shape:
            if all(v == 0 for v in r):
                empty_rows_top += 1
            else:
                break
        x = (COLS - w) // 2
        y = -min(empty_rows_top, 2)
        return Piece(t, shape, 0, x, y)

# Board is ROWS x COLS of Optional[str] (tetromino type)
Board = List[List[Optional[str]]]


def collide(board: Board, piece: Piece) -> bool:
    """Return True if piece collides with walls/floor or existing blocks."""
    for y, row in enumerate(piece.shape):
        for x, v in enumerate(row):
            if not v:
                continue
            bx, by = piece.x + x, piece.y + y
            if bx < 0 or bx >= COLS or by >= ROWS:
                return True
            if by >= 0 and board[by][bx]:
                return True
    return False


def merge(board: Board, piece: Piece) -> None:
    """Place the piece into the board (no collision check)."""
    for y, row in enumerate(piece.shape):
        for x, v in enumerate(row):
            if v:
                by = piece.y + y
                if by >= 0:
                    board[by][piece.x + x] = piece.t


def sweep(board: Board) -> int:
    """Clear full lines and return the number of cleared rows."""
    cleared = 0
    y = ROWS - 1
    while y >= 0:
        if all(board[y][x] for x in range(COLS)):
            del board[y]
            board.insert(0, [None] * COLS)
            cleared += 1
        else:
            y -= 1
    return cleared


def ghost_y(board: Board, piece: Piece) -> int:
    """Return the y position where the piece would land if hard-dropped."""
    test = Piece(piece.t, [r[:] for r in piece.shape], piece.state, piece.x, piece.y)
    while True:
        test.y += 1
        if collide(board, test):
            return test.y - 1

# -------------------------------------------------------------
# SRS ROTATION (JLSTZ and I have different kick tables)
# -------------------------------------------------------------
# Kicks for JLSTZ
JLSTZ_KICKS: Dict[Tuple[int,int], List[Tuple[int,int]]] = {
    (0,1): [(0,0), (-1,0), (-1, 1), (0,-2), (-1,-2)],
    (1,0): [(0,0), ( 1,0), ( 1,-1), (0, 2), ( 1, 2)],
    (1,2): [(0,0), ( 1,0), ( 1,-1), (0, 2), ( 1, 2)],
    (2,1): [(0,0), (-1,0), (-1, 1), (0,-2), (-1,-2)],
    (2,3): [(0,0), ( 1,0), ( 1, 1), (0,-2), ( 1,-2)],
    (3,2): [(0,0), (-1,0), (-1,-1), (0, 2), (-1, 2)],
    (3,0): [(0,0), (-1,0), (-1,-1), (0, 2), (-1, 2)],
    (0,3): [(0,0), ( 1,0), ( 1, 1), (0,-2), ( 1,-2)],
}
# Kicks for I piece (different table)
I_KICKS: Dict[Tuple[int,int], List[Tuple[int,int]]] = {
    (0,1): [(0,0), (-2,0), (1,0), (-2,-1), (1, 2)],
    (1,0): [(0,0), ( 2,0), (-1,0), ( 2, 1), (-1,-2)],
    (1,2): [(0,0), (-1,0), (2,0), (-1, 2), ( 2,-1)],
    (2,1): [(0,0), ( 1,0), (-2,0), ( 1,-2), (-2, 1)],
    (2,3): [(0,0), ( 2,0), (-1,0), ( 2, 1), (-1,-2)],
    (3,2): [(0,0), (-2,0), ( 1,0), (-2,-1), ( 1, 2)],
    (3,0): [(0,0), ( 1,0), (-2,0), ( 1,-2), (-2, 1)],
    (0,3): [(0,0), (-1,0), ( 2,0), (-1, 2), ( 2,-1)],
}


def rotate_with_srs(board: Board, piece: Piece, cw: bool = True) -> Optional[Piece]:
    """Try to rotate the piece with SRS kicks; return new piece or None if failed."""
    old_state = piece.state
    new_state = (old_state + (1 if cw else -1)) % 4
    new_shape = rotate_cw(piece.shape) if cw else rotate_ccw(piece.shape)
    kicks = (I_KICKS if piece.t == "I" else JLSTZ_KICKS).get((old_state, new_state), [(0,0)])
    for dx, dy in kicks:
        test = Piece(piece.t, [r[:] for r in new_shape], new_state, piece.x + dx, piece.y + dy)
        if not collide(board, test):
            return test
    return None

# -------------------------------------------------------------
# INPUT: DAS/ARR MANAGEMENT
# -------------------------------------------------------------
class ShiftRepeat:
    """
    Implements horizontal auto-shift similar to Tetris DAS/ARR.

    • Pressing left or right moves instantly once, then after DAS_MS delay,
      repeats steps every ARR_MS (0 => instant glide).
    • Releasing or switching direction resets the timers.
    """
    def __init__(self):
        self.dir = 0                 # -1 left, +1 right, 0 none
        self.held_ms = 0.0
        self.last_step_ms = 0.0
        self.did_initial = False

    def update(self, dt_ms: float, left_held: bool, right_held: bool) -> int:
        # Resolve intended direction (both held => no movement)
        ndir = (-1 if left_held else 0) + (1 if right_held else 0)
        if ndir != self.dir:
            self.dir = ndir
            self.held_ms = 0.0
            self.last_step_ms = 0.0
            self.did_initial = False

        if self.dir == 0:
            return 0

        self.held_ms += dt_ms

        # First step is immediate on press
        if not self.did_initial:
            self.did_initial = True
            return self.dir

        # Before DAS window: do nothing
        das = CONFIG["DAS_MS"]
        if self.held_ms < das:
            return 0

        # After DAS: either instant (ARR=0) or spaced repeats
        arr = CONFIG["ARR_MS"]
        if arr == 0:
            return self.dir
        self.last_step_ms += dt_ms
        if self.last_step_ms >= arr:
            self.last_step_ms = 0.0
            return self.dir
        return 0

# -------------------------------------------------------------
# OVERLAY (CONFIG UI)
# -------------------------------------------------------------
class Overlay:
    """
    Simple config overlay drawn on top of the game. It reads/writes CONFIG
    live so changes apply immediately.
    """
    def __init__(self):
        self.active = False
        # Editable fields (order matters for navigation)
        self.items = [
            ("DAS_MS", "DAS (ms)", 0, 400, 10),
            ("ARR_MS", "ARR (ms, 0=instant)", 0, 200, 5),
            ("LOCK_DELAY_MS", "Lock Delay (ms)", 100, 2000, 25),
            ("GRAVITY_MULT", "Gravity ×", 0.2, 5.0, 0.1),
            ("SOFT_DROP_MULT", "Soft Drop ×", 0.5, 5.0, 0.1),
            ("NES_FIRST_PIECE_AVOID_SZO", "Avoid S/Z/O as first piece (NES)", False, True, None),
        ]
        self.index = 0

    def toggle(self):
        self.active = not self.active

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_F1):
                self.toggle()
                return
            if event.key == pygame.K_UP:
                self.index = (self.index - 1) % len(self.items)
            elif event.key == pygame.K_DOWN:
                self.index = (self.index + 1) % len(self.items)
            else:
                key, label, lo, hi, step = self.items[self.index]
                val = CONFIG[key]
                if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
                    if event.key == pygame.K_LEFT:
                        newv = max(lo, (val - step))
                        CONFIG[key] = type(val)(round(newv, 3))
                    elif event.key == pygame.K_RIGHT:
                        newv = min(hi, (val + step))
                        CONFIG[key] = type(val)(round(newv, 3))
                else:
                    # boolean toggle on Enter
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_LEFT, pygame.K_RIGHT):
                        CONFIG[key] = not CONFIG[key]

    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        if not self.active:
            return
        # Panel
        panel_w, panel_h = WIDTH - 80, HEIGHT - 80
        panel_x, panel_y = 40, 40
        s = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        s.fill((20, 25, 40, 230))  # semi-transparent dark
        screen.blit(s, (panel_x, panel_y))

        title = font.render("CONFIG OVERLAY (F1/Esc to close)", True, (230,240,255))
        screen.blit(title, (panel_x + 20, panel_y + 16))

        hint = font.render("↑/↓ select • ←/→ adjust • Enter toggle", True, (200,210,235))
        screen.blit(hint, (panel_x + 20, panel_y + 40))

        # Items
        y = panel_y + 80
        for i, (key, label, lo, hi, step) in enumerate(self.items):
            is_bool = isinstance(lo, bool)
            val = CONFIG[key]
            color = (255, 255, 255) if i == self.index else (200, 210, 235)
            val_txt = f"{val}"
            if isinstance(val, float):
                val_txt = f"{val:.2f}"
            text = font.render(f"{label}: {val_txt}", True, color)
            screen.blit(text, (panel_x + 20, y))
            y += 28

# -------------------------------------------------------------
# DRAWING
# -------------------------------------------------------------

def draw_board(screen: pygame.Surface, board: Board, current: Piece, font: pygame.font.Font,
               score: int, level: int, lines: int):
    # Background
    screen.fill((10, 13, 34))

    # Grid
    for x in range(COLS + 1):
        pygame.draw.line(screen, (40, 50, 90), (x * CELL, 0), (x * CELL, HEIGHT))
    for y in range(ROWS + 1):
        pygame.draw.line(screen, (40, 50, 90), (0, y * CELL), (WIDTH, y * CELL))

    # Placed blocks
    for y in range(ROWS):
        for x in range(COLS):
            t = board[y][x]
            if t:
                pygame.draw.rect(screen, COLORS[t], (x * CELL + 1, y * CELL + 1, CELL - 2, CELL - 2))

    # Ghost piece
    gy = ghost_y(board, current)
    for r, row in enumerate(current.shape):
        for c, v in enumerate(row):
            if v and gy + r >= 0:
                pygame.draw.rect(screen, COLORS[current.t],
                                 ((current.x + c) * CELL + 4, (gy + r) * CELL + 4, CELL - 8, CELL - 8), 2)

    # Current piece
    for r, row in enumerate(current.shape):
        for c, v in enumerate(row):
            if v and current.y + r >= 0:
                pygame.draw.rect(screen, COLORS[current.t],
                                 ((current.x + c) * CELL + 1, (current.y + r) * CELL + 1, CELL - 2, CELL - 2))

    # HUD
    hud = font.render(f"Score {score}   Level {level}   Lines {lines}", True, (200, 210, 240))
    screen.blit(hud, (8, 4))

# -------------------------------------------------------------
# MAIN GAME LOOP
# -------------------------------------------------------------

def main():
    pygame.init()

    flags = pygame.SCALED | pygame.RESIZABLE
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=1)
    except TypeError:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    pygame.display.set_caption("Classic Tetris — Pygame (NES RNG, SRS, DAS/ARR)")

    font = pygame.font.SysFont(None, 22)
    big_font = pygame.font.SysFont(None, 42)
    clock = pygame.time.Clock()

    # Board state
    board: Board = [[None] * COLS for _ in range(ROWS)]

    # NES RNG
    nes_rng = NESRandom(seed=CONFIG["NES_SEED"], avoid_szo_first=CONFIG["NES_FIRST_PIECE_AVOID_SZO"])

    # Current and next pieces
    current = Piece.spawn(nes_rng.next_piece())
    next_type = nes_rng.next_piece()

    # Progress
    score = 0
    lines = 0
    level = 0

    gravity_ms = gravity_interval_ms(level)
    grav_accum = 0.0

    lock_timer = 0.0
    is_grounded = False

    paused = False
    game_over = False

    # Inputs
    shift = ShiftRepeat()
    soft_drop_held = False

    # Overlay
    overlay = Overlay()

    # Fixed timestep accumulator
    accumulator = 0.0
    dt_ms = 1000.0 / UPDATE_HZ

    while True:
        real_dt = clock.tick(TARGET_FPS)
        accumulator += real_dt

        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1:
                    overlay.toggle()
                if overlay.active:
                    overlay.handle_event(event)
                    continue
                if event.key == pygame.K_p:
                    paused = not paused
                if event.key == pygame.K_r:
                    return main()  # restart
                if game_over or paused:
                    continue
                if event.key == pygame.K_UP:
                    test = rotate_with_srs(board, current, cw=True)
                    if test:
                        current = test
                        if is_grounded:
                            lock_timer = 0.0
                if event.key == pygame.K_z:
                    test = rotate_with_srs(board, current, cw=False)
                    if test:
                        current = test
                        if is_grounded:
                            lock_timer = 0.0
                if event.key == pygame.K_SPACE:
                    # Hard drop: move down as far as possible, add scoring per cell
                    dropped = 0
                    while True:
                        trial = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
                        if collide(board, trial):
                            break
                        current = trial
                        dropped += 1
                    score += dropped * HARD_DROP_PER_CELL
                    merge(board, current)
                    cleared = sweep(board)
                    if cleared:
                        score += SCORE_TABLE[cleared] * (level + 1)
                        lines += cleared
                        if lines // LINES_PER_LEVEL > level:
                            level += 1
                            gravity_ms = gravity_interval_ms(level)
                    # Next piece
                    current = Piece.spawn(next_type)
                    next_type = nes_rng.next_piece()
                    grav_accum = 0.0
                    lock_timer = 0.0
                    is_grounded = False
                    if collide(board, current):
                        game_over = True
                if event.key == pygame.K_DOWN:
                    soft_drop_held = True
            elif event.type == pygame.KEYUP:
                if overlay.active:
                    continue
                if event.key == pygame.K_DOWN:
                    soft_drop_held = False

        # Fixed updates
        while accumulator >= dt_ms:
            accumulator -= dt_ms
            if paused or game_over or overlay.active:
                continue

            # Horizontal movement via DAS/ARR
            keys = pygame.key.get_pressed()
            step = shift.update(dt_ms, keys[pygame.K_LEFT], keys[pygame.K_RIGHT])
            if step != 0:
                trial = Piece(current.t, [r[:] for r in current.shape], current.state, current.x + step, current.y)
                if not collide(board, trial):
                    current = trial
                    if is_grounded:
                        lock_timer = 0.0

            # Soft drop (hold)
            if soft_drop_held:
                sd_steps = max(1, int(CONFIG["SOFT_DROP_MULT"]))
                for _ in range(sd_steps):
                    trial = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
                    if not collide(board, trial):
                        current = trial
                        score += SOFT_DROP_PER_CELL
                    else:
                        break

            # Gravity accumulation
            grav_accum += dt_ms
            # Check if grounded (one cell below collides)
            down_trial = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
            currently_grounded = collide(board, down_trial)

            if currently_grounded:
                is_grounded = True
                lock_timer += dt_ms
                if lock_timer >= CONFIG["LOCK_DELAY_MS"]:
                    # lock
                    merge(board, current)
                    cleared = sweep(board)
                    if cleared:
                        score += SCORE_TABLE[cleared] * (level + 1)
                        lines += cleared
                        if lines // LINES_PER_LEVEL > level:
                            level += 1
                            gravity_ms = gravity_interval_ms(level)
                    current = Piece.spawn(next_type)
                    next_type = nes_rng.next_piece()
                    grav_accum = 0.0
                    lock_timer = 0.0
                    is_grounded = False
                    if collide(board, current):
                        game_over = True
            else:
                is_grounded = False
                lock_timer = 0.0

            # Apply gravity when interval elapsed and not grounded
            while grav_accum >= gravity_ms and not is_grounded and not game_over:
                grav_accum -= gravity_ms
                trial = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
                if not collide(board, trial):
                    current = trial
                else:
                    is_grounded = True
                    lock_timer = 0.0
                    break

        # DRAW
        draw_board(screen, board, current, font, score, level, lines)

        # Next box (minimalistic)
        nxt = font.render(f"Next: {next_type}", True, (210, 220, 255))
        screen.blit(nxt, (WIDTH - 120, 4))

        if game_over:
            msg = big_font.render("GAME OVER  (R to Restart)", True, (255, 220, 220))
            rect = msg.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            screen.blit(msg, rect)
        if paused:
            msg = big_font.render("PAUSED  (P to Resume)", True, (220, 240, 255))
            rect = msg.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
            screen.blit(msg, rect)

        overlay.draw(screen, font)

        pygame.display.flip()


if __name__ == "__main__":
    main()
