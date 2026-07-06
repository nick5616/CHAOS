import os
import json
from tqdm import tqdm

def create_manifest(config: dict, file_list: list = None):
    """Walks the captures folder (or uses an explicit list) to create a JSON manifest."""
    data_folder = config['data_folder']
    manifest_path = os.path.join(data_folder, 'manifest.json')

    if file_list is not None:
        video_files = [str(p) for p in file_list]
        print(f"Using {len(video_files)} explicitly selected video file(s)")
    else:
        captures_folder = config['captures_folder']
        video_files = []
        print(f"Scanning for video files in: {captures_folder}")
        for root, _, files in tqdm(os.walk(captures_folder), desc="Scanning directories"):
            for file in files:
                if file.lower().endswith('.mp4'):
                    video_files.append(os.path.join(root, file))

    with open(manifest_path, 'w') as f:
        json.dump(video_files, f, indent=2)

    print(f"Found {len(video_files)} video files. Manifest saved to {manifest_path}")