"""Main Pygame dashboard — premium layout with algorithm intro cards."""

from __future__ import annotations

import csv
from datetime import datetime
import math
import os
from pathlib import Path
import sys
import time

import pygame

from agents.algorithms import SearchAlgorithms
from core.constants import COLORS, FPS, H, MAX_DEATHS, SPEEDS, W
from core.level_generator import generate_maze
from data.levels import ALGO_LABELS, ALGO_NAMES, LEVELS
from ui.level_runner import LevelRunner
from ui.renderer import show_comparison
from ui.widgets import Button, Checkbox, Dropdown, FONT_LG, FONT_MD, FONT_SM

_ALGO_MAP = {
    "BFS":    SearchAlgorithms.bfs,
    "DFS":    SearchAlgorithms.dfs,
    "UCS":    SearchAlgorithms.ucs,
    "Greedy": SearchAlgorithms.greedy,
    "A*":     SearchAlgorithms.astar,
}

SIDEBAR_W     = 330
_RESULT_PAUSE = 1.5   # seconds between Run-All algorithms
_INTRO_SECS   = 3.0   # seconds to show the algorithm intro card

_ALGO_INFO = {
    "BFS": {
        "full":  "Breadth-First Search",
        "color": (48, 196, 181),
        "lines": [
            "Explores all neighbours level by level.",
            "Guarantees the SHORTEST PATH (fewest steps).",
            "Completely ignores terrain costs — may walk",
            "straight through water or lava.",
            "Watch: the agent takes the most direct route,",
            "but the path cost may be very high.",
        ],
        "badge": "OPTIMAL STEPS",
    },
    "DFS": {
        "full":  "Depth-First Search",
        "color": (241, 184, 76),
        "lines": [
            "Dives deep into one corridor before backtracking.",
            "Does NOT guarantee an optimal path.",
            "Explores the branches furthest from the goal first,",
            "causing long, winding, inefficient routes.",
            "Watch: the agent takes a visibly longer detour",
            "compared to BFS and A*.",
        ],
        "badge": "SUB-OPTIMAL",
    },
    "UCS": {
        "full":  "Uniform Cost Search",
        "color": (100, 160, 240),
        "lines": [
            "Expands nodes in order of cumulative path cost.",
            "Guarantees the CHEAPEST path by terrain cost.",
            "Will actively avoid water (cost 5) and lava (cost 10)",
            "by taking a longer but cheaper route.",
            "Watch: the path may be longer in steps than BFS,",
            "but avoids expensive terrain entirely.",
        ],
        "badge": "OPTIMAL COST",
    },
    "Greedy": {
        "full":  "Greedy Best-First Search",
        "color": (220, 100, 180),
        "lines": [
            "Always moves toward the cell closest to the goal.",
            "Uses heuristic only — ignores actual path cost.",
            "Very fast but NOT optimal: may rush through hazards",
            "because they appear physically closer to the exit.",
            "Watch: the agent may cut through lava zones",
            "that UCS and A* carefully avoid.",
        ],
        "badge": "FAST / RISKY",
    },
    "A*": {
        "full":  "A* Search",
        "color": (100, 210, 130),
        "lines": [
            "Combines actual cost (g) + heuristic estimate (h).",
            "Guarantees the OPTIMAL path in both steps and cost.",
            "Expands far fewer nodes than UCS while staying optimal.",
            "Considered the gold-standard search algorithm.",
            "Watch: fewest nodes expanded, lowest or tied cost,",
            "fastest runtime among optimal algorithms.",
        ],
        "badge": "GOLD STANDARD",
    },
}

