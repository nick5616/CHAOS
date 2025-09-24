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
    echo "      FFmpeg not found. Installing via Homebrew..."
    if ! command -v brew &> /dev/null; then
        echo "ERROR: Homebrew not found. Please install Homebrew first:"
        echo "      /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    brew install ffmpeg || exit 1
    echo "      FFmpeg installed."
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
pip install torch torchvision torchaudio || exit 1
echo "      PyTorch installed."
echo

echo "[6/6] Setup Complete!"
echo "======================================================"
echo
echo "To use CHAOS, open a terminal in this folder and run:"
echo "  source venv/bin/activate"
echo "Then run the main script:"
echo "  python3 main.py analyze --debug"
echo