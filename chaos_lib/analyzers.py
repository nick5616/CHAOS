# === FILE: chaos_lib/analyzers.py ===
import os
import json
import time
import cv2
import whisper
import librosa
import numpy as np
import shutil
from thefuzz import fuzz

def scale_roi_for_resolution(roi_coords, video_width, video_height, reference_width=2560, reference_height=1440):
    """
    Scale ROI coordinates from reference resolution to actual video resolution.
    
    Args:
        roi_coords: [x1, y1, x2, y2] coordinates for reference resolution
        video_width: Actual video width
        video_height: Actual video height
        reference_width: Reference resolution width (default: 2560 for ultrawide)
        reference_height: Reference resolution height (default: 1440)
    
    Returns:
        [x1, y1, x2, y2] scaled coordinates for actual video resolution
    """
    x1, y1, x2, y2 = roi_coords
    
    # Calculate scaling factors
    width_scale = video_width / reference_width
    height_scale = video_height / reference_height
    
    # Scale coordinates
    scaled_x1 = int(x1 * width_scale)
    scaled_y1 = int(y1 * height_scale)
    scaled_x2 = int(x2 * width_scale)
    scaled_y2 = int(y2 * height_scale)
    
    # Ensure coordinates are within video bounds
    scaled_x1 = max(0, min(scaled_x1, video_width))
    scaled_y1 = max(0, min(scaled_y1, video_height))
    scaled_x2 = max(0, min(scaled_x2, video_width))
    scaled_y2 = max(0, min(scaled_y2, video_height))
    
    # Ensure x2 > x1 and y2 > y1
    if scaled_x2 <= scaled_x1:
        scaled_x2 = min(scaled_x1 + 10, video_width)
    if scaled_y2 <= scaled_y1:
        scaled_y2 = min(scaled_y1 + 10, video_height)
    
    return [scaled_x1, scaled_y1, scaled_x2, scaled_y2]

