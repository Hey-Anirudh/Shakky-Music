#!/bin/bash
# vps_fix.sh - Permanent fix for "Node.js not running" error in Shakky bot
# Run this on your VPS as root (sudo bash vps_fix.sh)

echo "--- STARTING SHAKKY VPS REPAIR ---"

# 1. Update system package list
echo "Updating system..."
sudo apt update -y

# 2. Install essential system libraries for Native Streaming (ntgcalls)
echo "Installing essential media libraries..."
sudo apt install -y libopus0 libglib2.0-0 ffmpeg python3-pip

# 3. Ensure Node.js is installed as a reliable backup
if ! command -v node \u0026\u003e /dev/null
then
    echo "Node.js not found. Installing Node.js 18..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt install -y nodejs
else
    echo "Node.js already installed: $(node -v)"
fi

# 4. Verify/Reinstall Python dependencies to ensure binary compatibility
echo "Refreshing Python dependencies..."
pip3 install --upgrade pip
pip3 install wheel
pip3 install --ignore-installed ntgcalls pytgcalls==3.0.0.dev20

# 5. Set environment variable for the current session and persistent profile
echo "Setting implementation preferences..."
export PYTGCALLS_IMPLEMENTATION=\"native\"
if ! grep -q \"PYTGCALLS_IMPLEMENTATION\" ~/.bashrc; then
    echo 'export PYTGCALLS_IMPLEMENTATION=\"native\"' \u003e\u003e ~/.bashrc
fi

echo "--- REPAIR COMPLETE ---"
echo "Please restart your bot now."
echo "If issues persist, check 'last_error.txt' in the bot directory."
