"""
Settings for the web UI: the config.yaml keys the Settings screen and setup
wizard may change, each with its type and range, so a bad value from the
page can't end up in the config.

Only settings the pipeline reads are listed. Left out on purpose:
chat_roi and the T/CT name colours (nothing reads them), and the
enemy-rage-chat weight (nothing produces chat events).

Keys are dotted paths into the config ("moments.mode").
"""

HSV_KEYS = ("red_hsv_lower1", "red_hsv_upper1", "red_hsv_lower2", "red_hsv_upper2")

# key -> (kind, min, max). kind: str, path, bool, int, float, names, roi, res, hsv, choice
SCHEMA = {
    "captures_folder": ("path", None, None),
    "data_folder": ("path", None, None),
    "final_clips_folder": ("path", None, None),
    "player_names": ("names", None, None),
    "killfeed_roi": ("roi", 0, 16384),
    "killfeed_roi_resolution": ("res", 1, 16384),
    "moments.mode": ("choice", ("off", "funny", "conversations"), None),
    "subtitles.enabled": ("bool", None, None),
    "gui.setup_complete": ("bool", None, None),
    "killfeed_rect_min_height": ("int", 10, 100),
    "killfeed_rect_max_height": ("int", 20, 200),
    "killfeed_rect_min_aspect_ratio": ("float", 1.0, 20.0),
    "killfeed_sample_interval_seconds": ("float", 0.5, 7.0),
    "clip_pre_buffer_seconds": ("float", 0.0, 30.0),
    "clip_post_buffer_seconds": ("float", 0.0, 30.0),
    "scoring_weights.kill": ("int", 0, 100),
    "scoring_weights.multi_kill_bonus": ("int", 0, 100),
    "scoring_weights.headshot_bonus": ("int", 0, 200),
    "scoring_weights.smoke_kill_bonus": ("int", 0, 200),
    "scoring_weights.team_hype_voice": ("int", 0, 100),
    "scoring_weights.audio_spike": ("int", 0, 100),
    "scoring_weights.banter": ("int", 0, 100),
    **{k: ("hsv", 0, 255) for k in HSV_KEYS},
}

# What "Reset detection tuning" puts back (everything but folders, names,
# regions and voice-chat choices).
TUNING_KEYS = [k for k in SCHEMA if k.startswith(("killfeed_rect", "killfeed_sample", "clip_", "scoring_weights", "red_hsv"))]


def _get(config: dict, key: str):
    node = config
    for part in key.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _set(config: dict, key: str, value):
    *parents, last = key.split(".")
    node = config
    for part in parents:
        node = node.setdefault(part, {})
    node[last] = value


def _clean(key: str, value):
    kind, lo, hi = SCHEMA[key]
    if kind in ("str", "path"):
        if not isinstance(value, str):
            raise ValueError(f"{key} must be text")
        return value.strip()
    if kind == "bool":
        return bool(value)
    if kind == "choice":
        if value not in lo:
            raise ValueError(f"{key} must be one of {', '.join(lo)}")
        return value
    if kind == "int":
        return max(lo, min(hi, int(round(float(value)))))
    if kind == "float":
        return round(max(lo, min(hi, float(value))), 2)
    if kind == "names":
        if not isinstance(value, list):
            raise ValueError("player_names must be a list")
        return [str(n).strip() for n in value if str(n).strip()]
    if kind == "roi":
        x1, y1, x2, y2 = (max(lo, min(hi, int(round(float(v))))) for v in value)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("The killfeed region needs a positive width and height")
        return [x1, y1, x2, y2]
    if kind == "res":
        if value is None:
            return None
        w, h = (max(lo, min(hi, int(v))) for v in value)
        return [w, h]
    if kind == "hsv":
        hmax = 180
        h, s, v = (int(round(float(x))) for x in value)
        return [max(0, min(hmax, h)), max(lo, min(hi, s)), max(lo, min(hi, v))]
    raise ValueError(f"Unknown setting {key}")


def read(config: dict) -> dict:
    return {k: _get(config, k) for k in SCHEMA}


def apply(config: dict, patch: dict) -> dict:
    """Validate `patch` and write it into `config` (in place). Unknown keys
    are an error, so typos don't silently do nothing."""
    for key in patch:
        if key not in SCHEMA:
            raise ValueError(f"Unknown setting {key}")
    for key, value in patch.items():
        _set(config, key, _clean(key, value))
    return config
