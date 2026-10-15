#!/usr/bin/env python3
"""
=============================================================================
Advanced Queueing System Simulator - Main Entry Point
Designed for Master's Degree Courses in Network Design and Telecommunications.
=============================================================================
"""

import sys
from cli import parse_arguments, run_headless_cli


def main() -> None:
    args = parse_arguments()

    if args.cli:
        run_headless_cli(args)
        return

    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFont
        from gui.main_window import QueueSimulatorApp
    except ImportError:
        print("Notice: PyQt6 or Matplotlib not detected. Falling back to CLI mode.")
        run_headless_cli(args)
        return

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 9))
    window = QueueSimulatorApp(cli_args=args)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()