"""Standalone Dashboard visual-review launcher."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# When this file is started directly, Python adds only the tools directory
# to sys.path. Add the project root so imports such as "from app..." work.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)

from PySide6.QtWidgets import QApplication

from app.ui.pages.dashboard_page import DashboardPage
from app.ui.theme.colors import ThemeName


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Corteris Dashboard with synthetic demo data."
    )
    parser.add_argument(
        "--theme",
        choices=("dark", "light"),
        default="dark",
    )
    parser.add_argument("--width", type=int, default=1500)
    parser.add_argument("--height", type=int, default=920)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QApplication.instance() or QApplication(sys.argv)

    window = DashboardPage(
        theme=ThemeName(args.theme),
        demo_mode=True,
    )
    window.setWindowTitle(
        "Corteris Tender AI — Dashboard Visual Review"
    )
    window.resize(max(760, args.width), max(640, args.height))
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
