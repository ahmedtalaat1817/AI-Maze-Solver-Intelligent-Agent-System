"""Procedural maze generation with recursive backtracking."""

from __future__ import annotations

from collections import deque
import random


def generate_maze(
    cols: int = 25,
    rows: int = 17,
    num_enemies: int = 2,
    seed: int | None = None,
) -> list[str]:
    """Generate a solvable random maze in the same format as `data.levels`."""
    rng = random.Random(seed)
    cols = cols if cols % 2 == 1 else cols + 1
    rows = rows if rows % 2 == 1 else rows + 1

    grid = [["#"] * cols for _ in range(rows)]
    start_cx = rng.randrange(1, cols - 1, 2)
    start_cy = rng.randrange(1, rows - 1, 2)

    grid[start_cy][start_cx] = "."
    stack = [(start_cx, start_cy)]
    visited = {(start_cx, start_cy)}

    while stack:
        cx, cy = stack[-1]
        neighbours = []
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            nx, ny = cx + dx, cy + dy
            if 1 <= nx < cols - 1 and 1 <= ny < rows - 1 and (nx, ny) not in visited:
                neighbours.append((nx, ny, dx, dy))

        if not neighbours:
            stack.pop()
            continue

        nx, ny, dx, dy = rng.choice(neighbours)
        grid[cy + dy // 2][cx + dx // 2] = "."
        grid[ny][nx] = "."
        visited.add((nx, ny))
        stack.append((nx, ny))

    # Add loops by knocking down some walls
    wall_candidates = []
    for cy in range(1, rows - 1):
        for cx in range(1, cols - 1):
            if grid[cy][cx] == "#":
                if grid[cy][cx-1] == "." and grid[cy][cx+1] == ".":
                    wall_candidates.append((cx, cy))
                elif grid[cy-1][cx] == "." and grid[cy+1][cx] == ".":
                    wall_candidates.append((cx, cy))
                    
    rng.shuffle(wall_candidates)
    num_to_remove = int(len(wall_candidates) * 0.15)  # 15% of internal walls
    for cx, cy in wall_candidates[:num_to_remove]:
        grid[cy][cx] = "."

    open_cells = [
        (cx, cy)
        for cy in range(rows)
        for cx in range(cols)
        if grid[cy][cx] == "."
    ]

    player_candidates = [c for c in open_cells if c[0] < cols // 2 and c[1] < rows // 2]
    player_pos = rng.choice(player_candidates) if player_candidates else open_cells[0]
    grid[player_pos[1]][player_pos[0]] = "P"

    exit_candidates = [c for c in open_cells if c[0] >= cols // 2 and c[1] >= rows // 2]
    if not exit_candidates:
        exit_candidates = open_cells
    exit_pos = _bfs_farthest(grid, player_pos, exit_candidates)
    grid[exit_pos[1]][exit_pos[0]] = "E"

    remaining = [
        c
        for c in open_cells
        if c != player_pos
        and c != exit_pos
        and abs(c[0] - player_pos[0]) + abs(c[1] - player_pos[1]) > 5
        and abs(c[0] - exit_pos[0]) + abs(c[1] - exit_pos[1]) > 3
    ]
    rng.shuffle(remaining)
    for ex, ey in remaining[:num_enemies]:
        grid[ey][ex] = "e"

    _add_terrain_patches(grid, open_cells, rng, ".", "~", cols * rows // 25, 0.60)
    _add_terrain_patches(grid, open_cells, rng, ".", "W", cols * rows // 35, 0.40)
    _add_single_terrain(grid, open_cells, rng, ".", "X", cols * rows // 50)

    return ["".join(row) for row in grid]


def generate_limited_visibility_maze(
    cols: int = 25,
    rows: int = 17,
    num_enemies: int = 2,
    seed: int | None = None,
) -> list[str]:
    """Generate a random maze suitable for fog-of-war runs."""
    return generate_maze(cols, rows, num_enemies, seed)


def _bfs_farthest(grid: list[list[str]], start_cell: tuple[int, int], candidates: list):
    rows = len(grid)
    cols = len(grid[0])
    walls = {
        (cx, cy)
        for cy in range(rows)
        for cx in range(cols)
        if grid[cy][cx] == "#"
    }

    dist = {start_cell: 0}
    queue = deque([start_cell])
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (cx + dx, cy + dy)
            if nb in dist or nb in walls:
                continue
            if 0 <= nb[0] < cols and 0 <= nb[1] < rows:
                dist[nb] = dist[(cx, cy)] + 1
                queue.append(nb)

    reachable = [(dist[c], c) for c in candidates if c in dist]
    reachable.sort(reverse=True)
    return reachable[0][1] if reachable else candidates[0]


def _add_terrain_patches(
    grid: list[list[str]],
    open_cells: list[tuple[int, int]],
    rng: random.Random,
    source: str,
    terrain: str,
    count: int,
    neighbour_probability: float,
):
    open_lookup = set(open_cells)
    for _ in range(count):
        cx, cy = rng.choice(open_cells)
        if grid[cy][cx] != source:
            continue
        grid[cy][cx] = terrain
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (cx + dx, cy + dy)
            if (
                nb in open_lookup
                and grid[nb[1]][nb[0]] == source
                and rng.random() < neighbour_probability
            ):
                grid[nb[1]][nb[0]] = terrain


def _add_single_terrain(
    grid: list[list[str]],
    open_cells: list[tuple[int, int]],
    rng: random.Random,
    source: str,
    terrain: str,
    count: int,
):
    for _ in range(count):
        cx, cy = rng.choice(open_cells)
        if grid[cy][cx] == source:
            grid[cy][cx] = terrain
