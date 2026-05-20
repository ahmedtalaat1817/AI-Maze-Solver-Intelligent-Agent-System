from __future__ import annotations

import os
from pathlib import Path
import site
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCAL_SITE = ROOT / ".venv" / "Lib" / "site-packages"
if LOCAL_SITE.exists():
    site.addsitedir(str(LOCAL_SITE))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("MPLBACKEND", "Agg")

import pygame  # noqa: E402

from agents.algorithms import SearchAlgorithms  # noqa: E402
from agents.nn_predictor import TrapPredictor  # noqa: E402
from core.level_generator import generate_maze  # noqa: E402
from core.maze import Maze  # noqa: E402
from data.levels import ALGO_NAMES, LEVELS  # noqa: E402
from ui.level_runner import LevelRunner  # noqa: E402
from ui.renderer import _save_chart  # noqa: E402


ALGO_MAP = {
    "BFS": SearchAlgorithms.bfs,
    "DFS": SearchAlgorithms.dfs,
    "UCS": SearchAlgorithms.ucs,
    "Greedy": SearchAlgorithms.greedy,
    "A*": SearchAlgorithms.astar,
}

SIMPLE_GRID = [
    "#####",
    "#P.E#",
    "#####",
]

WEIGHTED_GRID = [
    "#######",
    "#P..XE#",
    "#.###.#",
    "#.....#",
    "#######",
]


def path_cost(maze: Maze, path: list[tuple[int, int]]) -> int:
    return sum(maze.cell_cost(cell) for cell in path[1:])


class MazeSolverProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def assert_valid_path(self, maze: Maze, path: list[tuple[int, int]]):
        self.assertTrue(path, "Expected a non-empty path.")
        self.assertEqual(path[0], maze.start)
        self.assertEqual(path[-1], maze.end)
        for cell in path:
            self.assertTrue(maze.in_bounds(*cell), f"{cell} is out of bounds.")
            self.assertFalse(maze.is_wall(*cell), f"{cell} is a wall.")
        for a, b in zip(path, path[1:]):
            self.assertEqual(abs(a[0] - b[0]) + abs(a[1] - b[1]), 1)

    def test_all_fixed_levels_are_solvable_by_all_algorithms(self):
        for level_index, grid in enumerate(LEVELS, start=1):
            maze = Maze(grid)
            for algo in ALGO_NAMES:
                with self.subTest(level=level_index, algo=algo):
                    path, events = ALGO_MAP[algo](
                        maze.walls_set,
                        maze.cols,
                        maze.rows,
                        maze.start,
                        maze.end,
                        maze.costs,
                    )
                    self.assert_valid_path(maze, path)
                    self.assertTrue(any(event[0] == "explore" for event in events))

    def test_bfs_and_astar_have_same_steps_on_unweighted_level(self):
        unweighted_grid = [
            "#######",
            "#P....#",
            "#.###.#",
            "#....E#",
            "#######",
        ]
        maze = Maze(unweighted_grid)
        bfs_path, _ = SearchAlgorithms.bfs(
            maze.walls_set, maze.cols, maze.rows, maze.start, maze.end, maze.costs
        )
        astar_path, _ = SearchAlgorithms.astar(
            maze.walls_set, maze.cols, maze.rows, maze.start, maze.end, maze.costs
        )
        self.assertEqual(len(bfs_path) - 1, len(astar_path) - 1)

    def test_weighted_search_prefers_lower_cost_route(self):
        maze = Maze(WEIGHTED_GRID)
        bfs_path, _ = SearchAlgorithms.bfs(
            maze.walls_set, maze.cols, maze.rows, maze.start, maze.end, maze.costs
        )
        ucs_path, _ = SearchAlgorithms.ucs(
            maze.walls_set, maze.cols, maze.rows, maze.start, maze.end, maze.costs
        )
        astar_path, _ = SearchAlgorithms.astar(
            maze.walls_set, maze.cols, maze.rows, maze.start, maze.end, maze.costs
        )

        self.assert_valid_path(maze, bfs_path)
        self.assert_valid_path(maze, ucs_path)
        self.assert_valid_path(maze, astar_path)
        self.assertLess(path_cost(maze, ucs_path), path_cost(maze, bfs_path))
        self.assertEqual(path_cost(maze, astar_path), path_cost(maze, ucs_path))

    def test_generated_maze_is_solvable(self):
        maze = Maze(generate_maze(25, 17, num_enemies=2, seed=7))
        path, _ = SearchAlgorithms.astar(
            maze.walls_set, maze.cols, maze.rows, maze.start, maze.end, maze.costs
        )
        self.assert_valid_path(maze, path)

    def test_trap_predictor_returns_bounded_risk(self):
        maze = Maze(WEIGHTED_GRID)
        predictor = TrapPredictor()
        predictor.train(maze)

        self.assertIn((4, 1), maze.risk_cells)
        for cell in [maze.start, (4, 1), maze.end]:
            risk = predictor.predict_risk(cell)
            self.assertGreaterEqual(risk, 0.0)
            self.assertLessEqual(risk, 1.0)
            self.assertRegex(predictor.risk_label(cell), r"^(LOW|MED|HIGH)")

    def test_level_runner_reaches_goal_and_records_metrics(self):
        runner = LevelRunner("BFS", SearchAlgorithms.bfs, SIMPLE_GRID)
        runner.speed_idx = 4
        for _ in range(50):
            runner.update()
            if runner.state in {"SUCCESS", "FAIL"}:
                break

        self.assertEqual(runner.state, "SUCCESS")
        self.assertIsNotNone(runner.result)
        self.assertTrue(runner.result["success"])
        self.assertEqual(runner.result["path_len"], 2)
        self.assertEqual(runner.result["path_cost"], 2)

    def test_chart_generation_writes_timestamped_and_latest_files(self):
        results = [
            {
                "level": "Unit",
                "algo": "BFS",
                "success": True,
                "path_len": 2,
                "path_cost": 2,
                "nodes": 3,
                "time": 0.001,
                "avg_risk": 0.1,
                "deaths": 0,
            },
            {
                "level": "Unit",
                "algo": "DFS",
                "success": False,
                "path_len": 0,
                "path_cost": 0,
                "nodes": 1,
                "time": 0.002,
                "avg_risk": 0.5,
                "deaths": 1,
            },
        ]
        chart_path = _save_chart(results, update_latest=False)
        self.assertTrue(Path(chart_path).exists())


if __name__ == "__main__":
    unittest.main()
