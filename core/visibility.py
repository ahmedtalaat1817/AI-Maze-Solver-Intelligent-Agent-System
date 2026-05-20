"""Limited-visibility fog-of-war helpers."""

from __future__ import annotations

import pygame

from core.constants import TILE

VISIBILITY_RADIUS = 4
DIM_ALPHA         = 130   # alpha for previously-visited (dimmed) cells


def draw_fog(
    surface: pygame.Surface,
    agent_cell: tuple[int, int],
    visited_cells: set[tuple[int, int]],
    cols: int,
    rows: int,
    cam_x: int,
    cam_y: int,
) -> None:
    """
    Correct fog-of-war using three layers:
      1. Fully opaque dark overlay covering the whole viewport.
      2. Punch semi-transparent holes over visited cells (dim memory).
      3. Punch a smooth radial hole centred on the agent (clear view).

    We use BLEND_RGBA_SUB to *subtract* alpha from the overlay,
    which is the correct way to "erase" parts of an SRCALPHA surface.
    """
    ax, ay = agent_cell
    sw, sh = surface.get_size()

    # --- Layer 1: fully opaque fog covering everything ---
    fog = pygame.Surface((sw, sh), pygame.SRCALPHA)
    fog.fill((10, 12, 16, 255))

    # --- Layer 2: dim (memory) patches for visited cells ---
    # We subtract most of the alpha, leaving a faint shadow.
    dim_erase = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    dim_erase.fill((0, 0, 0, 255 - DIM_ALPHA))   # amount to subtract

    for (cx, cy) in visited_cells:
        rx = cx * TILE - cam_x
        ry = cy * TILE - cam_y
        if -TILE <= rx <= sw and -TILE <= ry <= sh:
            fog.blit(dim_erase, (rx, ry), special_flags=pygame.BLEND_RGBA_SUB)

    # --- Layer 3: radial gradient hole around the player ---
    px = ax * TILE + TILE // 2 - cam_x
    py = ay * TILE + TILE // 2 - cam_y

    radius = VISIBILITY_RADIUS * TILE + TILE // 2
    grad   = _make_erase_gradient(radius)
    fog.blit(grad, (px - radius, py - radius), special_flags=pygame.BLEND_RGBA_SUB)

    surface.blit(fog, (0, 0))


def _make_erase_gradient(radius: int) -> pygame.Surface:
    """
    Returns a radial gradient surface whose alpha channel encodes
    how much fog to *erase* at each pixel.
    Centre → alpha 255 (fully clear).  Edge → alpha 0 (full fog).
    """
    diam = radius * 2
    surf = pygame.Surface((diam, diam), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))   # start transparent

    # Draw concentric circles from outside in, decreasing alpha
    for r in range(radius, 0, -1):
        # Linear falloff: centre fully erases, edge erases nothing
        erase_alpha = int(255 * (1.0 - r / radius) ** 0.6)
        pygame.draw.circle(surf, (0, 0, 0, erase_alpha), (radius, radius), r)

    return surf


def cells_in_view(agent_cell: tuple[int, int], cols: int, rows: int) -> set[tuple[int, int]]:
    """Return all cells currently visible to the agent."""
    ax, ay = agent_cell
    return {
        (cx, cy)
        for cy in range(rows)
        for cx in range(cols)
        if abs(cx - ax) + abs(cy - ay) <= VISIBILITY_RADIUS
    }
