#!/bin/bash
# vps_fix.sh - Enhanced repair for ARM/x64 VPS
# Run as root: sudo bash vps_fix.sh

echo "--- SHAKKY VPS REPAIR v2.0 ---"

# 1. Core Native Dependencies
echo "Installing media libraries..."
sudo apt update -y
sudo apt install -y ffmpeg libopus-dev libglib2.0-0 pkg-config \
    libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev \
    libswresample-dev libswscale-dev python3-pip python3-dev \
    build-essential curl nodejs

# 2. Fix Node Path (Common ARM Issue)
echo "Syncing Node.js paths..."
NODE_PATH=$(which node)
if [ ! -z "$NODE_PATH" ]; then
    sudo ln -sf "$NODE_PATH" /usr/bin/node
    sudo ln -sf "$NODE_PATH" /usr/local/bin/node
fi

# 3. Clean environment logic
echo "Resetting environment implementation..."
sed -i '/PYTGCALLS_IMPLEMENTATION/d' ~/.bashrc
# On ARM, we default to javascript because ntgcalls wheels are often missing for 3.x dev
if [[ $(uname -m) == *"aarch64"* ]]; then
    echo "ARM detected: Defaulting to JavaScriptCore for stability."
    echo 'export PYTGCALLS_IMPLEMENTATION="javascript"' >> ~/.bashrc
    export PYTGCALLS_IMPLEMENTATION="javascript"
else
    echo "x86/x64 detected: Defaulting to NativeCore."
    echo 'export PYTGCALLS_IMPLEMENTATION="native"' >> ~/.bashrc
    export PYTGCALLS_IMPLEMENTATION="native"
fi

# 4. Refresh Dependencies
echo "Refreshing Python Core..."
python3 -m pip install --upgrade pip
# Install with javascript extra to ensure tgcalls is ready
pip3 install "pytgcalls[javascript]==3.0.0.dev20" --upgrade
# Try to install ntgcalls but don't fail if it's missing (JS will take over)
pip3 install ntgcalls==3.0.0.dev20 || echo "Native wheel missing for this arch. Using JS fallback."

echo "--- REPAIR COMPLETE ---"
echo "Please restart your bot."

