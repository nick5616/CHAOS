# === FILE: chaos_lib/analyzers.py ===
import os
import json
import time
import cv2
import whisper
import librosa
import numpy as np
import shutil
import subprocess
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

# --- KILLFEED ROW LAYOUT ------------------------------------------------------
#
# A CS2 killfeed row reads, left to right:
#     [blind] killer [+ assister] WEAPON [no-scope] [smoke] [wallbang] [headshot] victim
# Names are always drawn in a team colour (yellow T, blue CT) while every icon
# is white or grey, so colour alone separates icons from names. That gives the
# row's structure from pixels: the first icon after the killer's name is the
# weapon, the icons between it and the victim's name are the kill's modifiers,
# and an icon before the killer's name is the "attacker was blind" mark. The
# killer and victim are then OCR'd from their own crops, so an icon can't be
# misread as part of a name and a victim OCR missed can't be confused with
# the last word of the killer's name.

_ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'killfeed_icons')
# Template file stem (before any "_2" suffix for a second example) -> event detail flag.
# Before the killer's name only "blind" can appear; after the weapon, the rest.
_ICON_FLAGS = {
    'blind': 'attackerBlind',
    'noscope': 'noScope',
    'smoke': 'throughSmoke',
    'wallbang': 'wallbang',
    'headshot': 'isHeadshot',
}
_ICON_GRID = 20          # icons are compared as masks resampled to this square grid
_ICON_MIN_SCORE = 0.6    # IoU with the best template; measured: matches score 0.7+, other icons under 0.45
_ICON_MAX_ASPECT = 0.4   # |log(aspect ratio)| difference allowed between an icon and a template
_ICON_MIN_H = 0.5        # an icon's height and area relative to the row's tallest icon
_ICON_MIN_AREA = 0.2
_icon_templates = None


