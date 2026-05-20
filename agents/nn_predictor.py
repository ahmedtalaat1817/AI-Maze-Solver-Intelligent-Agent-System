"""
Neural-network risk predictor.

TrapPredictor is the required starter ML component for the course project. It
trains a small MLP on features derived from the maze, then returns a danger
probability for any cell in the agent's path.
"""

from __future__ import annotations

import random

from core.constants import RISK_RADIUS, TILE

try:
    from sklearn.neural_network import MLPClassifier

    _SKLEARN = True
except ImportError:
    _SKLEARN = False


class TrapPredictor:
    """Predicts trap probability from local maze features."""

    def __init__(self):
        if _SKLEARN:
            self._model = MLPClassifier(
                hidden_layer_sizes=(16, 8),
                activation="relu",
                solver="lbfgs",
                max_iter=500,
                random_state=42,
            )
        else:
            self._model = _FallbackLogistic()

        self._trained = False
        self._cols = 1
        self._rows = 1
        self._walls: set[tuple[int, int]] = set()
        self._spawns: list[tuple[int, int]] = []
        self._goal = (0, 0)
        self._danger: set[tuple[int, int]] = set()

    def train(self, maze):
        """Build a synthetic training set from the maze and fit the model."""
        self._cols = maze.cols
        self._rows = maze.rows
        self._walls = set(maze.walls_set)
        self._goal = maze.end
        self._danger = set(getattr(maze, "risk_cells", set()))

        for rect in getattr(maze, "danger_tiles", []):
            self._danger.add((rect.x // TILE, rect.y // TILE))

        for cell, cost in getattr(maze, "costs", {}).items():
            if cost >= 10:
                self._danger.add(cell)

        self._spawns = [
            (int(px // TILE), int(py // TILE)) for px, py in maze.enemy_spawns
        ]

        X, y = self._build_dataset()
        if len(set(y)) < 2:
            self._trained = False
            return

        self._model.fit(X, y)
        self._trained = True

    def predict_risk(self, cell: tuple[int, int] | None) -> float:
        """Return a risk probability in [0, 1] for a cell."""
        if cell is None:
            return 0.0

        feats = self._features(cell)
        if not self._trained:
            return min(1.0, feats[3] * 0.55 + feats[5] * 0.30 + feats[6] * 0.45)

        if _SKLEARN:
            prob = self._model.predict_proba([feats])[0][1]
        else:
            prob = self._model.predict_proba(feats)
        return max(0.0, min(1.0, float(prob)))

    def risk_label(self, cell: tuple[int, int] | None) -> str:
        p = self.predict_risk(cell)
        if p >= 0.70:
            return f"HIGH ({p:.0%})"
        if p >= 0.40:
            return f"MED ({p:.0%})"
        return f"LOW ({p:.0%})"

    def risk_color(self, cell: tuple[int, int] | None):
        p = self.predict_risk(cell)
        if p >= 0.70:
            return (255, 86, 86)
        if p >= 0.40:
            return (244, 194, 82)
        return (82, 218, 132)

    def _features(self, cell: tuple[int, int]) -> list[float]:
        cx, cy = cell
        gx, gy = self._goal
        max_dist = max(1, self._cols + self._rows)

        dx_norm = (gx - cx) / max_dist
        dy_norm = (gy - cy) / max_dist
        dist_norm = (abs(gx - cx) + abs(gy - cy)) / max_dist

        neighbours = [
            (cx + dx, cy + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if (dx, dy) != (0, 0)
        ]
        wall_count = sum(
            1
            for nx, ny in neighbours
            if (nx, ny) in self._walls
            or not (0 <= nx < self._cols and 0 <= ny < self._rows)
        )
        wall_density = wall_count / 8.0

        open_cardinals = sum(
            1
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            if (cx + dx, cy + dy) not in self._walls
            and 0 <= cx + dx < self._cols
            and 0 <= cy + dy < self._rows
        )
        dead_end = 1.0 if open_cardinals <= 1 else 0.0

        near_enemy = 0.0
        for ex, ey in self._spawns:
            if abs(cx - ex) + abs(cy - ey) <= RISK_RADIUS:
                near_enemy = 1.0
                break

        is_danger = 1.0 if cell in self._danger else 0.0

        patch_open = sum(
            1
            for dx in range(-2, 3)
            for dy in range(-2, 3)
            if (cx + dx, cy + dy) not in self._walls
            and 0 <= cx + dx < self._cols
            and 0 <= cy + dy < self._rows
        )
        open_space = patch_open / 25.0

        return [
            dx_norm,
            dy_norm,
            dist_norm,
            wall_density,
            dead_end,
            near_enemy,
            is_danger,
            open_space,
        ]

    def _build_dataset(self):
        X, y = [], []
        rng = random.Random(42)

        open_cells = [
            (cx, cy)
            for cy in range(self._rows)
            for cx in range(self._cols)
            if (cx, cy) not in self._walls
        ]

        for cell in open_cells:
            feats = self._features(cell)
            X.append(feats)
            y.append(self._heuristic_label(feats))

        augmented_X, augmented_y = list(X), list(y)
        for feats, label in zip(X, y):
            noisy = [f + rng.gauss(0, 0.025) for f in feats]
            augmented_X.append(noisy)
            augmented_y.append(label)

        return augmented_X, augmented_y

    @staticmethod
    def _heuristic_label(feats: list[float]) -> int:
        _, _, _, wall_density, dead_end, near_enemy, is_danger, open_space = feats
        score = (
            dead_end * 0.35
            + near_enemy * 0.30
            + is_danger * 0.45
            + (0.20 if wall_density > 0.55 and open_space < 0.35 else 0.0)
        )
        return 1 if score >= 0.35 else 0


class _FallbackLogistic:
    """Tiny logistic-regression fallback when scikit-learn is unavailable."""

    def __init__(self):
        self.w = [0.0] * 8
        self.b = 0.0
        self.lr = 0.05

    def fit(self, X, y):
        for _ in range(350):
            for feats, label in zip(X, y):
                p = self._sigmoid(self._dot(feats))
                err = p - label
                self.w = [wi - self.lr * err * xi for wi, xi in zip(self.w, feats)]
                self.b -= self.lr * err

    def predict_proba(self, feats: list[float]) -> float:
        return self._sigmoid(self._dot(feats))

    def _dot(self, feats):
        return self.b + sum(w * x for w, x in zip(self.w, feats))

    @staticmethod
    def _sigmoid(z: float) -> float:
        import math

        try:
            return 1.0 / (1.0 + math.exp(-z))
        except OverflowError:
            return 0.0 if z < 0 else 1.0