def _save_debug_screenshot(config: dict, image, video_path: str, event_type: str, timestamp: float, suffix: str = ""):
    if not config.get('debug_mode', False): return
    debug_folder = os.path.join(config['data_folder'], 'debug_screenshots')
    os.makedirs(debug_folder, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    time_str = f"{timestamp:08.2f}".replace('.', '_')
    filename = f"{event_type}_{time_str}_{base_name}{suffix}.png"
    filepath = os.path.join(debug_folder, filename)
    cv2.imwrite(filepath, image)

# --- ICON DETECTION FUNCTIONS ---
def _detect_headshot_icon(image_region):
    """
    Detect headshot icon in the killfeed region.
    Looks for the characteristic skull/bullet icon pattern.
    """
    # Convert to grayscale for template matching
    gray = cv2.cvtColor(image_region, cv2.COLOR_BGR2GRAY)
    
    # Look for white/light colored objects (headshot icons are typically white)
    # Be more restrictive with the color range
    white_mask = cv2.inRange(gray, 220, 255)  # Only very bright white
    contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Look for specific headshot icon characteristics
    headshot_icons_found = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        # Headshot icons are typically small, compact shapes
        if 30 < area < 300:  # Smaller, more restrictive area
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # Headshot icons should be roughly square or slightly rectangular
            if 0.7 < aspect_ratio < 1.5:
                # Additional check: look for skull-like shape characteristics
                # Headshot icons have more complex contours than simple rectangles
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    # Headshot icons are moderately circular (skull shape)
                    if 0.4 < circularity < 0.9:
                        headshot_icons_found += 1
    
    # Only return True if we find exactly 1 headshot icon (not multiple false positives)
    return headshot_icons_found == 1

def _detect_smoke_icon(image_region):
    """
    Detect smoke icon in the killfeed region.
    Looks for the characteristic cloud/smoke icon pattern.
    """
    # Convert to grayscale for template matching
    gray = cv2.cvtColor(image_region, cv2.COLOR_BGR2GRAY)
    
    # Look for smoke icons - they should be very specific cloud-like shapes
    # Smoke icons are typically medium gray, not bright white like text
    smoke_mask = cv2.inRange(gray, 120, 200)  # Medium gray range, not bright white
    contours, _ = cv2.findContours(smoke_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Look for specific smoke icon characteristics
    smoke_icons_found = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        # Smoke icons are typically small, compact shapes
        if 40 < area < 150:  # Very specific size range for smoke icons
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # Smoke icons should be roughly square or slightly rectangular
            if 0.7 < aspect_ratio < 1.4:  # More restrictive aspect ratio
                # Additional checks for cloud-like characteristics
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    # Smoke icons are irregular (cloud-like), not circular or rectangular
                    if 0.2 < circularity < 0.6:  # Very irregular shapes
                        # Additional check: look for multiple "bumps" like a cloud
                        hull = cv2.convexHull(contour)
                        hull_area = cv2.contourArea(hull)
                        if hull_area > 0:
                            solidity = area / hull_area
                            # Smoke icons have low solidity (lots of indentations like a cloud)
                            if solidity < 0.8:
                                smoke_icons_found += 1
    
    # Only return True if we find exactly 1 smoke icon (not multiple false positives)
    return smoke_icons_found == 1

# --- FINAL, ROBUST PARSING & IDENTIFICATION LOGIC ---
def _parse_and_identify_kill(text: str, player_names=()) -> dict | None:
    """
    Parses a raw OCR string from the killfeed to extract all relevant details.

    CS2 draws the red border on every row involving the local player: their
    kills, but also their deaths and assists. A row starting with one of the
    player's names is their kill; a row with their name elsewhere is a death
    or assist. A row with none of their names (no names configured, or they
    played under a name not in the list) falls back to trusting the border.
    """
    assister = None
    parts = text.split()
    if len(parts) < 2:
        return None # Not a valid line

    victim = parts[-1]
    is_player_kill = True
    lowered = text.lower()
    for name in player_names:
        name = name.lower()
        if fuzz.ratio(lowered[:len(name)], name) >= 80:
            is_player_kill = True
            # Everything after the player's name: the victim (plus any
            # assister). Multi-word names like "Spike Spiegel" stay whole.
            victim = text[len(name):].strip() or victim
            break
        if fuzz.partial_ratio(name, lowered) >= 85:
            is_player_kill = False  # their name, but not as the killer

    # Check for an assist
    if '+' in parts:
        try:
            plus_index = parts.index('+')
            # The assister is the name right after the '+'
            if plus_index + 1 < len(parts):
                assister = parts[plus_index + 1]
        except ValueError:
            pass # No '+' found
            
    # Parse the killer from the text
    if ' + ' in text:
        detected_player = text.split(' + ')[0].strip()
    elif ' ► ' in text:
        detected_player = text.split(' ► ')[0].strip()
    else:
        detected_player = parts[0]

    return {
        "killer": detected_player,
        "assister": assister,
        "victim": victim,
        "is_player_kill": is_player_kill,
        "raw_text": text
    }

def _name_key(name: str) -> str:
    return ''.join(ch for ch in name.lower() if ch.isalnum())


def _find_fuzzy_victim(victim: str, active_kills: dict, threshold: int = 85) -> str | None:
    """Return the matching key in active_kills if one is fuzzy-similar enough, else None.

    Compared on letters and digits only, so OCR punctuation noise ("se." vs
    "se _") doesn't matter. The threshold is high because victims carry shared
    prefixes like "BOT ": "BOT Mayer" vs "BOT Maru" scores 80 and must not merge."""
    key = _name_key(victim)
    for known in active_kills:
        if fuzz.ratio(key, _name_key(known)) >= threshold:
            return known
    return None

# --- KILLFEED ---------------------------------------------------------------
#
# CS2 death notices (huddeathnotice.xml/.css): a row involving the local player
# (the red-bordered rows we look for) stays on screen for 7.5 s, other rows for
# 5 s, then fades out over 1 s. So we don't need to look at every 30th frame:
# sampling every ~2.5 s still sees each of our kills about three times, which
# leaves slack for an OCR miss or the fade-out.
#
# Each row is fingerprinted from its pixels (_row_signature), so on later
# samples a row we already know about is recognised without running OCR on it
# again. OCR, the expensive step, only runs on rows we haven't seen before.
# Because a sample only tells us a kill happened sometime since the previous
# sample, we binary-search the frames in between for the moment the row first
# appeared, which pins the kill time to within ~0.15 s for a handful of extra
# frame decodes (no OCR).

KILLFEED_OWN_LIFETIME_S = 7.5
KILLFEED_FADE_S = 1.0
DEFAULT_SAMPLE_INTERVAL_S = KILLFEED_OWN_LIFETIME_S / 3
APPEARANCE_RESOLUTION_S = 0.15

_SIG_SIZE = (96, 12)          # (w, h) of the downsampled row fingerprint
_SIG_WINDOW = _SIG_SIZE[0] // 12  # compare in windows of a few characters, so one differing name stands out
_ROW_WIDTH_TOLERANCE = 0.04   # rows of the same kill keep their width to within a few px
# Distances measured on real footage (354 rows, 3 clips): the same row seen at
# different times scores up to 0.15 (new rows flash briefly and the game shows
# through the panel); different rows that pass the width check score 0.136 and up.
# The two overlap, so a fingerprint alone may only *skip* OCR when it is far
# below every different-row pair; anything in between is OCR'd and deduped by
# victim name. A false "same" would drop a kill, a false "different" costs one OCR call.
_SAME_ROW_MAX = 0.08
_PRESENT_MAX = 0.15           # looser bound for "is this row on screen yet?" in _find_appearance

# Set by _init_analysis_worker in pool processes; checked between units of work.
_gaming_event = None
_GAMING_IDLE_RATIO = 3.0      # while gaming, sleep 3x as long as we worked: ~25% duty cycle
_gaming_priority_applied = False


def _yield_if_gaming(work_seconds: float) -> None:
    """While the user is playing, back off so the game keeps its frame rate:
    drop this process (and the ffmpeg children it spawns) to idle CPU priority
    and sleep in proportion to the work just done, leaving the GPU and CPU free
    most of the time."""
    global _gaming_priority_applied
    gaming = _gaming_event is not None and _gaming_event.is_set()
    if gaming != _gaming_priority_applied:
        _set_low_priority(gaming)
        _gaming_priority_applied = gaming
    if gaming and work_seconds > 0:
        time.sleep(work_seconds * _GAMING_IDLE_RATIO)


def _set_low_priority(low: bool) -> None:
    try:
        import psutil
        p = psutil.Process()
        if os.name == 'nt':
            p.nice(psutil.IDLE_PRIORITY_CLASS if low else psutil.NORMAL_PRIORITY_CLASS)
        else:
            p.nice(19 if low else 0)  # raising priority back may need privileges; ignored below
    except Exception:
        pass


def _read_frame(cap, frame_idx: int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    return frame if ok else None


def _find_kill_rows(killfeed_crop, params) -> list:
    """Bounding boxes of red-bordered (local player) rows in the killfeed crop."""
    hsv = cv2.cvtColor(killfeed_crop, cv2.COLOR_BGR2HSV)
    red_mask = cv2.bitwise_or(cv2.inRange(hsv, params['lo1'], params['hi1']),
                              cv2.inRange(hsv, params['lo2'], params['hi2']))
    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rows = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if params['min_h'] <= h <= params['max_h'] and h > 0 and w / h >= params['min_ar']:
            rows.append((x, y, w, h))
    return rows


def _row_signature(row_img) -> np.ndarray:
    """Position-independent fingerprint of one killfeed row: its text and icons
    (Otsu-thresholded, so the translucent background showing the game through
    mostly drops out) downsampled to a fixed grid. The same row matches itself
    after sliding up the feed; rows with different names or weapons don't."""
    gray = cv2.cvtColor(row_img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.resize(mask, _SIG_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def _row_distance(sig_a, w_a, sig_b, w_b) -> float:
    """0 for identical rows; the worst few-character window's mean difference otherwise."""
    if abs(w_a - w_b) > max(4, _ROW_WIDTH_TOLERANCE * max(w_a, w_b)):
        return float('inf')
    col = np.abs(sig_a - sig_b).mean(axis=0)
    return float(np.convolve(col, np.ones(_SIG_WINDOW) / _SIG_WINDOW, mode='valid').max())


def _find_appearance(cap, fps, lo_idx, hi_idx, sig, w, known, crop_box, params) -> int:
    """Binary-search frames (lo_idx, hi_idx] for the first one showing this row.
    lo_idx is the previous sample (row absent), hi_idx the current one (present).
    A probe row only counts as this row if it looks more like it than like any
    row already on screen (`known`), so a similar older row can't fool the search."""
    x1, y1, x2, y2 = crop_box
    min_frames = max(1, int(APPEARANCE_RESOLUTION_S * fps))
    while hi_idx - lo_idx > min_frames:
        mid = (lo_idx + hi_idx) // 2
        frame = _read_frame(cap, mid)
        if frame is None:
            break
        crop = frame[y1:y2, x1:x2]
        present = False
        for rx, ry, rw, rh in _find_kill_rows(crop, params):
            probe = _row_signature(crop[ry:ry + rh, rx:rx + rw])
            d = _row_distance(sig, w, probe, rw)
            if d < _PRESENT_MAX and all(d < _row_distance(k['sig'], k['w'], probe, rw) for k in known):
                present = True
                break
        if present:
            hi_idx = mid
        else:
            lo_idx = mid
    return hi_idx


def analyze_killfeed(video_path: str, config: dict, reader) -> list:
    player_names = [n for n in config.get('player_names') or [] if n and n.strip()]
    interval = float(config.get('killfeed_sample_interval_seconds', DEFAULT_SAMPLE_INTERVAL_S))
    # Never sample less often than a row stays up, or kills could slip between samples.
    interval = min(max(interval, 0.1), KILLFEED_OWN_LIFETIME_S - 0.5)
    # A row can't still be on screen this long after it appeared; past that,
    # the same victim name is a new kill (they died again in a later round).
    row_lifetime = KILLFEED_OWN_LIFETIME_S + KILLFEED_FADE_S

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    # killfeed_roi is stored in absolute pixels for whatever resolution the user
    # picked/tuned it at (killfeed_roi_resolution); if that isn't recorded,
    # treat the ROI as already matching this video.
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ref_w, ref_h = config.get('killfeed_roi_resolution') or (video_width, video_height)
    crop_box = scale_roi_for_resolution(config['killfeed_roi'], video_width, video_height, ref_w, ref_h)
    x1, y1, x2, y2 = crop_box
    # Row heights are tuned at the same reference resolution as the ROI, so
    # they scale with it (a row is ~42 px tall at 1440p, ~63 px at 4K).
    h_scale = video_height / ref_h
    params = {
        'lo1': np.array(config['red_hsv_lower1']), 'hi1': np.array(config['red_hsv_upper1']),
        'lo2': np.array(config['red_hsv_lower2']), 'hi2': np.array(config['red_hsv_upper2']),
        'min_h': config['killfeed_rect_min_height'] * h_scale,
        'max_h': config['killfeed_rect_max_height'] * h_scale,
        'min_ar': config['killfeed_rect_min_aspect_ratio'],
    }

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(interval * fps))

    kill_events = []
    on_screen = []   # rows we've already counted: {sig, w, victim, appeared}
    prev_idx = None

    for frame_idx in range(0, total_frames, step):
        t0 = time.perf_counter()
        frame = _read_frame(cap, frame_idx)
        if frame is None:
            break
        timestamp = frame_idx / fps
        on_screen = [k for k in on_screen if timestamp - k['appeared'] <= row_lifetime]
        crop = frame[y1:y2, x1:x2]

        for x, y, w, h in _find_kill_rows(crop, params):
            row_img = crop[y:y + h, x:x + w]
            sig = _row_signature(row_img)
            if any(_row_distance(k['sig'], k['w'], sig, w) < _SAME_ROW_MAX for k in on_screen):
                continue  # same row as an earlier sample: already counted, no OCR needed

            ocr_result = reader.readtext(row_img, detail=0, paragraph=True)
            if not ocr_result:
                continue
            parsed = _parse_and_identify_kill(" ".join(ocr_result), player_names)
            if not parsed or not parsed.get('victim'):
                continue

            # The fingerprint can miss (e.g. the row is mid-fade), so fall back
            # to the victim name before deciding this is a new kill.
            victims = {k['victim']: k for k in on_screen}
            match = _find_fuzzy_victim(parsed['victim'], victims)
            if match:
                victims[match].update(sig=sig, w=w)  # match by pixels next time
                continue

            if not parsed['is_player_kill']:
                # The player's death or assist: remember the row so it isn't
                # OCR'd again, but it's not a highlight.
                on_screen.append({'sig': sig, 'w': w, 'victim': parsed['victim'], 'appeared': timestamp})
                continue

            appeared_idx = frame_idx
            if prev_idx is not None:
                appeared_idx = _find_appearance(cap, fps, prev_idx, frame_idx, sig, w, on_screen, crop_box, params)
            appeared = appeared_idx / fps
            on_screen.append({'sig': sig, 'w': w, 'victim': parsed['victim'], 'appeared': appeared})

            _save_debug_screenshot(config, row_img, video_path, "kill_NEW", appeared, suffix=f"_{parsed['victim']}")
            is_headshot = _detect_headshot_icon(row_img)
            through_smoke = _detect_smoke_icon(row_img)
            kill_events.append({
                "source_video": video_path,
                "timestamp_seconds": appeared,
                "type": "kill",
                "details": {
                    "raw_text": parsed['raw_text'],
                    "detected_player": parsed['killer'],
                    "assister": parsed['assister'],
                    "victim": parsed['victim'],
                    "isHeadshot": is_headshot,
                    "throughSmoke": through_smoke,
                },
            })

        prev_idx = frame_idx
        _yield_if_gaming(time.perf_counter() - t0)

    cap.release()
    kill_events.sort(key=lambda e: e['timestamp_seconds'])
    return kill_events


# --- AUDIO ------------------------------------------------------------------

_SAMPLE_RATE = 16000
_RMS_HOP = 512
_GAMING_CHUNK_S = 30  # Whisper's own window; while gaming we transcribe one at a time and back off between


def _transcribe(model, audio: np.ndarray) -> list:
    fp16 = getattr(model, 'device', None) is not None and model.device.type == 'cuda'
    if not (_gaming_event is not None and _gaming_event.is_set()):
        return model.transcribe(audio, fp16=fp16)['segments']
    # Gaming: one 30 s window per call so the GPU gets long idle gaps instead
    # of one multi-second burst that would stutter the game.
    segments = []
    chunk = _GAMING_CHUNK_S * _SAMPLE_RATE
    for start in range(0, len(audio), chunk):
        t0 = time.perf_counter()
        offset = start / _SAMPLE_RATE
        for seg in model.transcribe(audio[start:start + chunk], fp16=fp16)['segments']:
            segments.append({**seg, 'start': seg['start'] + offset, 'end': seg['end'] + offset})
        _yield_if_gaming(time.perf_counter() - t0)
    return segments


def analyze_audio(video_path: str, model) -> tuple[list, list]:
    try:
        # ffmpeg decodes straight to 16 kHz mono in memory: one decode feeds
        # both Whisper and the loudness analysis, no temp WAV on disk.
        audio = whisper.load_audio(video_path, sr=_SAMPLE_RATE)
        if audio.size == 0:
            return [], []

        voice_events = []
        for segment in _transcribe(model, audio):
            # Skip segments Whisper itself is uncertain about (likely noise/music)
            if segment.get('no_speech_prob', 0) > 0.5:
                continue
            voice_events.append({"source_video": video_path, "timestamp_seconds": segment['start'],
                                 "type": "voice", "details": {"text": segment['text']}})

        # Loudness spikes: one event per contiguous run of loud frames (at its
        # peak), not one per 32 ms frame.
        rms = librosa.feature.rms(y=audio, frame_length=2048, hop_length=_RMS_HOP)[0]
        spike_events = []
        if len(rms) > 0:
            rms_normalized = (rms - np.min(rms)) / (np.max(rms) - np.min(rms) + 1e-6)
            loud = rms_normalized > 0.8
            edges = np.flatnonzero(np.diff(np.concatenate(([0], loud.astype(np.int8), [0]))))
            for start, end in zip(edges[::2], edges[1::2]):
                peak = start + int(np.argmax(rms_normalized[start:end]))
                spike_events.append({
                    "source_video": video_path,
                    "timestamp_seconds": float(librosa.frames_to_time(peak, sr=_SAMPLE_RATE, hop_length=_RMS_HOP)),
                    "type": "audio_spike",
                    "details": {"intensity": float(rms_normalized[peak])},
                })
        return voice_events, spike_events
    except Exception as e:
        print(f"  - Error processing audio for {os.path.basename(video_path)}: {e}")
        return [], []


# ---------------------------------------------------------------------------
# Worker-process helpers for parallel analysis
# ---------------------------------------------------------------------------

_worker_ocr = None
_worker_whisper = None


def _init_analysis_worker(whisper_model_name: str, device: str = 'cpu', torch_threads: int = 1,
                          gaming_event=None) -> None:
    """Runs once in each worker process to load models into module globals."""
    global _worker_ocr, _worker_whisper, _gaming_event
    import torch
    import easyocr as _easyocr
    # Workers run side by side; each takes its share of the cores instead of
    # every one of them spinning up a thread per core.
    torch.set_num_threads(torch_threads)
    cv2.setNumThreads(torch_threads)
    _gaming_event = gaming_event
    _worker_ocr = _easyocr.Reader(['en'], gpu=(device == 'cuda'), verbose=False)
    _worker_whisper = whisper.load_model(whisper_model_name, device=device)


def _analyze_video_worker(video_path: str, config: dict) -> list:
    """Runs in a worker process. Uses module-level models loaded by the initializer."""
    kill_events = analyze_killfeed(video_path, config, _worker_ocr)
    voice_events, spike_events = analyze_audio(video_path, _worker_whisper)
    return kill_events + spike_events + voice_events


def make_analysis_pool(config: dict, plan, gaming_event=None):
    """Process pool sized by `plan` (see chaos_lib.resources). Always uses the
    spawn start method: worker processes initialise CUDA themselves, which is
    unsafe in a forked child."""
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    return ProcessPoolExecutor(
        max_workers=plan.max_workers,
        mp_context=multiprocessing.get_context('spawn'),
        initializer=_init_analysis_worker,
        initargs=(config['whisper_model'], plan.device, plan.torch_threads, gaming_event),
    )


# ---------------------------------------------------------------------------

def run_analysis(config: dict, progress_callback=None):
    from concurrent.futures import as_completed
    from chaos_lib.resources import plan_analysis_workers

    data_folder = config['data_folder']
    manifest_path = os.path.join(data_folder, 'manifest.json')
    with open(manifest_path, 'r') as f:
        video_paths = json.load(f)

    if config.get('debug_mode', False):
        debug_folder = os.path.join(config['data_folder'], 'debug_screenshots')
        if os.path.exists(debug_folder):
            print("DEBUG: Deleting old debug screenshots...")
            shutil.rmtree(debug_folder)
        if not video_paths:
            print("Debug mode enabled, but manifest is empty. Nothing to process.")
            return
        video_paths = video_paths[:1]
        print(f"DEBUG: Processing a single video: {video_paths[0]}")

    if not video_paths:
        print("No video paths to analyze.")
        return

    requested = config.get('pipeline', {}).get('analysis_workers', config.get('analysis_workers'))
    plan = plan_analysis_workers(config, requested, n_videos=len(video_paths))
    print(plan.summary)

    n = len(video_paths)
    all_events = []
    with make_analysis_pool(config, plan) as pool:
        futures = {pool.submit(_analyze_video_worker, path, config): path for path in video_paths}
        for completed, future in enumerate(as_completed(futures), start=1):
            video_path = futures[future]
            all_events.extend(future.result())
            print(f"  Finished {os.path.basename(video_path)} ({completed}/{n})")
            if progress_callback:
                progress_callback('analyze', video_path, completed, n)

    events_path = os.path.join(data_folder, 'all_events.json')
    with open(events_path, 'w') as f:
        json.dump(all_events, f, indent=2)
    print(f"\nAll events saved to {events_path}")
