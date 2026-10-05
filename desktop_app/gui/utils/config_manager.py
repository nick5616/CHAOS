"""
Configuration manager for the CHAOS desktop application.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional


class ConfigManager:
    """Manages configuration loading, saving, and validation."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, uses default.
        """
        if config_path is None:
            # Use the config.yaml in the project root
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / "config.yaml"
        
        self.config_path = Path(config_path)
        self.default_config = self._get_default_config()
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get the default configuration."""
        return {
            # File paths
            "captures_folder": "",
            "data_folder": "./data",
            "final_clips_folder": "./final_clips",
            
            # Analysis parameters
            "player_names": [],
            "killfeed_roi": [1920, 40, 2550, 300],
            "killfeed_roi_resolution": [2560, 1440],  # resolution killfeed_roi/chat_roi were calibrated at
            "chat_roi": [30, 1150, 650, 1300],
            
            # Kill detection tuning
            "red_hsv_lower1": [0, 120, 70],
            "red_hsv_upper1": [10, 255, 255],
            "red_hsv_lower2": [170, 120, 70],
            "red_hsv_upper2": [180, 255, 255],
            
            # Color ranges for parsing names
            "t_orange_hsv_lower": [10, 150, 150],
            "t_orange_hsv_upper": [25, 255, 255],
            "ct_blue_hsv_lower": [100, 150, 150],
            "ct_blue_hsv_upper": [130, 255, 255],
            
            # Shape detection
            "killfeed_rect_min_height": 25,
            "killfeed_rect_max_height": 50,
            "killfeed_rect_min_aspect_ratio": 5.0,
            
            # General analysis. CS2 keeps the player's killfeed rows up for
            # 7.5 s, so sampling every 2.5 s sees each kill about three times.
            "killfeed_sample_interval_seconds": 2.5,
            "whisper_model": "base",
            
            # Correlation & scoring
            "clip_pre_buffer_seconds": 7,
            "clip_post_buffer_seconds": 6,
            "scoring_weights": {
                "kill": 10,
                "multi_kill_bonus": 15,
                "team_hype_voice": 20,
                "enemy_rage_chat": 25,
                "audio_spike": 5
            },
            
            # GUI-specific settings
            "gui": {
                "window_size": [1200, 800],
                "theme": "cs2",
                "auto_save": True,
                "setup_complete": False
            },
            
            # System settings
            "system": {
                "cuda_available": False,
                "pytorch_version": "cpu",
                "ffmpeg_path": "ffmpeg",
                "ffmpeg_available": False,
                "dependencies_installed": False
            },
            
            # ROI configuration
            "roi": {
                "killfeed": [1920, 40, 2550, 300],
                "chat": [30, 1150, 650, 1300],
                "video_source": "auto"
            },
            
            # Pipeline settings
            "pipeline": {
                "auto_start": False,
                "show_logs": True,
                "save_debug": False,
                "analysis_workers": "auto"  # sized from free VRAM/RAM at start (chaos_lib/resources.py)
            }
        }
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge override into base, returning a new dict."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file.
        
        Returns:
            Configuration dictionary.
            
        Raises:
            FileNotFoundError: If config file doesn't exist.
            yaml.YAMLError: If config file is invalid YAML.
        """
        if not self.config_path.exists():
            # Create default config if it doesn't exist
            self.save_config(self.default_config)
            return self.default_config.copy()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}

            # Deep-merge with defaults so nested dicts (e.g. 'gui') get new keys
            merged_config = self._deep_merge(self.default_config, config)

            # Auto-mark setup complete for existing configs that already have
            # a valid captures folder and player names (migration from pre-wizard versions).
            if (not merged_config.get("gui", {}).get("setup_complete", False)
                    and merged_config.get("captures_folder")
                    and merged_config.get("player_names")):
                merged_config.setdefault("gui", {})["setup_complete"] = True

            return merged_config
            
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in config file: {e}")
        except Exception as e:
            raise Exception(f"Error loading config file: {e}")
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file.
        
        Args:
            config: Configuration dictionary to save.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Ensure the directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save with proper formatting
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2, sort_keys=False)
            
            return True
            
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def validate_config(self, config: Dict[str, Any], skip_folder_check: bool = False) -> List[str]:
        """Validate configuration and return list of errors.

        Args:
            config: Configuration dictionary to validate.
            skip_folder_check: Skip captures_folder check (use when file_list is provided).

        Returns:
            List of validation error messages.
        """
        errors = []

        # Check required paths
        if not skip_folder_check and not config.get('captures_folder'):
            errors.append("Captures folder is required")
        
        if not config.get('data_folder'):
            errors.append("Data folder is required")
        
        if not config.get('final_clips_folder'):
            errors.append("Final clips folder is required")
        
        # Check ROI coordinates
        killfeed_roi = config.get('killfeed_roi', [])
        if len(killfeed_roi) != 4:
            errors.append("Killfeed ROI must have 4 coordinates [x1, y1, x2, y2]")
        elif killfeed_roi[0] >= killfeed_roi[2] or killfeed_roi[1] >= killfeed_roi[3]:
            errors.append("Invalid killfeed ROI coordinates")
        
        chat_roi = config.get('chat_roi', [])
        if len(chat_roi) != 4:
            errors.append("Chat ROI must have 4 coordinates [x1, y1, x2, y2]")
        elif chat_roi[0] >= chat_roi[2] or chat_roi[1] >= chat_roi[3]:
            errors.append("Invalid chat ROI coordinates")
        
        # Check player names
        player_names = config.get('player_names', [])
        if not isinstance(player_names, list):
            errors.append("Player names must be a list")
        
        # Check scoring weights
        scoring_weights = config.get('scoring_weights', {})
        required_weights = ['kill', 'multi_kill_bonus', 'team_hype_voice', 'enemy_rage_chat', 'audio_spike']
        for weight in required_weights:
            if weight not in scoring_weights:
                errors.append(f"Missing scoring weight: {weight}")
            elif not isinstance(scoring_weights[weight], (int, float)):
                errors.append(f"Scoring weight '{weight}' must be a number")
        
        return errors
    
    def resolve_path(self, path: str) -> str:
        """Resolve a config path (possibly relative) against the project root."""
        if not path:
            return path
        p = Path(path)
        if p.is_absolute():
            return str(p)
        return str((self.config_path.parent / path).resolve())

    def reset_to_defaults(self) -> Dict[str, Any]:
        """Reset configuration to defaults.
        
        Returns:
            Default configuration dictionary.
        """
        return self.default_config.copy()
    
    def export_config(self, export_path: str) -> bool:
        """Export current configuration to a file.
        
        Args:
            export_path: Path where to export the configuration.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            config = self.load_config()
            export_path = Path(export_path)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2, sort_keys=False)
            
            return True
            
        except Exception as e:
            print(f"Error exporting config: {e}")
            return False
    
    def import_config(self, import_path: str) -> bool:
        """Import configuration from a file.
        
        Args:
            import_path: Path to the configuration file to import.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            import_path = Path(import_path)
            
            if not import_path.exists():
                return False
            
            with open(import_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if config is None:
                return False
            
            # Validate the imported config
            errors = self.validate_config(config)
            if errors:
                print(f"Import validation errors: {errors}")
                return False
            
            # Save the imported config
            return self.save_config(config)
            
        except Exception as e:
            print(f"Error importing config: {e}")
            return False
