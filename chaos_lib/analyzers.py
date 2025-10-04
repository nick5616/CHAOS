# === FILE: chaos_lib/analyzers.py ===
import os
import json
import cv2
import whisper
import librosa
import numpy as np
import subprocess
import shutil
from tqdm import tqdm
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

# (Helper functions _save_debug_screenshot and _extract_audio remain the same)
def _save_debug_screenshot(config: dict, image, video_path: str, event_type: str, timestamp: float, suffix: str = ""):
    if not config.get('debug_mode', False): return
    debug_folder = os.path.join(config['data_folder'], 'debug_screenshots')
    os.makedirs(debug_folder, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    time_str = f"{timestamp:08.2f}".replace('.', '_')
    filename = f"{event_type}_{time_str}_{base_name}{suffix}.png"
    filepath = os.path.join(debug_folder, filename)
    cv2.imwrite(filepath, image)

def _extract_audio(video_path: str, temp_dir: str) -> str:
    os.makedirs(temp_dir, exist_ok=True)
    audio_filename = os.path.splitext(os.path.basename(video_path))[0] + ".wav"
    output_path = os.path.join(temp_dir, audio_filename)
    command = ['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', output_path]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

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
def _parse_and_identify_kill(text: str) -> dict | None:
    """
    Parses a raw OCR string from the killfeed to extract all relevant details.
    Since we're using red rectangle detection, any detected kill is valid.
    """
    # Parse out the victim and assister
    victim = "Unknown"
    assister = None
    parts = text.split()
    if len(parts) < 2:
        return None # Not a valid line
    
    # Victim is always the last word
    victim = parts[-1]

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
        "is_player_kill": True,  # Always True since red rectangle detection is sufficient
        "raw_text": text
    }

def analyze_killfeed(video_path: str, config: dict, reader) -> list:
    kill_events = []
    
    # --- STATE MACHINE: Stores victims currently on screen to prevent duplicates ---
    active_kills = {} # Format: { "victim_name": {"first_seen": timestamp} }
    
    # Load config parameters
    hsv_lower1, hsv_upper1 = np.array(config['red_hsv_lower1']), np.array(config['red_hsv_upper1'])
    hsv_lower2, hsv_upper2 = np.array(config['red_hsv_lower2']), np.array(config['red_hsv_upper2'])
    min_h, max_h = config['killfeed_rect_min_height'], config['killfeed_rect_max_height']
    min_aspect_ratio = config['killfeed_rect_min_aspect_ratio']
    memory_duration = config['kill_memory_duration_seconds']

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return []

    frame_step = config['ocr_frame_step']
    
    # Get video resolution and scale ROI accordingly
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    roi_coords = config['killfeed_roi']
    x1, y1, x2, y2 = scale_roi_for_resolution(roi_coords, video_width, video_height)
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Video resolution: {video_width}x{video_height}")
    print(f"Original killfeed ROI: {roi_coords}")
    print(f"Scaled killfeed ROI: [{x1}, {y1}, {x2}, {y2}]")

    for frame_idx in range(0, total_frames, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret: break

        timestamp = frame_idx / fps
        killfeed_crop = frame[y1:y2, x1:x2]
        
        hsv = cv2.cvtColor(killfeed_crop, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, hsv_lower1, hsv_upper1)
        mask2 = cv2.inRange(hsv, hsv_lower2, hsv_upper2)
        red_mask = cv2.bitwise_or(mask1, mask2)
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        current_frame_victims = set()

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / h if h > 0 else 0
            
            # 1. Filter by shape to find valid kill entries
            if not (min_h <= h <= max_h and aspect_ratio >= min_aspect_ratio):
                continue
            
            # 2. OCR the valid entry to get raw text
            kill_line_image = killfeed_crop[y:y+h, x:x+w]
            ocr_result = reader.readtext(kill_line_image, detail=0, paragraph=True)
            if not ocr_result: continue
            
            full_text = " ".join(ocr_result)
            parsed_info = _parse_and_identify_kill(full_text)
            
            if not parsed_info or not parsed_info.get('victim'): continue

            victim = parsed_info['victim']
            current_frame_victims.add(victim)
            
            # 3. STATE LOGIC: Check if this is a new, unseen kill
            if victim not in active_kills:
                # This is a new kill!
                _save_debug_screenshot(config, kill_line_image, video_path, "kill_NEW", timestamp, suffix=f"_{victim}")
                
                # --- THIS IS THE CRITICAL FIX ---
                # A. IMMEDIATELY add it to our memory to prevent future duplicates.
                active_kills[victim] = {"first_seen": timestamp}
                
                # B. THEN, check if it's a kill we care about (one of our kills).
                if parsed_info['is_player_kill']:
                    # Detect special kill types (headshot and smoke)
                    is_headshot = _detect_headshot_icon(kill_line_image)
                    through_smoke = _detect_smoke_icon(kill_line_image)
                    
                    # Debug output for icon detection
                    if is_headshot or through_smoke:
                        print(f"  Special kill detected: {parsed_info['victim']} - Headshot: {is_headshot}, Smoke: {through_smoke}")
                    
                    kill_event = {
                        "source_video": video_path,
                        "timestamp_seconds": timestamp,
                        "type": "kill",
                        "details": {
                            "raw_text": parsed_info['raw_text'],
                            "detected_player": parsed_info['killer'],
                            "assister": parsed_info['assister'],
                            "victim": parsed_info['victim'],
                            "isHeadshot": is_headshot,
                            "throughSmoke": through_smoke
                        }
                    }
                    kill_events.append(kill_event)

        # 4. STATE CLEANUP: Remove victims who are no longer on screen
        disappeared_victims = [vic for vic in active_kills if vic not in current_frame_victims]
        for vic in disappeared_victims:
            if timestamp - active_kills[vic]["first_seen"] > memory_duration:
                del active_kills[vic]
    
    cap.release()
    return kill_events



def analyze_audio(video_path: str, model, temp_dir: str) -> tuple[list, list]:
    audio_path = None
    try:
        audio_path = _extract_audio(video_path, temp_dir)
        transcription = model.transcribe(audio_path, fp16=False)
        voice_events = []
        for segment in transcription['segments']:
            voice_events.append({"source_video": video_path, "timestamp_seconds": segment['start'], "type": "voice", "details": {"text": segment['text']}})
        y, sr = librosa.load(audio_path, sr=16000)
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        spike_events = []
        if len(rms) > 0:
            rms_normalized = (rms - np.min(rms)) / (np.max(rms) - np.min(rms) + 1e-6)
            spike_frames = np.where(rms_normalized > 0.8)[0]
            for frame_idx in spike_frames:
                timestamp = librosa.frames_to_time(frame_idx, sr=sr, hop_length=512)
                spike_events.append({"source_video": video_path, "timestamp_seconds": timestamp, "type": "audio_spike", "details": {"intensity": float(rms_normalized[frame_idx])}})
        return voice_events, spike_events
    except Exception as e:
        print(f"  - Error processing audio for {os.path.basename(video_path)}: {e}")
        return [], []
    finally:
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)

