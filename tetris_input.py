
"""DAS/ARR controller"""
from typing import Optional
import pygame
from tetris_config import CONFIG

class ShiftRepeat:
    def __init__(self):
        self.dir=0; self.held_ms=0; self.last=0; self.initial=False
    def update(self, dt, left, right):
        nd=(-1 if left else 0)+(1 if right else 0)
        if nd!=self.dir:
            self.dir=nd; self.held_ms=0; self.last=0; self.initial=False
        if self.dir==0: return 0
        self.held_ms+=dt
        if not self.initial:
            self.initial=True; return self.dir
        if self.held_ms < CONFIG["DAS_MS"]: return 0
        arr=CONFIG["ARR_MS"]
        if arr==0: return self.dir
        self.last+=dt
        if self.last>=arr:
            self.last=0; return self.dir
        return 0
