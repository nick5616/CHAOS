"""
The Highlights screen's data: ordered_highlights.json from the last run,
with each clip's file located and its events made relative to the clip.
"""

import json
import os

# Events worth marking on the timeline. "speech" just says someone talked
# (the "voice" events carry the words), so it's left out.
_SHOWN = {"kill", "voice", "chat", "laughter", "audio_spike"}
_KILL_KEYS = ("victim", "inferred_player", "detected_player", "assister",
              "attackerBlind", "inAir", "noScope", "throughSmoke", "wallbang", "isHeadshot")


def _event(ev: dict, file_start: float) -> dict | None:
    kind = ev.get("type")
    if kind not in _SHOWN:
        return None
    d = ev.get("details") or {}
    if kind == "kill":
        details = {k: d.get(k) for k in _KILL_KEYS if d.get(k) is not None}
    elif kind in ("voice", "chat"):
        text = (d.get("text") or "").strip()
        if not text:
            return None
        details = {"text": text}
        if d.get("end") is not None:
            details["end"] = max(0.0, float(d["end"]) - file_start)
    elif kind == "laughter":
        details = {"confidence": d.get("confidence")}
    else:
        details = {"intensity": d.get("intensity")}
    return {"type": kind, "t": max(0.0, float(ev.get("timestamp_seconds", 0)) - file_start), "details": details}


def load(data_folder: str, clips_folder: str, media) -> dict:
    path = os.path.join(data_folder, "ordered_highlights.json")
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {"clips": [], "clips_folder": clips_folder, "found": False}

    out = []
    for rank, h in enumerate(raw, 1):
        # The clipper cuts from clip_start (pre-buffer included), never before 0.
        file_start = max(0.0, float(h.get("clip_start", 0)))
        name = h.get("clip_filename")
        file = os.path.join(clips_folder, name) if name else None
        exists = bool(file) and os.path.isfile(file)
        events = [e for e in (_event(ev, file_start) for ev in h.get("events_in_window", [])) if e]
        events.sort(key=lambda e: e["t"])
        out.append({
            "rank": rank,
            "kind": h.get("kind", "kill"),
            "score": h.get("score", 0),
            "tags": h.get("tags", []),
            "source": os.path.basename(h.get("source_video", "")),
            "length": max(0.0, float(h.get("clip_end", 0)) - file_start),
            "file": file if exists else None,
            "file_name": name,
            "size": os.path.getsize(file) if exists else 0,
            "url": media.url(file) if exists else None,
            "kills": sum(1 for e in events if e["type"] == "kill"),
            "events": events,
        })
    return {"clips": out, "clips_folder": clips_folder, "found": True}
