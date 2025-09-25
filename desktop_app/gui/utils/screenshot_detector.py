"""
Screenshot detection utilities for auto video detection.
"""

import cv2
import glob
import os
from pathlib import Path
from typing import Optional, Tuple


class ScreenshotDetector:
    """Utility class for detecting and extracting frames from videos."""
    
    @staticmethod
    def get_frame_from_first_video(captures_folder: str) -> Tuple[Optional[cv2.Mat], Optional[str]]:
        """Extract a frame from the first video file found.
        
        Args:
            captures_folder: Path to the folder containing video files
            
        Returns:
            Tuple of (frame, video_path) or (None, None) if no video found
        """
        if not os.path.exists(captures_folder):
            return None, None
            
        # Find first video file
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        for ext in video_extensions:
            pattern = os.path.join(captures_folder, f"**/*{ext}")
            video_files = glob.glob(pattern, recursive=True)
            if video_files:
                # Get a frame from the middle of the video
                cap = cv2.VideoCapture(video_files[0])
                if not cap.isOpened():
                    continue
                    
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames > 0:
                    middle_frame = total_frames // 2
                    cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
                    
                    ret, frame = cap.read()
                    cap.release()
                    
                    if ret:
                        return frame, video_files[0]
                else:
                    cap.release()
        
        return None, None
    
    @staticmethod
    def get_frame_at_time(video_path: str, time_seconds: float) -> Optional[cv2.Mat]:
        """Extract a frame at a specific time from a video.
        
        Args:
            video_path: Path to the video file
            time_seconds: Time in seconds to extract frame
            
        Returns:
            Frame as OpenCV Mat or None if failed
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            cap.release()
            return None
            
        frame_number = int(time_seconds * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        
        ret, frame = cap.read()
        cap.release()
        
        return frame if ret else None
    
    @staticmethod
    def get_video_info(video_path: str) -> dict:
        """Get information about a video file.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary with video information
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {}
            
        info = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': 0
        }
        
        if info['fps'] > 0:
            info['duration'] = info['frame_count'] / info['fps']
            
        cap.release()
        return info
    
    @staticmethod
    def find_videos_in_folder(folder_path: str) -> list:
        """Find all video files in a folder.
        
        Args:
            folder_path: Path to the folder to search
            
        Returns:
            List of video file paths
        """
        if not os.path.exists(folder_path):
            return []
            
        video_files = []
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        
        for ext in video_extensions:
            pattern = os.path.join(folder_path, f"**/*{ext}")
            video_files.extend(glob.glob(pattern, recursive=True))
            
        return sorted(video_files)
    
    @staticmethod
    def extract_roi_from_frame(frame: cv2.Mat, roi: list) -> Optional[cv2.Mat]:
        """Extract a region of interest from a frame.
        
        Args:
            frame: Input frame
            roi: ROI coordinates [x1, y1, x2, y2]
            
        Returns:
            Extracted ROI as OpenCV Mat or None if invalid
        """
        if len(roi) != 4:
            return None
            
        x1, y1, x2, y2 = roi
        
        # Validate coordinates
        if x1 >= x2 or y1 >= y2:
            return None
            
        height, width = frame.shape[:2]
        if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
            return None
            
        return frame[y1:y2, x1:x2]
