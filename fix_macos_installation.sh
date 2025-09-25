#!/bin/bash
# Fix macOS installation by moving to system Applications folder

echo "Fixing CHAOS macOS installation..."

# Move the app bundle to system Applications folder
echo "Moving CHAOS.app to system Applications folder..."
sudo mv ~/Applications/CHAOS.app /Applications/

# Keep the CHAOS folder in user Applications (contains the actual app files)
echo "CHAOS folder remains in ~/Applications/CHAOS/ (contains app files)"

# Update the app bundle launcher to point to the correct location
echo "Updating app bundle launcher..."
cat > /Applications/CHAOS.app/Contents/MacOS/chaos << 'APP_LAUNCHER_EOF'
#!/bin/bash
# CHAOS Desktop Application Launcher

CHAOS_DIR="$HOME/Applications/CHAOS"

# Check if CHAOS is installed
if [ ! -d "$CHAOS_DIR" ]; then
    osascript -e 'display dialog "CHAOS is not installed. Please run the installer first." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# Change to CHAOS directory and run
cd "$CHAOS_DIR"
exec ./start_chaos.sh
APP_LAUNCHER_EOF

# Make launcher executable
chmod +x /Applications/CHAOS.app/Contents/MacOS/chaos

# Register with Launch Services
echo "Registering with Launch Services..."
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f /Applications/CHAOS.app

# Force Spotlight to re-index
echo "Forcing Spotlight re-index..."
mdimport /Applications/CHAOS.app

echo ""
echo "✅ Installation fixed!"
echo "📱 CHAOS.app is now in /Applications/ (system folder)"
echo "📁 CHAOS files remain in ~/Applications/CHAOS/ (user folder)"
echo "🔍 Spotlight should now find 'CHAOS' when you search"
echo ""
echo "You can now:"
echo "  - Search for 'CHAOS' in Spotlight (Cmd+Space)"
echo "  - Find it in Applications folder"
echo "  - Launch from Launchpad"
echo ""

# Test Spotlight
echo "Testing Spotlight search..."
if mdfind "kMDItemDisplayName == 'CHAOS'" | grep -q "CHAOS.app"; then
    echo "✅ Spotlight can find the app!"
else
    echo "⚠️  Spotlight might need a moment to index the app"
fi
