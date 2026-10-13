import os
import csv
import json
import pandas as pd
from tqdm import tqdm

from chaos_lib import moments


def _merge_overlapping(clips: list) -> list:
    """Merge clips whose windows overlap: scores add, tags and events union.
    A merged clip containing a kill counts as a kill clip."""
    if not clips:
        return []
    clips = sorted(clips, key=lambda x: x['clip_start'])
    merged = [clips[0]]
    for clip in clips[1:]:
        last = merged[-1]
        if clip['clip_start'] < last['clip_end']:
            last['clip_end'] = max(last['clip_end'], clip['clip_end'])
            last['score'] += clip['score']
            last['tags'] = list(set(last['tags']) | set(clip['tags']))
            seen = {(e['type'], e['timestamp_seconds']) for e in last['events_in_window']}
            last['events_in_window'] += [e for e in clip['events_in_window']
                                         if (e['type'], e['timestamp_seconds']) not in seen]
            if 'kill' in (last.get('kind'), clip.get('kind')):
                last['kind'] = 'kill'
            if 'banter' in clip:
                last['banter'] = max(last.get('banter', 0), clip['banter'])
        else:
            merged.append(clip)
    return merged


def _write_timeline(video_path: str, rows: list, config: dict) -> None:
    if not rows:
        return
    folder = os.path.join(config['data_folder'], 'debug')
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(video_path))[0]
    with open(os.path.join(folder, f"moments_{stem}.csv"), 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def correlate_video_events(video_path: str, events: list, config: dict) -> list:
    """
    Correlate events from a single already-analysed video.
    Returns a list of merged highlight specs for that video only.
    Called immediately after each video finishes analysis in the streaming pipeline.

    Kill windows and funny voice-chat moments that overlap merge into one clip.
    Conversation moments (for review) are kept only where no other clip
    already covers them.
    """
    if not events:
        return []

    df = pd.DataFrame(events)
    df['details_str'] = df['details'].astype(str)

    weights   = config['scoring_weights']
    pre_buf   = config['clip_pre_buffer_seconds']
    post_buf  = config['clip_post_buffer_seconds']

    potential = []
    for trigger in df[df['type'] == 'kill'].to_dict('records'):
        ts   = trigger['timestamp_seconds']
        win  = df[(df['timestamp_seconds'] >= ts - pre_buf) &
                  (df['timestamp_seconds'] <= ts + post_buf) &
                  ~df['type'].str.endswith('_info')]  # bookkeeping, not events
        if win.empty:
            continue

        score = 0
        tags  = set()

        num_kills = len(win[win['type'] == 'kill'])
        score += num_kills * weights['kill']
        if num_kills > 1:
            score += weights['multi_kill_bonus']
            tags.add('multi-kill')

        for _, ev in win[win['type'] == 'kill'].iterrows():
            d = ev['details']
            if d.get('isHeadshot'):
                score += weights['headshot_bonus']
                tags.add('headshot')
            if d.get('throughSmoke'):
                score += weights['smoke_kill_bonus']
                tags.add('smoke_kill')

        if any('rage' in s for s in win[win['type'] == 'chat']['details_str']):
            score += weights['enemy_rage_chat']
            tags.add('enemy_rage')
        if any('hype' in s for s in win[win['type'] == 'voice']['details_str']):
            score += weights['team_hype_voice']
            tags.add('team_hype')
        if not win[win['type'] == 'audio_spike'].empty:
            score += weights['audio_spike']
            tags.add('loud_reaction')

        potential.append({
            'source_video': video_path,
            'clip_start':   ts - pre_buf,
            'clip_end':     ts + post_buf,
            'score':        score,
            'kind':         'kill',
            'tags':         list(tags),
            'events_in_window': win.drop(columns=['details_str']).to_dict('records'),
        })

    timeline = [] if config.get('pipeline', {}).get('save_debug') else None
    found = moments.find_moments(video_path, events, config, timeline)
    if timeline:
        _write_timeline(video_path, timeline, config)

    merged = _merge_overlapping(potential + [m for m in found if m['kind'] == 'funny'])
    conversations = [c for c in found if c['kind'] == 'conversation'
                     and not any(c['clip_start'] < h['clip_end'] and h['clip_start'] < c['clip_end']
                                 for h in merged)]
    return merged + conversations


def run_correlation(config: dict):
    """Loads all events, finds clusters, scores them, and saves the final list of clips."""
    data_folder = config['data_folder']
    events_path = os.path.join(data_folder, 'all_events.json')

    print(f"Loading events from {events_path}...")
    with open(events_path, 'r') as f:
        all_events = json.load(f)

    if not all_events:
        print("No events found to correlate. Please run the 'analyze' stage first.")
        return

    by_video: dict = {}
    for event in all_events:
        by_video.setdefault(event['source_video'], []).append(event)

    print("Finding and scoring potential clips...")
    merged_clips = []
    for video_path, events in tqdm(by_video.items(), desc="Correlating Events"):
        events.sort(key=lambda e: e['timestamp_seconds'])
        merged_clips.extend(correlate_video_events(video_path, events, config))

    if not merged_clips:
        print("No potential clips were found after correlation.")
        return

    merged_clips.sort(key=lambda x: x['score'], reverse=True)

    highlights_path = os.path.join(data_folder, 'ordered_highlights.json')
    with open(highlights_path, 'w') as f:
        json.dump(merged_clips, f, indent=2)

    print(f"\nFound and merged {len(merged_clips)} clips. Saved to {highlights_path}")
