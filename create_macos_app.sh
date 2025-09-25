#!/bin/bash
# Create proper macOS app bundle for CHAOS

INSTALL_DIR="$HOME/Applications/CHAOS"
APP_BUNDLE="$HOME/Applications/CHAOS.app"

echo "Creating macOS app bundle for CHAOS..."

# Remove existing app bundle if it exists
if [ -d "$APP_BUNDLE" ]; then
    echo "Removing existing app bundle..."
    rm -rf "$APP_BUNDLE"
fi

# Create app bundle structure
echo "Creating app bundle structure..."
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Create Info.plist
echo "Creating Info.plist..."
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
    <key>CFBundleDisplayName</key>
    <string>CHAOS</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.14</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
PLIST_EOF

# Create launcher script
echo "Creating launcher script..."
cat > "$APP_BUNDLE/Contents/MacOS/chaos" << 'APP_LAUNCHER_EOF'
#!/bin/bash
# CHAOS Desktop Application Launcher

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
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
chmod +x "$APP_BUNDLE/Contents/MacOS/chaos"

# Create a simple icon (optional)
echo "Creating app icon..."
# We'll create a simple text-based icon for now
cat > "$APP_BUNDLE/Contents/Resources/chaos_icon.txt" << 'ICON_EOF'
CHAOS
CS2 Highlight Analysis
ICON_EOF

# Update Spotlight index
echo "Updating Spotlight index..."
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_BUNDLE"

echo ""
echo "✅ macOS app bundle created successfully!"
echo "📱 App bundle: $APP_BUNDLE"
echo "🔍 Spotlight should now find 'CHAOS' when you search"
echo ""
echo "You can now:"
echo "  - Search for 'CHAOS' in Spotlight"
echo "  - Double-click the app in Applications"
echo "  - Launch from Launchpad"
echo ""

# Test if Spotlight can find it
echo "Testing Spotlight search..."
if mdfind "kMDItemDisplayName == 'CHAOS'" | grep -q "CHAOS.app"; then
    echo "✅ Spotlight can find the app!"
else
    echo "⚠️  Spotlight might need a moment to index the app"
    echo "   Try searching again in a few seconds"
fi
