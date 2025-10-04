import os
import json
import subprocess
import shutil
from tqdm import tqdm

def run_clipping(config: dict):
    """Reads the highlights file and uses FFmpeg to cut the final clips at maximum speed."""
    data_folder = config['data_folder']
    output_folder = config['final_clips_folder']
    highlights_path = os.path.join(data_folder, 'ordered_highlights.json')

    if not os.path.exists(highlights_path):
        print(f"Highlights file not found at {highlights_path}. Please run the 'correlate' stage first.")
        return

    with open(highlights_path, 'r') as f:
        highlights = json.load(f)

    print(f"Starting to clip {len(highlights)} videos using high-speed stream copy...")
    progress = tqdm(highlights, desc="Clipping Videos")
    for i, clip_data in enumerate(progress):
        source_video = clip_data['source_video']
        start_time = max(0, clip_data['clip_start'])
        duration = clip_data['clip_end'] - start_time
        
        if duration <= 0:
            continue

        score = int(clip_data['score'])
        base_name = os.path.splitext(os.path.basename(source_video))[0]
        
        # Build special kill type suffixes
        special_types = []
        tags = clip_data.get('tags', [])
        if 'headshot' in tags:
            special_types.append('headshot')
        if 'smoke_kill' in tags:
            special_types.append('smoke')
        
        # Create filename: <clip_number>_<score>_<special_types>_<filename>
        special_suffix = '_'.join(special_types) if special_types else ''
        if special_suffix:
            output_filename = f"{i+1}_{score}_{special_suffix}_{base_name[:20]}.mp4"
        else:
            output_filename = f"{i+1}_{score}_{base_name[:20]}.mp4"
        output_path = os.path.join(output_folder, output_filename)

        # Find FFmpeg executable
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            # Try common FFmpeg locations on Windows
            common_paths = [
                r"C:\Users\nickb\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe",
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"
            ]
            for path_pattern in common_paths:
                import glob
                matches = glob.glob(path_pattern)
                if matches:
                    ffmpeg_path = matches[0]
                    break
        
        if not ffmpeg_path:
            raise FileNotFoundError("FFmpeg not found. Please ensure FFmpeg is installed and in your PATH.")
        
        # Use the '-c copy' command for a lossless, fast cut without re-encoding.
        command = [
            ffmpeg_path, '-y', 
            '-ss', str(start_time), 
            '-i', source_video,
            '-t', str(duration), 
            '-c', 'copy', 
            output_path
        ]
        
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("\nClipping complete.")