"""Moving enemy that periodically replans toward the agent."""

from __future__ import annotations

import math

import pygame

from agents.algorithms import SearchAlgorithms
from core.constants import COLORS, ENEMY_REFRESH, ENEMY_SPEED, TILE


class Enemy:
    """A chasing enemy with smooth pixel movement."""

    def __init__(self, pixel_centre: list[float]):
        self.pos = list(pixel_centre)
        self._path: list[tuple[int, int]] = []
        self._timer = 0

    def update(self, walls_set: set, cols: int, rows: int, agent_grid_pos: tuple):
        self._timer += 1
        if self._timer > ENEMY_REFRESH:
            self._timer = 0
            my_grid = (int(self.pos[0] // TILE), int(self.pos[1] // TILE))
            self._path, _ = SearchAlgorithms.bfs(
                walls_set, cols, rows, my_grid, agent_grid_pos
            )

        if not self._path:
            return

        tx = self._path[0][0] * TILE + TILE // 2
        ty = self._path[0][1] * TILE + TILE // 2
        dist = math.hypot(tx - self.pos[0], ty - self.pos[1])
        if dist < 5:
            self._path.pop(0)
            return

        self.pos[0] += (tx - self.pos[0]) / dist * ENEMY_SPEED
        self.pos[1] += (ty - self.pos[1]) / dist * ENEMY_SPEED

    @property
    def pixel_pos(self) -> tuple[float, float]:
        return (self.pos[0], self.pos[1])

    def collides_with_agent(self, agent_pixel_pos: tuple, threshold: int = 20) -> bool:
        return (
            math.hypot(agent_pixel_pos[0] - self.pos[0], agent_pixel_pos[1] - self.pos[1])
            < threshold
        )

    def draw(self, surface: pygame.Surface, cam_x: int, cam_y: int):
        center = (int(self.pos[0] - cam_x), int(self.pos[1] - cam_y))
        pygame.draw.circle(surface, COLORS["enemy"], center, 10)
        pygame.draw.circle(surface, (255, 210, 220), center, 4)
