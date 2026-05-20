# Maze Solver Challenge - AI Game Agent

Build a game agent that escapes faster and smarter.

This project is a complete CET251 Artificial Intelligence prototype. A maze
agent starts from a defined point, avoids walls/traps/enemies, reaches the goal,
and compares multiple search strategies with measurable outputs.

## What Is Included

- 4 hand-built maze levels plus procedural random mazes.
- 5 search algorithms: BFS, DFS, Uniform Cost Search, Greedy Best-First, and A*.
- Weighted terrain: sand, water, and hazard tiles affect UCS/A* path cost.
- Moving enemy agents that chase the player.
- Optional limited-visibility fog-of-war mode.
- Neural-network add-on: an MLP trap-risk predictor trained from local maze
  features.
- Exports: CSV metrics, screenshots, comparison charts, PDF report, and PPTX
  presentation.

## Course Requirement Mapping

| Requirement | Project support |
| --- | --- |
| Python main language | Pygame + Python modules |
| At least 3 mazes | 4 fixed levels + random generator |
| At least 3 search algorithms | BFS, DFS, UCS, Greedy, A* |
| AI concepts | Agents/environments, search, heuristics, partial observability |
| Neural-network component | `TrapPredictor` MLP risk prediction |
| Evaluation outputs | Path steps, cost, runtime, nodes expanded, success/failure |

## Setup

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the dashboard:

```bash
python main.py
```

If dependencies were installed into the local `.venv/Lib/site-packages` target,
`main.py` automatically adds that folder to Python's package path.

## Using The Dashboard

1. Choose an algorithm.
2. Choose a fixed or random maze.
3. Toggle fog-of-war if you want limited visibility.
4. Choose the speed.
5. Click `Start` for one run, or `Run All` to compare all algorithms fairly on
   the same selected maze.
6. Click `Generate Comparison` to save and view the latest chart.

## Outputs

- `outputs/csv/stats_*.csv`: recorded run metrics.
- `outputs/screenshots/run_*.png`: captured simulation panel images.
- `outputs/charts/comparison_*.png`: timestamped comparison charts.
- `comparison_chart.png`: latest comparison chart shortcut.
- `outputs/reports/Maze_Solver_Report.pdf`: generated final report.
- `outputs/reports/Maze_Solver_Presentation.pptx`: generated presentation.

Generate the report and presentation after running comparisons:

```bash
python scripts/generate_report.py
```

## Testing

Run the automated smoke tests:

```bash
python -m unittest discover -s tests
```

The tests validate maze parsing, algorithm path correctness, weighted search,
risk prediction bounds, chart generation, and an end-to-end runner success case.
