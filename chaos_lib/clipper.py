import os
import json
import glob
import subprocess
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from chaos_lib import subtitles


_REPO_BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bin')


def _get_ffmpeg() -> str:
    """ffmpeg on PATH, else the copy setup put in <repo>/bin, else a winget/manual
    install that hasn't reached this process's PATH yet (winget only updates PATH
    for processes started after it ran)."""
    path = shutil.which('ffmpeg')
    if path:
        return path
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    for pattern in [
        os.path.join(_REPO_BIN, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'),
        os.path.join(local_appdata, r"Microsoft\WinGet\Links\ffmpeg.exe"),
        os.path.join(local_appdata, r"Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe"),
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    raise FileNotFoundError("FFmpeg not found. Run setup again, or install FFmpeg and add it to your PATH.")


def _get_ffprobe() -> str:
    """ffprobe on PATH, else the one shipped next to ffmpeg."""
    path = shutil.which('ffprobe')
    if path:
        return path
    ffmpeg = _get_ffmpeg()
    return os.path.join(os.path.dirname(ffmpeg), os.path.basename(ffmpeg).replace('ffmpeg', 'ffprobe'))


def _clip_one(i: int, clip_data: dict, output_folder: str, ffmpeg_path: str,
              subs: dict | None = None) -> str | None:
    """Cut one clip and record its path relative to output_folder on clip_data['clip_filename'].

    The `i` prefix only reflects the order clips were submitted in (streaming
    pipelines submit as soon as each video finishes, not in final score
    order), so it must never be re-derived later from list position — callers
    that need to find this file again should read clip_data['clip_filename']
    instead of reconstructing the name from a rank/index.

    Voice-chat conversations go to a conversations/ subfolder for review, named
    by banter score (zero-padded, so sorting by name puts the likeliest-funny
    first). `subs` (subtitles.options) adds an .srt and/or burned-in captions.
    """
    source_video = clip_data['source_video']
    start_time = max(0, clip_data['clip_start'])
    duration = clip_data['clip_end'] - start_time
    if duration <= 0:
        return None

    score = int(clip_data['score'])
    base_name = os.path.splitext(os.path.basename(source_video))[0]

    cues = []
    if subs:
        segments = subtitles.segments_for_clip(clip_data.get('events_in_window', []),
                                               start_time, clip_data['clip_end'])
        cues = subtitles.build_cues(segments, start_time, duration)
    burn = bool(subs and subs['burn_in'] and cues)
    subs_suffix = '_subs' if burn else ''

    if clip_data.get('kind') == 'conversation':
        minutes, seconds = divmod(int(start_time), 60)
        output_filename = os.path.join(
            'conversations',
            f"{int(round(clip_data.get('banter', 0) * 100)):04d}_{base_name[:20]}_{minutes:02d}-{seconds:02d}{subs_suffix}.mp4")
    else:
        tags = clip_data.get('tags', [])
        special_types = [t for t in ('headshot', 'smoke', 'funny') if t in tags or f'{t}_kill' in tags]
        special_suffix = '_'.join(special_types)
        if special_suffix:
            output_filename = f"{i + 1}_{score}_{special_suffix}_{base_name[:20]}{subs_suffix}.mp4"
        else:
            output_filename = f"{i + 1}_{score}_{base_name[:20]}{subs_suffix}.mp4"
    output_path = os.path.join(output_folder, output_filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    clip_data['clip_filename'] = output_filename

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return output_filename

    if subs and subs['write_srt'] and cues:
        subtitles.write_srt(cues, os.path.splitext(output_path)[0] + '.srt')
    if burn:
        subtitles.burn(ffmpeg_path, source_video, start_time, duration, cues, output_path)
        return output_filename

    subprocess.run(
        [ffmpeg_path, '-y', '-ss', str(start_time), '-i', source_video,
         '-t', str(duration), '-c', 'copy', output_path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return output_filename


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
    subs = subtitles.options(config)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_clip_one, i, clip_data, output_folder, ffmpeg_path, subs): (i, clip_data)
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

    # _clip_one recorded the exact output filename on each clip_data dict —
    # persist it so downstream tools (GUI, etc.) can look clips up by name
    # instead of re-deriving it from list position.
    with open(highlights_path, 'w') as f:
        json.dump(highlights, f, indent=2)

    print("\nClipping complete.")
