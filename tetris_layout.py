# tetris_layout.py
from dataclasses import dataclass
from tetris_config import CONFIG

COLS, ROWS = 10, 20

@dataclass
class Dims:
    cell: int
    margin: int
    panel_w: int
    board_w: int
    board_h: int
    total_w: int
    total_h: int
    board_x: int
    board_y: int
    panel_x: int
    panel_y: int

def compute_dims() -> Dims:
    cell = int(CONFIG["CELL_SIZE"])
    margin = 16
    panel_w = 220

    board_w = COLS * cell
    board_h = ROWS * cell

    total_w = margin + board_w + margin + panel_w + margin
    total_h = margin + board_h + margin

    board_x = margin
    board_y = margin
    panel_x = board_x + board_w + margin
    panel_y = margin

    return Dims(
        cell=cell, margin=margin, panel_w=panel_w,
        board_w=board_w, board_h=board_h,
        total_w=total_w, total_h=total_h,
        board_x=board_x, board_y=board_y,
        panel_x=panel_x, panel_y=panel_y
    )
