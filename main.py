# === FILE: main_robust.py ===
import argparse
import yaml
import os
import json
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from chaos_lib import ingestion, analyzers, correlator, clipper, summary

class RobustPipeline:
    def __init__(self, config_path='config.yaml'):
        self.config_path = config_path
        self.load_config()
        self.progress_file = os.path.join(self.config['data_folder'], 'processing_progress.json')
        self.progress = self.load_progress()
        
    def load_config(self):
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
    def load_progress(self):
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'ingestion_completed': False,
            'videos_processed': [],
            'videos_failed': [],
            'current_stage': 'ingestion',
            'start_time': None,
            'last_update': None
        }
    
    def save_progress(self):
        self.progress['last_update'] = datetime.now().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def run_ingestion(self):
        if self.progress['ingestion_completed']:
            print(' Ingestion already completed, skipping...')
            return True
            
        print('\n--- Running Stage: Ingestion ---')
        try:
            ingestion.create_manifest(self.config)
            self.progress['ingestion_completed'] = True
            self.progress['current_stage'] = 'analysis'
            self.save_progress()
            print(' Ingestion completed successfully')
            return True
        except Exception as e:
            print(f' Ingestion failed: {e}')
            return False
    
    def get_video_list(self):
        manifest_path = os.path.join(self.config['data_folder'], 'manifest.json')
        if not os.path.exists(manifest_path):
            print('No manifest found. Please run ingestion first.')
            return []
            
        with open(manifest_path, 'r') as f:
            return json.load(f)
    
    def get_unprocessed_videos(self, debug_mode=False, max_videos=None):
        all_videos = self.get_video_list()
        processed = set(self.progress['videos_processed'])
        failed = set(self.progress['videos_failed'])
        unprocessed = [v for v in all_videos if v not in processed and v not in failed]
        
        if debug_mode and max_videos is not None:
            unprocessed = unprocessed[:max_videos]
            print(f'Debug mode: Processing only first {len(unprocessed)} videos')
        
        return unprocessed
    
    def process_single_video(self, video_path, use_gpu=False):
        video_name = os.path.basename(video_path)
        print(f'\n Processing: {video_name}')
        
        try:
            video_config = self.config.copy()
            video_config['debug_mode'] = False
            video_config['use_gpu'] = use_gpu
            
            video_data_folder = os.path.join(self.config['data_folder'], 'videos', 
                                           os.path.splitext(video_name)[0])
            os.makedirs(video_data_folder, exist_ok=True)
            video_config['data_folder'] = video_data_folder
            
            video_manifest_path = os.path.join(video_data_folder, 'manifest.json')
            with open(video_manifest_path, 'w') as f:
                json.dump([video_path], f)
            
            print(f'   Analyzing {video_name}...')
            analyzers.run_analysis(video_config)
            
            print(f'   Correlating events for {video_name}...')
            correlator.run_correlation(video_config)
            
            print(f'    Clipping {video_name}...')
            clipper.run_clipping(video_config)
            
            self.progress['videos_processed'].append(video_path)
            self.save_progress()
            
            print(f'   Completed: {video_name}')
            return True
            
        except Exception as e:
            print(f'   Failed: {video_name} - {e}')
            self.progress['videos_failed'].append(video_path)
            self.save_progress()
            return False
    
    def run_analysis_parallel(self, max_workers=2, debug_mode=False, use_gpu=False):
        print(f'Running analysis parallel with {max_workers} workers, debug mode: {debug_mode}, GPU: {use_gpu}')
        unprocessed = self.get_unprocessed_videos(debug_mode, max_videos=max_workers if debug_mode else None)   
        if not unprocessed:
            print('No unprocessed videos found.')
            return
        
        print(f'\n--- Running Stage: Analysis (Parallel) ---')
        print(f'Processing {len(unprocessed)} videos with {max_workers} workers...')
        if use_gpu:
            print('GPU acceleration enabled')
        
        if not self.progress['start_time']:
            self.progress['start_time'] = datetime.now().isoformat()
            self.save_progress()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_video = {
                executor.submit(self.process_single_video, video, use_gpu): video 
                for video in unprocessed
            }
            
            completed = 0
            total = len(unprocessed)
            
            for future in as_completed(future_to_video):
                video = future_to_video[future]
                try:
                    success = future.result()
                    completed += 1
                    print(f'Progress: {completed}/{total} videos completed')
                except Exception as e:
                    print(f'Exception processing {video}: {e}')
                    self.progress['videos_failed'].append(video)
                    self.save_progress()
    
    def run_analysis_sequential(self, debug_mode=False, max_videos=None, use_gpu=False):
        unprocessed = self.get_unprocessed_videos(debug_mode, max_videos)
        if not unprocessed:
            print('No unprocessed videos found.')
            return
        
        print(f'\n--- Running Stage: Analysis (Sequential) ---')
        print(f'Processing {len(unprocessed)} videos...')
        if use_gpu:
            print('GPU acceleration enabled')
        
        if not self.progress['start_time']:
            self.progress['start_time'] = datetime.now().isoformat()
            self.save_progress()
        
        for i, video in enumerate(unprocessed, 1):
            print(f'\nProgress: {i}/{len(unprocessed)}')
            self.process_single_video(video, use_gpu)
    
    def run_summary(self):
        print('\n--- Running Stage: Summary Generation ---')
        
        all_events = []
        for video_path in self.progress['videos_processed']:
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            video_data_folder = os.path.join(self.config['data_folder'], 'videos', video_name)
            events_path = os.path.join(video_data_folder, 'all_events.json')
            
            if os.path.exists(events_path):
                with open(events_path, 'r') as f:
                    video_events = json.load(f)
                    all_events.extend(video_events)
        
        combined_events_path = os.path.join(self.config['data_folder'], 'all_events.json')
        with open(combined_events_path, 'w') as f:
            json.dump(all_events, f, indent=2)
        
        print(f'Combined {len(all_events)} events from all processed videos')
        
        print('Running final correlation...')
        correlator.run_correlation(self.config)
        
        summary.generate_summary(self.config)
        
        print(' Summary generation completed')
    
    def show_status(self):
        all_videos = self.get_video_list()
        processed = len(self.progress['videos_processed'])
        failed = len(self.progress['videos_failed'])
        remaining = len(all_videos) - processed - failed
        
        print(f'\n Processing Status:')
        print(f'  Total videos: {len(all_videos)}')
        print(f'  Processed: {processed}')
        print(f'  Failed: {failed}')
        print(f'  Remaining: {remaining}')
        
        if self.progress['start_time']:
            start_time = datetime.fromisoformat(self.progress['start_time'])
            elapsed = datetime.now() - start_time
            print(f'  Elapsed time: {elapsed}')
        
        if failed > 0:
            print(f'\nFailed videos:')
            for video in self.progress['videos_failed']:
                print(f'  - {os.path.basename(video)}')
    
    def reset_progress(self):
        self.progress = {
            'ingestion_completed': False,
            'videos_processed': [],
            'videos_failed': [],
            'current_stage': 'ingestion',
            'start_time': None,
            'last_update': None
        }
        self.save_progress()
        print('Progress reset successfully')

