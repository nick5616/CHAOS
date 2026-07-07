#!/usr/bin/env python3
"""
CHAOS Desktop Application - Main GUI Entry Point

This is the main entry point for the CHAOS desktop application.
"""

import sys
import os
from pathlib import Path

# Must be imported before PyQt6/cv2/torch: those claim Windows DLL TLS slots
# on load, and if none are left by the time llvmlite (via numba/whisper)
# tries to init, it fails with WinError 1114.
import numba

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QStatusBar, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont

from desktop_app.gui.main_window import ChaosMainWindow
from desktop_app.gui.utils.theme_manager import ThemeManager


def main():
    """Main entry point for the desktop application."""
    # Redirect OS-level fd 2 to suppress FFmpeg/libavcodec decode noise from
    # cv2.VideoCapture on DVR recordings (writes go straight to fd 2, not sys.stderr).
    # Dup fd 2 first so Python's own exception tracebacks remain visible.
    try:
        import io
        _real_stderr_fd = os.dup(2)
        sys.stderr = io.open(_real_stderr_fd, 'w', errors='replace')
        _nul = open(os.devnull, 'w')
        os.dup2(_nul.fileno(), 2)
    except OSError:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("CHAOS")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("CHAOS Team")

    app.setStyle('Fusion')

    # Apply CS2 theme before any window is created so dialogs inherit it
    theme_manager = ThemeManager()
    theme_manager.apply_theme('cs2')

    window = ChaosMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
