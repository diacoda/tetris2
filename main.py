
import pygame, sys
from tetris_rng import NESRandom
from tetris_config import CONFIG
from tetris_piece import Piece, try_rotate
from tetris_board import collide, merge, sweep, ghost_y
from tetris_input import ShiftRepeat
from tetris_overlay import Overlay
from tetris_layout import compute_dims, COLS, ROWS
from tetris_render import RenderAssets

# Gravity interval with multiplier

def gravity_interval(level):
    base, step = 1000, 60
    mult = max(CONFIG["GRAVITY_MULT"], 0.1)
    return max(60, int((base - level * step) / mult))


def recreate_window(dims, flags=pygame.DOUBLEBUF):
    try:
        return pygame.display.set_mode((dims.total_w, dims.total_h), flags, vsync=1)
    except TypeError:
        return pygame.display.set_mode((dims.total_w, dims.total_h), flags)


def main():
    pygame.init()

    # Allow only necessary events (cuts overhead)
    pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP])

    dims = compute_dims()
    screen = recreate_window(dims)
    pygame.display.set_caption("Classic Tetris — Optimized Rendering")

    font = pygame.font.SysFont(None, 22)
    big_font = pygame.font.SysFont(None, 42)

    # Pre-rendered assets (cells, bg, HUD caches)
    render = RenderAssets(dims, font)

    clock = pygame.time.Clock()

    board = [[None]*COLS for _ in range(ROWS)]
    rng = NESRandom(CONFIG["NES_SEED"], CONFIG["NES_FIRST_PIECE_AVOID_SZO"])
    current = Piece.spawn(rng.next_piece())
    next_type = rng.next_piece()

    score = lines = level = 0
    grav = gravity_interval(level)
    acc = 0
    lock_timer = 0
    is_grounded = False

    shift = ShiftRepeat()
    overlay = Overlay()
    soft_drop_held = False

    def refresh_assets_if_cell_changed():
        nonlocal dims, screen, render
        new_dims = compute_dims()
        if new_dims.cell != dims.cell:
            dims = new_dims
            screen = recreate_window(dims)
            render = RenderAssets(dims, font)

    while True:
        dt = clock.tick_busy_loop(60)  # more consistent timing on macOS
        acc += dt

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F1:
                    overlay.toggle(); continue
                if overlay.active:
                    overlay.handle(e); continue
                if e.key == pygame.K_UP:
                    t = try_rotate(board, current, True)
                    if t: current = t; lock_timer = 0
                if e.key == pygame.K_z:
                    t = try_rotate(board, current, False)
                    if t: current = t; lock_timer = 0
                if e.key == pygame.K_SPACE:
                    drop = 0
                    while True:
                        test = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y+1)
                        if collide(board, test): break
                        current = test; drop += 1
                    score += drop*2
                    merge(board, current)
                    c = sweep(board)
                    if c:
                        score += c*(level+1)*100; lines += c
                        if lines // 10 > level:
                            level += 1; grav = gravity_interval(level)
                    current = Piece.spawn(next_type)
                    next_type = rng.next_piece()
                    acc = 0; lock_timer = 0; is_grounded = False
                    if collide(board, current):
                        # Game over screen
                        render.redraw_static(screen)
                        # Draw board state
                        for y in range(ROWS):
                            for x in range(COLS):
                                tcell = board[y][x]
                                if tcell: render.draw_cell(screen, tcell, x, y)
                        render.draw_panel_hud(screen, score, level, lines, next_type)
                        msg = big_font.render("GAME OVER (R to Restart)", True, (255,220,220))
                        rect = msg.get_rect(center=(dims.board_x + dims.board_w//2, dims.board_y + dims.board_h//2))
                        screen.blit(msg, rect)
                        pygame.display.flip()
                        waiting = True
                        while waiting:
                            for ev in pygame.event.get():
                                if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
                                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_r: return main()
                if e.key == pygame.K_DOWN:
                    soft_drop_held = True
            if e.type == pygame.KEYUP:
                if overlay.active: continue
                if e.key == pygame.K_DOWN:
                    soft_drop_held = False

        refresh_assets_if_cell_changed()

        if overlay.active:
            render.redraw_static(screen)
            # Draw board (use blits)
            for y in range(ROWS):
                for x in range(COLS):
                    tcell = board[y][x]
                    if tcell: render.draw_cell(screen, tcell, x, y)
            # Current + Ghost
            gy = ghost_y(board, current)
            for r, row in enumerate(current.shape):
                for c, v in enumerate(row):
                    if v and gy + r >= 0: render.draw_ghost_cell(screen, current.t, current.x + c, gy + r)
            for r, row in enumerate(current.shape):
                for c, v in enumerate(row):
                    if v and current.y + r >= 0: render.draw_cell(screen, current.t, current.x + c, current.y + r)
            render.draw_panel_hud(screen, score, level, lines, next_type)
            overlay.draw(screen, font, dims.total_w, dims.total_h)
            pygame.display.flip()
            continue

        # Horizontal movement
        keys = pygame.key.get_pressed()
        step = shift.update(dt, keys[pygame.K_LEFT], keys[pygame.K_RIGHT])
        if step:
            t = Piece(current.t, [r[:] for r in current.shape], current.state, current.x + step, current.y)
            if not collide(board, t):
                current = t
                down = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y+1)
                if collide(board, down): lock_timer = 0

        # Soft drop
        if soft_drop_held:
            sd = max(1, int(CONFIG["SOFT_DROP_MULT"]))
            for _ in range(sd):
                t = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y+1)
                if not collide(board, t): current = t; score += 1
                else: break

        # Gravity and lock delay
        down = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y+1)
        grounded = collide(board, down)
        if grounded:
            is_grounded = True
            lock_timer += dt
            if lock_timer >= CONFIG["LOCK_DELAY_MS"]:
                merge(board, current)
                c = sweep(board)
                if c:
                    score += c*(level+1)*100; lines += c
                    if lines // 10 > level:
                        level += 1; grav = gravity_interval(level)
                current = Piece.spawn(next_type)
                next_type = rng.next_piece()
                acc = 0; lock_timer = 0; is_grounded = False
        else:
            is_grounded = False
            lock_timer = 0

        while acc >= grav and not is_grounded:
            acc -= grav
            t = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y+1)
            if not collide(board, t): current = t
            else:
                is_grounded = True
                lock_timer = 0
                break

        # DRAW (blit-only path)
        render.redraw_static(screen)
        for y in range(ROWS):
            for x in range(COLS):
                tcell = board[y][x]
                if tcell: render.draw_cell(screen, tcell, x, y)
        gy = ghost_y(board, current)
        for r, row in enumerate(current.shape):
            for c, v in enumerate(row):
                if v and gy + r >= 0: render.draw_ghost_cell(screen, current.t, current.x + c, gy + r)
        for r, row in enumerate(current.shape):
            for c, v in enumerate(row):
                if v and current.y + r >= 0: render.draw_cell(screen, current.t, current.x + c, current.y + r)

        render.draw_panel_hud(screen, score, level, lines, next_type)
        pygame.display.flip()


if __name__ == '__main__':
    main()
