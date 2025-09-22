import os
import json
from tqdm import tqdm

def create_manifest(config: dict):
    """Walks the captures folder and creates a JSON list of all video files."""
    captures_folder = config['captures_folder']
    data_folder = config['data_folder']
    manifest_path = os.path.join(data_folder, 'manifest.json')
    
    video_files = []
    print(f"Scanning for video files in: {captures_folder}")
    # Use os.walk which is very efficient for directory trees
    for root, _, files in tqdm(os.walk(captures_folder), desc="Scanning directories"):
        for file in files:
            if file.lower().endswith('.mp4'):
                video_files.append(os.path.join(root, file))

    with open(manifest_path, 'w') as f:
        json.dump(video_files, f, indent=2)

    print(f"Found {len(video_files)} video files. Manifest saved to {manifest_path}")