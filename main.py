"""Entry point for the Maze Solver Challenge dashboard."""

from __future__ import annotations

from pathlib import Path
import site


LOCAL_SITE = Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"
if LOCAL_SITE.exists():
    site.addsitedir(str(LOCAL_SITE))

from ui.game import Game  # noqa: E402


if __name__ == "__main__":
    Game().run()