def main():
    parser = argparse.ArgumentParser(description='CHAOS: Robust CS2 Highlight Analysis & Organization System')
    parser.add_argument('stage', choices=['all', 'ingest', 'analyze', 'summary', 'status', 'reset'], 
                        help='The pipeline stage to run.')
    parser.add_argument('--workers', type=int, default=1, 
                        help='Number of parallel workers for analyze stage (default: 1, use >1 for parallel processing)')
    parser.add_argument('--debug', action='store_true', 
                        help='Debug mode: process only the first w videos where w is the number of workers')
    parser.add_argument('--gpu', action='store_true', 
                        help='Use GPU acceleration for AI models (requires CUDA-compatible GPU and proper PyTorch installation)')
    parser.add_argument('--config', default='config.yaml', 
                        help='Path to config file (default: config.yaml)')
    args = parser.parse_args()

    os.makedirs('./data', exist_ok=True)
    os.makedirs('./final_clips', exist_ok=True)
    os.makedirs('./data/videos', exist_ok=True)

    pipeline = RobustPipeline(args.config)
    
    if args.stage == 'status':
        pipeline.show_status()
        return
    
    if args.stage == 'reset':
        pipeline.reset_progress()
        return
    
    if args.stage in ['all', 'ingest']:
        if not pipeline.run_ingestion():
            return
    
    if args.stage in ['all', 'analyze']:
        pipeline.run_analysis_parallel(args.workers, debug_mode=args.debug, use_gpu=args.gpu)
    
    if args.stage in ['all', 'summary']:
        pipeline.run_summary()
    
    pipeline.show_status()

if __name__ == '__main__':
    main()
