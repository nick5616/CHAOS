"""
Entry point for the web UI: a pywebview window showing the React app in
frontend/. Started with `python run_desktop_app.py --web`.

Set CHAOS_DEV=1 to load the Vite dev server (`npm run dev` in frontend/)
for hot reload instead of the built frontend/dist. CHAOS_CONFIG points at a
different config.yaml, which is handy for testing.
"""

import os
import sys
from pathlib import Path

# Before cv2/torch, see the WinError 1114 note in desktop_app/main_gui.py.
import numba  # noqa: F401

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DIST = PROJECT_ROOT / "frontend" / "dist"
DEV_URL = "http://localhost:5199"

sys.path.insert(0, str(PROJECT_ROOT))


def main():
    import webview
    from desktop_app.gui.utils.config_manager import ConfigManager
    from desktop_app.web.api import Api
    from desktop_app.web.events import Events
    from desktop_app.web.media import MediaServer

    dev = os.environ.get("CHAOS_DEV") == "1"
    if not dev and not (DIST / "index.html").exists():
        sys.exit("The web UI isn't built. Run `npm install` and `npm run build` in frontend/.")

    config_manager = ConfigManager(os.environ.get("CHAOS_CONFIG"))

    def media_roots():
        config = config_manager.load_config()
        data = config_manager.resolve_path(config.get("data_folder", ""))
        return [config.get("captures_folder"),
                config_manager.resolve_path(config.get("final_clips_folder", "")),
                os.path.join(data, "thumbnails") if data else None]

    events = Events()
    media = MediaServer(media_roots).start()
    api = Api(config_manager, events, media, dev=dev)
    api._start()

    window = webview.create_window(
        "CHAOS", DEV_URL if dev else str(DIST / "index.html"), js_api=api,
        width=1280, height=820, min_size=(960, 640), background_color="#0a0a0c")
    events.attach(window)
    api._window = window
    webview.start(debug=dev, http_server=not dev)
    media.stop()


if __name__ == "__main__":
    main()
