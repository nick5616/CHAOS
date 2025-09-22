import os
import json
from collections import Counter

def generate_summary(config: dict):
    """
    Analyzes the final highlights file to generate stats about kills per player.
    """
    data_folder = config['data_folder']
    highlights_path = os.path.join(data_folder, 'ordered_highlights.json')

    if not os.path.exists(highlights_path):
        print(f"Highlights file not found at {highlights_path}. Please run the 'correlate' stage first.")
        return

    with open(highlights_path, 'r') as f:
        highlights = json.load(f)

    print("Generating kill summary statistics...")
    
    kill_counter = Counter()

    for clip in highlights:
        for event in clip.get('events_in_window', []):
            if event.get('type') == 'kill':
                player_name = event.get('details', {}).get('detected_player', 'Unknown')
                kill_counter[player_name] += 1

    summary_path = os.path.join(config['data_folder'], 'kill_summary.txt')
    with open(summary_path, 'w') as f:
        f.write("--- CHAOS Kill Summary ---\n\n")
        f.write(f"Total Clips Analyzed: {len(highlights)}\n")
        f.write(f"Total Kills Detected in Clips: {sum(kill_counter.values())}\n\n")
        f.write("Kills per Player (in final clips):\n")
        f.write("------------------------------------\n")
        
        sorted_kills = kill_counter.most_common()
        
        for player, count in sorted_kills:
            f.write(f"- {player}: {count} kills\n")

    print(f"Summary saved successfully to {summary_path}")