#!/bin/bash
echo "======================================================"
echo " CHAOS Project Setup Script for macOS / Linux"
echo "======================================================"
echo

cd "$(dirname "$0")"
echo "[0/5] Setting working directory to: $(pwd)"
echo

echo "[1/5] Checking for Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Please install it."
    exit 1
fi
echo "      Python 3 found."
echo

echo "[2/5] Checking for FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "      FFmpeg not found. Attempting to install automatically..."
    
    # Try different package managers based on OS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        echo "      Trying Homebrew (macOS)..."
        if ! command -v brew &> /dev/null; then
            echo "      Homebrew not found. Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || {
                echo "ERROR: Failed to install Homebrew. Please install manually:"
                echo "      /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                exit 1
            }
        fi
        brew install ffmpeg || {
            echo "ERROR: Failed to install FFmpeg via Homebrew."
            exit 1
        }
        echo "      FFmpeg installed via Homebrew."
    else
        # Linux
        echo "      Trying system package manager (Linux)..."
        if command -v apt-get &> /dev/null; then
            # Ubuntu/Debian
            sudo apt-get update && sudo apt-get install -y ffmpeg || {
                echo "ERROR: Failed to install FFmpeg via apt-get."
                exit 1
            }
            echo "      FFmpeg installed via apt-get."
        elif command -v yum &> /dev/null; then
            # CentOS/RHEL
            sudo yum install -y ffmpeg || {
                echo "ERROR: Failed to install FFmpeg via yum."
                exit 1
            }
            echo "      FFmpeg installed via yum."
        elif command -v dnf &> /dev/null; then
            # Fedora
            sudo dnf install -y ffmpeg || {
                echo "ERROR: Failed to install FFmpeg via dnf."
                exit 1
            }
            echo "      FFmpeg installed via dnf."
        elif command -v pacman &> /dev/null; then
            # Arch Linux
            sudo pacman -S --noconfirm ffmpeg || {
                echo "ERROR: Failed to install FFmpeg via pacman."
                exit 1
            }
            echo "      FFmpeg installed via pacman."
        else
            echo "ERROR: No supported package manager found."
            echo "      Please install FFmpeg manually for your Linux distribution."
            exit 1
        fi
    fi
else
    echo "      FFmpeg found."
fi
echo

echo "[3/6] Creating virtual environment 'venv'..."
if [ -d "venv" ]; then
    echo "      Virtual environment exists. Skipping."
else
    python3 -m venv venv || exit 1
    echo "      Virtual environment created."
fi
echo

echo "[4/6] Activating environment and installing base packages..."
source venv/bin/activate
pip install -r requirements.txt || exit 1
echo "      Base packages installed."
echo

echo "[5/6] Installing PyTorch for Apple Silicon (MPS) / CPU..."
echo "      This is the slowest step. Please be patient."
echo "      Installing PyTorch with MPS support for Apple Silicon..."
pip install torch torchvision torchaudio || exit 1
echo "      PyTorch installed with MPS support!"
echo "      You can now use --gpu flag for faster processing on Apple Silicon."
echo

echo "[6/6] Setup Complete!"
echo "======================================================"
echo
echo "To use CHAOS, open a terminal in this folder and run:"
echo "  source venv/bin/activate"
echo "Then run the main script:"
echo "  python3 main.py analyze --debug"
echo "  python3 main.py analyze --debug --gpu  (for GPU acceleration)"
echo