"""Rendering helpers for comparison screens and output charts."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

import pygame

from core.constants import COLORS, H, W


def _make_fonts():
    pygame.font.init()
    return (
        pygame.font.SysFont("segoeui", 20),
        pygame.font.SysFont("segoeui", 30, bold=True),
        pygame.font.SysFont("segoeui", 16),
    )


font, font_big, font_small = _make_fonts()


def splash(screen: pygame.Surface, lines: list[tuple[str, tuple]]):
    screen.fill(COLORS["bg"])
    y = H // 2 - len(lines) * 30
    for i, (text, color) in enumerate(lines):
        active_font = font_big if i == 0 else font
        rendered = active_font.render(text, True, color)
        screen.blit(rendered, (W // 2 - rendered.get_width() // 2, y + i * 50))
    pygame.display.flip()
    _wait_keypress()


def _wait_keypress():
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                return


def _deduplicate_results(results: list[dict]) -> list[dict]:
    """Keep only the LAST run for each unique (level, algo) pair.
    This prevents duplicate bars when a user runs the same algorithm twice."""
    seen: dict[tuple, dict] = {}
    for r in results:
        key = (r.get("level", "Custom"), r.get("algo", ""))
        seen[key] = r           # later runs overwrite earlier ones
    return list(seen.values())


def show_comparison(screen: pygame.Surface, results: list[dict]):
    chart_path = _save_chart(results)

    screen.fill(COLORS["bg"])
    pygame.draw.rect(screen, COLORS["panel"], (0, 0, W, H))

    title = font_big.render("Algorithm Comparison", True, COLORS["accent"])
    screen.blit(title, (W // 2 - title.get_width() // 2, 18))

    note = font.render(
        "Search metrics + neural risk estimate — one entry per algorithm",
        True, COLORS["text_dim"],
    )
    screen.blit(note, (W // 2 - note.get_width() // 2, 56))

    headers = ["Algo", "Result", "Steps", "Cost", "Nodes", "Time (ms)", "Risk", "Score"]
    col_x   = [90, 210, 310, 390, 480, 590, 710, 820]
    y = 98
    for i, header in enumerate(headers):
        screen.blit(font_small.render(header, True, COLORS["accent_2"]), (col_x[i], y))
    pygame.draw.line(screen, COLORS["wall"], (80, y + 25), (980, y + 25), 1)
    y += 36

    deduped = _deduplicate_results(results)
    for result in deduped[-12:]:
        ok     = bool(result.get("success"))
        color  = COLORS["exit"] if ok else COLORS["danger"]
        status = "✓ OK" if ok else "✗ FAIL"
        risk   = f"{result.get('avg_risk', 0.0):.0%}"
        score  = _quality_score(result)
        score_str = f"{score:.1f}" if ok else "—"
        values = [
            str(result.get("algo", "")),
            status,
            str(result.get("path_len", 0)),
            str(result.get("path_cost", 0)),
            str(result.get("nodes", 0)),
            f"{result.get('time', 0) * 1000:.2f}",
            risk,
            score_str,
        ]
        row_rect = pygame.Rect(80, y - 6, 900, 28)
        if (y // 28) % 2 == 0:
            pygame.draw.rect(screen, COLORS["ui_bg"], row_rect, border_radius=4)
        for i, value in enumerate(values):
            screen.blit(font_small.render(value, True, color), (col_x[i], y))
        y += 30

    y += 10
    insights = [
        "BFS: Shortest steps, ignores terrain cost — may walk through lava.",
        "DFS: Long winding routes, explores furthest branches first.",
        "UCS: Optimal cost — avoids sand/water/lava intelligently.",
        "Greedy: Rushes toward goal by heuristic only, ignores terrain cost.",
        "A*: Optimal cost + fewer nodes expanded — best overall algorithm.",
        "Score = path quality × speed × exploration efficiency (higher = better).",
    ]
    for line in insights:
        if y > H - 60:
            break
        screen.blit(font_small.render(line, True, COLORS["text"]), (90, y))
        y += 24

    if chart_path:
        chart_msg = f"Chart saved: {chart_path}"
    else:
        chart_msg = "matplotlib not installed — chart not saved."
    rendered = font_small.render(chart_msg, True, COLORS["accent"])
    screen.blit(rendered, (W // 2 - rendered.get_width() // 2, H - 48))

    msg = font.render("Press any key or click to return.", True, COLORS["text_dim"])
    screen.blit(msg, (W // 2 - msg.get_width() // 2, H - 24))

    pygame.display.flip()
    _wait_keypress()
    return chart_path


# --------------------------------------------------------------------------- chart
def _save_chart(results: list[dict], update_latest: bool = True):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        import numpy as np
        from datetime import datetime
    except ImportError:
        print("[Chart] matplotlib not installed; skipping.")
        return None

    # ---- Deduplicate: one bar per algorithm (keep last run) ----
    deduped = _deduplicate_results(results)
    if not deduped:
        return None

    out_dir     = Path("outputs") / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp   = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath    = out_dir / f"comparison_{timestamp}.png"
    latest_path = Path("comparison_chart.png")

    labels  = [r.get("algo", "?") for r in deduped]
    steps   = [r.get("path_len",  0)   for r in deduped]
    costs   = [r.get("path_cost", 0)   for r in deduped]
    nodes   = [r.get("nodes",     0)   for r in deduped]
    times_ms= [r.get("time", 0.0) * 1000 for r in deduped]
    risks   = [r.get("avg_risk",  0.0) * 100 for r in deduped]
    success = [bool(r.get("success")) for r in deduped]
    scores  = [_quality_score(r) if r.get("success") else 0.0 for r in deduped]

    x           = np.arange(len(labels))
    n           = len(labels)
    bar_w       = 0.55

    FAIL_C  = "#d64c58"
    BASE_C  = "#30c4b5"
    BEST_C  = "#f1b84c"
    WORST_C = "#6a7682"

    def rank_colors(vals):
        valid = [(v, i) for i, (v, s) in enumerate(zip(vals, success)) if s and v > 0]
        if not valid:
            return [FAIL_C] * n
        best_v  = min(valid, key=lambda t: t[0])[0]
        worst_v = max(valid, key=lambda t: t[0])[0]
        out = []
        for v, s in zip(vals, success):
            if not s:
                out.append(FAIL_C)
            elif v == best_v:
                out.append(BEST_C)
            elif v == worst_v and worst_v != best_v:
                out.append(WORST_C)
            else:
                out.append(BASE_C)
        return out

    def rank_colors_high(vals):
        """For metrics where HIGHER is better (score)."""
        valid = [(v, i) for i, (v, s) in enumerate(zip(vals, success)) if s and v > 0]
        if not valid:
            return [FAIL_C] * n
        best_v  = max(valid, key=lambda t: t[0])[0]
        worst_v = min(valid, key=lambda t: t[0])[0]
        out = []
        for v, s in zip(vals, success):
            if not s:
                out.append(FAIL_C)
            elif v == best_v:
                out.append(BEST_C)
            elif v == worst_v and worst_v != best_v:
                out.append(WORST_C)
            else:
                out.append(BASE_C)
        return out

    def annotate(ax, values, colors, fmt=".0f", suffix="", offset_ratio=0.04):
        ymax = max(values) if values else 1
        for i, (v, c) in enumerate(zip(values, colors)):
            label = format(v, fmt) + suffix
            if c == BEST_C:
                label += " ★"
            ax.text(
                i, v + ymax * offset_ratio, label,
                ha="center", va="bottom", fontsize=8.5,
                color="#eef1f3",
                fontweight="bold" if c == BEST_C else "normal",
            )

    # ---- figure layout ----
    fig = plt.figure(figsize=(15, 9), facecolor="#101214")
    gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.52, wspace=0.38,
                             left=0.06, right=0.97, top=0.90, bottom=0.10)

    def styled_ax(ax):
        ax.set_facecolor("#16191c")
        ax.tick_params(colors="#d5dadf", labelsize=9)
        ax.grid(axis="y", alpha=0.18, color="#4a5058")
        for spine in ax.spines.values():
            spine.set_edgecolor("#4a5058")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=9, color="#d5dadf")
        return ax

    def bar_chart(ax, values, colors, title, ylabel):
        styled_ax(ax)
        ax.bar(x, values, color=colors, width=bar_w, edgecolor="#303840", linewidth=0.8)
        ax.set_title(title, color="#eef1f3", fontweight="bold", fontsize=10, pad=8)
        ax.set_ylabel(ylabel, color="#a1a9b0", fontsize=9)
        ax.set_ylim(0, max(values) * 1.22 if values and max(values) > 0 else 1)
        return ax

    # Panel 1: Path Steps
    ax1 = bar_chart(
        fig.add_subplot(gs[0, 0]), steps, rank_colors(steps),
        "Path Steps  (lower = better)", "Steps"
    )
    annotate(ax1, steps, rank_colors(steps))

    # Panel 2: Weighted Cost
    ax2 = bar_chart(
        fig.add_subplot(gs[0, 1]), costs, rank_colors(costs),
        "Weighted Path Cost  (lower = better)", "Cost units"
    )
    annotate(ax2, costs, rank_colors(costs))

    # Panel 3: Nodes Expanded
    ax3 = bar_chart(
        fig.add_subplot(gs[0, 2]), nodes, rank_colors(nodes),
        "Nodes Expanded  (lower = better)", "Nodes"
    )
    annotate(ax3, nodes, rank_colors(nodes), fmt=".0f")

    # Panel 4: Runtime
    ax4 = bar_chart(
        fig.add_subplot(gs[1, 0]), times_ms, rank_colors(times_ms),
        "Runtime  (lower = better)", "ms  (avg of 8 runs)"
    )
    annotate(ax4, times_ms, rank_colors(times_ms), fmt=".2f", suffix=" ms")

    # Panel 5: Quality Score (higher = better)
    ax5 = bar_chart(
        fig.add_subplot(gs[1, 1]), scores, rank_colors_high(scores),
        "Quality Score  (higher = better)", "Score"
    )
    annotate(ax5, scores, rank_colors_high(scores), fmt=".1f")
    ax5.set_ylim(0, max(scores) * 1.30 if scores and max(scores) > 0 else 1)

    # Panel 6: Avg Path Risk (line chart, not bars — clearer representation)
    ax6 = fig.add_subplot(gs[1, 2])
    styled_ax(ax6)
    ax6.set_title("Avg Path Risk  (lower = safer)", color="#eef1f3",
                  fontweight="bold", fontsize=10, pad=8)
    ax6.set_ylabel("Risk  (%)", color="#a1a9b0", fontsize=9)
    ax6.set_ylim(0, max(100, max(risks, default=0) * 1.2))

    bar_cols = rank_colors(risks)
    ax6.bar(x, risks, color=bar_cols, width=bar_w, edgecolor="#303840", linewidth=0.8)
    annotate(ax6, risks, bar_cols, fmt=".0f", suffix="%")
    # Note explaining risk source
    ax6.text(0.5, -0.18,
             "Risk = MLP neural predictor avg probability of danger along path.",
             ha="center", transform=ax6.transAxes,
             fontsize=7.5, color="#808890", style="italic")

    # ---- super title + legend note ----
    fig.suptitle(
        "Maze Solver Challenge — Search Algorithm Evaluation",
        color="#30c4b5", fontsize=15, fontweight="bold", y=0.97,
    )
    fig.text(
        0.5, 0.01,
        ("★ Gold = best in metric   |   Gray = worst   |   Red = failed run   |   "
         "Score = 100 × (1/cost_ratio) × (1/nodes_ratio) × (1/time_ratio)   "
         "[ratio vs best]   |   Runtime averaged over 8 runs"),
        color="#808890", fontsize=8, ha="center",
    )

    plt.savefig(filepath, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)

    if update_latest:
        shutil.copyfile(filepath, latest_path)
        print(f"[Chart] Saved to {filepath} and {latest_path}")
    else:
        print(f"[Chart] Saved to {filepath}")
    return str(filepath)


# --------------------------------------------------------------------------- helpers
def _quality_score(result: dict) -> float:
    """
    Composite Quality Score (0–100, higher is better).

    Penalises algorithms proportionally for:
      - Weighted path cost   (reflects terrain avoidance)
      - Nodes expanded       (reflects search efficiency)
      - Runtime              (reflects computational speed)

    Formula:
      score = 100 / (cost_factor × nodes_factor × time_factor)
      where each factor = actual / reference_minimum   (≥ 1.0)

    A perfect algorithm with minimum cost, nodes, and time → score = 100.
    """
    cost  = max(1, result.get("path_cost", 1))
    nodes = max(1, result.get("nodes",     1))
    t_ms  = max(0.001, result.get("time",  0.001) * 1000)

    # Normalise relative to theoretical perfect (each = 1 gives ratio 1.0)
    # We use log-scale so extreme outliers (DFS) don't dominate completely.
    import math
    cost_score  = 1.0 / math.log1p(cost  / 10)
    nodes_score = 1.0 / math.log1p(nodes / 50)
    time_score  = 1.0 / math.log1p(t_ms  / 0.5)

    raw = cost_score * nodes_score * time_score * 5000
    return round(min(raw, 100.0), 2)


def _short_level_label(level: str) -> str:
    if level.startswith("Level "):
        return "L" + level.split(" ", 1)[1]
    for tag in ("25", "35", "55"):
        if tag in level:
            return tag + "×"
    return str(level)[:8]
