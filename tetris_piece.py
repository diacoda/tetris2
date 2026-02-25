
"""Piece model, shapes, SRS rotation"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

COLS, ROWS = 10, 20

SHAPES = {
    "I": [[0,0,0,0],[1,1,1,1],[0,0,0,0],[0,0,0,0]],
    "J": [[1,0,0],[1,1,1],[0,0,0]],
    "L": [[0,0,1],[1,1,1],[0,0,0]],
    "O": [[1,1],[1,1]],
    "S": [[0,1,1],[1,1,0],[0,0,0]],
    "T": [[0,1,0],[1,1,1],[0,0,0]],
    "Z": [[1,1,0],[0,1,1],[0,0,0]],
}

def rotate_cw(m): return [list(r) for r in zip(*m[::-1])]
def rotate_ccw(m): return [list(c) for c in zip(*m)][::-1]

JLSTZ_KICKS = {
    (0,1):[(0,0),(-1,0),(-1,1),(0,-2),(-1,-2)],
    (1,0):[(0,0),(1,0),(1,-1),(0,2),(1,2)],
    (1,2):[(0,0),(1,0),(1,-1),(0,2),(1,2)],
    (2,1):[(0,0),(-1,0),(-1,1),(0,-2),(-1,-2)],
    (2,3):[(0,0),(1,0),(1,1),(0,-2),(1,-2)],
    (3,2):[(0,0),(-1,0),(-1,-1),(0,2),(-1,2)],
    (3,0):[(0,0),(-1,0),(-1,-1),(0,2),(-1,2)],
    (0,3):[(0,0),(1,0),(1,1),(0,-2),(1,-2)],
}
I_KICKS = {
    (0,1):[(0,0),(-2,0),(1,0),(-2,-1),(1,2)],
    (1,0):[(0,0),(2,0),(-1,0),(2,1),(-1,-2)],
    (1,2):[(0,0),(-1,0),(2,0),(-1,2),(2,-1)],
    (2,1):[(0,0),(1,0),(-2,0),(1,-2),(-2,1)],
    (2,3):[(0,0),(2,0),(-1,0),(2,1),(-1,-2)],
    (3,2):[(0,0),(-2,0),(1,0),(-2,-1),(1,2)],
    (3,0):[(0,0),(1,0),(-2,0),(1,-2),(-2,1)],
    (0,3):[(0,0),(-1,0),(2,0),(-1,2),(2,-1)],
}

@dataclass
class Piece:
    t: str
    shape: List[List[int]]
    state: int
    x: int
    y: int
    @staticmethod
    def spawn(t: str):
        s = [r[:] for r in SHAPES[t]]
        w = len(s[0])
        empty = 0
        for r in s:
            if all(v==0 for v in r): empty+=1
            else: break
        return Piece(t, s, 0, (COLS-w)//2, -min(empty,2))

# rotation

def try_rotate(board, piece, cw=True):
    old = piece.state
    new = (old + (1 if cw else -1)) % 4
    ns = rotate_cw(piece.shape) if cw else rotate_ccw(piece.shape)
    kicks = (I_KICKS if piece.t=="I" else JLSTZ_KICKS).get((old,new),[(0,0)])
    from tetris_board import collide
    for dx,dy in kicks:
        test = Piece(piece.t, [r[:] for r in ns], new, piece.x+dx, piece.y+dy)
        if not collide(board,test): return test
    return None
