
"""Board helpers: collide, merge, sweep, ghost"""
from typing import Optional, List
from tetris_piece import Piece, COLS, ROWS

Board = List[List[Optional[str]]]

def collide(board: Board, piece: Piece) -> bool:
    for y,row in enumerate(piece.shape):
        for x,v in enumerate(row):
            if not v: continue
            bx,by = piece.x+x, piece.y+y
            if bx<0 or bx>=COLS or by>=ROWS: return True
            if by>=0 and board[by][bx]: return True
    return False

def merge(board:Board, piece:Piece):
    for y,r in enumerate(piece.shape):
        for x,v in enumerate(r):
            if v:
                by = piece.y+y
                if by>=0: board[by][piece.x+x]=piece.t

def sweep(board:Board)->int:
    c=0; y=ROWS-1
    while y>=0:
        if all(board[y][x] for x in range(COLS)):
            del board[y]; board.insert(0,[None]*COLS); c+=1
        else: y-=1
    return c

def ghost_y(board:Board,piece:Piece)->int:
    from copy import deepcopy
    t=deepcopy(piece)
    while True:
        t.y+=1
        if collide(board,t): return t.y-1
