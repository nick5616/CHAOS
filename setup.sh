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

echo "[2/5] Creating virtual environment 'venv'..."
if [ -d "venv" ]; then
    echo "      Virtual environment exists. Skipping."
else
    python3 -m venv venv || exit 1
    echo "      Virtual environment created."
fi
echo

echo "[3/5] Activating environment and installing base packages..."
source venv/bin/activate
pip install -r requirements.txt || exit 1
echo "      Base packages installed."
echo

echo "[4/5] Installing PyTorch for Apple Silicon (MPS) / CPU..."
echo "      This is the slowest step. Please be patient."
pip install torch torchvision torchaudio || exit 1
echo "      PyTorch installed."
echo

echo "[5/5] Setup Complete!"
echo "======================================================"
echo
echo "To use CHAOS, open a terminal in this folder and run:"
echo "  source venv/bin/activate"
echo "Then run the main script:"
echo "  python3 main.py analyze --debug"
echo