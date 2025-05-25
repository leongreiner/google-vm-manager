# Google VM Control Panel

A PyQt5-based GUI application for managing Google Cloud VM instances with VNC support. This tool allows you to easily start/stop multiple Google Cloud VMs and automatically connect to them via VNC using Remmina.

## Installation

### 1. Install System Dependencies

```bash
# Update package list
sudo apt update

# Install Python 3 and pip
sudo apt install python3 python3-pip

# Install PyQt5
sudo apt install python3-pyqt5

# Install Remmina (VNC client)
sudo apt install remmina remmina-plugin-vnc

# Install network tools (for connection testing)
sudo apt install netcat-openbsd

# Install Git (if not already installed)
sudo apt install git
```

### 2. Install Google Cloud SDK

If you don't have Google Cloud SDK installed:

```bash
# Install Required Packages
sudo apt install apt-transport-https ca-certificates gnupg curl

# Add the Google Cloud SDK Package Source
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Import the Google Cloud public key
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -

# Update and install the Cloud SDK
sudo apt update && sudo apt install google-cloud-cli
```

### 3. Configure Google Cloud SDK

```bash
# Initialize gcloud and authenticate
gcloud init

# Set your default project (replace with your project ID)
gcloud config set project YOUR_PROJECT_ID

# Verify installation
gcloud compute instances list
```

### 4. Download the Application

```bash
# Clone the repository
git clone https://github.com/leongreiner/google-vm-manager.git

# Navigate to the application directory
cd google-vm-manager

# Make the shell script executable
chmod +x google_vm_manager.sh
chmod +x google_vm_gui.py

# Create system-wide desktop entry (optional - adds to applications menu for all users)
chmod +x create_desktop_entry.sh
sudo ./create_desktop_entry.sh
```

## VM Setup Requirements

### 1. SSH Key Configuration

Generate SSH keys for your VMs (if you haven't already):

```bash
# Generate SSH key pair (replace 'your_vm_name' with actual VM name)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/your_vm_name_key -C "your_email@example.com"

# Add public key to your VM's metadata or user account
# You can do this via Google Cloud Console or gcloud command
```

### 2. VM Requirements

Your Google Cloud VMs need to have:

- **VNC Server installed**: `sudo apt install tigervnc-standalone-server tigervnc-common`
- **Desktop environment**: GNOME, XFCE, or similar
- **SSH access enabled**
- **Firewall rules**: Allow VNC port 5901 (if using external VNC access)

#### Easy VM Setup with VS Code Remote

For easier VM management and VNC server installation, you can use VS Code with the Remote SSH extension:

1. **Install VS Code Remote SSH extension**: Install the "Remote - SSH" extension in VS Code
2. **Automatic SSH config**: This GUI automatically updates your `~/.ssh/config` file when starting VMs, making it easy to connect via VS Code
3. **Connect via VS Code**: After starting a VM (with or without VNC), you can connect directly through VS Code Remote SSH using the VM name

#### Install VNC Server on your VM:

This can be done easily by starting the VM without VNC first, then connecting via VS Code Remote SSH to install the required packages:

```bash
# Start VM without VNC using this GUI, then connect via VS Code Remote SSH
# Or SSH directly into your VM
ssh your_username@your_vm_ip

# Install VNC server
sudo apt update
sudo apt install tigervnc-standalone-server tigervnc-common

# Install a lightweight desktop (optional, if not already installed)
sudo apt install xfce4 xfce4-goodies

# Set up VNC password (optional, for secure connections)
vncpasswd
```

## Usage

### 1. Launch the Application

You can launch the application in several ways:

**Option 1: From Applications Menu (if desktop entry was created)**
- Look for "Google VM Manager" in your applications menu
- Click to launch

**Option 2: From Command Line**
```bash
cd google-vm-manager
python3 google_vm_gui.py
```

**Option 3: From File Manager**
- Navigate to the `google-vm-manager` directory
- Double-click on `google_vm_gui.py`

### 2. Configure VMs

1. Click the **"Settings"** button in the main window
2. Click **"Add VM"** to add a new VM configuration
3. Fill in the required fields:
   - **VM Name**: The name of your Google Cloud VM instance
   - **Zone**: Select from the dropdown (e.g., `us-central1-a`, `europe-west1-b`)
   - **Project ID**: Your Google Cloud project ID
4. Click **"OK"** to save the configuration
5. Repeat for additional VMs

### 3. Start/Stop VMs

1. Select a VM from the dropdown in the main window
2. Choose an action:
   - **Start with VNC**: Starts the VM and sets up VNC connection
   - **Start without VNC**: Starts the VM only (no VNC setup)
   - **Stop VM**: Stops the selected VM
3. Monitor the progress in the log output area

### 4. VNC Connection

When starting a VM with VNC:
- The application automatically detects your screen resolution
- Sets up the VNC server on the remote VM
- Creates a Remmina configuration file
- Launches Remmina with the connection

## File Structure

```
google-vm-manager/
├── google_vm_gui.py              # Main GUI application
├── google_vm_manager.sh          # Shell script for VM operations
├── create_desktop_entry.sh       # Script to create desktop entry
├── google-vm-manager.png         # Application icon (required for desktop entry)
├── vm_settings.json              # VM configurations (created automatically)
├── README.md                     # This file
└── *.remmina                     # Remmina connection files (created automatically)
```

## Configuration Files

The application creates these files in the same directory:

- `vm_settings.json`: Stores your VM configurations
- `{vm_name}_dynamic.remmina`: Remmina connection files for each VM

## Troubleshooting

### Common Issues

**1. "Permission denied" error:**
```bash
chmod +x google_vm_manager.sh
```

**2. VNC connection fails:**
- Check if VNC server is installed on the VM
- Verify firewall settings allow port 5901
- Ensure the VM is fully started before connecting

**3. gcloud authentication issues:**
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

**4. Missing PyQt5:**
```bash
sudo apt install python3-pyqt5
```

**5. VNC server refuses to start (security warning):**
- Set up VNC password authentication with `vncpasswd` on your VM

### SSH Configuration

The application automatically updates your `~/.ssh/config` file with VM IP addresses. Make sure your SSH keys are properly configured:

```bash
# Example SSH config entry (automatically generated)
Host your_vm_name
    HostName VM_EXTERNAL_IP
    User your_username
    IdentityFile ~/.ssh/your_vm_name_key
    StrictHostKeyChecking no
```

## Requirements Summary

- **OS**: Ubuntu/Debian Linux
- **Python**: 3.6+
- **Dependencies**: PyQt5, Google Cloud SDK, Remmina, netcat
- **Network**: Internet connection for Google Cloud API access
- **Authentication**: Google Cloud credentials, SSH keys for VMs