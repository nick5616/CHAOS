"""
System detection utilities for the CHAOS desktop application.
"""

import subprocess
import sys
import platform
import shutil
from pathlib import Path
from typing import Dict, Tuple, Optional


class SystemDetector:
    """Detects system capabilities and requirements."""
    
    @staticmethod
    def check_python_version() -> Tuple[bool, str]:
        """Check if Python version meets requirements.
        
        Returns:
            Tuple of (is_compatible, version_string)
        """
        version = sys.version_info
        version_string = f"{version.major}.{version.minor}.{version.micro}"
        
        # Require Python 3.8+
        is_compatible = version.major == 3 and version.minor >= 8
        
        return is_compatible, version_string
    
    @staticmethod
    def check_ffmpeg() -> Tuple[bool, str]:
        """Check if FFmpeg is available.
        
        Returns:
            Tuple of (is_available, version_string_or_path)
        """
        try:
            # Try to run ffmpeg -version
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Extract version from output
                version_line = result.stdout.split('\n')[0]
                return True, version_line
            else:
                return False, "FFmpeg not found in PATH"
                
        except subprocess.TimeoutExpired:
            return False, "FFmpeg command timed out"
        except FileNotFoundError:
            return False, "FFmpeg not found in PATH"
        except Exception as e:
            return False, f"Error checking FFmpeg: {str(e)}"
    
    @staticmethod
    def detect_cuda() -> Dict[str, any]:
        """Detect CUDA availability and version.
        
        Returns:
            Dictionary with CUDA information.
        """
        try:
            import torch
            
            if torch.cuda.is_available():
                return {
                    'available': True,
                    'version': torch.version.cuda,
                    'device_count': torch.cuda.device_count(),
                    'device_name': torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else "Unknown",
                    'pytorch_version': torch.__version__
                }
            else:
                return {
                    'available': False,
                    'version': None,
                    'device_count': 0,
                    'device_name': None,
                    'pytorch_version': torch.__version__ if 'torch' in sys.modules else None
                }
                
        except ImportError:
            return {
                'available': False,
                'version': None,
                'device_count': 0,
                'device_name': None,
                'pytorch_version': None
            }
        except Exception as e:
            return {
                'available': False,
                'version': None,
                'device_count': 0,
                'device_name': None,
                'pytorch_version': None,
                'error': str(e)
            }
    
    @staticmethod
    def get_pytorch_install_command() -> str:
        """Get the appropriate PyTorch installation command.
        
        Returns:
            PyTorch installation command string.
        """
        cuda_info = SystemDetector.detect_cuda()
        
        if cuda_info['available'] and cuda_info['version']:
            cuda_version = cuda_info['version']
            
            if cuda_version.startswith('11.8'):
                return "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118"
            elif cuda_version.startswith('12.1'):
                return "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
            elif cuda_version.startswith('12.4'):
                return "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124"
            else:
                # Fallback to CPU version for unsupported CUDA versions
                return "pip install torch torchvision torchaudio"
        else:
            # CPU-only version
            return "pip install torch torchvision torchaudio"
    
    @staticmethod
    def check_dependencies() -> Dict[str, any]:
        """Check if all required dependencies are installed.
        
        Returns:
            Dictionary with dependency status.
        """
        dependencies = {
            'pyyaml': False,
            'pandas': False,
            'tqdm': False,
            'opencv-python': False,
            'easyocr': False,
            'whisper': False,
            'librosa': False,
            'thefuzz': False,
            'PyQt6': False,
            'Pillow': False,
            'psutil': False
        }
        
        for dep in dependencies.keys():
            try:
                if dep == 'opencv-python':
                    import cv2
                elif dep == 'whisper':
                    import whisper
                elif dep == 'PyQt6':
                    import PyQt6
                elif dep == 'Pillow':
                    import PIL
                elif dep == 'pyyaml':
                    import yaml
                else:
                    __import__(dep)
                dependencies[dep] = True
            except ImportError:
                dependencies[dep] = False
        
        return dependencies
    
    @staticmethod
    def get_system_info() -> Dict[str, str]:
        """Get general system information.
        
        Returns:
            Dictionary with system information.
        """
        return {
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': sys.version,
            'python_executable': sys.executable
        }
    
    @staticmethod
    def check_disk_space(path: str = ".") -> Dict[str, any]:
        """Check available disk space.
        
        Args:
            path: Path to check disk space for.
            
        Returns:
            Dictionary with disk space information.
        """
        try:
            import shutil
            
            total, used, free = shutil.disk_usage(path)
            
            return {
                'total_gb': round(total / (1024**3), 2),
                'used_gb': round(used / (1024**3), 2),
                'free_gb': round(free / (1024**3), 2),
                'free_percent': round((free / total) * 100, 2)
            }
        except Exception as e:
            return {
                'error': str(e)
            }
    
    @staticmethod
    def install_ffmpeg() -> Tuple[bool, str]:
        """Attempt to install FFmpeg based on the platform.
        
        Returns:
            Tuple of (success, message)
        """
        system = platform.system().lower()
        
        try:
            if system == "darwin":  # macOS
                # Try to install via Homebrew
                if shutil.which("brew"):
                    result = subprocess.run(
                        ["brew", "install", "ffmpeg"],
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minutes timeout
                    )
                    if result.returncode == 0:
                        return True, "FFmpeg installed successfully via Homebrew"
                    else:
                        return False, f"Homebrew installation failed: {result.stderr}"
                else:
                    return False, "Homebrew not found. Please install FFmpeg manually."
            
            elif system == "linux":
                # Try to install via package manager
                package_managers = [
                    (["sudo", "apt", "update", "&&", "sudo", "apt", "install", "-y", "ffmpeg"], "apt"),
                    (["sudo", "yum", "install", "-y", "ffmpeg"], "yum"),
                    (["sudo", "dnf", "install", "-y", "ffmpeg"], "dnf"),
                    (["sudo", "pacman", "-S", "--noconfirm", "ffmpeg"], "pacman")
                ]
                
                for cmd, manager in package_managers:
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        if result.returncode == 0:
                            return True, f"FFmpeg installed successfully via {manager}"
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        continue
                
                return False, "No suitable package manager found. Please install FFmpeg manually."
            
            elif system == "windows":
                return False, "Please install FFmpeg manually on Windows. Download from https://ffmpeg.org/download.html"
            
            else:
                return False, f"Unsupported platform: {system}"
                
        except Exception as e:
            return False, f"Error installing FFmpeg: {str(e)}"
