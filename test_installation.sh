#!/bin/bash
# Test script to verify CHAOS installation

INSTALL_DIR="$HOME/Applications/CHAOS"

echo "CHAOS Installation Test"
echo "======================"
echo ""

if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ CHAOS is not installed at: $INSTALL_DIR"
    echo "Run ./install_chaos.sh first"
    exit 1
fi

echo "✅ Installation directory exists: $INSTALL_DIR"

# Check virtual environment
if [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "❌ Virtual environment not found"
    exit 1
fi
echo "✅ Virtual environment exists"

# Check application files
required_files=("chaos_lib" "desktop_app" "config.yaml" "requirements.txt" "start_chaos.sh")
for file in "${required_files[@]}"; do
    if [ ! -e "$INSTALL_DIR/$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
    echo "✅ Found: $file"
done

# Test virtual environment activation
echo ""
echo "Testing virtual environment..."
cd "$INSTALL_DIR"
source venv/bin/activate

# Check Python packages
echo "Checking Python packages..."
python -c "import PyQt6; print('✅ PyQt6 available')" 2>/dev/null || echo "❌ PyQt6 not available"
python -c "import cv2; print('✅ OpenCV available')" 2>/dev/null || echo "❌ OpenCV not available"
python -c "import yaml; print('✅ PyYAML available')" 2>/dev/null || echo "❌ PyYAML not available"

# Test application import
echo ""
echo "Testing application import..."
python -c "from desktop_app.main_gui import main; print('✅ Application imports successfully')" 2>/dev/null || echo "❌ Application import failed"

echo ""
echo "Installation test complete!"
echo ""
echo "To start CHAOS:"
echo "  $INSTALL_DIR/start_chaos.sh"
echo ""
echo "To uninstall:"
echo "  $INSTALL_DIR/uninstall.sh"