def run_analysis(config: dict):
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
    print("Initializing AI Models (EasyOCR & Whisper)...")
    import easyocr
    
    # Check if GPU should be used
    use_gpu = config.get('use_gpu', False)
    if use_gpu:
        print("GPU acceleration enabled for AI models")
    else:
        print("Using CPU for AI models")
    
    # Platform-specific GPU handling
    import platform
    system = platform.system()
    
    if system == 'Darwin' and use_gpu:
        # macOS: Force CPU usage to avoid MPS compatibility issues with EasyOCR
        # EasyOCR has issues with torch.mps.current_device() in newer PyTorch versions
        print("macOS detected: Using CPU to avoid MPS compatibility issues")
        ocr_reader = easyocr.Reader(['en'], gpu=False)
    else:
        # Windows/Linux: Use GPU acceleration normally, or CPU if disabled
        ocr_reader = easyocr.Reader(['en'], gpu=use_gpu)
    whisper_model = whisper.load_model(config['whisper_model'], device='cuda' if use_gpu else 'cpu')
    all_events = []
    progress = tqdm(video_paths, desc="Analyzing Videos")
    for video_path in progress:
        base_name = os.path.basename(video_path)
        progress.set_description(f"Analyzing {base_name[:30]}...")
        kill_events = analyze_killfeed(video_path, config, ocr_reader)
        # chat_events = analyze_chat(video_path, config, ocr_reader)
        voice_events, spike_events = analyze_audio(video_path, whisper_model, os.path.join(data_folder, "temp_audio"))
        all_events.extend(kill_events)
        # all_events.extend(chat_events)
        all_events.extend(spike_events)
        all_events.extend(voice_events)
    events_path = os.path.join(data_folder, "all_events.json")
    with open(events_path, 'w') as f:
        json.dump(all_events, f, indent=2)
    print(f"\nAll events saved to {events_path}")
