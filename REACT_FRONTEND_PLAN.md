# React Frontend Plan

**Status:** Phases 0 to 6 done (2026-10-30). Design direction signed off: CS2-style menus with the hand-drawn logo. Next is Phase 7, the cutover. Try it with `python run_desktop_app.py --web`.

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

**Result (passed, no proxies needed).** WebView2 156 played H.264 clips at 2560x1440 and HEVC captures at 5120x1440, with audio, and seeked in 12 to 64 ms. Notes:

- Clips don't keep all audio tracks. `-c copy` without `-map` keeps one video and one audio stream, the first one. That's fine: in two-track ShadowPlay captures, track 0 holds game audio, including in-game voice chat. Track 1 is the local mic, which was silent in the captures checked. Browsers play only the first track anyway.
- HEVC worked because the RTX 3070 decodes it in hardware. A machine without HEVC decode can't play those captures, so keep the proxy idea for that case (check with `MediaSource.isTypeSupported`).
- pywebview exposes every public attribute of the `js_api` object to JavaScript and walks into it, so `Api` keeps its state in underscore attributes.

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

Done. Two pieces are deferred until their screens exist: the gate before Run (Phase 3) and after settings changes (Phase 6). `models.fetch` gained a `verifying` callback for the "Checking" state. The model check takes about 5 s on a cold start because looking up the model list imports torch. The host starts it before the window opens, and the page shows a wordmark-only boot screen after a 350 ms delay, so a warm start goes straight in.

### Developing the UI

- `npm run dev:mock` in `frontend/` runs the UI in a browser against the fake host in `src/bridge/mock.ts`. URL params pick scenarios: `?models=missing|error`, `?gpu=nocuda|cpu`.
- `CHAOS_DEV=1 python run_desktop_app.py --web` loads the dev server in the real window with the real host.
- After changing `frontend/src`, run `npm run build` and commit `frontend/dist`.
- Design tokens live in `frontend/src/index.css` (`@theme`). Orange is the accent, for actions and anything in progress. Blue is the secondary, for done, success and healthy states. Both are the logo's own colours (`src/assets/logo.png`, hand-drawn, keep its handmade look). The logo blue is too dark for small text, so blue text uses `secondary-hi`, a lighter tint of the same hue.

### Phase 3: Clip source + Run

Done.

- **Pipeline transport.** `desktop_app/workers/pipeline.py` holds the pipeline as `PipelineRunner`, which has no Qt. Its channels have the old signal names, and the pipeline code is byte-for-byte the old worker's. `pipeline_worker.PipelineWorker` is now a thin QThread wrapper, and the web host's `RunController` (`desktop_app/web/run.py`) drives the same runner. A `clips_found` channel was added for per-video clip counts.
- **Thumbnails.** ffmpeg cuts a JPEG and reports the duration in the same call, cached in `<data_folder>/thumbnails` and keyed by path, size and mtime. Cards ask for them as they scroll into view, newest requests first. They take about 140 ms each with 4 workers.
- **Hover preview.** No preview files: the card plays the original file and seeks 1 s every 100 ms (10x), which keeps the decode load steady at any resolution. The magnifier draws a 4x crop of the full-resolution frame into a canvas.
- **Run.** The download screen appears before a run if a model is missing (`start_run` refuses with `models_missing`). The low-disk warning, worker stepper, gaming mode, CUDA install dialog and log with errors filter and export are ported. A running pipeline shows in the top bar from any screen.
- **Dropped:** the Qt "add individual files" mode (the folder grid covers it) and Pause, which never paused anything in the Qt app because the runner doesn't check the flag.
- **Not yet:** the clip selection isn't remembered between launches.

### Phase 4: Results + clip player

Done, as the Highlights screen. `desktop_app/web/highlights.py` reads `ordered_highlights.json`, finds each clip by its recorded `clip_filename`, and makes event times relative to the clip file, which starts at `max(0, clip_start)`. The screen has a ranked list with Kills, Funny and Banter filters, and thumbnails from the same cache as the Clips screen.

The player has a scrubber with event markers stacked in up to three lanes, with hover tooltips; clicking a marker jumps just before it. During playback a CS2-style killfeed row appears under the scoreboard for each kill, and voice lines show as subtitles. The event list jumps the player too.

Keys: Space plays and pauses, the left and right arrows seek 5 s, and the up and down arrows move through the list. "Show in folder" opens Explorer on the clip. Gotcha found on the way: in Edge 156 `scrollIntoView()` returns a Promise, so a React effect must never return its result.

### Phase 5: Watch + export

Done. The Watch screen plays the last run's highlights back to back. The sequence strip uses Motion's `Reorder`: drag to reorder, tap to play, × to leave a clip out, and "Put back" to restore them. The order survives switching tabs (`state/watch.ts`) and resets when a new run replaces the highlights.

Export (`desktop_app/web/export.py`) probes each clip with ffprobe:
- **Same format (codec, size, frame rate, audio):** the clips are joined with ffmpeg's concat demuxer and `-c copy`. Three 2560x1440 clips took 2.9 s.
- **Mixed formats:** a stream copy would make a broken file, so it re-encodes. Clips are scaled and padded to the most common size at 60 fps, with h264_nvenc when available (libx264 otherwise). A 2560 H.264 clip plus a 5120 HEVC clip took 10.9 s.

Progress comes from ffmpeg's `-progress` output. The Qt export always stream-copied, so mixed libraries came out broken there.

### Phase 6: Settings, first-run wizard, ROI editor

Done.

