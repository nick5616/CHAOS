"""
System detection utilities for the CHAOS desktop application.
"""

import re
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
        from chaos_lib.clipper import _get_ffmpeg
        try:
            # Try to run ffmpeg -version
            result = subprocess.run(
                [_get_ffmpeg(), '-version'],
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
    def detect_nvidia_gpu() -> Dict[str, "any"]:
        """Detect an NVIDIA GPU via nvidia-smi, independent of PyTorch.

        Unlike detect_cuda(), this works even when PyTorch isn't installed or
        was installed as a CPU-only build, so the UI can tell "no GPU" apart
        from "GPU present but CUDA-enabled PyTorch isn't".

        Returns:
            Dictionary with GPU presence, name, driver version, and the
            highest CUDA version the installed driver supports.
        """
        try:
            query = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if query.returncode != 0 or not query.stdout.strip():
                return {'present': False, 'name': None, 'driver_version': None, 'max_cuda_version': None}

            first_line = query.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first_line.split(",")]
            name = parts[0] if parts and parts[0] else "NVIDIA GPU"
            driver_version = parts[1] if len(parts) > 1 else None

            max_cuda_version = None
            header = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=10)
            # Older drivers print "CUDA Version: 12.4"; newer ones (R580+) print
            # "CUDA UMD Version: 13.2" instead - match both.
            match = re.search(r"CUDA(?:\s+UMD)?\s+Version:\s*([\d.]+)", header.stdout)
            if match:
                max_cuda_version = match.group(1)

            return {
                'present': True,
                'name': name,
                'driver_version': driver_version,
                'max_cuda_version': max_cuda_version,
            }

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {'present': False, 'name': None, 'driver_version': None, 'max_cuda_version': None}
        except Exception as e:
            return {'present': False, 'name': None, 'driver_version': None, 'max_cuda_version': None, 'error': str(e)}

    @staticmethod
    def pick_cuda_wheel_tag(max_cuda_version: Optional[str]) -> Optional[str]:
        """Newest PyTorch CUDA wheel tag (e.g. "cu128") the driver can run.

        Args:
            max_cuda_version: The highest CUDA version the installed NVIDIA
                driver supports, as reported by nvidia-smi.

        Returns:
            The wheel tag, or None if there is no driver or it is too old for
            any currently-supported PyTorch CUDA build.
        """
        if not max_cuda_version:
            return None
        try:
            bits = max_cuda_version.split('.')
            version = (int(bits[0]), int(bits[1]) if len(bits) > 1 else 0)
        except (ValueError, IndexError):
            return None

        if version >= (12, 9):
            return "cu129"
        if version >= (12, 8):
            return "cu128"
        if version >= (12, 6):
            return "cu126"
        if version >= (11, 8):
            return "cu118"
        return None

    @staticmethod
    def get_pytorch_install_command(max_cuda_version: Optional[str] = None) -> str:
        """Get the appropriate PyTorch installation command.

        Args:
            max_cuda_version: The highest CUDA version the installed NVIDIA
                driver supports (as reported by nvidia-smi). If omitted, this
                is looked up via detect_nvidia_gpu().

        Returns:
            PyTorch installation command string.
        """
        if max_cuda_version is None:
            max_cuda_version = SystemDetector.detect_nvidia_gpu().get('max_cuda_version')

        tag = SystemDetector.pick_cuda_wheel_tag(max_cuda_version)
        if tag is None:
            # No NVIDIA driver, or one too old for any CUDA build - CPU-only version
            return "pip install torch torchvision torchaudio"

        # --force-reinstall is required: if a CPU build is already installed, it
        # already satisfies the bare "torch" requirement as far as pip is
        # concerned, so a plain `pip install torch` against the CUDA index
        # silently no-ops ("Requirement already satisfied") and exits 0 without
        # installing anything.
        #
        # --no-deps is required too: without it, --force-reinstall also
        # re-resolves torch/torchvision's pure-Python dependencies (e.g. numpy)
        # to their latest allowed versions, which can silently break unrelated
        # packages elsewhere in the environment that pin an upper bound (numba
        # requires numpy <= 2.3; a plain reinstall pulled in numpy 2.4 and broke
        # it). This path only ever runs when a CPU build of torch is already
        # present (see the gpu_present-but-not-cuda_available check that gates
        # this dialog), so its dependencies are already satisfied and safe to
        # leave untouched.
        return (
            "pip install torch torchvision torchaudio "
            f"--index-url https://download.pytorch.org/whl/{tag} --force-reinstall --no-deps"
        )
    
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
                if shutil.which("winget"):
                    result = subprocess.run(
                        ["winget", "install", "-e", "--id", "Gyan.FFmpeg",
                         "--accept-package-agreements", "--accept-source-agreements", "--silent"],
                        capture_output=True,
                        text=True,
                        timeout=600
                    )
                    if SystemDetector.check_ffmpeg()[0]:
                        return True, "FFmpeg installed successfully via winget"
                    return False, f"winget installation failed: {result.stdout or result.stderr}"
                return False, "Please install FFmpeg manually on Windows. Download from https://ffmpeg.org/download.html"
            
            else:
                return False, f"Unsupported platform: {system}"
                
        except Exception as e:
            return False, f"Error installing FFmpeg: {str(e)}"