_ALGO_COLORS = {k: v["color"] for k, v in _ALGO_INFO.items()}


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Maze Solver Challenge — AI Agent Dashboard")
        self.clock  = pygame.time.Clock()

        self._big_font   = pygame.font.SysFont("segoeui", 48, bold=True)
        self._med_font   = pygame.font.SysFont("segoeui", 22, bold=True)
        self._body_font  = pygame.font.SysFont("segoeui", 18)
        self._small_font = pygame.font.SysFont("segoeui", 15)

        self.maze_options = [f"Level {i+1}" for i in range(len(LEVELS))]
        self.maze_options += ["Random 25x17", "Random 35x25", "Random 55x35"]

        # ---- Layout constants ----
        PAD  = 18          # left/right padding inside sidebar
        IW   = SIDEBAR_W - PAD * 2   # inner widget width
        y    = 68          # running Y cursor

        # Algorithm section
        # label drawn in _draw() at y, dropdown below
        self._lbl_algo_y = y          # store for _draw()
        y += 22
        self.algo_dropdown = Dropdown(PAD, y, IW, 36, ALGO_NAMES)
        y += 44            # dropdown height + gap

        # Maze section
        self._lbl_maze_y = y
        y += 22
        self.maze_dropdown = Dropdown(PAD, y, IW, 36, self.maze_options)
        y += 48

        # Fog checkbox
        self.fog_checkbox = Checkbox(PAD, y, "Limited Visibility (Fog)")
        y += 36

        # Speed button
        self.speed_idx = 0            # DEFAULT x1 — slow enough to watch
        self.speed_btn = Button(PAD, y, IW, 36,
                                f"Speed: x{SPEEDS[self.speed_idx]}", self._cycle_speed)
        y += 46

        # Start / Stop / Run All row
        BW = (IW - 8) // 3
        self.start_btn   = Button(PAD,        y, BW, 42, "Start",   self._start_sim, accent=True)
        self.stop_btn    = Button(PAD+BW+4,   y, BW, 42, "Stop",    self._stop_sim)
        self.run_all_btn = Button(PAD+BW*2+8, y, BW, 42, "Run All", self._run_all,   accent=True)
        y += 52

        # Comparison chart button
        self.chart_btn = Button(PAD, y, IW, 38,
                                "Show Comparison Chart", self._show_comparison, accent=True)
        self._stats_panel_y = y + 50  # stats panel starts below chart btn

        self.widgets = [
            self.chart_btn, self.run_all_btn, self.stop_btn,
            self.start_btn, self.speed_btn, self.fog_checkbox,
            self.maze_dropdown, self.algo_dropdown,
        ]

        self.runner: LevelRunner | None = None
        self.algo_queue: list[str]      = []
        self.results:    list[dict]     = []
        self.status_text = "Ready — pick a maze and algorithm."

        self._batch_grid      = None
        self._batch_level     = None
        self._batch_generated = False
        self._pause_until: float = 0.0
        self._intro_until: float = 0.0
        self._intro_algo:  str   = ""
        self._pending_runner: LevelRunner | None = None   # built during intro

        self.sim_surface = pygame.Surface((W - SIDEBAR_W, H))

        self.output_dirs = {
            "charts":      Path("outputs") / "charts",
            "csv":         Path("outputs") / "csv",
            "screenshots": Path("outputs") / "screenshots",
            "logs":        Path("outputs") / "logs",
        }
        for d in self.output_dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        # Fix 2: one timestamp per session — CSV/log overwrite rather than spam
        self.session_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # ---------------------------------------------------------------- grid
    def _build_grid(self, sel: str):
        if sel.startswith("Level"):
            return LEVELS[int(sel.split()[1])-1], sel, False
        if "25" in sel: return generate_maze(25, 17, num_enemies=1), sel, True
        if "35" in sel: return generate_maze(35, 25, num_enemies=3), sel, True
        if "55" in sel: return generate_maze(55, 35, num_enemies=5), sel, True
        return generate_maze(35, 25, num_enemies=3), sel, True

    # -------------------------------------------------------------- outputs
    def _export(self):
        """Overwrite the same session CSV/log file — no spam."""
        if not self.results: return
        ts     = self.session_ts   # fixed for this app session
        fields = ["level","algo","success","path_len","path_cost",
                  "nodes","time","deaths","avg_risk","max_risk",
                  "limited_vis","generated","reason"]
        with (self.output_dirs["csv"] / f"stats_{ts}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader(); w.writerows(self.results)
        with (self.output_dirs["logs"] / f"log_{ts}.txt").open("w", encoding="utf-8") as fh:
            fh.write(f"Maze Solver Log  {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
            for r in self.results:
                s = "OK" if r.get("success") else "FAIL"
                fh.write(f"[{s}] {r['algo']} on {r['level']}  "
                         f"steps={r['path_len']} cost={r['path_cost']} "
                         f"nodes={r['nodes']} time={r['time']:.4f}s\n")

    def _screenshot(self):
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        pygame.image.save(self.sim_surface, self.output_dirs["screenshots"]/f"run_{ts}.png")

    def _record(self):
        if not self.runner or not self.runner.result: return
        if self.runner.result in self.results:         return
        self.results.append(self.runner.result)
        self._export(); self._screenshot()
        ok = self.runner.result["success"]
        self.status_text = f"{self.runner.result['algo']} — {'Success' if ok else 'Failed'}"

    # ------------------------------------------------------------ controls
    def _cycle_speed(self):
        self.speed_idx = (self.speed_idx + 1) % len(SPEEDS)
        self.speed_btn.text = f"Speed: x{SPEEDS[self.speed_idx]}"
        if self.runner: self.runner.speed_idx = self.speed_idx

    def _make_runner(self, algo, grid, level, generated):
        r = LevelRunner(algo, _ALGO_MAP[algo], grid, self.fog_checkbox.checked)
        r.speed_idx = self.speed_idx
        r.generated = bool(generated)
        r.level     = level
        return r

    def _start_sim(self, algo=None, grid=None, level=None, generated=None):
        if algo is None:
            self.algo_queue.clear()
            self._pause_until = self._intro_until = 0.0
        selected = algo or self.algo_dropdown.selected
        if grid is None:
            grid, level, generated = self._build_grid(self.maze_dropdown.selected)
        if selected in ALGO_NAMES:
            self.algo_dropdown.selected_idx = ALGO_NAMES.index(selected)
        # Build runner immediately (so search is done during intro)
        self._pending_runner = self._make_runner(selected, grid, level, generated)
        self._intro_algo     = selected
        self._intro_until    = time.monotonic() + _INTRO_SECS
        self.status_text     = f"Preparing {selected}…"

    def _run_all(self):
        grid, level, generated = self._build_grid(self.maze_dropdown.selected)
        self._batch_grid = grid; self._batch_level = level; self._batch_generated = generated
        self.algo_queue = list(ALGO_NAMES)
        self.results.clear()
        self._pause_until = self._intro_until = 0.0
        self._start_next()

    def _start_next(self):
        if not self.algo_queue: return
        algo = self.algo_queue.pop(0)
        self._start_sim(algo=algo, grid=self._batch_grid,
                        level=self._batch_level, generated=self._batch_generated)

    def _stop_sim(self):
        self.algo_queue.clear()
        self._pause_until = self._intro_until = 0.0
        self._pending_runner = None
        if self.runner: self._record(); self.runner = None
        self.status_text = "Stopped."

    def _show_comparison(self):
        if self.runner and self.runner.result: self._record(); self.runner = None
        if not self.results:
            self.status_text = "Run at least one simulation first."; return
        chart_path = show_comparison(self.screen, self.results)
        self.status_text = "Chart saved."
        if chart_path and Path(chart_path).exists():
            try: os.startfile(chart_path)
            except AttributeError:
                import subprocess; subprocess.Popen(["xdg-open", chart_path])

    # -------------------------------------------------------------- loop
    def run(self):
        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                for w in reversed(self.widgets):
                    if w.handle_event(event): break

            now = time.monotonic()

            # ---- intro card phase ----
            if self._intro_until and now < self._intro_until:
                self._draw_intro_card()
                continue

            if self._intro_until and now >= self._intro_until:
                self._intro_until = 0.0
                self.runner           = self._pending_runner
                self._pending_runner  = None
                if self.runner:
                    self.status_text = f"Running {self.runner.algo_name} on {self.runner.level}"
                continue

            # ---- pause between algos ----
            if self._pause_until:
                if now < self._pause_until:
                    self._draw(); continue
                # Pause over — clear the finished runner now before launching next
                self.runner        = None
                self._pause_until  = 0.0
                if self.algo_queue:
                    self._start_next()
                elif len(self.results) >= len(ALGO_NAMES):
                    self.status_text = "All done! Opening chart…"
                    self._draw(); self._show_comparison()
                continue

            # ---- normal tick ----
            if self.runner:
                self.runner.update()
                if self.runner.state in {"SUCCESS", "FAIL"}:
                    # Fix 3a: render the FINAL frame to sim_surface BEFORE screenshot
                    self._draw_sim()
                    self._record()
                    # Fix 3b: keep runner alive so the completed path stays visible
                    # during the pause — only clear it when the next algo starts
                    if self.algo_queue:
                        done = len(ALGO_NAMES) - len(self.algo_queue)
                        self.status_text = f"Done {done}/{len(ALGO_NAMES)} — next: {self.algo_queue[0]}"
                        self._pause_until = now + _RESULT_PAUSE
                        # runner stays alive here intentionally
                    else:
                        self.runner = None
                        if len(self.results) >= len(ALGO_NAMES):
                            self.status_text = "All done! Opening chart…"
                            self._draw(); self._show_comparison()

            self._draw()

    # --------------------------------------------------------- intro card
    def _draw_intro_card(self):
        """Full-screen intro card with proper fade-in applied to every surface."""
        info  = _ALGO_INFO.get(self._intro_algo, {})
        color = info.get("color", COLORS["accent"])
        now   = time.monotonic()

        # Fix 4: correct fade-in — 0 at start, 255 by 1/3 of intro time
        elapsed = _INTRO_SECS - (self._intro_until - now)
        alpha   = min(255, int(255 * (elapsed / _INTRO_SECS) * 3))

        # Background
        self.screen.fill((10, 12, 15))

        # Accent top bar (always full opacity — intentional anchor)
        bar_col = (*color, alpha)
        bar_surf = pygame.Surface((W, 6), pygame.SRCALPHA)
        bar_surf.fill(bar_col)
        self.screen.blit(bar_surf, (0, 0))

        # Badge pill
        badge = info.get("badge", "")
        if badge:
            b_surf = self._small_font.render(badge, True, (10, 12, 15))
            b_surf.set_alpha(alpha)
            bw = b_surf.get_width() + 24
            bh = b_surf.get_height() + 10
            bx = W // 2 - bw // 2
            badge_bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
            badge_bg.fill((*color, alpha))
            self.screen.blit(badge_bg, (bx, 60))
            self.screen.blit(b_surf,   (bx + 12, 65))

        # Algorithm name (huge)
        name_surf = self._big_font.render(self._intro_algo, True, color)
        name_surf.set_alpha(alpha)
        self.screen.blit(name_surf, (W//2 - name_surf.get_width()//2, 95))

        # Full algorithm name
        full_surf = self._med_font.render(info.get("full", ""), True, (200, 208, 216))
        full_surf.set_alpha(alpha)
        self.screen.blit(full_surf, (W//2 - full_surf.get_width()//2, 160))

        # Divider line on its own surface so alpha can be applied
        div_surf = pygame.Surface((W // 2, 2), pygame.SRCALPHA)
        div_surf.fill((*color, min(80, alpha)))
        self.screen.blit(div_surf, (W // 4, 196))

        # Description lines
        for i, line in enumerate(info.get("lines", [])):
            s = self._body_font.render(line, True, (188, 196, 204))
            s.set_alpha(alpha)
            self.screen.blit(s, (W//2 - s.get_width()//2, 216 + i * 30))

        # Progress bar + hint
        total   = _INTRO_SECS
        ratio   = min(1.0, elapsed / total)
        bar_w   = 260
        bx      = W // 2 - bar_w // 2
        pygame.draw.rect(self.screen, (30, 36, 44), (bx, H-60, bar_w, 6), border_radius=3)
        fill_surf = pygame.Surface((int(bar_w * ratio) or 1, 6), pygame.SRCALPHA)
        fill_surf.fill((*color, alpha))
        self.screen.blit(fill_surf, (bx, H-60))
        hint = self._small_font.render("Starting automatically…", True, (100, 110, 120))
        hint.set_alpha(alpha)
        self.screen.blit(hint, (W//2 - hint.get_width()//2, H-46))

        pygame.display.flip()

    # ---------------------------------------------------------------- draw
    def _draw(self):
        self.screen.fill((12, 14, 18))

        # Sidebar gradient
        for y in range(H):
            t = y / H
            r = int(18 + 5*t); g = int(21 + 5*t); b = int(26 + 6*t)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (SIDEBAR_W, y))
        pygame.draw.line(self.screen, (45, 52, 62), (SIDEBAR_W, 0), (SIDEBAR_W, H), 1)

        # Title block
        title = self._med_font.render("Maze Solver", True, COLORS["accent"])
        self.screen.blit(title, (SIDEBAR_W//2 - title.get_width()//2, 14))
        sub = self._small_font.render("AI Search  •  Risk Prediction  •  Analytics",
                                      True, (90, 100, 115))
        self.screen.blit(sub, (SIDEBAR_W//2 - sub.get_width()//2, 38))
        pygame.draw.line(self.screen, (40, 48, 58), (12, 60), (SIDEBAR_W-12, 60), 1)

        # Section labels — drawn BEFORE dropdowns so they can't overlap
        lbl_col = (90, 104, 122)
        self.screen.blit(
            self._small_font.render("ALGORITHM", True, lbl_col),
            (18, self._lbl_algo_y + 4)
        )
        self.screen.blit(
            self._small_font.render("MAZE", True, lbl_col),
            (18, self._lbl_maze_y + 4)
        )

        for widget in reversed(self.widgets):
            widget.draw(self.screen)
        if self.algo_dropdown.open: self.algo_dropdown.draw(self.screen)
        if self.maze_dropdown.open: self.maze_dropdown.draw(self.screen)

        self._draw_stats()
        self._draw_progress()
        self._draw_sim()
        pygame.display.flip()

    def _draw_stats(self):
        PX, PY, PW, PH = 12, self._stats_panel_y, SIDEBAR_W-24, 260
        s = pygame.Surface((PW, PH), pygame.SRCALPHA)
        s.fill((12, 15, 19, 220))
        self.screen.blit(s, (PX, PY))
        pygame.draw.rect(self.screen, (42, 50, 62), (PX, PY, PW, PH), 1, border_radius=6)

        self.screen.blit(self._med_font.render("Stats", True, COLORS["accent"]), (PX+10, PY+8))
        pygame.draw.line(self.screen, (42, 50, 62), (PX+10, PY+32), (PX+PW-10, PY+32), 1)

        if self.runner:
            ac = _ALGO_COLORS.get(self.runner.algo_name, COLORS["accent"])
            rows = [
                ("Algorithm", ALGO_LABELS.get(self.runner.algo_name, self.runner.algo_name), ac),
                ("State",     self.runner.state,                          COLORS["text"]),
                ("Steps",     str(self.runner.path_len),                  COLORS["text"]),
                ("Cost",      str(self.runner.path_cost),                 COLORS["text"]),
                ("Nodes",     str(self.runner.total_nodes),               COLORS["text"]),
                ("Time",      f"{self.runner.total_time*1000:.2f} ms",    COLORS["text"]),
                ("Deaths",    f"{self.runner.deaths}/{MAX_DEATHS}",        COLORS["text"]),
            ]
        elif self.results:
            last = self.results[-1]
            ok   = last["success"]
            rows = [
                ("Last",   last["algo"],                              _ALGO_COLORS.get(last["algo"], COLORS["accent"])),
                ("Result", "Success" if ok else "Failed",            COLORS["exit"] if ok else COLORS["danger"]),
                ("Steps",  str(last["path_len"]),                    COLORS["text"]),
                ("Cost",   str(last["path_cost"]),                   COLORS["text"]),
                ("Nodes",  str(last["nodes"]),                       COLORS["text"]),
                ("Time",   f"{last['time']*1000:.2f} ms",            COLORS["text"]),
                ("Saved",  str(len(self.results)) + " runs",         COLORS["text"]),
            ]
        else:
            rows = [
                ("Algorithms", "BFS DFS UCS Greedy A*",    (90, 100, 115)),
                ("Levels",     "4 fixed + 3 random",       (90, 100, 115)),
                ("Terrain",    "Sand Water Lava",           (90, 100, 115)),
                ("AI",         "MLP risk predictor",        (90, 100, 115)),
                ("Outputs",    "CSV log screenshot chart",  (90, 100, 115)),
            ]

        for i, (lbl, val, col) in enumerate(rows[:8]):
            y = PY + 40 + i * 26
            self.screen.blit(self._small_font.render(lbl, True, (80, 92, 108)), (PX+10, y))
            v = self._small_font.render(str(val), True, col)
            self.screen.blit(v, (PX+PW-v.get_width()-10, y))

        st = self._small_font.render(self.status_text[:38], True, (70, 82, 98))
        self.screen.blit(st, (PX+10, PY+PH-20))

    def _draw_progress(self):
        if not self.results and not self.algo_queue and not self.runner:
            return
        PX  = 12
        PY  = self._stats_panel_y + 268   # just below the stats panel
        PW  = SIDEBAR_W - 24
        if PY > H - 40:
            return   # not enough space, skip
        self.screen.blit(self._small_font.render("Run All Progress", True, (70, 82, 98)), (PX, PY))
        by = PY + 18
        pygame.draw.rect(self.screen, (28, 34, 42), (PX, by, PW, 6), border_radius=3)
        done_n = len(self.results) + (1 if self.runner else 0)
        fw = int(PW * min(done_n / len(ALGO_NAMES), 1.0))
        if fw: pygame.draw.rect(self.screen, COLORS["accent"], (PX, by, fw, 6), border_radius=3)

        slot_w = PW // len(ALGO_NAMES)
        for i, name in enumerate(ALGO_NAMES):
            dx   = PX + i * slot_w + slot_w // 2
            col  = _ALGO_COLORS.get(name, COLORS["text_dim"])
            done = any(r["algo"] == name for r in self.results)
            curr = self.runner and self.runner.algo_name == name
            if done:
                pygame.draw.circle(self.screen, col, (dx, by+3), 5)
            elif curr:
                pygame.draw.circle(self.screen, col, (dx, by+3), 5)
                pygame.draw.circle(self.screen, (255,255,255), (dx, by+3), 2)
            else:
                pygame.draw.circle(self.screen, (36, 44, 54), (dx, by+3), 5)
                pygame.draw.circle(self.screen, (55, 65, 78), (dx, by+3), 5, 1)
            lbl = self._small_font.render(name, True, col if (done or curr) else (55, 65, 78))
            self.screen.blit(lbl, (dx - lbl.get_width()//2, by + 10))

    def _draw_sim(self):
        self.sim_surface.fill((12, 14, 18))
        if self.runner:
            self.runner.draw(self.sim_surface)
        else:
            sw, sh = self.sim_surface.get_size()
            r = self._med_font.render("Ready", True, COLORS["accent"])
            s = self._small_font.render(
                "Select an algorithm and maze, then click  Start  or  Run All.",
                True, (70, 82, 98))
            self.sim_surface.blit(r, (sw//2 - r.get_width()//2, sh//2 - 24))
            self.sim_surface.blit(s, (sw//2 - s.get_width()//2, sh//2 + 10))
        self.screen.blit(self.sim_surface, (SIDEBAR_W, 0))


if __name__ == "__main__":
    Game().run()
