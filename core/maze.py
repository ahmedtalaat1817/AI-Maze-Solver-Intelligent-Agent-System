"""
Maze geometry parsing.

The Maze class converts a list of text rows into a rectangular grid and exposes
the walls, start, goal, enemy spawns, weighted terrain, and risky cells used by
the search and learning layers.
"""

from __future__ import annotations

import pygame

from core.constants import COLORS, TILE


TERRAIN_COSTS = {
    "~": 3,   # sand
    "W": 5,   # water / swamp
    "X": 10,  # dangerous but still traversable unless re-planning blocks it
}


class Maze:
    """Holds the static geometry of one level."""

    def __init__(self, grid: list[str]):
        if not grid:
            raise ValueError("Maze grid cannot be empty.")

        self.rows = len(grid)
        self.cols = max(len(row) for row in grid)
        self.grid = [row.ljust(self.cols, "#") for row in grid]

        self.walls_set: set[tuple[int, int]] = set()
        self.wall_rects: list[pygame.Rect] = []
        self.danger_tiles: list[pygame.Rect] = []
        self.risk_cells: set[tuple[int, int]] = set()
        self.start: tuple[int, int] | None = None
        self.end: tuple[int, int] | None = None
        self.exit_rect: pygame.Rect | None = None
        self.enemy_spawns: list[list[int]] = []
        self.costs: dict[tuple[int, int], int] = {}

        self._parse()

        if self.start is None:
            raise ValueError("Maze grid must contain a player start cell 'P'.")
        if self.end is None:
            raise ValueError("Maze grid must contain a goal cell 'E'.")

    def _parse(self):
        for ry, row in enumerate(self.grid):
            for cx, ch in enumerate(row):
                rect = pygame.Rect(cx * TILE, ry * TILE, TILE, TILE)
                cell = (cx, ry)

                if ch == "#":
                    self.wall_rects.append(rect)
                    self.walls_set.add(cell)
                elif ch == "P":
                    self.start = cell
                elif ch == "E":
                    self.end = cell
                    self.exit_rect = rect
                elif ch == "e":
                    self.enemy_spawns.append(
                        [cx * TILE + TILE // 2, ry * TILE + TILE // 2]
                    )
                elif ch in TERRAIN_COSTS:
                    self.costs[cell] = TERRAIN_COSTS[ch]
                    if ch == "X":
                        self.risk_cells.add(cell)
                        self.danger_tiles.append(rect)

    def add_danger(self, cell: tuple[int, int]):
        """Mark a cell as blocked after the agent dies there."""
        if cell in self.walls_set or cell == self.start or cell == self.end:
            return

        self.walls_set.add(cell)
        self.risk_cells.add(cell)
        rect = pygame.Rect(cell[0] * TILE, cell[1] * TILE, TILE, TILE)
        self.danger_tiles.append(rect)

    def is_wall(self, cx: int, cy: int) -> bool:
        return (cx, cy) in self.walls_set

    def in_bounds(self, cx: int, cy: int) -> bool:
        return 0 <= cx < self.cols and 0 <= cy < self.rows

    def cell_cost(self, cell: tuple[int, int]) -> int:
        return self.costs.get(cell, 1)

    def draw(self, surface: pygame.Surface, cam_x: int, cam_y: int):
        for rect in self.wall_rects:
            pygame.draw.rect(surface, COLORS["wall"], rect.move(-cam_x, -cam_y))

        for rect in self.danger_tiles:
            pygame.draw.rect(surface, COLORS["danger"], rect.move(-cam_x, -cam_y))

        if self.exit_rect:
            pygame.draw.rect(
                surface, COLORS["exit"], self.exit_rect.move(-cam_x, -cam_y)
            )
