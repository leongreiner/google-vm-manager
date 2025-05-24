#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/google-vm-manager.desktop"
ICON_FILE="$SCRIPT_DIR/google-vm-manager.png"

echo "Creating desktop entry for Google VM Manager..."

# Create the desktop entry
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Google VM Manager
Comment=Control Google Cloud VM instances with VNC support
Exec=python3 "$SCRIPT_DIR/google_vm_gui.py"
Icon=$ICON_FILE
Terminal=false
Categories=Network;System;
StartupNotify=true
EOF

# Make the desktop file executable
chmod +x "$DESKTOP_FILE"

# Create a simple icon if it doesn't exist
if [ ! -f "$ICON_FILE" ]; then
    echo "Creating application icon..."
    # Create a simple SVG icon and convert to PNG
    cat > "$SCRIPT_DIR/google-vm-manager.svg" << 'SVGEOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <rect width="64" height="64" rx="8" fill="#4285f4"/>
  <rect x="8" y="12" width="48" height="32" rx="4" fill="white"/>
  <rect x="12" y="16" width="40" height="20" fill="#34a853"/>
  <circle cx="20" cy="26" r="3" fill="white"/>
  <rect x="28" y="24" width="20" height="4" fill="white"/>
  <rect x="8" y="48" width="12" height="8" rx="2" fill="#ea4335"/>
  <rect x="26" y="48" width="12" height="8" rx="2" fill="#fbbc04"/>
  <rect x="44" y="48" width="12" height="8" rx="2" fill="#34a853"/>
</svg>
SVGEOF

    # Convert SVG to PNG if ImageMagick is available
    if command -v convert >/dev/null 2>&1; then
        convert "$SCRIPT_DIR/google-vm-manager.svg" "$ICON_FILE" 2>/dev/null
        rm "$SCRIPT_DIR/google-vm-manager.svg"
    elif command -v rsvg-convert >/dev/null 2>&1; then
        rsvg-convert -w 64 -h 64 "$SCRIPT_DIR/google-vm-manager.svg" > "$ICON_FILE"
        rm "$SCRIPT_DIR/google-vm-manager.svg"
    else
        # If no conversion tools available, use a generic icon
        ICON_FILE="network-server"
        echo "No image conversion tools found. Using system icon: $ICON_FILE"
        # Update the desktop file to use system icon
        sed -i "s|Icon=.*|Icon=$ICON_FILE|" "$DESKTOP_FILE"
    fi
fi

echo "✅ Desktop entry created: $DESKTOP_FILE"
echo "✅ Application icon: $ICON_FILE"
echo ""
echo "The Google VM Manager should now appear in your applications menu."
echo "You can also run it from the command line with: python3 $SCRIPT_DIR/google_vm_gui.py"

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null
    echo "✅ Desktop database updated"
fi

echo ""
echo "🚀 Setup complete! Look for 'Google VM Manager' in your applications menu."
