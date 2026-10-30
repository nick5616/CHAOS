#!/usr/bin/env python3
"""
Simple launcher for the CHAOS desktop application.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Handle being launched without a console (pythonw.exe, as the Start Menu
# shortcut does). This runs in pipeline worker processes too, since they
# re-import this module.
if sys.stdout is None:
    # print()/tqdm/tracebacks would hit a None stream; send them to a log
    # instead. The main process starts it fresh; everyone then appends, so
    # workers' lines don't overwrite the main process's. (Workers re-import
    # this before multiprocessing marks them as children, hence the env var.)
    log_path = project_root / "chaos.log"
    if not os.environ.get("CHAOS_LOG_OPEN"):
        open(log_path, "w").close()
        os.environ["CHAOS_LOG_OPEN"] = "1"
    sys.stdout = sys.stderr = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")

if os.name == "nt":
    import ctypes
    if not ctypes.windll.kernel32.GetConsoleWindow():
        # With no console to share, every console tool we run (ffmpeg,
        # nvidia-smi, ...) would flash its own window. Hide them all.
        _popen_init = subprocess.Popen.__init__

        def _popen_init_no_window(self, *args, creationflags=0, **kwargs):
            _popen_init(self, *args, creationflags=creationflags | subprocess.CREATE_NO_WINDOW, **kwargs)

        subprocess.Popen.__init__ = _popen_init_no_window

# Import and run the desktop app. --web opens the new React UI instead
# (see REACT_FRONTEND_PLAN.md); the Qt app stays the default until it's done.
if "--web" in sys.argv:
    from desktop_app.web.main import main
else:
    from desktop_app.main_gui import main

if __name__ == "__main__":
    main()
