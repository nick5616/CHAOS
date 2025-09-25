#!/bin/bash
# CHAOS Desktop Application Installer

set -e  # Exit on any error

APP_NAME="CHAOS"
INSTALL_DIR="$HOME/Applications/CHAOS"
VENV_DIR="$INSTALL_DIR/venv"
BACKUP_DIR="$HOME/.chaos_backup"

echo "CHAOS Desktop Application Installer"
echo "=================================="
echo ""

# Check if already installed
if [ -d "$INSTALL_DIR" ]; then
    echo "CHAOS is already installed at: $INSTALL_DIR"
    read -p "Do you want to reinstall? (y/N): " reinstall
    if [[ ! $reinstall =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    
    # Backup existing installation
    echo "Backing up existing installation..."
    if [ -d "$BACKUP_DIR" ]; then
        rm -rf "$BACKUP_DIR"
    fi
    mv "$INSTALL_DIR" "$BACKUP_DIR"
fi

# Create installation directory
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Get the source directory (where this script is run from)
SOURCE_DIR="$(pwd)"

# Copy application files
echo "Copying application files..."
cp -r "$SOURCE_DIR/chaos_lib" "$INSTALL_DIR/"
cp -r "$SOURCE_DIR/desktop_app" "$INSTALL_DIR/"
cp "$SOURCE_DIR/config.yaml" "$INSTALL_DIR/"
cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SOURCE_DIR/setup.sh" "$INSTALL_DIR/"
cp "$SOURCE_DIR/setup.bat" "$INSTALL_DIR/"

# Create virtual environment
echo "Creating virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv

# Activate virtual environment and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create launcher script
echo "Creating launcher..."
cat > "$INSTALL_DIR/start_chaos.sh" << 'LAUNCHER_EOF'
#!/bin/bash
# CHAOS Desktop Application Launcher

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Run the application
python desktop_app/main_gui.py
LAUNCHER_EOF

chmod +x "$INSTALL_DIR/start_chaos.sh"

# Create desktop shortcut (optional)
read -p "Create desktop shortcut? (y/N): " create_shortcut
if [[ $create_shortcut =~ ^[Yy]$ ]]; then
    SHORTCUT_PATH="$HOME/Desktop/CHAOS.desktop"
    cat > "$SHORTCUT_PATH" << 'SHORTCUT_EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=CHAOS
Comment=CS2 Highlight Analysis & Organization System
Exec=/bin/bash -c "cd $HOME/Applications/CHAOS && ./start_chaos.sh"
Icon=applications-games
Terminal=false
Categories=Game;Utility;
SHORTCUT_EOF
    chmod +x "$SHORTCUT_PATH"
    echo "Desktop shortcut created: $SHORTCUT_PATH"
fi

# Create Applications folder entry (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    APP_BUNDLE="$HOME/Applications/CHAOS.app"
    if [ -d "$APP_BUNDLE" ]; then
        rm -rf "$APP_BUNDLE"
    fi
    
    mkdir -p "$APP_BUNDLE/Contents/MacOS"
    mkdir -p "$APP_BUNDLE/Contents/Resources"
    
    # Create Info.plist
    cat > "$APP_BUNDLE/Contents/Info.plist" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>chaos</string>
    <key>CFBundleIdentifier</key>
    <string>com.chaos.desktop</string>
    <key>CFBundleName</key>
    <string>CHAOS</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
PLIST_EOF
    
    # Create launcher script
    cat > "$APP_BUNDLE/Contents/MacOS/chaos" << 'APP_LAUNCHER_EOF'
#!/bin/bash
cd "$HOME/Applications/CHAOS"
./start_chaos.sh
APP_LAUNCHER_EOF
    
    chmod +x "$APP_BUNDLE/Contents/MacOS/chaos"
    echo "macOS app bundle created: $APP_BUNDLE"
fi

echo ""
echo "Installation complete!"
echo "====================="
echo ""
echo "CHAOS has been installed to: $INSTALL_DIR"
echo ""
echo "To start CHAOS:"
echo "  - Run: $INSTALL_DIR/start_chaos.sh"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  - Or double-click: $HOME/Applications/CHAOS.app"
fi
echo ""
echo "To uninstall, run: $INSTALL_DIR/uninstall.sh"
echo ""

# Create uninstaller
cat > "$INSTALL_DIR/uninstall.sh" << 'UNINSTALL_EOF'
#!/bin/bash
# CHAOS Desktop Application Uninstaller

INSTALL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
APP_NAME="CHAOS"

echo "CHAOS Desktop Application Uninstaller"
echo "====================================="
echo ""
echo "This will remove CHAOS from: $INSTALL_DIR"
echo ""

read -p "Are you sure you want to uninstall CHAOS? (y/N): " confirm
if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo "Removing CHAOS installation..."

# Remove desktop shortcut
if [ -f "$HOME/Desktop/CHAOS.desktop" ]; then
    rm "$HOME/Desktop/CHAOS.desktop"
    echo "Removed desktop shortcut"
fi

# Remove macOS app bundle
if [[ "$OSTYPE" == "darwin"* ]]; then
    if [ -d "$HOME/Applications/CHAOS.app" ]; then
        rm -rf "$HOME/Applications/CHAOS.app"
        echo "Removed macOS app bundle"
    fi
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "Removed installation directory"
fi

echo ""
echo "CHAOS has been completely uninstalled."
echo ""

# Restore backup if it exists
if [ -d "$HOME/.chaos_backup" ]; then
    read -p "Restore previous installation from backup? (y/N): " restore
    if [[ $restore =~ ^[Yy]$ ]]; then
        mv "$HOME/.chaos_backup" "$INSTALL_DIR"
        echo "Previous installation restored."
    else
        rm -rf "$HOME/.chaos_backup"
        echo "Backup removed."
    fi
fi
UNINSTALL_EOF

chmod +x "$INSTALL_DIR/uninstall.sh"

echo "Uninstaller created: $INSTALL_DIR/uninstall.sh"
