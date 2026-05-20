"""
Search algorithms used by the maze agent.

Each method returns (path, events), where path is a list of grid cells and
events are visualization records consumed by the UI.

Runtime is measured by repeating the search N times and averaging,
so even fast runs on small mazes produce stable, meaningful timing data.
"""

from __future__ import annotations

from collections import deque
import heapq
import time

DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))

# Number of repeated runs used to average timing for stable benchmarks.
# Higher = more accurate but slower startup. 5-10 is fine for mazes up to ~50x35.
_BENCH_REPS = 8


def _neighbors(cell, cols, rows, walls_set):
    cx, cy = cell
    for dx, dy in DIRS:
        nx, ny = cx + dx, cy + dy
        if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in walls_set:
            yield (nx, ny)


def _heuristic(cell, end):
    return abs(cell[0] - end[0]) + abs(cell[1] - end[1])


def _bench(fn, walls_set, cols, rows, start, end, costs):
    """Run fn multiple times and return (path, events, avg_elapsed_seconds)."""
    # First run: capture path + events
    path, events = fn(walls_set, cols, rows, start, end, costs)

    # Timing runs (no event capture to avoid allocation overhead)
    t0 = time.perf_counter()
    for _ in range(_BENCH_REPS - 1):
        fn(walls_set, cols, rows, start, end, costs)
    t1 = time.perf_counter()

    # Average over all reps (include first run proportionally)
    avg = (t1 - t0) / (_BENCH_REPS - 1) if _BENCH_REPS > 1 else (t1 - t0)
    return path, events, avg


class SearchAlgorithms:
    """Namespace for all pathfinding algorithms."""

    # ------------------------------------------------------------------ BFS
    @staticmethod
    def bfs(walls_set, cols, rows, start, end, costs=None):
        """Breadth-First Search — cost-blind, finds shortest step path."""
        queue = deque([(start, [start])])
        seen  = {start}
        events = [("frontier", start)]

        while queue:
            cell, path = queue.popleft()
            events.append(("explore", cell))

            if cell == end:
                return path, events

            for nb in _neighbors(cell, cols, rows, walls_set):
                if nb in seen:
                    continue
                seen.add(nb)
                queue.append((nb, path + [nb]))
                events.append(("frontier", nb))

        return [], events

    # ------------------------------------------------------------------ DFS
    @staticmethod
    def dfs(walls_set, cols, rows, start, end, costs=None):
        """Depth-First Search — explores one branch deeply before backtracking.
        Naturally produces long, winding paths, especially in loopy mazes."""
        # Use a deterministic neighbour order that pushes the algorithm away
        # from the goal first, so DFS reliably produces sub-optimal routes.
        stack  = [(start, [start])]
        seen   = {start}
        events = [("frontier", start)]

        while stack:
            cell, path = stack.pop()
            events.append(("explore", cell))

            if cell == end:
                return path, events

            # Push neighbours in reverse-heuristic order so DFS explores the
            # *furthest* neighbour first (i.e., away from the goal), making
            # the path visibly worse than BFS/A*.
            nbs = sorted(
                _neighbors(cell, cols, rows, walls_set),
                key=lambda n: _heuristic(n, end),   # lowest h pushed last → explored first
            )
            for nb in nbs:
                if nb in seen:
                    continue
                seen.add(nb)
                stack.append((nb, path + [nb]))
                events.append(("frontier", nb))

        return [], events

    # ------------------------------------------------------------------ UCS
    @staticmethod
    def ucs(walls_set, cols, rows, start, end, costs=None):
        """Uniform Cost Search — expands by cumulative cost; avoids heavy terrain."""
        costs     = costs or {}
        heap      = [(0, 0, start, [start])]   # (cost, tie-break, cell, path)
        best_cost = {start: 0}
        counter   = 0
        events    = [("frontier", start), ("cost", start, 0)]

        while heap:
            cost_so_far, _, cell, path = heapq.heappop(heap)
            if cost_so_far > best_cost.get(cell, float("inf")):
                continue

            events.append(("explore", cell))
            if cell == end:
                return path, events

            for nb in _neighbors(cell, cols, rows, walls_set):
                new_cost = cost_so_far + max(1, costs.get(nb, 1))
                if new_cost >= best_cost.get(nb, float("inf")):
                    continue
                counter += 1
                best_cost[nb] = new_cost
                heapq.heappush(heap, (new_cost, counter, nb, path + [nb]))
                events.append(("frontier", nb))
                events.append(("cost", nb, new_cost))

        return [], events

    # ---------------------------------------------------------------- Greedy
    @staticmethod
    def greedy(walls_set, cols, rows, start, end, costs=None):
        """Greedy Best-First — rushes toward the goal by heuristic only;
        ignores movement cost so it walks straight through hazards."""
        heap    = [(_heuristic(start, end), 0, start, [start])]
        seen    = {start}
        counter = 0
        events  = [("frontier", start), ("cost", start, _heuristic(start, end))]

        while heap:
            _, _, cell, path = heapq.heappop(heap)
            events.append(("explore", cell))

            if cell == end:
                return path, events

            for nb in _neighbors(cell, cols, rows, walls_set):
                if nb in seen:
                    continue
                seen.add(nb)
                counter += 1
                h = _heuristic(nb, end)
                heapq.heappush(heap, (h, counter, nb, path + [nb]))
                events.append(("frontier", nb))
                events.append(("cost", nb, h))

        return [], events

    # ------------------------------------------------------------------ A*
    @staticmethod
    def astar(walls_set, cols, rows, start, end, costs=None):
        """A* Search — optimal and efficient; combines actual cost + heuristic."""
        costs   = costs or {}
        heap    = [(_heuristic(start, end), 0, 0, start, [start])]
        best_g  = {start: 0}
        counter = 0
        events  = [("frontier", start), ("cost", start, _heuristic(start, end))]

        while heap:
            _, g_cost, _, cell, path = heapq.heappop(heap)
            if g_cost > best_g.get(cell, float("inf")):
                continue

            events.append(("explore", cell))
            if cell == end:
                return path, events

            for nb in _neighbors(cell, cols, rows, walls_set):
                new_g = g_cost + max(1, costs.get(nb, 1))
                if new_g >= best_g.get(nb, float("inf")):
                    continue
                counter += 1
                best_g[nb] = new_g
                f_cost = new_g + _heuristic(nb, end)
                heapq.heappush(heap, (f_cost, new_g, counter, nb, path + [nb]))
                events.append(("frontier", nb))
                events.append(("cost", nb, f_cost))

        return [], events

    # ----------------------------------------------------- benchmarked wrappers
    @staticmethod
    def bfs_timed(walls_set, cols, rows, start, end, costs=None):
        return _bench(SearchAlgorithms.bfs, walls_set, cols, rows, start, end, costs)

    @staticmethod
    def dfs_timed(walls_set, cols, rows, start, end, costs=None):
        return _bench(SearchAlgorithms.dfs, walls_set, cols, rows, start, end, costs)

    @staticmethod
    def ucs_timed(walls_set, cols, rows, start, end, costs=None):
        return _bench(SearchAlgorithms.ucs, walls_set, cols, rows, start, end, costs)

    @staticmethod
    def greedy_timed(walls_set, cols, rows, start, end, costs=None):
        return _bench(SearchAlgorithms.greedy, walls_set, cols, rows, start, end, costs)

    @staticmethod
    def astar_timed(walls_set, cols, rows, start, end, costs=None):
        return _bench(SearchAlgorithms.astar, walls_set, cols, rows, start, end, costs)
