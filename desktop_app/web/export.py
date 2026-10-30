"""
Stitch clips into one video for the Watch screen.

When every clip has the same video codec, size and frame rate (the usual
case: one recorder, one resolution), ffmpeg's concat demuxer joins them
without re-encoding, which takes seconds. Otherwise stream-copying would
give a broken file, so the clips are scaled and padded to the most common
size and re-encoded, with NVENC when ffmpeg has it.
"""

import collections
import json
import os
import subprocess
import tempfile
import threading

from chaos_lib.clipper import _get_ffmpeg, _get_ffprobe


def _probe(path: str) -> dict:
    out = subprocess.run(
        [_get_ffprobe(), "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration", "-of", "json", path],
        capture_output=True, text=True, timeout=30)
    data = json.loads(out.stdout or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return {
        "key": (video.get("codec_name"), video.get("width"), video.get("height"), video.get("r_frame_rate")),
        "size": (video.get("width") or 1920, video.get("height") or 1080),
        "audio": any(s.get("codec_type") == "audio" for s in data.get("streams", [])),
        "duration": float(data.get("format", {}).get("duration") or 0),
    }


def _has_nvenc() -> bool:
    try:
        out = subprocess.run([_get_ffmpeg(), "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=15)
        return "h264_nvenc" in out.stdout
    except Exception:
        return False


def stitch(paths: list[str], out_path: str, progress) -> str:
    """Join `paths` into `out_path`. `progress(fraction)` is called as it
    goes. Returns "copy" or "encode"; raises RuntimeError with ffmpeg's
    last lines on failure."""
    probes = [_probe(p) for p in paths]
    total = sum(p["duration"] for p in probes) or 1.0
    same = len({p["key"] for p in probes}) == 1 and all(p["audio"] for p in probes)
    ffmpeg = _get_ffmpeg()

    list_file = None
    try:
        if same:
            fd, list_file = tempfile.mkstemp(suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for p in paths:
                    safe = p.replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{safe}'\n")
            cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy",
                   "-progress", "pipe:1", "-nostats", out_path]
            mode = "copy"
        else:
            w, h = collections.Counter(p["size"] for p in probes).most_common(1)[0][0]
            has_audio = all(p["audio"] for p in probes)
            cmd = [ffmpeg, "-y"]
            for p in paths:
                cmd += ["-i", p]
            chains, labels = [], []
            for i in range(len(paths)):
                chains.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=60,format=yuv420p[v{i}]")
                labels.append(f"[v{i}]" + (f"[{i}:a]" if has_audio else ""))
            graph = ";".join(chains) + ";" + "".join(labels) + \
                f"concat=n={len(paths)}:v=1:a={1 if has_audio else 0}[v]" + ("[a]" if has_audio else "")
            cmd += ["-filter_complex", graph, "-map", "[v]"]
            if has_audio:
                cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
            if _has_nvenc():
                cmd += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21"]
            else:
                cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]
            cmd += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", out_path]
            mode = "encode"

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
        tail = collections.deque(maxlen=12)

        def read_err():
            for line in proc.stderr:
                tail.append(line.rstrip())
        t = threading.Thread(target=read_err, daemon=True)
        t.start()
        for line in proc.stdout:
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                try:
                    progress(min(1.0, int(line.split("=")[1]) / 1e6 / total))
                except ValueError:
                    pass
        proc.wait()
        t.join(timeout=2)
        if proc.returncode != 0:
            raise RuntimeError("\n".join(tail) or f"ffmpeg exited with code {proc.returncode}")
        progress(1.0)
        return mode
    finally:
        if list_file and os.path.exists(list_file):
            os.remove(list_file)