- **Settings** has General, Detection and Appearance tabs, and changes save themselves (debounced for sliders). `desktop_app/web/settings.py` whitelists every key with its type and range, so the page can't write anything else and keys it doesn't show survive. Changing voice-chat options rechecks which models a run needs, and offers the download.
- **Only live settings are shown.** `chat_roi`, the T/CT name colours and the enemy-rage-chat weight are left out because nothing in the pipeline reads them (there's no chat detection). The headshot and through-smoke bonuses, which the Qt app never showed, are in.
- **Setup wizard** (shown while `gui.setup_complete` is false):
  1. System check: Python, FFmpeg, and the GPU with the CUDA install offer. `setup.bat` already installs dependencies, so this only checks.
  2. Recordings folder, with a count of what it found.
  3. Name (optional).
  4. Killfeed region, picked from the newest recording's resolution.
- **Region editor**: draw, drag or resize the box on a full-resolution frame from your recordings, scrub to a moment with kills, flip between recordings, and check a zoomed view of what's inside the box. Presets are scaled to the frame. Saving stores the frame's resolution as `killfeed_roi_resolution`, which the analyzer uses to scale the region to other resolutions.
- **Gotchas found on the way:**
  - `ConfigManager.load_config` marks setup complete by itself whenever a captures folder and player names are set.
  - Motion's `AnimatePresence mode="wait"` can leave a stale child on screen when the key changes quickly, so the save indicator doesn't use it.

### Phase 7: Cutover

Make the web UI the default, delete `desktop_app/gui/` and the Qt workers, drop PyQt6 from `requirements.txt` (unless Linux needs it as the pywebview backend), update the README and the setup shortcut.

### After cutover: caption editing and reel export

Requested 2026-10-29, to start once the migration is done. Today `chaos_lib/subtitles.py` builds caption cues from Whisper word timestamps at clip time and writes an `.srt`, burns them in, or both, with the player's own lines in the accent colour. Missing:

- **Captions as data.** Store each clip's caption words (text, start, end, speaker) as JSON next to the clip, and burn them in only at export, so fixing a word never means re-running analysis.
- **Caption editor in Watch.** A caption track under the timeline, synced to the player. Click a word to retype it, merge or split chunks, nudge timing. The preview draws captions over the video in the browser, so edits show instantly.
- **Export options.** 16:9 or 9:16 reel, with the reel crop centred on the crosshair (or draggable). Captions on, off, or as a separate `.srt`. Today "Export as one video…" only joins clips with ffmpeg concat.
- **Caption style ("the littlest text on screen at a time").**
  - One to three words on screen, timed to speech, never full sentences.
  - A pop or scale-in on each new chunk, with the spoken word highlighted.
  - Heavy, bold, rounded type with a thick outline or shadow so it reads over any footage.
  - In reels, captions sit in the middle-lower third, clear of the killfeed and the platform's UI.
  - The player's lines in the accent colour, teammates in white, with an optional emphasis colour on loud or yelled words (from the laughter and yelling detector).
  - A short shake or punch-in on kill moments or big yells.
- **Burn-in matches the preview.** Generate an ASS subtitle file with per-word pop and highlight effects and burn it with ffmpeg.

## Design direction

The current look is not liked, so the new UI is a redesign, not a port of the old layout. Before Phase 3, make a short design pass (palette, type, layout of the main screens) and get sign-off. The Phase 2 download screen sets the tone, so it's the first chance to test a direction.

Signed off 2026-10-29, with "it should look more like CS2". So: a top tab bar like CS2's main menu, condensed uppercase headings (Barlow Condensed standing in for CS2's Stratum2), near-square corners, translucent slate panels over a blurred, dimmed frame of the newest recording, and the hand-drawn logo with its orange and blue.

Behind the app, instead of a blurred recording, is a nod to the Black Ops title screen: a dark room of CRTs, a red doorway and a hanging lamp, built as a CSS 3D scene (`frontend/src/components/Room.tsx`, no WebGL). It stays blurred and still, except for a slight head turn with the mouse. It's an easter egg, not a menu: clicking the settings gear five times quickly brings it into focus, the mouse turns your head, depth of field follows where you look, and the menu CRT works. Esc returns to the app. Its animations are paused while it's behind the app, so it costs nothing while you work or a run uses the GPU. Head movement is slow and only happens while the mouse moves, then settles. WASD in the easter egg leans against the chair straps; mash it and the chair jolts and the menu CRT flashes SUBJECT RESTRAINED. Walking around was ruled out: the layers are flat cut-outs that only look right from the chair, so it would need a real three.js room. Settings > Appearance has two switches, Background (on/off) and Background motion, saved in config.yaml under `gui`. The OS reduce-motion setting is honoured too.

## Risks

- **Video playback:** codecs and multiple audio tracks (see Phase 0).
- **WebView2 runtime:** built into Windows 11, may be missing on older Windows 10. Setup should detect that and point to Microsoft's installer.
- **Linux:** pywebview needs GTK (`python3-gi`) or QtWebEngine. macOS works out of the box.
- **Stale committed bundle:** easy to change `frontend/src` and forget to rebuild `frontend/dist`. Add a check (e.g. a test comparing a source hash recorded at build time) if it bites.
- **Hover-preview performance:** the Qt app decodes frames live. Pre-generating previews costs disk and time on first scan, so it needs a cache with eviction.

## Open questions

1. Design direction: CS2-flavoured dark UI, or something else? Any reference apps you like?
2. ~~OK to commit `frontend/dist/`?~~ Yes, confirmed 2026-10-29.
