
import pygame, sys
from tetris_rng import NESRandom
from tetris_config import CONFIG
from tetris_piece import Piece, try_rotate
from tetris_board import collide, merge, sweep, ghost_y
from tetris_input import ShiftRepeat
from tetris_overlay import Overlay
from tetris_layout import compute_dims, COLS, ROWS
from tetris_render import RenderAssets


def gravity_interval(level):
    base, step = 1000, 60
    mult = max(CONFIG["GRAVITY_MULT"], 0.1)
    return max(60, int((base - level * step) / mult))


def recreate_window(dims, flags=pygame.DOUBLEBUF):
    try:
        return pygame.display.set_mode((dims.total_w, dims.total_h), flags, vsync=1)
    except TypeError:
        return pygame.display.set_mode((dims.total_w, dims.total_h), flags)


def piece_cells(p):
    cells = []
    for r, row in enumerate(p.shape):
        for c, v in enumerate(row):
            if v and p.y + r >= 0:
                cells.append((p.x + c, p.y + r))
    return cells


def main():
    pygame.init()
    pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP])

    dims = compute_dims()
    screen = recreate_window(dims)
    pygame.display.set_caption("Classic Tetris — Dirty Rects + Board Cache")
    font = pygame.font.SysFont(None, 22)
    big_font = pygame.font.SysFont(None, 42)

    render = RenderAssets(dims, font)
    clock = pygame.time.Clock()

    board = [[None] * COLS for _ in range(ROWS)]
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

    # Build initial board surface (empty) and force one-time full redraw
    render.rebuild_board_surface(board)
    need_full_redraw = True

    # Track previous positions for dirty rects
    prev_piece = piece_cells(current)
    prev_ghost = []

    def refresh_assets_if_cell_changed():
        nonlocal dims, screen, render, need_full_redraw
        new_dims = compute_dims()
        if new_dims.cell != dims.cell:
            dims = new_dims
            screen = recreate_window(dims)
            render = RenderAssets(dims, font)
            render.rebuild_board_surface(board)
            # After resizing/rebuilding, redraw full screen once
            need_full_redraw = True

    while True:
        dt = clock.tick_busy_loop(60)
        acc += dt
        dirty = []

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
                        test = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
                        if collide(board, test): break
                        current = test; drop += 1
                    score += drop * 2
                    merge(board, current)
                    c = sweep(board)
                    if c:
                        score += c * (level + 1) * 100; lines += c
                        if lines // 10 > level:
                            level += 1; grav = gravity_interval(level)
                    render.rebuild_board_surface(board)
                    # Redraw whole board region after lock/sweep
                    dirty.append(render.board_rect.copy())
                    current = Piece.spawn(next_type)
                    next_type = rng.next_piece()
                    acc = 0; lock_timer = 0; is_grounded = False
                    if collide(board, current):
                        # Full redraw + simple flip on game over prompt
                        render.blit_bg_region(screen, screen.get_rect())
                        render.blit_board_region(screen, render.board_rect)
                        msg = big_font.render("GAME OVER (R to Restart)", True, (255, 220, 220))
                        rect = msg.get_rect(center=(dims.board_x + dims.board_w // 2, dims.board_y + dims.board_h // 2))
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
            # For overlay we keep simple full redraw
            render.blit_bg_region(screen, screen.get_rect())
            render.blit_board_region(screen, render.board_rect)
            # Current + ghost
            gy = ghost_y(board, current)
            for r, row in enumerate(current.shape):
                for c, v in enumerate(row):
                    if v and gy + r >= 0:
                        screen.blit(render.ghost_surf[current.t], render.cell_rect(current.x + c, gy + r).inflate(-4, -4).topleft)
            for r, row in enumerate(current.shape):
                for c, v in enumerate(row):
                    if v and current.y + r >= 0:
                        screen.blit(render.cell_surf[current.t], render.cell_rect(current.x + c, current.y + r).inflate(-2, -2).topleft)
            render.draw_panel_hud(screen, score, level, lines, next_type)
            overlay.draw(screen, font, dims.total_w, dims.total_h)
            pygame.display.flip()
            # Reset trackers and clear the full redraw request
            prev_piece = piece_cells(current)
            prev_ghost = []
            need_full_redraw = False
            continue

        # Soft drop
        if soft_drop_held:
            sd = max(1, int(CONFIG["SOFT_DROP_MULT"]))
            for _ in range(sd):
                t = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
                if not collide(board, t): current = t; score += 1
                else: break

        # Horizontal
        keys = pygame.key.get_pressed()
        step = shift.update(dt, keys[pygame.K_LEFT], keys[pygame.K_RIGHT])
        if step:
            t = Piece(current.t, [r[:] for r in current.shape], current.state, current.x + step, current.y)
            if not collide(board, t):
                current = t
                down = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
                if collide(board, down): lock_timer = 0

        # Gravity / lock
        down = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
        grounded = collide(board, down)
        if grounded:
            is_grounded = True
            lock_timer += dt
            if lock_timer >= CONFIG["LOCK_DELAY_MS"]:
                merge(board, current)
                c = sweep(board)
                if c:
                    score += c * (level + 1) * 100; lines += c
                    if lines // 10 > level:
                        level += 1; grav = gravity_interval(level)
                render.rebuild_board_surface(board)
                dirty.append(render.board_rect.copy())
                current = Piece.spawn(next_type)
                next_type = rng.next_piece()
                acc = 0; lock_timer = 0; is_grounded = False
        else:
            is_grounded = False
            lock_timer = 0

        while acc >= grav and not is_grounded:
            acc -= grav
            t = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
            if not collide(board, t): current = t
            else:
                is_grounded = True
                lock_timer = 0
                break

        # If we need a full refresh (first frame or after resize), mark full regions
        if need_full_redraw:
            dirty.append(render.board_rect.copy())
            dirty.append(render.panel_rect.copy())

        # Compute new piece & ghost cells and mark dirty areas (prev + new)
        new_piece = piece_cells(current)
        gy = ghost_y(board, current)
        new_ghost = [(current.x + c, gy + r) for r, row in enumerate(current.shape) for c, v in enumerate(row) if v and gy + r >= 0]
        for (cx, cy) in set(prev_piece + prev_ghost + new_piece + new_ghost):
            dirty.append(render.cell_rect(cx, cy))
        prev_piece, prev_ghost = new_piece, new_ghost

        # Expand rects a bit to avoid seam artifacts
        dirty = [r.inflate(2, 2) for r in dirty]
        # Always include HUD if it changed this frame
        hud_dirty = render.draw_panel_hud(screen, score, level, lines, next_type)
        dirty.extend(hud_dirty)

        # Redraw each dirty region: bg + board + moving piece overlays inside it
        for r in dirty:
            render.blit_bg_region(screen, r)
            render.blit_board_region(screen, r)
        # Draw current & ghost (overdraw into dirty areas is ok)
        for r, row in enumerate(current.shape):
            for c, v in enumerate(row):
                if v and gy + r >= 0:
                    screen.blit(render.ghost_surf[current.t], render.cell_rect(current.x + c, gy + r).inflate(-4, -4).topleft)
        for r, row in enumerate(current.shape):
            for c, v in enumerate(row):
                if v and current.y + r >= 0:
                    screen.blit(render.cell_surf[current.t], render.cell_rect(current.x + c, current.y + r).inflate(-2, -2).topleft)

        # Flip only the dirty rectangles
        if dirty:
            pygame.display.update(dirty)
        else:
            pygame.display.update()

        # One-time full redraw handled – go back to normal dirty rects
        need_full_redraw = False


if __name__ == '__main__':
    main()