def _icon_mask(img) -> np.ndarray:
    """White/grey pixels: icons (and the '+' before an assister), not names."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    v = hsv[..., 2]
    # Relative to the row's brightest pixels, so a row fading out still segments
    return ((v > max(110, 0.55 * np.percentile(v, 99.5))) & (hsv[..., 1] < 70)).astype(np.uint8)


def _text_mask(img) -> np.ndarray:
    """Team-coloured pixels: player names. Red is left out (the row's border)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    red = (h < 8) | (h > 172)
    return ((v > max(90, 0.45 * np.percentile(v, 99.5))) & (s >= 70) & ~red).astype(np.uint8)


def _icon_blobs(mask: np.ndarray, height: int) -> list:
    """(x0, x1, mask_crop) for each icon-sized blob, left to right. Nearby
    pieces (the headshot's bullet trail, the gaps in a weapon) are joined
    first so each icon is one blob. Sizes are relative to the tallest blob:
    icons fill a different share of the row at different HUD scales, and the
    smoke cloud is flatter than the rest."""
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(1, height // 10), max(1, height // 6)))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(mask, k))
    comps = [(i, *stats[i][:4]) for i in range(1, n) if stats[i][3] >= 0.3 * height]
    if not comps:
        return []
    tallest = max(c[4] for c in comps)
    blobs = []
    for i, x, y, w, h in comps:
        # Drops the '+' before an assister, text accents and stray pixels
        if h >= _ICON_MIN_H * tallest and w * h >= _ICON_MIN_AREA * tallest * tallest:
            blobs.append((x, x + w, mask[y:y + h, x:x + w] * (labels[y:y + h, x:x + w] == i)))
    return sorted(blobs, key=lambda b: b[0])


def _name_columns(img) -> np.ndarray:
    """x positions holding name text: team-coloured strokes of letter size
    that don't touch the crop's edge (what's left of the red border does)."""
    mask = _text_mask(img)
    h, w = mask.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, cw, ch, _ = stats[i]
        touches_edge = x == 0 or y == 0 or x + cw >= w or y + ch >= h
        keep[i] = ch >= 0.25 * h and not touches_edge
    return np.flatnonzero(keep[labels].any(axis=0))


def _icon_signature(mask: np.ndarray):
    """(grid, aspect) of an icon mask, cropped to its pixels; None if empty."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)
    grid = cv2.resize(crop, (_ICON_GRID, _ICON_GRID), interpolation=cv2.INTER_AREA) > 0.5
    return grid, crop.shape[1] / crop.shape[0]


def _load_icon_templates() -> dict:
    """{name: [(grid, aspect)]} from assets/killfeed_icons. Each template image
    goes through the same segmentation as a row, so both are compared alike."""
    global _icon_templates
    if _icon_templates is None:
        _icon_templates = {}
        for fname in sorted(os.listdir(_ICON_DIR)) if os.path.isdir(_ICON_DIR) else []:
            stem = os.path.splitext(fname)[0].split('_')[0]
            img = cv2.imread(os.path.join(_ICON_DIR, fname))
            if stem not in _ICON_FLAGS or img is None:
                continue
            mask = _icon_mask(img)
            blobs = _icon_blobs(mask, img.shape[0])
            # The template is the icon's main shape (the wallbang door without its arrow, as in a row)
            main = max(blobs, key=lambda b: int(b[2].sum()))[2] if blobs else mask
            sig = _icon_signature(main)
            if sig is not None:
                _icon_templates.setdefault(stem, []).append(sig)
    return _icon_templates


def _classify_icon(mask: np.ndarray, allowed) -> tuple:
    """(name, score) of the best-matching template among `allowed`, or (None, best score)."""
    sig = _icon_signature(mask)
    if sig is None:
        return None, 0.0
    grid, aspect = sig
    best, best_score = None, 0.0
    for name, examples in _load_icon_templates().items():
        if name not in allowed:
            continue
        for t_grid, t_aspect in examples:
            if abs(np.log(aspect / t_aspect)) > _ICON_MAX_ASPECT:
                continue
            score = (grid & t_grid).sum() / max(1, (grid | t_grid).sum())
            if score > best_score:
                best, best_score = name, float(score)
    return (best, best_score) if best_score >= _ICON_MIN_SCORE else (None, best_score)


def _row_layout(row_img) -> dict | None:
    """Split a killfeed row into killer, assister (None without one) and
    victim crops, plus the kill's flags.
    None when the row can't be read whole (no weapon icon, or no victim name
    after the icons, e.g. mid-fade): better to wait for the next sample than
    record a kill with half its names."""
    border = max(2, round(row_img.shape[0] * 0.09))
    inner = row_img[border:-border, border:-border]
    if inner.size == 0:
        return None
    height = inner.shape[0]
    blobs = _icon_blobs(_icon_mask(inner), height)
    text_cols = _name_columns(inner)
    if not blobs or len(text_cols) == 0:
        return None
    name_x0 = int(text_cols[0])
    after = [b for b in blobs if b[0] > name_x0]
    if not after:
        return None
    weapon_x0 = after[0][0]
    icons_x1 = max(b[1] for b in after)
    victim_cols = text_cols[text_cols >= icons_x1]
    killer_cols = text_cols[text_cols < weapon_x0]
    if len(victim_cols) == 0 or len(killer_cols) == 0:
        return None

    # "killer + assister": the '+' is a small white glyph between two names
    plus = _find_plus(inner, name_x0, weapon_x0, killer_cols)

    flags = {flag: False for flag in _ICON_FLAGS.values()}
    before = [b for b in blobs if b[1] <= name_x0]
    for allowed, group in ((('blind',), before), (tuple(n for n in _ICON_FLAGS if n != 'blind'), after[1:])):
        for _, _, mask in group:
            name, _ = _classify_icon(mask, allowed)
            if name:
                flags[_ICON_FLAGS[name]] = True

    # Cut at the structural boundaries, not tight to the letters: stylised
    # names (superscripts, thin script) don't all register as text pixels
    killer_x0 = max((b[1] for b in before), default=0)
    return {
        'killer_img': inner[:, killer_x0:plus[0] if plus else weapon_x0],
        'assister_img': inner[:, plus[1]:weapon_x0] if plus else None,
        'victim_img': inner[:, icons_x1:],
        'flags': flags,
    }


def _find_plus(inner, x0: int, x1: int, name_cols: np.ndarray):
    """(x0, x1) of the '+' between a killer and an assister, or None: a
    roughly square white glyph, a third to a half of the row tall, with name
    text on both sides."""
    height = inner.shape[0]
    n, labels, stats, _ = cv2.connectedComponentsWithStats(_icon_mask(inner[:, x0:x1]))
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (0.2 * height <= h <= 0.6 * height and 0.6 <= w / h <= 1.6
                and np.any(name_cols < x0 + x) and np.any(name_cols >= x0 + x + w)):
            continue
        glyph = labels[y:y + h, x:x + w] == i
        # Full strokes through the middle both ways: a '+', not the 'X's some clan tags wear
        if glyph[h // 2 - 1:h // 2 + 2].any(axis=0).mean() >= 0.8 and                 glyph[:, w // 2 - 1:w // 2 + 2].any(axis=1).mean() >= 0.8 and area < 0.7 * w * h:
            return x0 + x, x0 + x + w
    return None


_OCR_MIN_HEIGHT = 64  # px; killfeed text at 1080p is ~12 px tall, too small for EasyOCR to read reliably


def _ocr_text(reader, img) -> str:
    if img.shape[0] < _OCR_MIN_HEIGHT:
        f = _OCR_MIN_HEIGHT / img.shape[0]
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    # A margin of the row's own background: EasyOCR misses characters touching the edge
    pad = max(4, img.shape[0] // 4)
    img = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    return " ".join(reader.readtext(img, detail=0, paragraph=True)).strip()


def _read_row(reader, row_img) -> dict | None:
    """{killer, assister, victim, flags, raw_text} for a killfeed row, or None
    when it can't be read whole."""
    layout = _row_layout(row_img)
    if layout is None:
        return None
    killer = _ocr_text(reader, layout['killer_img'])
    victim = _ocr_text(reader, layout['victim_img'])
    if not killer or not victim:
        return None
    assister = _ocr_text(reader, layout['assister_img']) if layout['assister_img'] is not None else None
    if layout['assister_img'] is None and ' + ' in killer:
        killer, _, assister = (part.strip() for part in killer.partition(' + '))  # '+' missed by _find_plus
    return {
        'killer': killer,
        'assister': assister or None,
        'victim': victim,
        'flags': layout['flags'],
        'raw_text': f"{killer} + {assister} {victim}" if assister else f"{killer} {victim}",
    }


def _is_player_kill(row: dict, player_names) -> bool:
    """CS2 draws the red border on every row involving the local player: their
    kills, but also their deaths and assists. Their name as the killer is
    their kill; as the victim or assister it isn't. A row with none of their
    names (none known, or they played under another) trusts the border."""
    for name in player_names:
        key = _name_key(name)
        if fuzz.ratio(_name_key(row['killer']), key) >= 80:
            return True
        if any(part and fuzz.ratio(_name_key(part), key) >= 80 for part in (row['victim'], row['assister'])):
            return False
    return True


def _name_key(name: str) -> str:
    return ''.join(ch for ch in name.lower() if ch.isalnum())


def infer_player_name(rows: list, min_rows: int = 3, min_share: float = 0.6) -> str | None:
    """The local player's name, read off their red-bordered killfeed rows
    ({killer, assister, victim}, as _read_row gives them).

    Every red row involves the player (their kill, death or assist), so
    their name is the one that shows up as killer, assister or victim in
    nearly all of them, while victims and teammates vary. Worked out per
    video, so it follows name changes without anything configured. None
    when there are too few rows to tell."""
    if len(rows) < min_rows:
        return None
    roles = [[r[k] for k in ('killer', 'assister', 'victim') if r.get(k)] for r in rows]
    candidates = {}
    for names in roles:
        for name in names:
            if len(_name_key(name)) >= 2:
                candidates.setdefault(_name_key(name), name)
    best, best_score = None, (0, 0)
    for key, name in candidates.items():
        # Each row's closest role to this name, OCR noise allowed
        matches = [max(fuzz.ratio(_name_key(n), key) for n in names) for names in roles]
        hits = sum(m >= 80 for m in matches)
        score = (hits, sum(m for m in matches if m >= 80))
        if score > best_score:
            best, best_score = name, score
    if best is None or best_score[0] < max(1, min_share * len(rows)):
        return None
    return best


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

# Bump when kill detection changes: cached results from older versions are
# analysed again from scratch.
# 2: killer/victim read from either side of the icons; icons matched against
#    assets/killfeed_icons (no-scope, smoke, wallbang, blind, headshot)
KILLFEED_VERSION = 2

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
_SAME_MASK_MAX = 0.13         # same row by _mask_signature (see there)

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


def _mask_signature(row_img) -> np.ndarray:
    """Like _row_signature, but from the colour masks of names and icons,
    which the game showing through the panel barely changes. Distances
    measured on real footage: the same row seen at different times scores
    up to 0.105, different rows 0.163 and up."""
    border = max(2, round(row_img.shape[0] * 0.09))
    inner = row_img[border:-border, border:-border]
    mask = (_text_mask(inner) | _icon_mask(inner)).astype(np.float32)
    return cv2.resize(mask, _SIG_SIZE, interpolation=cv2.INTER_AREA)


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

    red_rows = []    # every distinct red row: the player's kills, deaths and assists
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
            msig = _mask_signature(row_img)
            if any(_row_distance(k['sig'], k['w'], sig, w) < _SAME_ROW_MAX
                   or _row_distance(k['msig'], k['w'], msig, w) < _SAME_MASK_MAX for k in on_screen):
                continue  # same row as an earlier sample: already counted, no OCR needed

            parsed = _read_row(reader, row_img)
            if not parsed:
                continue  # not readable whole yet (e.g. fading in): the next sample tries again

            # The fingerprint can miss (e.g. the row is mid-fade), so fall back
            # to the victim name before deciding this is a new kill.
            victims = {k['victim']: k for k in on_screen}
            match = _find_fuzzy_victim(parsed['victim'], victims)
            if match:
                victims[match].update(sig=sig, msig=msig, w=w)  # match by pixels next time
                continue

            # Whether this is the player's kill, death or assist is decided
            # once all rows are in (see below), so time every row now.
            appeared_idx = frame_idx
            if prev_idx is not None:
                appeared_idx = _find_appearance(cap, fps, prev_idx, frame_idx, sig, w, on_screen, crop_box, params)
            appeared = appeared_idx / fps
            on_screen.append({'sig': sig, 'msig': msig, 'w': w, 'victim': parsed['victim'], 'appeared': appeared})
            # copy(): a slice would keep the whole frame alive
            red_rows.append({**parsed, 'appeared': appeared, 'img': row_img.copy()})

        prev_idx = frame_idx
        _yield_if_gaming(time.perf_counter() - t0)

    cap.release()

    # Red rows are the player's kills, deaths and assists; only a row with the
    # player's name as killer is their kill. The name is read off this video's
    # own rows; configured names are the fallback when there are too few rows
    # to tell, and with neither, every red row counts.
    inferred = infer_player_name(red_rows)
    names = [inferred] if inferred else player_names

    kill_events = []
    for row in red_rows:
        if not _is_player_kill(row, names):
            continue
        _save_debug_screenshot(config, row['img'], video_path, "kill_NEW", row['appeared'],
                               suffix=f"_{row['victim']}")
        kill_events.append({
            "source_video": video_path,
            "timestamp_seconds": row['appeared'],
            "type": "kill",
            "details": {
                "raw_text": row['raw_text'],
                "detected_player": row['killer'],
                "inferred_player": inferred,
                "assister": row['assister'],
                "victim": row['victim'],
                **row['flags'],
            },
        })
    kill_events.sort(key=lambda e: e['timestamp_seconds'])
    return kill_events


def killfeed_info(video_path: str) -> dict:
    """Records which version of kill detection produced a video's cached kills."""
    return {"source_video": video_path, "timestamp_seconds": 0.0, "type": "killfeed_info",
            "details": {"version": KILLFEED_VERSION}}


def kills_are_stale(events: list) -> bool:
    info = next((e['details'] for e in events if e.get('type') == 'killfeed_info'), None)
    return not info or info.get('version', 0) < KILLFEED_VERSION


# --- AUDIO ------------------------------------------------------------------
#
# ShadowPlay saves either one mixed audio track or, with "Separate both
# tracks", game/system audio (track 1, which also carries in-game voice chat
# and Discord) plus the microphone alone (track 2). With two tracks each one is
# transcribed on its own, so subtitles can tell the player's own lines apart;
# loudness and laughter run on the two summed.

# Bump when audio events change shape: cached results from older versions get
# their audio analysis redone (kills are kept).
# 3: lines over silent audio dropped (Whisper says "you" at the end of every
#    30 s window of a silent track)
AUDIO_VERSION = 3

_SAMPLE_RATE = 16000
_RMS_HOP = 512
_GAMING_CHUNK_S = 30  # Whisper's own window; while gaming we transcribe one at a time and back off between

# Word timestamps feed subtitle timing. Not conditioning on the previous text
# stops Whisper from looping one line over and over through noisy stretches.
_TRANSCRIBE_OPTS = {'word_timestamps': True, 'condition_on_previous_text': False}
# Subtitles get beam search: greedy decoding of a noisy window sometimes
# returns one word for twenty seconds of talk; beam search never did that in
# testing, at a few seconds per clip.
_CAPTION_OPTS = {'beam_size': 5, 'best_of': 5}
# Whisper's well-known inventions over silence/music (it was trained on subtitled video)
# Speech can't come out of audio this quiet (RMS, ~-55 dBFS); Whisper still
# "hears" lines there, most often a lone "you".
_SILENCE_RMS = 10 ** (-55 / 20)
_HALLUCINATIONS = ('thanks for watching', 'thank you for watching', 'subtitles by',
                   'please subscribe', 'amara.org', 'transcribed by')


def probe_audio_streams(video_path: str) -> int:
    from chaos_lib.clipper import _get_ffprobe
    out = subprocess.run(
        [_get_ffprobe(), '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index',
         '-of', 'csv=p=0', video_path],
        capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    ).stdout
    return len([line for line in out.splitlines() if line.strip()])


def load_track(video_path: str, index: int) -> np.ndarray:
    """One audio track as 16 kHz mono float32, decoded in memory (what
    whisper.load_audio does, but with the track chosen)."""
    from chaos_lib.clipper import _get_ffmpeg
    out = subprocess.run(
        [_get_ffmpeg(), '-nostdin', '-threads', '0', '-i', video_path, '-map', f'0:a:{index}',
         '-f', 's16le', '-ac', '1', '-acodec', 'pcm_s16le', '-ar', str(_SAMPLE_RATE), '-'],
        capture_output=True, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    ).stdout
    return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0


def decode_tracks(video_path: str) -> list:
    """[(speaker, audio)]: [(None, mixed)] for one track, [("others", game), ("me", mic)] for two."""
    n = probe_audio_streams(video_path)
    if n == 0:
        return []
    if n == 1:
        return [(None, load_track(video_path, 0))]
    return [('others', load_track(video_path, 0)), ('me', load_track(video_path, 1))]


def _mix(tracks: list) -> np.ndarray:
    if len(tracks) == 1:
        return tracks[0][1]
    length = max(len(a) for _, a in tracks)
    mixed = np.zeros(length, np.float32)
    for _, a in tracks:
        mixed[:len(a)] += a
    return np.clip(mixed, -1.0, 1.0)


def _transcribe(model, audio: np.ndarray, **opts) -> list:
    fp16 = getattr(model, 'device', None) is not None and model.device.type == 'cuda'
    if not (_gaming_event is not None and _gaming_event.is_set()):
        return model.transcribe(audio, fp16=fp16, **opts)['segments']
    # Gaming: one 30 s window per call so the GPU gets long idle gaps instead
    # of one multi-second burst that would stutter the game.
    segments = []
    chunk = _GAMING_CHUNK_S * _SAMPLE_RATE
    for start in range(0, len(audio), chunk):
        t0 = time.perf_counter()
        offset = start / _SAMPLE_RATE
        for seg in model.transcribe(audio[start:start + chunk], fp16=fp16, **opts)['segments']:
            words = [{**w, 'start': w['start'] + offset, 'end': w['end'] + offset} for w in seg.get('words') or []]
            segments.append({**seg, 'start': seg['start'] + offset, 'end': seg['end'] + offset, 'words': words})
        _yield_if_gaming(time.perf_counter() - t0)
    return segments


def _keep_segment(seg: dict) -> bool:
    text = seg.get('text', '').strip().lower()
    if not text or any(h in text for h in _HALLUCINATIONS):
        return False
    # Long segments with hardly any words are Whisper inventing a line over
    # gunfire (seen: one 30 s "segment" of six words)
    duration = seg.get('end', 0) - seg.get('start', 0)
    if duration > 8 and len(text.split()) / duration < 0.7:
        return False
    # Whisper's own silence rule (likely no speech *and* low confidence; real
    # lines over gunfire often score no_speech 0.5-0.6), plus outright guesses,
    # plus repetition loops, which compress far better than real speech
    logprob = seg.get('avg_logprob', 0)
    if (seg.get('no_speech_prob', 0) > 0.6 and logprob < -1.0) or logprob < -1.5:
        return False
    return seg.get('compression_ratio', 0) <= 2.4


def _is_silent(audio: np.ndarray, start: float, end: float) -> bool:
    part = audio[int(start * _SAMPLE_RATE):max(int(end * _SAMPLE_RATE), int(start * _SAMPLE_RATE) + 1)]
    return part.size == 0 or float(np.sqrt(np.mean(part ** 2))) < _SILENCE_RMS


def transcribe_tracks(model, tracks: list, config: dict | None, video_path: str, event_type: str = 'voice',
                      start: float = 0.0, end: float | None = None, **decode_opts) -> list:
    """Voice events for [start, end) of every track, in time order."""
    # Whisper otherwise guesses the language from the first 30 s, which in a
    # match is often gunfire: seen guessing wrong and garbling a whole file.
    # (No initial_prompt: priming it with gamer phrases measurably lost lines.)
    language = (config or {}).get('whisper_language', 'en')
    opts = {**_TRANSCRIBE_OPTS, 'language': None if language in (None, '', 'auto') else language, **decode_opts}
    a, b = int(start * _SAMPLE_RATE), None if end is None else int(end * _SAMPLE_RATE)
    events = []
    for speaker, audio in tracks:
        piece = audio[a:b]
        if piece.size < _SAMPLE_RATE // 4 or not np.any(np.abs(piece) > _SILENCE_RMS):
            continue  # too short, or a silent track: nothing to transcribe
        for seg in _transcribe(model, piece, **opts):
            if not _keep_segment(seg) or _is_silent(piece, seg['start'], seg['end']):
                continue
            details = {
                "text": seg['text'].strip(),
                "start": round(seg['start'] + start, 2),
                "end": round(seg['end'] + start, 2),
                "speaker": speaker,
                "words": [[w['word'].strip(), round(w['start'] + start, 2), round(w['end'] + start, 2)]
                          for w in seg.get('words') or [] if w['word'].strip()],
                "avg_logprob": round(float(seg.get('avg_logprob', 0.0)), 3),
            }
            events.append({"source_video": video_path, "timestamp_seconds": details['start'],
                           "type": event_type, "details": details})
    events.sort(key=lambda e: e['timestamp_seconds'])
    return events


def _loudness_spikes(audio: np.ndarray, video_path: str) -> list:
    """One event per contiguous run of loud frames (at its peak), not one per 32 ms frame."""
    from chaos_lib.laughter import contiguous_runs
    rms = librosa.feature.rms(y=audio, frame_length=2048, hop_length=_RMS_HOP)[0]
    if len(rms) == 0:
        return []
    rms_normalized = (rms - np.min(rms)) / (np.max(rms) - np.min(rms) + 1e-6)
    events = []
    for start, end in contiguous_runs(rms_normalized > 0.8):
        peak = start + int(np.argmax(rms_normalized[start:end]))
        events.append({
            "source_video": video_path,
            "timestamp_seconds": float(librosa.frames_to_time(peak, sr=_SAMPLE_RATE, hop_length=_RMS_HOP)),
            "type": "audio_spike",
            "details": {"intensity": float(rms_normalized[peak])},
        })
    return events


def analyze_audio(video_path: str, model, config: dict | None = None, laugh_model=None, tracks=None) -> list:
    """Voice, loudness and (with `laugh_model`) laughter/excitement events, plus
    one `audio_info` event recording what was analysed, for cache checks."""
    from chaos_lib import laughter
    try:
        # ffmpeg decodes straight to 16 kHz mono in memory: one decode per
        # track feeds Whisper, loudness and laughter, no temp WAV on disk.
        tracks = decode_tracks(video_path) if tracks is None else tracks
        info = {"version": AUDIO_VERSION, "duration": 0.0, "tracks": len(tracks),
                "laughter": laugh_model is not None, "captions_model": None}
        events = [{"source_video": video_path, "timestamp_seconds": 0.0, "type": "audio_info", "details": info}]
        if not tracks:
            return events
        mixed = _mix(tracks)
        info["duration"] = round(len(mixed) / _SAMPLE_RATE, 2)

        events += transcribe_tracks(model, tracks, config, video_path)
        events += _loudness_spikes(mixed, video_path)
        if laugh_model is not None:
            moments_cfg = (config or {}).get('moments', {})
            on_gpu = next(laugh_model.parameters()).device.type == 'cuda'
            events += laughter.detect(
                laugh_model, mixed, video_path,
                laugh_threshold=moments_cfg.get('laughter_threshold', 0.05),
                excite_threshold=moments_cfg.get('excitement_threshold', 0.2),
                hop_s=0.5 if on_gpu else 1.0,  # half the work on CPU, at half the time resolution
                yield_fn=_yield_if_gaming,
            )
        return events
    except Exception as e:
        print(f"  - Error processing audio for {os.path.basename(video_path)}: {e}")
        return []


_CHUNK_MAX_S = 12.0  # speech runs are merged into chunks up to this long for the chunked pass


def _speech_chunks(runs: list, start: float, end: float) -> list:
    """[a, b) chunks covering the speech runs inside [start, end), neighbours
    merged while the chunk stays short, long runs split."""
    chunks = []
    for d in runs:
        a, b = max(start, d['start'] - 0.3), min(end, d['end'] + 0.3)
        if b <= a:
            continue
        if chunks and b - chunks[-1][0] <= _CHUNK_MAX_S:
            chunks[-1][1] = b
            continue
        while b - a > _CHUNK_MAX_S:
            chunks.append([a, a + _CHUNK_MAX_S])
            a += _CHUNK_MAX_S
        chunks.append([a, b])
    return chunks


def _best_transcript(window_pass: list, chunk_pass: list, chunks: list) -> list:
    """For each chunk of speech, the words of whichever pass heard more in it.
    Whisper on noisy game audio drops lines unpredictably: decoding a whole
    window loses some, decoding each burst of speech on its own loses others.
    Choosing by word timestamps (not whole segments) means one run-on line
    spanning several chunks can't repeat what the other pass already says."""
    def words(evs, pass_id):
        return [(w, s, e, pass_id, n, ev) for n, ev in enumerate(evs) for w, s, e in ev['details']['words']]

    def chunk_of(t):
        return next((i for i, (a, b) in enumerate(chunks) if a <= t < b), None)

    window_words, chunk_words = words(window_pass, 0), words(chunk_pass, 1)
    winner = []
    for a, b in chunks:
        in_w = sum(1 for w in window_words if a <= (w[1] + w[2]) / 2 < b)
        in_c = sum(1 for w in chunk_words if a <= (w[1] + w[2]) / 2 < b)
        winner.append(1 if in_c > in_w else 0)
    # Words between chunks (speech the detector didn't flag) come from the window pass
    chosen = sorted((w for w in window_words + chunk_words
                     if (winner[i] if (i := chunk_of((w[1] + w[2]) / 2)) is not None else 0) == w[3]),
                    key=lambda w: w[1])

    # Rebuild lines: consecutive chosen words from the same source line
    lines = []
    for w in chosen:
        if lines and lines[-1][0] == (w[3], w[4]):
            lines[-1][1].append(w)
        else:
            lines.append(((w[3], w[4]), [w]))
    out = []
    for _, ws in lines:
        src = ws[0][5]
        details = {**src['details'], 'text': ' '.join(w[0] for w in ws), 'start': ws[0][1], 'end': ws[-1][2],
                   'words': [[w[0], w[1], w[2]] for w in ws]}
        out.append({**src, 'timestamp_seconds': details['start'], 'details': details})
    return out


def caption_clip_windows(video_path: str, events: list, config: dict, model, tracks: list) -> list:
    """Re-transcribe just the windows that will become clips with the (larger)
    subtitle model: `caption` events, each tagged with the window it was made
    for. Whole-file transcription stays on the small, fast model."""
    from chaos_lib import correlator
    events = [e for e in events if e['type'] != 'caption']
    runs = sorted((e['details'] for e in events if e['type'] == 'speech'), key=lambda d: d['start'])
    captions = []
    for h in correlator.correlate_video_events(video_path, events, config):
        start, end = max(0.0, h['clip_start']), h['clip_end']
        lines = transcribe_tracks(model, tracks, config, video_path, 'caption', max(0.0, start - 0.5), end + 0.5,
                                  **_CAPTION_OPTS)
        chunks = _speech_chunks([d for d in runs if d['end'] > start and d['start'] < end],
                                max(0.0, start - 0.5), end + 0.5)
        if chunks:
            chunked = [ev for a, b in chunks
                       for ev in transcribe_tracks(model, tracks, config, video_path, 'caption', a, b, **_CAPTION_OPTS)]
            lines = _best_transcript(lines, chunked, chunks)
        for ev in lines:
            d = ev['details']
            if d['end'] <= start or d['start'] >= end:
                continue
            d['window'] = [round(start, 2), round(end, 2)]
            # Kept inside the window even when the line started just before it,
            # so it lands in this clip's events_in_window.
            ev['timestamp_seconds'] = max(d['start'], start)
            captions.append(ev)
    return captions


def audio_is_stale(events: list, config: dict, check_captions: bool = True) -> bool:
    """True when cached events predate the current audio analysis or lack what
    the current settings need (laughter for moments, captions for subtitles)."""
    from chaos_lib import moments, subtitles
    info = next((e['details'] for e in events if e.get('type') == 'audio_info'), None)
    if not info or info.get('version', 0) < AUDIO_VERSION:
        return True
    if moments.enabled(config) and not info.get('laughter'):
        return True
    wanted = subtitles.caption_model_name(config)
    return check_captions and wanted is not None and info.get('captions_model') != wanted


# ---------------------------------------------------------------------------
# Worker-process helpers for parallel analysis
# ---------------------------------------------------------------------------

_worker_ocr = None
_worker_whisper = None
_worker_laughter = None
_worker_caption_whisper = None


def _init_analysis_worker(whisper_model_name: str, device: str = 'cpu', torch_threads: int = 1,
                          gaming_event=None, data_folder: str | None = None,
                          caption_model_name: str | None = None) -> None:
    """Runs once in each worker process to load models into module globals.
    `data_folder` set loads the laughter model; `caption_model_name` a second
    Whisper for subtitles."""
    global _worker_ocr, _worker_whisper, _worker_laughter, _worker_caption_whisper, _gaming_event
    import torch
    import easyocr as _easyocr
    # Workers run side by side; each takes its share of the cores instead of
    # every one of them spinning up a thread per core.
    torch.set_num_threads(torch_threads)
    cv2.setNumThreads(torch_threads)
    _gaming_event = gaming_event
    _worker_ocr = _easyocr.Reader(['en'], gpu=(device == 'cuda'), verbose=False)
    _worker_whisper = whisper.load_model(whisper_model_name, device=device)
    if data_folder:
        try:
            from chaos_lib import laughter
            _worker_laughter = laughter.load_model(data_folder, device)
        except Exception as e:
            print(f"  - Laughter model unavailable, continuing without it: {e}")
    if caption_model_name:
        _worker_caption_whisper = whisper.load_model(caption_model_name, device=device)


def _audio_events(video_path: str, config: dict) -> list:
    tracks = decode_tracks(video_path)
    events = analyze_audio(video_path, _worker_whisper, config, _worker_laughter, tracks)
    return events, tracks


def _add_captions(video_path: str, events: list, config: dict, tracks: list) -> list:
    if _worker_caption_whisper is None or not tracks:
        return events
    events = events + caption_clip_windows(video_path, events, config, _worker_caption_whisper, tracks)
    from chaos_lib.subtitles import caption_model_name
    for e in events:
        if e['type'] == 'audio_info':
            e['details']['captions_model'] = caption_model_name(config)
    return events


def _analyze_video_worker(video_path: str, config: dict) -> list:
    """Runs in a worker process. Uses module-level models loaded by the initializer."""
    kill_events = analyze_killfeed(video_path, config, _worker_ocr) + [killfeed_info(video_path)]
    try:
        audio_events, tracks = _audio_events(video_path, config)
    except Exception as e:
        print(f"  - Error processing audio for {os.path.basename(video_path)}: {e}")
        audio_events, tracks = [], []
    return _add_captions(video_path, kill_events + audio_events, config, tracks)


def _reanalyze_audio_worker(video_path: str, config: dict, cached_events: list) -> list:
    """Redo only the audio analysis of a video whose cached audio events are
    stale; its kills (the expensive OCR part) are kept from the cache."""
    kept = [e for e in cached_events if e['type'] in ('kill', 'chat', 'killfeed_info')]
    try:
        audio_events, tracks = _audio_events(video_path, config)
    except Exception as e:
        print(f"  - Error processing audio for {os.path.basename(video_path)}: {e}")
        audio_events, tracks = [], []
    return _add_captions(video_path, kept + audio_events, config, tracks)


def make_analysis_pool(config: dict, plan, gaming_event=None, progress_callback=None):
    """Process pool sized by `plan` (see chaos_lib.resources). Always uses the
    spawn start method: worker processes initialise CUDA themselves, which is
    unsafe in a forked child. `progress_callback(done, total)` reports the
    one-time laughter model download."""
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    from chaos_lib import laughter, moments, subtitles
    laugh_folder = None
    if moments.enabled(config):
        # Downloaded here, once, rather than by every worker racing for it.
        try:
            laughter.ensure_checkpoint(config['data_folder'], progress_callback)
            laugh_folder = config['data_folder']
        except Exception as e:
            print(f"  - Could not download the laughter model, continuing without it: {e}")
    return ProcessPoolExecutor(
        max_workers=plan.max_workers,
        mp_context=multiprocessing.get_context('spawn'),
        initializer=_init_analysis_worker,
        initargs=(config['whisper_model'], plan.device, plan.torch_threads, gaming_event,
                  laugh_folder, subtitles.caption_model_name(config)),
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
