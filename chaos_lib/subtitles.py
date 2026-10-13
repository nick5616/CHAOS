"""
Voice-chat subtitles for clips: an .srt next to each clip, and the same
captions burned into the video with a bold, outlined style that reads on top
of gameplay.

Text comes from the clip's `caption` events (that window re-transcribed with
the larger subtitle model during analysis) when there are any, otherwise from
the whole-file `voice` transcript. Word timestamps split it into short cues.
With a separate mic track, the player's own lines ("me") get an accent colour.
"""

import os
import subprocess
import tempfile
import threading
from dataclasses import dataclass

MAX_LINE_CHARS = 42      # broadcast-caption line length; two lines fit at the font size below
MAX_LINES = 2
MAX_CUE_S = 4.0
GAP_SPLIT_S = 0.8        # a pause this long starts a new cue
MIN_CUE_S = 0.8
SENTENCE_MIN_CHARS = 15  # end a cue at . ! ? once it has at least this much text
ME_COLOUR = '&H003C96E8'  # CHAOS orange #e8963c, in ASS's &HAABBGGRR order

_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def options(config: dict) -> dict | None:
    """Subtitle settings when the checkbox is on, else None."""
    subs = config.get('subtitles') or {}
    if not subs.get('enabled'):
        return None
    return {'burn_in': subs.get('burn_in', True), 'write_srt': subs.get('write_srt', True)}


def caption_model_name(config: dict) -> str | None:
    """The Whisper model to re-transcribe clip windows with, or None when
    subtitles are off or would use the model the whole file already went through."""
    if options(config) is None:
        return None
    name = (config.get('subtitles') or {}).get('model', 'small')
    return None if name == config.get('whisper_model', 'base') else name


@dataclass
class Cue:
    start: float
    end: float
    text: str
    speaker: str | None = None


def segments_for_clip(events: list, start: float, end: float) -> list:
    """Speech segments (event details) overlapping [start, end): the caption
    transcript made for this window if there is one, else the voice transcript."""
    def overlapping(kind, window_ok=lambda d: True):
        return [e['details'] for e in events
                if e.get('type') == kind and window_ok(e['details'])
                and e['details'].get('end', e['details'].get('start', 0)) > start
                and e['details'].get('start', 0) < end]

    captions = overlapping('caption', lambda d: d.get('window') and
                           d['window'][0] <= start + 0.5 and d['window'][1] >= end - 0.5)
    segments = captions or overlapping('voice')
    return sorted((s for s in segments if s.get('text')), key=lambda s: s['start'])


def _words(segment: dict) -> list:
    """[(word, start, end)]. Older events without word timestamps get their
    text spread evenly over the segment."""
    if segment.get('words'):
        return [tuple(w) for w in segment['words']]
    tokens = segment['text'].split()
    span = max(segment.get('end', segment['start'] + 1) - segment['start'], 0.1) / max(len(tokens), 1)
    return [(t, segment['start'] + i * span, segment['start'] + (i + 1) * span) for i, t in enumerate(tokens)]


def _cues_for_speaker(words: list, speaker) -> list:
    cues, cur = [], []

    def flush():
        if cur:
            cues.append(Cue(cur[0][1], cur[-1][2], ' '.join(w for w, _, _ in cur), speaker))
            cur.clear()

    for word in words:
        if cur:
            text = ' '.join(w for w, _, _ in cur)
            if (word[1] - cur[-1][2] > GAP_SPLIT_S
                    or len(text) + 1 + len(word[0]) > MAX_LINE_CHARS * MAX_LINES
                    or word[2] - cur[0][1] > MAX_CUE_S
                    or (text[-1] in '.!?' and len(text) >= SENTENCE_MIN_CHARS)):
                flush()
        cur.append(word)
    flush()
    return cues


def build_cues(segments: list, clip_start: float, clip_len: float) -> list:
    """Cues timed relative to the clip. Each speaker's lines are split on their
    own, so overlapping talk on two tracks doesn't chop the other's sentences."""
    by_speaker: dict = {}
    for seg in segments:
        by_speaker.setdefault(seg.get('speaker'), []).extend(_words(seg))
    cues = []
    for speaker, words in by_speaker.items():
        words.sort(key=lambda w: w[1])
        mine = _cues_for_speaker(words, speaker)
        for i, cue in enumerate(mine):
            nxt = mine[i + 1].start if i + 1 < len(mine) else float('inf')
            # Stay up long enough to read, and linger briefly, without overlapping the next line
            cue.end = min(max(cue.end + 0.2, cue.start + MIN_CUE_S), nxt)
        cues.extend(mine)
    out = []
    for cue in sorted(cues, key=lambda c: c.start):
        start, end = cue.start - clip_start, cue.end - clip_start
        if end <= 0 or start >= clip_len:
            continue
        out.append(Cue(max(0.0, start), min(clip_len, end), cue.text, cue.speaker))
    return out


