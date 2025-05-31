#!/bin/bash

# Parse arguments
MODE="$1"
VM_NAME="$2"
ZONE="$3"
PROJECT_ID="$4"
VNC_RESOLUTION="$5"
SSH_KEY_PATH="$6"
SSH_USERNAME="$7"
NO_VNC=false

# Check if the 7th argument is --no-vnc or if the 8th argument is --no-vnc
if [[ "$7" == "--no-vnc" || "$7" == "no_vnc" ]]; then
  NO_VNC=true
  SSH_USERNAME=""
elif [[ "$8" == "--no-vnc" || "$8" == "no_vnc" ]]; then
  NO_VNC=true
fi

# Check valid action and parameters
if [[ "$MODE" != "start" && "$MODE" != "stop" ]] || [[ -z "$VM_NAME" ]] || [[ -z "$ZONE" ]] || [[ -z "$PROJECT_ID" ]]; then
  echo "Usage: $0 start|stop VM_NAME ZONE PROJECT_ID RESOLUTION [SSH_KEY_PATH] [SSH_USERNAME] [--no-vnc]"
  exit 1
fi

# Set default resolution if not provided
if [[ -z "$VNC_RESOLUTION" ]]; then
  VNC_RESOLUTION="1920x1080"
fi

# Use default SSH key if not provided
if [[ -z "$SSH_KEY_PATH" ]]; then
  SSH_KEY_PATH="~/.ssh/${VM_NAME}_key"
fi

# Expand tilde in SSH key path
SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"

# Get current user for SSH if not specified
if [[ -z "$SSH_USERNAME" ]]; then
  SSH_USERNAME=$(whoami)
fi

# Get current user for local operations
CURRENT_USER=$(whoami)

VNC_DISPLAY=":1"
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
REMOTECONFIG="${SCRIPT_DIR}/${VM_NAME}_dynamic.remmina"

echo "▶ $MODE VM: $VM_NAME in zone $ZONE (project: $PROJECT_ID)"
echo "▶ Using SSH username: $SSH_USERNAME"

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
    awk -v vm="$VM_NAME" -v ip="$VM_IP" -v key="$SSH_KEY_PATH" -v username="$SSH_USERNAME" '
        $1 == "Host" && $2 == vm { print; in_block=1; next }
        in_block && $1 == "HostName" { print "    HostName " ip; next }
        in_block && $1 == "User" { print "    User " username; next }
        in_block && $1 == "IdentityFile" { print "    IdentityFile " key; next }
        in_block && $1 == "Host" && $2 != vm { in_block=0 }
        { print }
    ' "$SSH_CONFIG_FILE" > "${SSH_CONFIG_FILE}.tmp" && mv "${SSH_CONFIG_FILE}.tmp" "$SSH_CONFIG_FILE"
else
    echo -e "\nHost $VM_NAME\n    HostName $VM_IP\n    User $SSH_USERNAME\n    IdentityFile $SSH_KEY_PATH\n    StrictHostKeyChecking no" >> "$SSH_CONFIG_FILE"
fi

if [ "$NO_VNC" = true ]; then
  echo "✅ VM started without VNC"
  exit 0
fi

echo "🖥️ Setting up VNC server ($VNC_RESOLUTION)..."

# Kill existing VNC sessions silently
ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
    $SSH_USERNAME@$VM_IP "vncserver -kill $VNC_DISPLAY" >/dev/null 2>&1

sleep 5

# Start VNC server and capture only essential output
VNC_OUTPUT=$(ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
    $SSH_USERNAME@$VM_IP "vncserver $VNC_DISPLAY -geometry $VNC_RESOLUTION -depth 24 -localhost no" 2>&1)

if echo "$VNC_OUTPUT" | grep -q "desktop"; then
    echo "✅ VNC server started successfully"
    # Extract the actual display number from output
    ACTUAL_DISPLAY=$(echo "$VNC_OUTPUT" | grep -o ":[0-9]\+" | head -1)
    if [[ -n "$ACTUAL_DISPLAY" ]]; then
        VNC_DISPLAY="$ACTUAL_DISPLAY"
        echo "▶ VNC running on display $VNC_DISPLAY"
    fi
else
    echo "❌ VNC server failed to start"
    echo "$VNC_OUTPUT" | grep -E "(ERROR|FAILED|refused|Permission denied)"
    exit 1
fi

echo "⏳ Waiting for VNC to be ready..."
sleep 8

# Calculate VNC port (display :1 = port 5901, :2 = port 5902, etc.)
DISPLAY_NUM=${VNC_DISPLAY#:}
VNC_PORT=$((5900 + DISPLAY_NUM))

echo "▶ Testing VNC connection on port $VNC_PORT..."

# Test connection silently with multiple attempts
VNC_READY=false
for i in {1..3}; do
    if nc -z -w5 $VM_IP $VNC_PORT >/dev/null 2>&1; then
        VNC_READY=true
        break
    fi
    echo "▶ Attempt $i failed, retrying..."
    sleep 3
done

if [ "$VNC_READY" = true ]; then
    echo "✅ VNC connection ready on port $VNC_PORT"
else
    echo "❌ VNC server not responding on port $VNC_PORT"
    # Try to get more info about what's running
    echo "▶ Checking VNC processes on remote server..."
    ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
        $SSH_USERNAME@$VM_IP "ps aux | grep vnc | grep -v grep" 2>/dev/null || echo "No VNC processes found"
    exit 1
fi

# Generate Remmina config
mkdir -p "$(dirname "$REMOTECONFIG")"
cat > "$REMOTECONFIG" <<EOL
[remmina]
protocol=VNC
server=$VM_IP:$VNC_PORT
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
echo "💡 Manual connection: $VM_IP:$VNC_PORT"
