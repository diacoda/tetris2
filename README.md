
# Classic Tetris — Pygame (Educational Edition)

**Features**
- TRUE NES-style randomizer (LCG + 50% repeat rejection, optional first-piece S/Z/O avoidance)
- Super Rotation System (SRS) with proper JLSTZ and I kick tables
- DAS/ARR horizontal movement, configurable lock delay
- Gravity similar to classic; live tuning via Config Overlay (F1)
- Heavy inline documentation in `tetris.py`

## Quick Start (macOS)

```bash
mkdir -p ~/src/tetris && cd ~/src/tetris
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install pygame
# Save the files tetris.py and README.md here
python tetris.py
```

## Controls

- **←/→** Move (DAS/ARR)
- **↓** Soft drop
- **↑** Rotate clockwise
- **Z** Rotate counter-clockwise
- **Space** Hard drop
- **P** Pause/Resume
- **R** Restart
- **F1** Toggle Config Overlay

### Config Overlay (F1)
- **↑/↓** Select setting
- **←/→** Adjust numeric values
- **Enter** Toggle booleans
- **Esc / F1** Close overlay

Settings you can change live:
- **DAS (ms)**: Delay before auto-shift begins when holding left/right
- **ARR (ms)**: Time between horizontal steps after DAS (0 = instant glide)
- **Lock Delay (ms)**: Time you can move/rotate a grounded piece before it locks
- **Gravity ×**: Multiplier on the base gravity curve (per level)
- **Soft Drop ×**: Multiplier for soft drop speed
- **Avoid S/Z/O First**: Optional NES rule for first piece

## NES Randomizer (Overview)

This build mirrors key NES behavior:
- Repeats are possible but less likely; when the newly rolled piece equals the previous one, a coin flip (50%) triggers a single re-roll.
- Long droughts can happen (e.g., many pieces without an I), unlike 7-bag systems.
- Optional rule: forbid S/Z/O as the first piece (commonly cited for NES starts).

The implementation uses a 32-bit LCG and maps random values to 0..6 (I,J,L,O,S,T,Z). It is educational and reproducible (set `CONFIG["NES_SEED"]`), not a byte-for-byte ROM re-implementation.

## Architecture

- **`NESRandom`**: Pseudo-random generator with NES-like repeat rejection.
- **`Piece`**: Current falling tetromino with rotation state and matrix.
- **Board helpers**: `collide`, `merge`, `sweep`, `ghost_y` are pure functions.
- **SRS rotation**: `rotate_with_srs` uses JLSTZ and I kick tables.
- **Input**: `ShiftRepeat` implements DAS/ARR behavior.
- **Overlay**: Live editing of `CONFIG` values during play.
- **Game loop**: Fixed-timestep update decoupled from rendering for smooth feel.

## Tweaking Feel

Open the overlay (F1) and tune:
- **DAS**: Lower = faster sideways auto-shift starts.
- **ARR**: Lower = faster repeated movement (0 = continuous glide).
- **Lock Delay**: Higher = more finesse on the stack before lock.
- **Gravity ×**: Raise to speed up; lower for practice.
- **Soft Drop ×**: Increase for faster soft drop.

You can also change defaults in `CONFIG` at the top of the file.

## Packaging to a macOS App (Optional)

```bash
pip install pyinstaller
pyinstaller --name "Classic Tetris" --windowed --onefile   --osx-bundle-identifier com.example.tetris   tetris_pygame.py
# App is in dist/Classic Tetris
```

Gatekeeper may warn on first launch (unsigned). Right-click → Open once or sign/notarize.

## Next Ideas

- Hold piece + 5-piece next queue
- Sound effects (rotate/land/line clear)
- Persist high scores and settings (~/.tetris/config.json)
- Theme/skin system and colorblind modes

