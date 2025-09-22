import os
import json
import pandas as pd
from tqdm import tqdm

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

    df = pd.DataFrame(all_events)
    # Convert details dict to string so pandas can handle it efficiently
    df['details_str'] = df['details'].astype(str)
    df.sort_values(by=['source_video', 'timestamp_seconds'], inplace=True)

    weights = config['scoring_weights']
    pre_buffer = config['clip_pre_buffer_seconds']
    post_buffer = config['clip_post_buffer_seconds']
    
    potential_clips = []
    trigger_events = df[df['type'] == 'kill'].to_dict('records')

    print("Finding and scoring potential clips...")
    for trigger in tqdm(trigger_events, desc="Correlating Events"):
        video_path = trigger['source_video']
        timestamp = trigger['timestamp_seconds']
        
        window_start = timestamp - pre_buffer
        window_end = timestamp + post_buffer
        
        window_df = df[(df['source_video'] == video_path) & 
                       (df['timestamp_seconds'] >= window_start) & 
                       (df['timestamp_seconds'] <= window_end)]
        
        if window_df.empty:
            continue
            
        score = 0
        tags = set()
        
        num_kills = len(window_df[window_df['type'] == 'kill'])
        score += num_kills * weights['kill']
        if num_kills > 1:
            score += weights['multi_kill_bonus']
            tags.add("multi-kill")
            
        if any("rage" in d_str for d_str in window_df[window_df['type'] == 'chat']['details_str']):
            score += weights['enemy_rage_chat']
            tags.add("enemy_rage")
            
        if any("hype" in d_str for d_str in window_df[window_df['type'] == 'voice']['details_str']):
            score += weights['team_hype_voice']
            tags.add("team_hype")
            
        if not window_df[window_df['type'] == 'audio_spike'].empty:
            score += weights['audio_spike']
            tags.add("loud_reaction")

        potential_clips.append({
            "source_video": video_path,
            "clip_start": window_start,
            "clip_end": window_end,
            "score": score,
            "tags": list(tags),
            "events_in_window": window_df.drop(columns=['details_str']).to_dict('records')
        })

    if not potential_clips:
        print("No potential clips were found after correlation.")
        return
        
    potential_clips.sort(key=lambda x: (x['source_video'], x['clip_start']))
    merged_clips = [potential_clips[0]]
    for current_clip in potential_clips[1:]:
        last_clip = merged_clips[-1]
        if current_clip['source_video'] == last_clip['source_video'] and current_clip['clip_start'] < last_clip['clip_end']:
            last_clip['clip_end'] = max(last_clip['clip_end'], current_clip['clip_end'])
            last_clip['score'] += current_clip['score']
            last_clip['tags'] = list(set(last_clip['tags']).union(set(current_clip['tags'])))
        else:
            merged_clips.append(current_clip)
            
    merged_clips.sort(key=lambda x: x['score'], reverse=True)

    highlights_path = os.path.join(data_folder, 'ordered_highlights.json')
    with open(highlights_path, 'w') as f:
        json.dump(merged_clips, f, indent=2)

    print(f"\nFound and merged {len(merged_clips)} clips. Saved to {highlights_path}")