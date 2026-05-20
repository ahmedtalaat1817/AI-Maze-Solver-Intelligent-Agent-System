"""
Shared constants and color palette for the Maze Solver Challenge.
"""

# Window and tile sizes
W, H, TILE = 1200, 720, 32
MAZE_W, MAZE_H = 800, 544
FPS = 35

# Balanced dark UI palette with distinct semantic colors.
COLORS = {
    "bg": (16, 18, 20),
    "panel": (28, 31, 35),
    "wall": (74, 80, 88),
    "danger": (214, 76, 88),
    "path": (74, 184, 118),
    "agent": (42, 190, 225),
    "enemy": (232, 84, 104),
    "exit": (78, 203, 126),
    "text": (238, 241, 243),
    "text_dim": (161, 169, 176),
    "ui_bg": (22, 25, 28),
    "visited": (43, 54, 61),
    "frontier": (88, 126, 184),
    "btn_bg": (43, 49, 55),
    "btn_hvr": (57, 67, 75),
    "accent": (48, 196, 181),
    "accent_2": (241, 184, 76),
    "sand": (185, 151, 83),
    "water": (62, 124, 190),
    "hazard": (198, 70, 72),
}

# Game rules
MAX_DEATHS = 5
ENEMY_SPEED = 1.5
ENEMY_REFRESH = 40
RISK_RADIUS = 3
LOOKAHEAD = 3

# Speed control: path steps processed per frame.
SPEEDS = [1, 2, 4, 8, 16]
DEFAULT_SPEED = 0
