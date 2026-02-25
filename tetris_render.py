
"""
High-performance rendering helpers for the Tetris project.

Optimizations:
- Pre-render block cell Surfaces per color & per size (normal + ghost outline) and blit them.
- Pre-render static background (grid + panel frame) when Dims or cell size changes.
- Cache HUD text surfaces; re-render only when values change.
"""
from __future__ import annotations
import pygame
from dataclasses import dataclass
from typing import Dict, Tuple
from tetris_layout import Dims, COLS, ROWS

# Colors per tetromino type (kept here to share across draw paths)
COLORS: Dict[str, Tuple[int,int,int]] = {
    "I": (102,224,255),
    "J": (106,119,255),
    "L": (255,158,94),
    "O": (255,224,102),
    "S": (94,224,142),
    "T": (200,119,255),
    "Z": (255,102,119),
}

@dataclass
class HudCache:
    score: int = -1
    level: int = -1
    lines: int = -1
    next_type: str = ""
    title: pygame.Surface | None = None
    score_s: pygame.Surface | None = None
    level_s: pygame.Surface | None = None
    lines_s: pygame.Surface | None = None
    next_label: pygame.Surface | None = None
    controls: list | None = None

class RenderAssets:
    def __init__(self, dims: Dims, font: pygame.font.Font):
        self.dims = dims
        self.font = font
        self._make_static()
        self._make_cells()
        self.hud = HudCache()

    def _make_static(self):
        d = self.dims
        # Background surface for full window
        self.bg = pygame.Surface((d.total_w, d.total_h))
        self.bg.fill((10,13,34))
        # Grid over board area
        grid_col = (40,50,90)
        for x in range(COLS+1):
            X = d.board_x + x*d.cell
            pygame.draw.line(self.bg, grid_col, (X, d.board_y), (X, d.board_y + d.board_h))
        for y in range(ROWS+1):
            Y = d.board_y + y*d.cell
            pygame.draw.line(self.bg, grid_col, (d.board_x, Y), (d.board_x + d.board_w, Y))
        # Panel frame
        panel_rect = pygame.Rect(d.panel_x, d.panel_y, d.panel_w, d.board_h)
        pygame.draw.rect(self.bg, (21,25,53), panel_rect)
        pygame.draw.rect(self.bg, (50,60,100), panel_rect, 1)
        # Next preview frame area basics are drawn dynamically (depends on next piece),
        # but the outer frame can be static as well.
        self.pv_cell = max(14, int(d.cell*0.75))
        self.pv_x = d.panel_x + 12
        self.pv_y = d.panel_y + 150
        frame = pygame.Rect(self.pv_x-6, self.pv_y-6, self.pv_cell*4+12, self.pv_cell*4+12)
        pygame.draw.rect(self.bg, (15,18,40), frame)
        pygame.draw.rect(self.bg, (55,65,110), frame, 1)

    def _make_cells(self):
        # Build per-color cell surfaces (solid) and ghost (outline)
        self.cell_surf: Dict[str, pygame.Surface] = {}
        self.ghost_surf: Dict[str, pygame.Surface] = {}
        c = self.dims.cell
        for t, col in COLORS.items():
            s = pygame.Surface((c-2, c-2))
            s.fill(col)
            self.cell_surf[t] = s
            # Ghost as 2px outline
            g = pygame.Surface((c-8, c-8), pygame.SRCALPHA)
            pygame.draw.rect(g, col, (0,0,c-8,c-8), 2)
            self.ghost_surf[t] = g

    def redraw_static(self, screen: pygame.Surface):
        screen.blit(self.bg, (0,0))

    def draw_cell(self, screen: pygame.Surface, t: str, bx: int, by: int):
        # Position inside board area
        rx = self.dims.board_x + bx*self.dims.cell + 1
        ry = self.dims.board_y + by*self.dims.cell + 1
        screen.blit(self.cell_surf[t], (rx, ry))

    def draw_ghost_cell(self, screen: pygame.Surface, t: str, bx: int, by: int):
        rx = self.dims.board_x + bx*self.dims.cell + 4
        ry = self.dims.board_y + by*self.dims.cell + 4
        screen.blit(self.ghost_surf[t], (rx, ry))

    def draw_panel_hud(self, screen: pygame.Surface, score: int, level: int, lines: int, next_type: str):
        d = self.dims
        f = self.font
        # Render only if changed
        if self.hud.title is None:
            self.hud.title = f.render("Classic Tetris", True, (197,202,233))
        if score != self.hud.score:
            self.hud.score = score
            self.hud.score_s = f.render(f"Score: {score}", True, (200,210,240))
        if level != self.hud.level:
            self.hud.level = level
            self.hud.level_s = f.render(f"Level: {level}", True, (200,210,240))
        if lines != self.hud.lines:
            self.hud.lines = lines
            self.hud.lines_s = f.render(f"Lines: {lines}", True, (200,210,240))
        if next_type != self.hud.next_type:
            self.hud.next_type = next_type
            # redraw next box content to a small surface
            from tetris_piece import SHAPES
            s = pygame.Surface((self.pv_cell*4, self.pv_cell*4), pygame.SRCALPHA)
            shape = SHAPES[next_type]
            offx = (4 - len(shape[0])) // 2
            offy = max(0, (4 - len(shape)) // 2)
            for y, row in enumerate(shape):
                for x, v in enumerate(row):
                    if v:
                        rx = (x + offx) * self.pv_cell
                        ry = (y + offy) * self.pv_cell
                        block = pygame.Surface((self.pv_cell-2, self.pv_cell-2))
                        block.fill(COLORS[next_type])
                        s.blit(block, (rx+1, ry+1))
            self.hud.next_label = s

        # Blit cached texts & next box
        screen.blit(self.hud.title, (d.panel_x + 12, d.panel_y + 12))
        if self.hud.score_s: screen.blit(self.hud.score_s, (d.panel_x + 12, d.panel_y + 44))
        if self.hud.level_s: screen.blit(self.hud.level_s, (d.panel_x + 12, d.panel_y + 68))
        if self.hud.lines_s: screen.blit(self.hud.lines_s, (d.panel_x + 12, d.panel_y + 92))
        # Next label text
        nl = f.render("Next:", True, (200,210,240))
        screen.blit(nl, (d.panel_x + 12, d.panel_y + 126))
        if self.hud.next_label:
            screen.blit(self.hud.next_label, (self.pv_x, self.pv_y))

        # Controls legend (static)
        if not self.hud.controls:
            self.hud.controls = [
                f.render("Controls:", True, (200,210,240)),
                f.render("←/→ Move", True, (165,175,215)),
                f.render("↓ Soft drop", True, (165,175,215)),
                f.render("↑ Rot CW", True, (165,175,215)),
                f.render("Z Rot CCW", True, (165,175,215)),
                f.render("Space Hard", True, (165,175,215)),
                f.render("P Pause • R Restart", True, (165,175,215)),
                f.render("F1 Overlay", True, (165,175,215)),
            ]
        y = d.panel_y + 260
        for i, surf in enumerate(self.hud.controls):
            screen.blit(surf, (d.panel_x + 12, y)); y += 20
