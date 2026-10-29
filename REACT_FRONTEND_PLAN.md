# React Frontend Plan

**Status:** planned, not started (written 2026-10-29).

Replace the PyQt6 desktop GUI with a React UI running in a native window. The pipeline (`chaos_lib/`) and the CLI (`main.py`) don't change. The goal is a much better UX: a fresh design, real animation, and faster iteration than hand-painted Qt widgets allow (today `theme_manager.py` is ~890 lines of Qt stylesheets and `animated_pipeline.py` ~490 lines of custom painting).

## Decisions

| Area | Choice | Why |
|---|---|---|
| Window shell | [pywebview](https://pywebview.flowrl.com/) | Python stays the host process, so the pipeline is called directly and there's no local API server or second process to coordinate. It uses the OS web engine (WebView2, built into Windows 11), so users don't need Node and `setup.bat` stays as it is. Electron would bundle Node + Chromium; Tauri needs a Rust toolchain. Neither buys much when the backend is Python. |
| Frontend | Vite + React + TypeScript | Standard, fast dev server with hot reload. |
| Styling / motion | Tailwind CSS, Motion (framer-motion) | Quick to build a polished UI; Motion covers the animated screens. |
| Shipping the UI | Commit the built bundle (`frontend/dist/`) | Users install from a git clone and shouldn't need Node. Only developers build. Revisit if we add CI or releases. |
| Migration | Build the new app alongside the Qt one | Qt stays the default until the web UI does everything it does, then `desktop_app/gui/` and PyQt6 are deleted. |

## Architecture

```
React UI (frontend/src)
   │  calls:  await window.pywebview.api.method(args)   → JSON
   │  events: window "chaos" CustomEvents ← Python emit()
   ▼
Python host (desktop_app/web/)
   ├─ main.py        create the window, pick dev or built UI
   ├─ api.py         Api class exposed to JS (one method per action)
   ├─ events.py      emit(name, payload) → window.evaluate_js(...), progress throttled to ~10/s
   ├─ media.py       local video/thumbnail server
   └─ pipeline.py    PipelineWorker ported off QThread
   ▼
chaos_lib (unchanged)
```

- **Calls:** each user action is an `Api` method returning plain JSON. Anything slow starts a background thread, returns immediately, and reports through events. pywebview runs API calls on their own threads, so `Api` must be thread-safe.
- **Events:** one helper, `emit(name, payload)`, dispatches a `CustomEvent("chaos", {detail: {name, payload}})` in the page. The frontend has a typed `onChaos(name, handler)` hook.
- **Typed bridge:** `frontend/src/bridge/` holds TypeScript types for every API method and event, plus a mock implementation so the UI can be developed in a normal browser with no Python.
- **Media server:** `<video>` and `<img>` need URLs, so `media.py` runs a small HTTP server on `127.0.0.1` (random port, per-session token, HTTP Range support for seeking). It serves only the captures folder, the output folder and the thumbnail cache.
- **Native dialogs:** folder and file pickers via pywebview's `create_file_dialog`.
- **Dev mode:** `CHAOS_DEV=1` points the window at the Vite dev server for hot reload; otherwise it loads `frontend/dist/index.html`.
- **Multiprocessing:** the analysis pool uses `spawn`, which re-imports the main module in every worker. Window startup must stay under `if __name__ == "__main__"`, and the no-console handling in `run_desktop_app.py` (log to `chaos.log`, hidden subprocess windows) must apply to the new entry point too.

### Porting the pipeline worker

`desktop_app/workers/pipeline_worker.py` is a `QThread` that talks to the UI through signals. Port it to a plain `threading.Thread` that takes an `emit` callback, with each signal becoming an event:

| Qt signal | Event |
|---|---|
| `progress_updated(int, str)` | `run:progress` |
| `stage_started(str)` / `stage_completed(str, bool)` | `run:stage` |
| `log_message(str)` / `error_occurred(str)` | `run:log` (with level) |
| `job_started` / `job_updated` / `job_finished` | `run:job` |
| `pipeline_count(int, int)` | `run:count` |
| `finished(bool)` | `run:finished` |

Keep the pipeline logic itself untouched; only the transport changes.

## What to port

| Current code | New screen | Notes |
|---|---|---|
| *(new)* | **Model download gate** | See Phase 2. Uses `chaos_lib/models.py`. |
| `wizard/first_run_wizard.py`, `tabs/setup_tab.py` (`SetupWorker`) | First-run wizard | Dependency/GPU check, CUDA-install offer, captures folder, player names, killfeed ROI. |
| `views/home_view.py` (`ClipSourceView`) | Clip source | Folder picker, video grid with thumbnails and durations, sped-up hover preview, include/exclude per video, disk-space check, player names. |
| `views/home_view.py` (`RunView`), `widgets/animated_pipeline.py`, `widgets/log_viewer.py` | Run | Live per-video job board, worker count stepper, gaming mode, CUDA install dialog, log with level filter and export. |
| `views/results_view.py`, `widgets/clip_preview.py` | Results | Ranked clips with tag chips, detail panel, player with event-timeline markers (lane layout, hover tooltips, playback overlays). |
| `views/watch_view.py` | Watch | Sequence player, drag-to-reorder timeline, export stitched video with ffmpeg concat. |
| `views/settings_modal.py`, `tabs/advanced_tab.py` | Settings | General settings, plus advanced detection tuning (HSV, shape, timing, scoring-weight sliders). |
| `widgets/video_roi_configurator.py` | ROI editor | Drag the killfeed region on a video frame. |
| `main_window.py` | App shell | Nav, background GPU/CUDA check on startup. |

Probably dead, so check before porting: `tabs/config_tab.py`, `tabs/pipeline_tab.py`, `tabs/results_tab.py`, `widgets/progress_tracker.py`. Only `advanced_tab` and `setup_tab` are imported from outside `tabs/`.

## Phases

Each phase leaves the web UI usable for its slice, with the Qt app still available.

### Phase 0: Spike (do first, it can change the plan)

Open a pywebview window showing a minimal Vite build, and play a **real clip from the output folder** through the media server.

- Clips are stream-copied (`-c copy` in `chaos_lib/clipper.py`), so they keep the recorder's video codec and **all audio tracks**. Check that the codec plays in WebView2 (H.264 and AV1 do; HEVC needs hardware support and an extension) and whether the voice-chat track is audible. Browsers play only the first audio track.
- If either fails, generate cached preview proxies with ffmpeg (H.264, audio tracks mixed into one) and play those. The originals stay untouched.

Exit: a clip with game and voice audio plays and seeks smoothly in the window.

### Phase 1: Foundation

- `frontend/` Vite app, `desktop_app/web/` host, bridge types and mock, events, media server, dev mode.
- Design tokens (colors, type, spacing) and the app shell with nav.
- Launch with `run_desktop_app.py --web` (Qt stays the default).
- Add `pywebview` to `requirements.txt` and to the import check in `scripts/install.py`.

### Phase 2: Model download screen

The user asked for this specifically: the app should never download models when you press Run.

- On launch, `models.missing(config)`. If anything is missing, show a full-screen animated download screen and don't enter the app until it finishes. If nothing is missing, go straight in with no flash.
- Shows each model (label, size, state: waiting / downloading / verifying / done), an overall progress bar, speed and time remaining, then a short "ready" transition into the app.
- Errors: a clear message (offline vs. checksum failure) and a Retry button. Partial downloads are already discarded by `models.fetch`.
- Same gate before Run, and after saving settings that change which models are needed (Whisper size, subtitles model, voice-chat moments).
- Backend: `Api.models_status()` and `Api.download_models()`, emitting `models:progress`, `models:done`, `models:error`.

### Phase 3: Clip source + Run

Thumbnails and hover previews are decoded with OpenCV into Qt images today. In the web UI, ffmpeg writes JPEG thumbnails and short preview files into a cache that the media server serves.

### Phase 4: Results + clip player

### Phase 5: Watch + export

### Phase 6: Settings, first-run wizard, ROI editor

### Phase 7: Cutover

Make the web UI the default, delete `desktop_app/gui/` and the Qt workers, drop PyQt6 from `requirements.txt` (unless Linux needs it as the pywebview backend), update the README and the setup shortcut.

## Design direction

The current look is not liked, so the new UI is a redesign, not a port of the old layout. Before Phase 3, make a short design pass (palette, type, layout of the main screens) and get sign-off. The Phase 2 download screen sets the tone, so it's the first chance to test a direction.

## Risks

- **Video playback:** codecs and multiple audio tracks (see Phase 0).
- **WebView2 runtime:** built into Windows 11, may be missing on older Windows 10. Setup should detect that and point to Microsoft's installer.
- **Linux:** pywebview needs GTK (`python3-gi`) or QtWebEngine. macOS works out of the box.
- **Stale committed bundle:** easy to change `frontend/src` and forget to rebuild `frontend/dist`. Add a check (e.g. a test comparing a source hash recorded at build time) if it bites.
- **Hover-preview performance:** the Qt app decodes frames live. Pre-generating previews costs disk and time on first scan, so it needs a cache with eviction.

## Open questions

1. Design direction: CS2-flavoured dark UI, or something else? Any reference apps you like?
2. OK to commit `frontend/dist/`, or would you rather setup install Node and build it?
