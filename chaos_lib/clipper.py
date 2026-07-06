import os
import json
import glob
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed


def _get_ffmpeg() -> str:
    path = shutil.which('ffmpeg')
    if path:
        return path
    for pattern in [
        r"C:\Users\nickb\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    raise FileNotFoundError("FFmpeg not found. Please ensure FFmpeg is installed and in your PATH.")


def _clip_one(i: int, clip_data: dict, output_folder: str, ffmpeg_path: str) -> None:
    source_video = clip_data['source_video']
    start_time = max(0, clip_data['clip_start'])
    duration = clip_data['clip_end'] - start_time
    if duration <= 0:
        return

    score = int(clip_data['score'])
    base_name = os.path.splitext(os.path.basename(source_video))[0]

    tags = clip_data.get('tags', [])
    special_types = [t for t in ('headshot', 'smoke') if t in tags or f'{t}_kill' in tags]
    special_suffix = '_'.join(special_types)

    if special_suffix:
        output_filename = f"{i + 1}_{score}_{special_suffix}_{base_name[:20]}.mp4"
    else:
        output_filename = f"{i + 1}_{score}_{base_name[:20]}.mp4"
    output_path = os.path.join(output_folder, output_filename)

    subprocess.run(
        [ffmpeg_path, '-y', '-ss', str(start_time), '-i', source_video,
         '-t', str(duration), '-c', 'copy', output_path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def run_clipping(config: dict, progress_callback=None):
    """Read the highlights file and cut final clips in parallel via FFmpeg stream-copy."""
    data_folder = config['data_folder']
    output_folder = config['final_clips_folder']
    highlights_path = os.path.join(data_folder, 'ordered_highlights.json')

    if not os.path.exists(highlights_path):
        print(f"Highlights file not found at {highlights_path}. Run the 'correlate' stage first.")
        return

    with open(highlights_path) as f:
        highlights = json.load(f)

    n = len(highlights)
    print(f"Clipping {n} highlights...")

    ffmpeg_path = _get_ffmpeg()
    max_workers = max(1, config.get('clip_workers', min(4, os.cpu_count() or 1)))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_clip_one, i, clip_data, output_folder, ffmpeg_path): (i, clip_data)
            for i, clip_data in enumerate(highlights)
        }
        completed = 0
        for future in as_completed(futures):
            future.result()  # raises on FFmpeg error
            completed += 1
            i, clip_data = futures[future]
            print(f"  Clipped {i + 1}/{n}")
            if progress_callback:
                progress_callback('clip', clip_data.get('source_video', ''), completed, n)

    print("\nClipping complete.")
