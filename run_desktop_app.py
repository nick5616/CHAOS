#!/usr/bin/env python3
"""
Simple launcher for the CHAOS desktop application.
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the desktop app
from desktop_app.main_gui import main

if __name__ == "__main__":
    main()
