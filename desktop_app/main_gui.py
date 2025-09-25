#!/usr/bin/env python3
"""
CHAOS Desktop Application - Main GUI Entry Point

This is the main entry point for the CHAOS desktop application.
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QStatusBar, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont

from desktop_app.gui.main_window import ChaosMainWindow


def main():
    """Main entry point for the desktop application."""
    # Create the QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("CHAOS")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("CHAOS Team")
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show the main window
    window = ChaosMainWindow()
    window.show()
    
    # Start the event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
