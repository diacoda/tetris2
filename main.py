import pygame, sys
from tetris_rng import NESRandom
from tetris_config import CONFIG
from tetris_piece import Piece, try_rotate
from tetris_board import collide, merge, sweep, ghost_y
from tetris_input import ShiftRepeat
from tetris_overlay import Overlay
from tetris_layout import compute_dims

COLS, ROWS = 10, 20

# Gravity interval with multiplier
def gravity_interval(level):
    base, step = 1000, 60
    mult = max(CONFIG["GRAVITY_MULT"], 0.1)
    return max(60, int((base - level * step) / mult))

def draw_panel(screen, font, dims, score, level, lines, next_type):
    # Panel background
    rect = pygame.Rect(dims.panel_x, dims.panel_y, dims.panel_w, dims.board_h)
    pygame.draw.rect(screen, (21,25,53), rect)
    pygame.draw.rect(screen, (50,60,100), rect, 1)

    def text_at(msg, y, color=(200,210,240)):
        screen.blit(font.render(msg, True, color), (dims.panel_x + 12, dims.panel_y + y))

    # Title & Stats
    text_at("Classic Tetris", 12, (197, 202, 233))
    text_at(f"Score: {score}", 44)
    text_at(f"Level: {level}", 68)
    text_at(f"Lines: {lines}", 92)

    # Next preview (4x4)
    text_at("Next:", 126)
    from tetris_piece import SHAPES
    pv_cell = max(14, int(dims.cell * 0.75))
    pv_x = dims.panel_x + 12
    pv_y = dims.panel_y + 150
    frame = pygame.Rect(pv_x-6, pv_y-6, pv_cell*4+12, pv_cell*4+12)
    pygame.draw.rect(screen, (15,18,40), frame)
    pygame.draw.rect(screen, (55,65,110), frame, 1)

    shape = SHAPES[next_type]
    offx = (4 - len(shape[0])) // 2
    offy = max(0, (4 - len(shape)) // 2)

    # Block colors
    COLORS = {
        "I": (102,224,255), "J": (106,119,255), "L": (255,158,94),
        "O": (255,224,102), "S": (94,224,142), "T": (200,119,255),
        "Z": (255,102,119),
    }

    for y, row in enumerate(shape):
        for x, v in enumerate(row):
            if v:
                rx = pv_x + (x + offx) * pv_cell
                ry = pv_y + (y + offy) * pv_cell
                pygame.draw.rect(screen, COLORS[next_type], (rx+1, ry+1, pv_cell-2, pv_cell-2))

    # Help
    text_at("Controls:", 260)
    help_lines = ["←/→ Move", "↓ Soft drop", "↑ Rot CW", "Z Rot CCW",
                  "Space Hard", "P Pause • R Restart", "F1 Overlay"]
    y = 282
    for hl in help_lines:
        text_at(hl, y, (165, 175, 215)); y += 20

def draw_board(screen, dims, board, current):
    # Background
    screen.fill((10,13,34))

    # Grid (subtle to keep it sharp)
    grid_col = (40,50,90)
    for x in range(COLS + 1):
        X = dims.board_x + x * dims.cell
        pygame.draw.line(screen, grid_col, (X, dims.board_y), (X, dims.board_y + dims.board_h))
    for y in range(ROWS + 1):
        Y = dims.board_y + y * dims.cell
        pygame.draw.line(screen, grid_col, (dims.board_x, Y), (dims.board_x + dims.board_w, Y))

    # Block colors
    COLORS = {
        "I": (102,224,255), "J": (106,119,255), "L": (255,158,94),
        "O": (255,224,102), "S": (94,224,142), "T": (200,119,255),
        "Z": (255,102,119),
    }

    # Placed blocks
    for y in range(ROWS):
        for x in range(COLS):
            t = board[y][x]
            if t:
                rx = dims.board_x + x * dims.cell + 1
                ry = dims.board_y + y * dims.cell + 1
                pygame.draw.rect(screen, COLORS[t], (rx, ry, dims.cell - 2, dims.cell - 2))

    # Ghost piece
    gy = ghost_y(board, current)
    for r, row in enumerate(current.shape):
        for c, v in enumerate(row):
            if v and gy + r >= 0:
                rx = dims.board_x + (current.x + c) * dims.cell + 4
                ry = dims.board_y + (gy + r) * dims.cell + 4
                pygame.draw.rect(screen, COLORS[current.t], (rx, ry, dims.cell - 8, dims.cell - 8), 2)

    # Current piece
    for r, row in enumerate(current.shape):
        for c, v in enumerate(row):
            if v and current.y + r >= 0:
                rx = dims.board_x + (current.x + c) * dims.cell + 1
                ry = dims.board_y + (current.y + r) * dims.cell + 1
                pygame.draw.rect(screen, COLORS[current.t], (rx, ry, dims.cell - 2, dims.cell - 2))

def recreate_window(dims, flags=0):
    # Exact pixel size — no blurry scaling
    try:
        return pygame.display.set_mode((dims.total_w, dims.total_h), flags, vsync=1)
    except TypeError:  # pygame < 2.5 without vsync kw
        return pygame.display.set_mode((dims.total_w, dims.total_h), flags)

def main():
    pygame.init()

    # Initial layout & window
    dims = compute_dims()
    screen = recreate_window(dims)
    pygame.display.set_caption("Classic Tetris — Modular (Sidebar + Configurable Cell Size)")
    font = pygame.font.SysFont(None, 22)
    big_font = pygame.font.SysFont(None, 42)
    clock = pygame.time.Clock()

    # State
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

    def refresh_layout_if_cell_changed():
        nonlocal dims, screen
        # Recompute dims and recreate the window if cell size changed in overlay
        new_dims = compute_dims()
        if new_dims.cell != dims.cell:
            dims = new_dims
            screen = recreate_window(dims)

    while True:
        dt = clock.tick(60)
        acc += dt

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F1:
                    overlay.toggle()
                    continue
                if overlay.active:
                    overlay.handle(e)
                    continue
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
                    score += drop * 2  # hard-drop score
                    merge(board, current)
                    cleared = sweep(board)
                    if cleared:
                        score += cleared * (level + 1) * 100
                        lines += cleared
                        if lines // 10 > level:
                            level += 1; grav = gravity_interval(level)
                    current = Piece.spawn(next_type)
                    next_type = rng.next_piece()
                    acc = 0; lock_timer = 0; is_grounded = False
                    if collide(board, current):  # game over
                        # Draw once more with message
                        draw_board(screen, dims, board, current)
                        draw_panel(screen, font, dims, score, level, lines, next_type)
                        msg = big_font.render("GAME OVER (R to Restart)", True, (255,220,220))
                        rect = msg.get_rect(center=(dims.board_x + dims.board_w//2, dims.board_y + dims.board_h//2))
                        screen.blit(msg, rect); pygame.display.flip()
                        # Simple wait loop
                        waiting = True
                        while waiting:
                            for ev in pygame.event.get():
                                if ev.type == pygame.QUIT: pygame.quit(); sys.exit()
                                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_r:
                                    return main()
                if e.key == pygame.K_DOWN:
                    soft_drop_held = True
            if e.type == pygame.KEYUP:
                if overlay.active:
                    continue
                if e.key == pygame.K_DOWN:
                    soft_drop_held = False

        # Live-layout refresh if CELL_SIZE changed in overlay
        refresh_layout_if_cell_changed()

        if overlay.active:
            # Draw underneath the overlay so you can see context
            draw_board(screen, dims, board, current)
            draw_panel(screen, font, dims, score, level, lines, next_type)
            overlay.draw(screen, font, dims.total_w, dims.total_h)
            pygame.display.flip()
            continue

        # Horizontal movement (DAS/ARR)
        keys = pygame.key.get_pressed()
        step = shift.update(dt, keys[pygame.K_LEFT], keys[pygame.K_RIGHT])
        if step:
            t = Piece(current.t, [r[:] for r in current.shape], current.state, current.x + step, current.y)
            if not collide(board, t):
                current = t
                # reset lock timer if on ground
                down = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
                if collide(board, down): lock_timer = 0

        # Soft drop hold
        if soft_drop_held:
            sd_steps = max(1, int(CONFIG["SOFT_DROP_MULT"]))
            for _ in range(sd_steps):
                t = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
                if not collide(board, t):
                    current = t
                    score += 1  # soft-drop score
                else:
                    break

        # Gravity
        # Check grounded status
        down = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
        grounded_now = collide(board, down)

        if grounded_now:
            is_grounded = True
            lock_timer += dt
            if lock_timer >= CONFIG["LOCK_DELAY_MS"]:
                merge(board, current)
                cleared = sweep(board)
                if cleared:
                    score += cleared * (level + 1) * 100
                    lines += cleared
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
            t = Piece(current.t, [r[:] for r in current.shape], current.state, current.x, current.y + 1)
            if not collide(board, t):
                current = t
            else:
                is_grounded = True
                lock_timer = 0
                break

        # Draw
        draw_board(screen, dims, board, current)
        draw_panel(screen, font, dims, score, level, lines, next_type)
        pygame.display.flip()

if __name__ == '__main__':
    main()