def wrap(text: str) -> list:
    """One line, or two of balanced length broken at the space nearest the middle."""
    if len(text) <= MAX_LINE_CHARS:
        return [text]
    mid = len(text) // 2
    spaces = [i for i, ch in enumerate(text) if ch == ' ']
    if not spaces:
        return [text]
    cut = min(spaces, key=lambda i: abs(i - mid))
    return [text[:cut], text[cut + 1:]]


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def write_srt(cues: list, path: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        for n, cue in enumerate(cues, start=1):
            f.write(f"{n}\n{_srt_time(cue.start)} --> {_srt_time(cue.end)}\n" + '\n'.join(wrap(cue.text)) + "\n\n")


def write_ass(cues: list, path: str, width: int, height: int) -> None:
    scale = height / 1080
    size, outline, shadow = round(60 * scale), round(3.5 * scale, 1), round(1.5 * scale, 1)
    # Lifted clear of CS2's bottom HUD row (health, armor, money, ammo)
    margin_h, margin_v = round(width * 0.08), round(height * 0.13)

    def style(name, colour):
        return (f"Style: {name},Arial,{size},{colour},&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,"
                f"100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1\n")

    with open(path, 'w', encoding='utf-8') as f:
        f.write("[Script Info]\nScriptType: v4.00+\n"
                f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
                "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
                "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                + style('Default', '&H00FFFFFF') + style('Me', ME_COLOUR) +
                "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for cue in cues:
            # Braces start override tags and backslashes escapes in ASS; neither belongs in speech.
            text = r'\N'.join(wrap(cue.text.replace('{', '(').replace('}', ')').replace('\\', '/')))
            f.write(f"Dialogue: 0,{_ass_time(cue.start)},{_ass_time(cue.end)},"
                    f"{'Me' if cue.speaker == 'me' else 'Default'},,0,0,0,,{text}\n")


_encoder_lock = threading.Lock()
_encoders: list | None = None
_X264 = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20']
_NVENC = ['-c:v', 'h264_nvenc', '-preset', 'p5', '-rc', 'vbr', '-cq', '20', '-b:v', '0']


def _encoder_choices(ffmpeg: str) -> list:
    """NVENC then libx264 if this ffmpeg and GPU can do NVENC (checked once
    with a tiny test encode), else just libx264."""
    global _encoders
    with _encoder_lock:
        if _encoders is None:
            test = subprocess.run(
                [ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=s=320x240:d=0.2',
                 *_NVENC, '-f', 'null', '-'],
                capture_output=True, creationflags=_NO_WINDOW,
            )
            _encoders = [_NVENC, _X264] if test.returncode == 0 else [_X264]
    return _encoders


def video_size(video_path: str) -> tuple[int, int]:
    from chaos_lib.clipper import _get_ffprobe
    out = subprocess.run(
        [_get_ffprobe(), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
         '-of', 'csv=p=0', video_path],
        capture_output=True, text=True, creationflags=_NO_WINDOW,
    ).stdout.strip()
    w, h = (int(x) for x in out.split(',')[:2])
    return w, h


def burn(ffmpeg: str, src: str, start: float, duration: float, cues: list, out_path: str) -> None:
    """Cut [start, start + duration) of `src` with the cues drawn in. This
    re-encodes, which also makes the cut frame-accurate so the .srt lines up."""
    width, height = video_size(src)
    with tempfile.TemporaryDirectory() as tmp:
        write_ass(cues, os.path.join(tmp, 'subs.ass'), width, height)
        base = [ffmpeg, '-y', '-ss', str(start), '-i', os.path.abspath(src), '-t', str(duration),
                '-map', '0:v:0', '-map', '0:a?', '-vf', 'ass=subs.ass']
        tail = ['-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', os.path.abspath(out_path)]
        err = b''
        # Run from the temp dir so the filter gets a bare file name: Windows
        # paths (C:\...) would need escaping inside a filter argument.
        for encoder in _encoder_choices(ffmpeg):  # NVENC can still fail, e.g. out of encoder sessions
            result = subprocess.run(base + encoder + tail, cwd=tmp, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, creationflags=_NO_WINDOW)
            if result.returncode == 0:
                return
            err = result.stderr
        raise RuntimeError(f"ffmpeg could not burn subtitles: {err.decode(errors='replace')[-400:]}")
