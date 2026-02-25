
"""NES-style randomizer module"""
import pygame
from typing import Optional

class NESRandom:
    PIECES = ["I","J","L","O","S","T","Z"]
    def __init__(self, seed: Optional[int], avoid_szo_first: bool=True):
        if seed is None:
            seed = pygame.time.get_ticks() & 0xFFFFFFFF
        self.state = seed & 0xFFFFFFFF
        self.prev_index = None
        self.avoid_szo_first = avoid_szo_first

    def _lcg_next(self):
        self.state = (self.state * 0x41C64E6D + 0x3039) & 0xFFFFFFFF
        return self.state

    def _rand(self):
        return (self._lcg_next() >> 16) & 0x7FFF

    def _rand_choice7(self):
        return self._rand() % 7

    def next_piece(self):
        cand = self._rand_choice7()
        if self.prev_index is None and self.avoid_szo_first:
            bad = {self.PIECES.index("S"), self.PIECES.index("Z"), self.PIECES.index("O")}
            while cand in bad:
                cand = self._rand_choice7()
        if self.prev_index is not None and cand == self.prev_index:
            if (self._rand() & 1) == 1:
                cand = self._rand_choice7()
        self.prev_index = cand
        return self.PIECES[cand]
