import os
import json
import cv2
import whisper
import librosa
import numpy as np
import subprocess
from tqdm import tqdm

def _parse_killer_from_text(text: str) -> str | None:
    """
    A simple heuristic parser to extract the killer's name from a killfeed line.
    Assumes the killer is the first significant name before symbols like '+' or '►'.
    """
    separators = [' + ', ' ► ']
    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            potential_name = parts[0].strip()
            if potential_name:
                return potential_name
    
    parts = text.split()
    if len(parts) >= 2:
        return parts[0]

    return None

def analyze_killfeed(video_path: str, config: dict, reader) -> list:
    """
    Finds player kills using a three-tier identification system:
    1. Check against a known list of player names.
    2. Fallback to parsing the name from the OCR text.
    3. Default to "Unknown" if all else fails.
    """
    player_names = config['player_names']
    kill_events = []

    hsv_lower1 = np.array(config['red_hsv_lower1'])
    hsv_upper1 = np.array(config['red_hsv_upper1'])
    hsv_lower2 = np.array(config['red_hsv_lower2'])
    hsv_upper2 = np.array(config['red_hsv_upper2'])
    min_area = config['min_red_contour_area']

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return []

    frame_step = config['ocr_frame_step']
    x1, y1, x2, y2 = config['killfeed_roi']
    
    total_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv.CAP_PROP_FPS)

    for frame_idx in range(0, total_frames, frame_step):
        cap.set(cv.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret: break

        killfeed_crop = frame[y1:y2, x1:x2]
        hsv = cv2.cvtColor(killfeed_crop, cv.COLOR_BGR2HSV)
        mask1 = cv.inRange(hsv, hsv_lower1, hsv_upper1)
        mask2 = cv.inRange(hsv, hsv_lower2, hsv_upper2)
        red_mask = cv.bitwise_or(mask1, mask2)
        
        contours, _ = cv.findContours(red_mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            if cv.contourArea(cnt) < min_area:
                continue

            detected_player = "Unknown"
            full_text = ""

            x, y, w, h = cv.boundingRect(cnt)
            kill_line_image = killfeed_crop[y:y+h, x:x+w]
            ocr_result = reader.readtext(kill_line_image, detail=0, paragraph=True)
            
            if ocr_result:
                full_text = " ".join(ocr_result)
                
                found_known_player = False
                for name in player_names:
                    if name in full_text:
                        detected_player = name
                        found_known_player = True
                        break
                
                if not found_known_player:
                    parsed_name = _parse_killer_from_text(full_text)
                    if parsed_name:
                        detected_player = parsed_name

            timestamp = frame_idx / fps
            kill_event = {
                "source_video": video_path,
                "timestamp_seconds": timestamp,
                "type": "kill",
                "details": {
                    "raw_text": full_text,
                    "detected_player": detected_player
                }
            }
            kill_events.append(kill_event)
            break 
    
    cap.release()
    return kill_events

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
            events.append({
                "source_video": video_path,
                "timestamp_seconds": timestamp,
                "type": "chat",
                "details": {"text": full_text, "sentiment": "neutral"}
            })

    cap.release()
    return events

def _extract_audio(video_path: str, temp_dir: str) -> str:
    os.makedirs(temp_dir, exist_ok=True)
    audio_filename = os.path.splitext(os.path.basename(video_path))[0] + ".wav"
    output_path = os.path.join(temp_dir, audio_filename)
    command = ['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', output_path]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path

def analyze_audio(video_path: str, model, temp_dir: str) -> tuple[list, list]:
    audio_path = None # Initialize to ensure it exists for the finally block
    try:
        audio_path = _extract_audio(video_path, temp_dir)
        
        # 1. Whisper Transcription
        transcription = model.transcribe(audio_path, fp16=False)
        voice_events = []
        for segment in transcription['segments']:
            voice_events.append({"source_video": video_path, "timestamp_seconds": segment['start'], "type": "voice", "details": {"text": segment['text']}})
            
        # 2. Audio Spike Detection
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
        # --- BUG FIX: This block ensures the temp audio file is always deleted ---
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)

def run_analysis(config: dict):
    """Main function to run all analysis on videos from the manifest."""
    data_folder = config['data_folder']
    manifest_path = os.path.join(data_folder, 'manifest.json')
    
    with open(manifest_path, 'r') as f:
        video_paths = json.load(f)

    # --- NEW DEBUG LOGIC ---
    # Check if debug_mode is enabled in the config.
    if config.get('debug_mode', False):
        if not video_paths:
            print("Debug mode enabled, but manifest is empty. Nothing to process.")
            return
        # If so, slice the list to only include the first video.
        video_paths = video_paths[:1]
        print(f"DEBUG: Processing a single video: {video_paths[0]}")
    # --- END OF DEBUG LOGIC ---

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
        chat_events = analyze_chat(video_path, config, ocr_reader)
        voice_events, spike_events = analyze_audio(video_path, whisper_model, os.path.join(data_folder, "temp_audio"))
        
        all_events.extend(kill_events)
        all_events.extend(chat_events)
        all_events.extend(spike_events)
        all_events.extend(voice_events)
        
    events_path = os.path.join(data_folder, "all_events.json")
    with open(events_path, 'w') as f:
        json.dump(all_events, f, indent=2)
    print(f"\nAll events saved to {events_path}")