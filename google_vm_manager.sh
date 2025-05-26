#!/bin/bash

# Parse arguments
MODE="$1"
VM_NAME="$2"
ZONE="$3"
PROJECT_ID="$4"
VNC_RESOLUTION="$5"
NO_VNC=false

if [[ "$6" == "--no-vnc" || "$6" == "no_vnc" ]]; then
  NO_VNC=true
fi

# Check valid action and parameters
if [[ "$MODE" != "start" && "$MODE" != "stop" ]] || [[ -z "$VM_NAME" ]] || [[ -z "$ZONE" ]] || [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: $0 start|stop VM_NAME ZONE PROJECT_ID RESOLUTION [--no-vnc]"
  exit 1
fi

# Set default resolution if not provided
if [[ -z "$VNC_RESOLUTION" ]]; then
  VNC_RESOLUTION="1920x1080"
fi

VNC_DISPLAY=":1"
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
REMOTECONFIG="${SCRIPT_DIR}/${VM_NAME}_dynamic.remmina"

echo "▶ $MODE VM: $VM_NAME in zone $ZONE (project: $PROJECT_ID)"

# Start/stop VM with filtered output
if [[ "$MODE" == "start" ]]; then
  echo "🚀 Starting VM..."
else
  echo "🛑 Stopping VM..."
fi

gcloud compute instances "$MODE" "$VM_NAME" \
  --zone="$ZONE" \
  --project="$PROJECT_ID" \
  --quiet 2>/dev/null | grep -E "(done|Updated|ERROR|FAILED)" || echo "✅ VM operation completed"

if [[ "$MODE" == "stop" ]]; then
  echo "✅ VM stopped successfully"
  exit 0
fi

echo "⏳ Getting VM IP address..."
sleep 3
VM_IP=$(gcloud compute instances describe "$VM_NAME" \
  --zone="$ZONE" \
  --project="$PROJECT_ID" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null)

if [[ -z "$VM_IP" ]]; then
  echo "❌ Could not retrieve external IP."
  exit 1
fi

echo "✅ VM external IP: $VM_IP"

# Update SSH config silently
SSH_CONFIG_FILE=~/.ssh/config
SSH_HOST_ENTRY="Host $VM_NAME"

if grep -q "$SSH_HOST_ENTRY" "$SSH_CONFIG_FILE" 2>/dev/null; then
    awk -v vm="$VM_NAME" -v ip="$VM_IP" '
        $1 == "Host" && $2 == vm { print; in_block=1; next }
        in_block && $1 == "HostName" { print "    HostName " ip; next }
        in_block && $1 == "Host" && $2 != vm { in_block=0 }
        { print }
    ' "$SSH_CONFIG_FILE" > "${SSH_CONFIG_FILE}.tmp" && mv "${SSH_CONFIG_FILE}.tmp" "$SSH_CONFIG_FILE"
else
    echo -e "\nHost $VM_NAME\n    HostName $VM_IP\n    User leon_greiner12345\n    IdentityFile ~/.ssh/${VM_NAME}_key\n    StrictHostKeyChecking no" >> "$SSH_CONFIG_FILE"
fi

if [ "$NO_VNC" = true ]; then
  echo "✅ VM started without VNC"
  exit 0
fi

echo "🖥️ Setting up VNC server ($VNC_RESOLUTION)..."

# Kill existing VNC sessions silently
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
    leon_greiner12345@$VM_IP "vncserver -kill $VNC_DISPLAY" >/dev/null 2>&1

sleep 5

# Start VNC server and capture only essential output
VNC_OUTPUT=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
    leon_greiner12345@$VM_IP "vncserver $VNC_DISPLAY -geometry $VNC_RESOLUTION -depth 24 -localhost no" 2>&1)

if echo "$VNC_OUTPUT" | grep -q "desktop"; then
    echo "✅ VNC server started successfully"
else
    echo "❌ VNC server failed to start"
    echo "$VNC_OUTPUT" | grep -E "(ERROR|FAILED|refused)"
    exit 1
fi

echo "⏳ Waiting for VNC to be ready..."
sleep 5

# Test connection silently
if nc -z -w5 $VM_IP 5901 >/dev/null 2>&1; then
    echo "✅ VNC connection ready"
else
    echo "❌ VNC server not responding"
    exit 1
fi

# Generate Remmina config
mkdir -p "$(dirname "$REMOTECONFIG")"
cat > "$REMOTECONFIG" <<EOL
[remmina]
protocol=VNC
server=$VM_IP:5901
name=${VM_NAME}_dynamic
group=
password=
quality=2
colordepth=32
disableencryption=1
EOL

echo "🚀 Launching VNC client..."

# Launch Remmina silently in background
G_MESSAGES_DEBUG="" remmina -c "$REMOTECONFIG" >/dev/null 2>&1 &

sleep 2
echo "✅ Setup complete! VNC client should be starting..."
echo "💡 Manual connection: $VM_IP:5901"
