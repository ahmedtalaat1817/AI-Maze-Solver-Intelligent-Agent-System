"""Agent entity that follows a computed path."""

from __future__ import annotations

import pygame

from core.constants import COLORS, LOOKAHEAD, RISK_RADIUS, TILE


class Agent:
    """The AI-driven maze character."""

    def __init__(self, start: tuple[int, int]):
        self.grid_pos = list(start)
        self.path: list[tuple[int, int]] = []
        self.step_idx = 0

    def set_path(self, path: list[tuple[int, int]]):
        self.path = path
        self.step_idx = 0
        if path:
            self.grid_pos = list(path[0])

    def advance(self):
        """Move one step forward along the current path."""
        if self.step_idx < len(self.path) - 1:
            self.step_idx += 1
            self.grid_pos = list(self.path[self.step_idx])

    @property
    def pixel_pos(self) -> tuple[int, int]:
        return (
            self.grid_pos[0] * TILE + TILE // 2,
            self.grid_pos[1] * TILE + TILE // 2,
        )

    @property
    def reached_end(self) -> bool:
        return bool(self.path) and self.step_idx == len(self.path) - 1

    def is_next_steps_risky(self, enemies: list) -> bool:
        lookahead = self.path[self.step_idx : self.step_idx + LOOKAHEAD]
        return any(_near_enemy(cell, enemies) for cell in lookahead)

    def draw(self, surface: pygame.Surface, cam_x: int, cam_y: int):
        px, py = self.pixel_pos
        pygame.draw.circle(
            surface, COLORS["agent"], (px - cam_x, py - cam_y), 10
        )
        pygame.draw.circle(
            surface, (235, 250, 255), (px - cam_x, py - cam_y), 4
        )

    def draw_path(self, surface: pygame.Surface, cam_x: int, cam_y: int):
        for cell in self.path:
            pygame.draw.rect(
                surface,
                COLORS["path"],
                pygame.Rect(cell[0] * TILE - cam_x, cell[1] * TILE - cam_y, TILE, TILE),
            )


def _near_enemy(cell: tuple[int, int], enemies: list) -> bool:
    cx, cy = cell
    for enemy in enemies:
        ex = int(enemy.pixel_pos[0] // TILE)
        ey = int(enemy.pixel_pos[1] // TILE)
        if abs(cx - ex) + abs(cy - ey) <= RISK_RADIUS:
            return True
    return False
