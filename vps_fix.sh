#!/bin/bash

# 🤖 Shakky ARM VPS Universal Fixer
# This script brute-forces through 4 eras of PyTgCalls to find the one your VPS loves.

echo "🚀 Starting Shakky ARM Restoration..."

# 1. Clean up broken files
echo "🧹 Cleaning existing library clutters..."
sudo rm -rf /usr/local/lib/python3.10/dist-packages/pytgcalls* /usr/local/lib/python3.10/dist-packages/ntgcalls* /usr/local/lib/python3.10/dist-packages/tgcalls*
pip3 uninstall -y pytgcalls ntgcalls tgcalls

# 2. Iterative Testing
VERSIONS=(
    "v3:ntgcalls==2.1.0:pytgcalls==3.0.0.dev20"
    "v2:ntgcalls==2.1.0:pytgcalls==2.1.0"
    "v1:ntgcalls==1.0.5:pytgcalls==1.1.2"
    "v0:ntgcalls==1.0.5:pytgcalls==0.0.24"
)

for ENTRY in "${VERSIONS[@]}"; do
    NAME=$(echo $ENTRY | cut -d: -f1)
    NTG=$(echo $ENTRY | cut -d: -f2)
    PTG=$(echo $ENTRY | cut -d: -f3)

    echo "🧪 Testing $NAME Era..."
    pip3 install $NTG --upgrade --no-cache-dir
    pip3 install $PTG --no-deps --upgrade --force-reinstall

    echo "📡 Attempting to start bot (waiting 10s for stability)..."
    python3 -m shakky & 
    BOT_PID=$!
    
    sleep 10
    
    if ps -p $BOT_PID > /dev/null; then
        echo "✅ SUCCESS! Bot is stable on $NAME."
        echo "🎉 Your VPS environment is now restored."
        exit 0
    else
        echo "❌ $NAME failed to start. Trying next..."
        # Cleanup
        kill $BOT_PID 2>/dev/null
        pip3 uninstall -y pytgcalls ntgcalls
    fi
done

echo "⚠️ ALL VERSIONS FAILED. Please check /nohup.out for details."
exit 1
