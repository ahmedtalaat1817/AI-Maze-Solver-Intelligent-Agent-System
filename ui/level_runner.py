"""Simulation state machine for one maze run."""

from __future__ import annotations

import math
import time

import pygame

from agents.agent import Agent
from agents.enemy import Enemy
from agents.nn_predictor import TrapPredictor
from core.constants import COLORS, DEFAULT_SPEED, MAX_DEATHS, SPEEDS, TILE
from core.maze import Maze
from core.visibility import cells_in_view, draw_fog


class LevelRunner:
    """Runs the agent through the maze — search computed instantly, agent walks visibly."""

    def __init__(self, algo_name, search_fn, grid, limited_vis=False):
        self.algo_name   = algo_name
        self.search_fn   = search_fn
        self.grid        = grid
        self.limited_vis = limited_vis
        self.speed_idx   = DEFAULT_SPEED
        self.paused      = False

        self.maze      = Maze(self.grid)
        self.predictor = TrapPredictor()
        self.predictor.train(self.maze)

        self.deaths     = 0
        self.total_time = 0.0
        self.total_nodes= 0
        self.path_len   = 0
        self.path_cost  = 0

        self.enemies: list[Enemy] = []
        self.agent: Agent | None  = None
        self.visited_cells: set[tuple[int, int]] = set()
        self.explored_nodes: set[tuple[int, int]] = set()
        self.explore_order: dict[tuple[int, int], int] = {}

        self.state     = "INIT"
        self.error_msg = ""
        self.result: dict | None = None
        self.generated = False
        self.level     = "Custom"
        self._init_attempt()

    # ------------------------------------------------------------------ init
    def _init_attempt(self):
        self.enemies = [Enemy(list(spawn)) for spawn in self.maze.enemy_spawns]
        self.explored_nodes.clear()
        self.explore_order.clear()

        from agents.algorithms import _bench
        path, events, avg_time = _bench(
            self.search_fn,
            self.maze.walls_set, self.maze.cols, self.maze.rows,
            self.maze.start, self.maze.end, self.maze.costs,
        )
        # Use the averaged benchmark time for stable, realistic comparisons
        self.total_time += avg_time

        # Build heatmap from events (instant, not animated)
        counter = 0
        for ev in events:
            if ev[0] == "explore":
                cell = ev[1]
                self.explored_nodes.add(cell)
                if cell not in self.explore_order:
                    self.explore_order[cell] = counter
                    counter += 1
        self.total_nodes += len(self.explored_nodes)

        if not path:
            self.agent     = None
            self.path_len  = 0
            self.path_cost = 0
            self.state     = "FAIL"
            self.error_msg = "No path found."
            self._set_result(success=False, death=False, reason=self.error_msg)
            return

        self.agent = Agent(self.maze.start)
        self.agent.set_path(path)
        self.path_len  = max(0, len(path) - 1)
        self.path_cost = self._path_cost(path)
        self.visited_cells = cells_in_view(
            tuple(self.agent.grid_pos), self.maze.cols, self.maze.rows
        )
        self.state = "PLAYING"

    # ---------------------------------------------------------------- update
    def update(self):
        if self.paused or self.state != "PLAYING":
            return
        if not self.agent:
            self.state     = "FAIL"
            self.error_msg = "Agent not initialized."
            self._set_result(success=False, death=False, reason=self.error_msg)
            return

        steps = SPEEDS[self.speed_idx]
        for _ in range(steps):
            self.agent.advance()
            self.visited_cells.update(
                cells_in_view(tuple(self.agent.grid_pos), self.maze.cols, self.maze.rows)
            )
            for enemy in self.enemies:
                enemy.update(
                    self.maze.walls_set, self.maze.cols, self.maze.rows,
                    tuple(self.agent.grid_pos),
                )
                if enemy.collides_with_agent(self.agent.pixel_pos):
                    self._handle_death()
                    return

        if self.agent.reached_end:
            self.state = "SUCCESS"
            self._set_result(success=True, death=False, reason="Goal reached.")

    # ----------------------------------------------------------- death / result
    def _handle_death(self):
        if not self.agent:
            return
        self.deaths += 1
        self.maze.add_danger(tuple(self.agent.grid_pos))
        self.predictor.train(self.maze)
        if self.deaths >= MAX_DEATHS:
            self.state     = "FAIL"
            self.error_msg = "Ran out of lives."
            self._set_result(success=False, death=True, reason=self.error_msg)
        else:
            self._init_attempt()

    def _set_result(self, success: bool, death: bool, reason: str):
        risk_values = []
        if self.agent and self.agent.path:
            risk_values = [self.predictor.predict_risk(c) for c in self.agent.path]
        avg_risk = sum(risk_values) / len(risk_values) if risk_values else 0.0
        max_risk = max(risk_values) if risk_values else 0.0
        self.result = {
            "algo": self.algo_name, "path_len": self.path_len,
            "path_cost": self.path_cost, "nodes": self.total_nodes,
            "time": self.total_time, "success": success, "death": death,
            "deaths": self.deaths, "limited_vis": self.limited_vis,
            "generated": self.generated, "level": self.level,
            "avg_risk": avg_risk, "max_risk": max_risk, "reason": reason,
        }

    def _path_cost(self, path):
        return sum(self.maze.cell_cost(c) for c in path[1:])

    # ------------------------------------------------------------------- draw
    def draw(self, surface: pygame.Surface):
        surface.fill(COLORS["bg"])
        if self.state not in {"PLAYING", "SUCCESS", "FAIL"}:
            return

        if self.agent:
            ax, ay = self.agent.pixel_pos
        else:
            ax = self.maze.start[0] * TILE + TILE // 2
            ay = self.maze.start[1] * TILE + TILE // 2

        sw, sh = surface.get_size()
        maze_px_w = self.maze.cols * TILE
        maze_px_h = self.maze.rows * TILE
        cam_x = max(0, min(ax - sw // 2, max(0, maze_px_w - sw)))
        cam_y = max(0, min(ay - sh // 2, max(0, maze_px_h - sh)))

        # Draw layers bottom → top
        self.maze.draw(surface, cam_x, cam_y)
        self._draw_heatmap(surface, cam_x, cam_y)
        self._draw_weighted_terrain(surface, cam_x, cam_y)

        if self.agent:
            self._draw_path_tiles(surface, cam_x, cam_y)

        for enemy in self.enemies:
            enemy.draw(surface, cam_x, cam_y)

        if self.agent:
            self._draw_agent(surface, cam_x, cam_y)

        if self.limited_vis and self.agent:
            draw_fog(
                surface, tuple(self.agent.grid_pos), self.visited_cells,
                self.maze.cols, self.maze.rows, cam_x, cam_y,
            )

        self._draw_hud(surface)

    # ---------------------------------------------------------- layer helpers
    def _draw_heatmap(self, surface: pygame.Surface, cam_x: int, cam_y: int):
        """Subtle heatmap overlay of all cells the algorithm explored."""
        max_exp = max(1, len(self.explore_order))
        heatmap = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        for cell, order in self.explore_order.items():
            ratio = order / max_exp
            r = int(12 + 20 * ratio)
            g = int(25 + 80 * ratio)
            b = int(35 + 110 * ratio)
            a = int(90 + 60 * ratio)
            heatmap.fill((r, g, b, a))
            surface.blit(heatmap, (cell[0] * TILE - cam_x, cell[1] * TILE - cam_y))

    def _draw_weighted_terrain(self, surface: pygame.Surface, cam_x: int, cam_y: int):
        overlay = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        for (cx, cy), cost in self.maze.costs.items():
            if cost == 3:
                overlay.fill((*COLORS["sand"], 130))
            elif cost == 5:
                overlay.fill((*COLORS["water"], 130))
            elif cost >= 10:
                overlay.fill((*COLORS["hazard"], 150))
            else:
                overlay.fill((110, 86, 52, 110))
            surface.blit(overlay, (cx * TILE - cam_x, cy * TILE - cam_y))

    def _draw_path_tiles(self, surface: pygame.Surface, cam_x: int, cam_y: int):
        """Vivid path: bright filled tiles with white border so the route is unmistakable."""
        if not self.agent or not self.agent.path:
            return

        agent_idx  = self.agent.step_idx
        agent_cell = tuple(self.agent.grid_pos)

        future_surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        walked_surf = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        walked_surf.fill((80, 90, 100, 90))   # dim grey trail

        for i, cell in enumerate(self.agent.path):
            if self.limited_vis and abs(cell[0]-agent_cell[0])+abs(cell[1]-agent_cell[1]) > 5:
                continue
            rx = cell[0] * TILE - cam_x
            ry = cell[1] * TILE - cam_y

            if i < agent_idx:
                surface.blit(walked_surf, (rx, ry))
            else:
                risk = self.predictor.predict_risk(cell)
                # Bright vivid gradient: green (safe) → orange (medium) → red (danger)
                r = int(40  + 215 * risk)
                g = int(200 - 160 * risk)
                b = int(80  -  60 * risk)
                future_surf.fill((r, g, b, 200))
                surface.blit(future_surf, (rx, ry))
                # White 1-px border so each tile is distinct
                pygame.draw.rect(surface, (255, 255, 255), (rx, ry, TILE, TILE), 1)

    def _draw_agent(self, surface: pygame.Surface, cam_x: int, cam_y: int):
        """Premium glowing ball agent."""
        px, py = self.agent.pixel_pos
        cx = px - cam_x
        cy = py - cam_y

        # Outer glow rings
        for radius, alpha in ((18, 30), (14, 60), (11, 100)):
            glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*COLORS["agent"], alpha), (radius, radius), radius)
            surface.blit(glow, (cx - radius, cy - radius))

        # Main ball
        pygame.draw.circle(surface, COLORS["agent"], (cx, cy), 9)
        # Inner highlight (specular)
        pygame.draw.circle(surface, (200, 240, 255), (cx - 3, cy - 3), 3)
        # White centre dot
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), 2)

    # ------------------------------------------------------------------- HUD
    def _draw_hud(self, surface: pygame.Surface):
        sw, sh = surface.get_size()
        font   = pygame.font.SysFont("segoeui", 17, bold=False)
        hud_h  = 42

        # Background bar
        bar = pygame.Surface((sw, hud_h), pygame.SRCALPHA)
        bar.fill((10, 12, 16, 210))
        surface.blit(bar, (0, sh - hud_h))
        pygame.draw.line(surface, COLORS["accent"], (0, sh - hud_h), (sw, sh - hud_h), 1)

        # Left text — stats
        if self.state == "FAIL":
            left  = f"  FAILED — {self.error_msg}"
            left_color = COLORS["danger"]
        elif self.state == "SUCCESS":
            left = (f"  ✓ SUCCESS  Steps: {self.path_len}  "
                    f"Cost: {self.path_cost}  Nodes: {self.total_nodes}  "
                    f"Time: {self.total_time*1000:.1f} ms")
            left_color = COLORS["exit"]
        else:
            left = (f"  Steps: {self.path_len}  Cost: {self.path_cost}  "
                    f"Nodes: {self.total_nodes}  Time: {self.total_time*1000:.1f} ms")
            left_color = COLORS["text"]

        surface.blit(font.render(left, True, left_color), (0, sh - hud_h + 12))

        # Right text — NN risk
        next_cell = None
        if self.agent and self.agent.step_idx < len(self.agent.path) - 1:
            next_cell = self.agent.path[self.agent.step_idx + 1]
        nn_label   = self.predictor.risk_label(next_cell)
        risk_color = COLORS["danger"] if "HIGH" in nn_label else (
                     COLORS["accent_2"] if "MED" in nn_label else COLORS["exit"])
        nn_surf = font.render(f"NN Risk: {nn_label}  ", True, risk_color)
        surface.blit(nn_surf, (sw - nn_surf.get_width(), sh - hud_h + 12))
