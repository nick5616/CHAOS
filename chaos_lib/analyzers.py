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

# (Helper functions _save_debug_screenshot and _extract_audio remain the same)
def _save_debug_screenshot(config: dict, image, video_path: str, event_type: str, timestamp: float):
    if not config.get('debug_mode', False): return
    debug_folder = os.path.join(config['data_folder'], 'debug_screenshots')
    os.makedirs(debug_folder, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    time_str = f"{timestamp:08.2f}".replace('.', '_')
    filename = f"{event_type}_{time_str}_{base_name}.png"
    filepath = os.path.join(debug_folder, filename)
    cv2.imwrite(filepath, image)

def _extract_audio(video_path: str, temp_dir: str) -> str:
    os.makedirs(temp_dir, exist_ok=True)
    audio_filename = os.path.splitext(os.path.basename(video_path))[0] + ".wav"
    output_path = os.path.join(temp_dir, audio_filename)
    command = ['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', output_path]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

# --- FINAL, ROBUST PARSING & IDENTIFICATION LOGIC ---
def _parse_and_identify_kill(text: str, known_players: list) -> dict | None:
    """
    Parses a killfeed line to extract killer and victim, handling abbreviations.
    Returns a dictionary with parsed info or None.
    """
    parts = text.split()
    if len(parts) < 2:
        return None # Not a valid kill line

    # The victim is reliably the last part of the string.
    victim = parts[-1]
    
    # The killer is everything before the victim, minus icons/modifiers.
    # We can't OCR icons, so we use a robust matching approach.
    detected_player = "Unknown"
    highest_match_score = 0

    for name in known_players:
        # `partial_ratio` is perfect for matching "excellent mage of 6 sense"
        # against "excellent mage of 6 se..."
        # We set a high threshold to ensure it's a confident match.
        match_score = fuzz.partial_ratio(name, text)
        if match_score > 90 and match_score > highest_match_score:
            detected_player = name # Store the full, non-abbreviated name
            highest_match_score = match_score

    # If no known player was found via fuzzy match, fallback to a simple parse.
    if detected_player == "Unknown":
        # Heuristic: Find the text before common weapon separators
        separators = [' + ', ' ► ']
        for sep in separators:
            if sep in text:
                detected_player = text.split(sep)[0].strip()
                break
        else: # If no separator, assume first word is killer
            detected_player = parts[0]

    return {
        "killer": detected_player,
        "victim": victim,
        "raw_text": text
    }

def analyze_killfeed(video_path: str, config: dict, reader) -> list:
    player_names = config['player_names']
    kill_events = []

    hsv_lower1, hsv_upper1 = np.array(config['red_hsv_lower1']), np.array(config['red_hsv_upper1'])
    hsv_lower2, hsv_upper2 = np.array(config['red_hsv_lower2']), np.array(config['red_hsv_upper2'])
    min_h, max_h = config['killfeed_rect_min_height'], config['killfeed_rect_max_height']
    min_aspect_ratio = config['killfeed_rect_min_aspect_ratio']
    dedup_secs = config['kill_deduplication_seconds']
    
    # Debouncer tracks a list of recent victims: [(timestamp, victim_name), ...]
    recent_victims = []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return []

    frame_step = config['ocr_frame_step']
    x1, y1, x2, y2 = config['killfeed_roi']
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    for frame_idx in range(0, total_frames, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret: break

        killfeed_crop = frame[y1:y2, x1:x2]
        hsv = cv2.cvtColor(killfeed_crop, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, hsv_lower1, hsv_upper1)
        mask2 = cv2.inRange(hsv, hsv_lower2, hsv_upper2)
        red_mask = cv2.bitwise_or(mask1, mask2)
        
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        timestamp = frame_idx / fps

        # --- Debouncer Cleanup: Remove old victims from our tracking list ---
        recent_victims = [(ts, vic) for ts, vic in recent_victims if timestamp - ts < dedup_secs]
        
        current_frame_victims = set()

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / h if h > 0 else 0
            
            if not (min_h <= h <= max_h and aspect_ratio >= min_aspect_ratio):
                continue
            
            kill_line_image = killfeed_crop[y:y+h, x:x+w]
            ocr_result = reader.readtext(kill_line_image, detail=0, paragraph=True)
            
            if not ocr_result: continue
            
            full_text = " ".join(ocr_result)
            parsed_info = _parse_and_identify_kill(full_text, player_names)
            
            if not parsed_info: continue

            victim_name = parsed_info['victim']
            
            # Prevent logging the same victim twice in the same frame
            if victim_name in current_frame_victims:
                continue

            # Check if this victim has been seen in recent frames
            is_duplicate = False
            for _, recent_vic in recent_victims:
                if fuzz.ratio(victim_name, recent_vic) > 85:
                    is_duplicate = True
                    break
            
            if is_duplicate:
                continue

            # This is a new, unique kill.
            _save_debug_screenshot(config, kill_line_image, video_path, "kill", timestamp)
            kill_event = {
                "source_video": video_path,
                "timestamp_seconds": timestamp,
                "type": "kill",
                "details": {
                    "raw_text": parsed_info['raw_text'],
                    "detected_player": parsed_info['killer'],
                    "victim": parsed_info['victim']
                }
            }
            kill_events.append(kill_event)
            
            # Add to both current frame and long-term lists to prevent all duplicates
            current_frame_victims.add(victim_name)
            recent_victims.append((timestamp, victim_name))
    
    cap.release()
    return kill_events

# (analyze_chat, analyze_audio, and run_analysis remain the same)
def analyze_chat(video_path: str, config: dict, reader) -> list:
    x1, y1, x2, y2 = config['chat_roi']
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return []
    events = []
    frame_step = config['ocr_frame_step']
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    for frame_idx in range(0, total_frames, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret: break
        cropped_frame = frame[y1:y2, x1:x2]
        results = reader.readtext(cropped_frame, detail=0, paragraph=True)
        if results:
            timestamp = frame_idx / fps
            full_text = " ".join(results)
            _save_debug_screenshot(config, cropped_frame, video_path, "chat", timestamp)
            events.append({"source_video": video_path, "timestamp_seconds": timestamp, "type": "chat", "details": {"text": full_text, "sentiment": "neutral"}})
    cap.release()
    return events

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
    ocr_reader = easyocr.Reader(['en'], gpu=True)
    whisper_model = whisper.load_model(config['whisper_model'])
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
