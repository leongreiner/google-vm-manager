import sys, os, subprocess, json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QDialogButtonBox, QTabWidget
)
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette, QScreen
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

# Use relative paths for distribution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(SCRIPT_DIR, "google_vm_manager.sh")
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "vm_settings.json")

class VMStatusWorker(QThread):
    status_ready = pyqtSignal(str, str)  # status, color

    def __init__(self, vm_config):
        super().__init__()
        self.vm_config = vm_config

    def run(self):
        try:
            # Get both status and detailed info to better determine actual state
            cmd = f"gcloud compute instances describe {self.vm_config['name']} --zone={self.vm_config['zone']} --project={self.vm_config['project_id']} --format='value(status,scheduling.preemptible)'"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output_lines = result.stdout.strip().split('\n')
                status = output_lines[0] if output_lines else 'UNKNOWN'
                
                # Handle Google Cloud's inconsistent status reporting
                # Sometimes "TERMINATED" is used for stopped preemptible instances
                if status == 'TERMINATED':
                    # Check if this is actually a stopped instance vs truly terminated
                    list_cmd = f"gcloud compute instances list --filter='name={self.vm_config['name']}' --zones={self.vm_config['zone']} --project={self.vm_config['project_id']} --format='value(status)'"
                    list_result = subprocess.run(
                        ["bash", "-c", list_cmd],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if list_result.returncode == 0 and list_result.stdout.strip():
                        # If the instance appears in the list, it's likely STOPPED, not truly TERMINATED
                        actual_status = list_result.stdout.strip()
                        if actual_status in ['TERMINATED', 'STOPPING']:
                            status = 'STOPPED'  # Treat as stopped for practical purposes
                        else:
                            status = actual_status
                
                # Map status to colors
                color_map = {
                    'RUNNING': '#4CAF50',      # Green
                    'STOPPED': '#f44336',      # Red
                    'STOPPING': '#ff9800',     # Orange
                    'STARTING': '#2196F3',     # Blue
                    'PROVISIONING': '#9C27B0', # Purple
                    'REPAIRING': '#ff5722',    # Deep Orange
                    'TERMINATED': '#607D8B'    # Blue Grey (truly terminated)
                }
                color = color_map.get(status, '#757575')  # Default grey
                self.status_ready.emit(status, color)
            else:
                self.status_ready.emit('UNKNOWN', '#757575')
        except Exception:
            self.status_ready.emit('ERROR', '#f44336')

class GoogleVMWorker(QThread):
    output = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, action, vm_config, no_vnc=False, resolution="1920x1080"):
        super().__init__()
        self.action = action
        self.vm_config = vm_config
        self.no_vnc = no_vnc
        self.resolution = resolution

    def run(self):
        # Ensure script has execute permissions
        try:
            import stat
            st = os.stat(SCRIPT_PATH)
            if not bool(st.st_mode & stat.S_IEXEC):
                os.chmod(SCRIPT_PATH, st.st_mode | stat.S_IEXEC)
                self.output.emit(f"Fixed permissions for {SCRIPT_PATH}")
        except Exception as e:
            self.output.emit(f"Warning: Could not check/fix script permissions: {e}")

        # Get SSH key path and username from config
        ssh_key_path = self.vm_config.get('ssh_key_path', '')
        ssh_username = self.vm_config.get('ssh_username', '')
        
        cmd = f"{SCRIPT_PATH} {self.action} {self.vm_config['name']} {self.vm_config['zone']} {self.vm_config['project_id']} {self.resolution} {ssh_key_path}"
        # Add username parameter if available
        if ssh_username:
            cmd += f" {ssh_username}"
            
        if self.no_vnc:
            cmd += " --no-vnc"
        
        process = subprocess.Popen(
            ["bash", "-lc", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        for line in process.stdout:
            self.output.emit(line.strip())
        
        exit_code = process.wait()
        self.finished.emit(exit_code)

class VMSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VM Settings")
        self.setFixedSize(600, 500)
        self.vm_configs = self.load_settings()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # VM List
        list_layout = QVBoxLayout()
        list_layout.addWidget(QLabel("Configured VMs:"))
        
        self.vm_list = QListWidget()
        self.refresh_vm_list()
        list_layout.addWidget(self.vm_list)
        
        # Buttons for VM management
        vm_btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add VM")
        self.edit_btn = QPushButton("Edit VM")
        self.delete_btn = QPushButton("Delete VM")
        
        self.add_btn.clicked.connect(self.add_vm)
        self.edit_btn.clicked.connect(self.edit_vm)
        self.delete_btn.clicked.connect(self.delete_vm)
        
        vm_btn_layout.addWidget(self.add_btn)
        vm_btn_layout.addWidget(self.edit_btn)
        vm_btn_layout.addWidget(self.delete_btn)
        
        list_layout.addLayout(vm_btn_layout)
        layout.addLayout(list_layout)
        
        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_settings(self):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_settings(self):
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(self.vm_configs, f, indent=2)

    def refresh_vm_list(self):
        self.vm_list.clear()
        for vm in self.vm_configs:
            item = QListWidgetItem(f"{vm['name']} ({vm['zone']}, {vm['project_id']})")
            item.setData(Qt.UserRole, vm)
            self.vm_list.addItem(item)

    def add_vm(self):
        dialog = VMConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.vm_configs.append(dialog.get_config())
            self.refresh_vm_list()

    def edit_vm(self):
        current_item = self.vm_list.currentItem()
        if current_item:
            vm_config = current_item.data(Qt.UserRole)
            dialog = VMConfigDialog(self, vm_config)
            if dialog.exec_() == QDialog.Accepted:
                index = self.vm_configs.index(vm_config)
                self.vm_configs[index] = dialog.get_config()
                self.refresh_vm_list()

    def delete_vm(self):
        current_item = self.vm_list.currentItem()
        if current_item:
            vm_config = current_item.data(Qt.UserRole)
            reply = QMessageBox.question(self, "Delete VM", 
                                       f"Delete VM '{vm_config['name']}'?")
            if reply == QMessageBox.Yes:
                self.vm_configs.remove(vm_config)
                self.refresh_vm_list()

    def accept(self):
        self.save_settings()
        super().accept()

class VMConfigDialog(QDialog):
    def __init__(self, parent=None, vm_config=None):
        super().__init__(parent)
        self.setWindowTitle("VM Configuration")
        self.vm_config = vm_config or {}
        self.setup_ui()

    def get_google_zones(self):
        """Return list of Google Cloud zones"""
        return [
            "us-central1-a", "us-central1-b", "us-central1-c", "us-central1-f",
            "us-east1-a", "us-east1-b", "us-east1-c", "us-east1-d",
            "us-east4-a", "us-east4-b", "us-east4-c",
            "us-west1-a", "us-west1-b", "us-west1-c",
            "us-west2-a", "us-west2-b", "us-west2-c",
            "us-west3-a", "us-west3-b", "us-west3-c",
            "us-west4-a", "us-west4-b", "us-west4-c",
            "europe-central2-a", "europe-central2-b", "europe-central2-c",
            "europe-north1-a", "europe-north1-b", "europe-north1-c",
            "europe-west1-b", "europe-west1-c", "europe-west1-d",
            "europe-west2-a", "europe-west2-b", "europe-west2-c",
            "europe-west3-a", "europe-west3-b", "europe-west3-c",
            "europe-west4-a", "europe-west4-b", "europe-west4-c",
            "europe-west6-a", "europe-west6-b", "europe-west6-c",
            "europe-west8-a", "europe-west8-b", "europe-west8-c",
            "europe-west9-a", "europe-west9-b", "europe-west9-c",
            "asia-east1-a", "asia-east1-b", "asia-east1-c",
            "asia-east2-a", "asia-east2-b", "asia-east2-c",
            "asia-northeast1-a", "asia-northeast1-b", "asia-northeast1-c",
            "asia-northeast2-a", "asia-northeast2-b", "asia-northeast2-c",
            "asia-northeast3-a", "asia-northeast3-b", "asia-northeast3-c",
            "asia-south1-a", "asia-south1-b", "asia-south1-c",
            "asia-south2-a", "asia-south2-b", "asia-south2-c",
            "asia-southeast1-a", "asia-southeast1-b", "asia-southeast1-c",
            "asia-southeast2-a", "asia-southeast2-b", "asia-southeast2-c",
            "australia-southeast1-a", "australia-southeast1-b", "australia-southeast1-c",
            "australia-southeast2-a", "australia-southeast2-b", "australia-southeast2-c",
            "southamerica-east1-a", "southamerica-east1-b", "southamerica-east1-c",
            "southamerica-west1-a", "southamerica-west1-b", "southamerica-west1-c",
            "northamerica-northeast1-a", "northamerica-northeast1-b", "northamerica-northeast1-c",
            "northamerica-northeast2-a", "northamerica-northeast2-b", "northamerica-northeast2-c"
        ]

    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.name_edit = QLineEdit(self.vm_config.get('name', ''))
        
        self.zone_combo = QComboBox()
        zones = self.get_google_zones()
        self.zone_combo.addItems(zones)
        # Set current zone if editing existing VM
        current_zone = self.vm_config.get('zone', '')
        if current_zone in zones:
            self.zone_combo.setCurrentText(current_zone)
        self.zone_combo.setEditable(True)  # Allow custom zones
        
        self.project_edit = QLineEdit(self.vm_config.get('project_id', ''))
        
        # Add SSH key selection
        ssh_key_layout = QHBoxLayout()
        self.ssh_key_edit = QLineEdit(self.vm_config.get('ssh_key_path', ''))
        self.ssh_key_edit.setPlaceholderText("Path to SSH private key")
        self.ssh_key_browse = QPushButton("Browse...")
        self.ssh_key_browse.clicked.connect(self.browse_ssh_key)
        ssh_key_layout.addWidget(self.ssh_key_edit)
        ssh_key_layout.addWidget(self.ssh_key_browse)
        
        layout.addRow("VM Name:", self.name_edit)
        layout.addRow("Zone:", self.zone_combo)
        layout.addRow("Project ID:", self.project_edit)
        layout.addRow("SSH Key:", ssh_key_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_ssh_key(self):
        from PyQt5.QtWidgets import QFileDialog
        
        home_dir = os.path.expanduser("~")
        ssh_dir = os.path.join(home_dir, ".ssh")
        
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Key", ssh_dir, 
            "SSH Keys (id_rsa id_*);; All Files (*)"
        )
        
        if fileName:
            self.ssh_key_edit.setText(fileName)
            # Try to extract username from public key
            username = self.extract_username_from_key(fileName)
            if username:
                # Display the extracted username
                QMessageBox.information(
                    self, 
                    "Username Detected", 
                    f"Username '{username}' will be used for SSH connection."
                )

    def extract_username_from_key(self, private_key_path):
        """Extract username from SSH key's corresponding public key"""
        try:
            # Try to find the public key file
            public_key_path = private_key_path + ".pub"
            if not os.path.exists(public_key_path):
                return None
                
            # Read the public key file
            with open(public_key_path, 'r') as f:
                pubkey_content = f.read().strip()
            
            # The public key format is typically: <type> <key> <comment>
            # The comment often contains an email address
            parts = pubkey_content.split()
            if len(parts) >= 3:
                comment = parts[2]
                # Extract username from email (part before @)
                if '@' in comment:
                    return comment.split('@')[0]
            return None
        except Exception as e:
            print(f"Error extracting username from key: {e}")
            return None

    def get_config(self):
        config = {
            'name': self.name_edit.text(),
            'zone': self.zone_combo.currentText(),
            'project_id': self.project_edit.text(),
            'ssh_key_path': self.ssh_key_edit.text(),
        }
        
        # Try to extract username from key
        username = self.extract_username_from_key(self.ssh_key_edit.text())
        if username:
            config['ssh_username'] = username
            
        return config

    def accept(self):
        if not all([self.name_edit.text(), self.zone_combo.currentText(), self.project_edit.text()]):
            QMessageBox.warning(self, "Error", "VM name, zone, and project ID are required!")
            return
        super().accept()

class GoogleVMControlApp(QWidget):
    def __init__(self):
        super().__init__()
        self.vm_configs = self.load_vm_configs()
        self.status_worker = None
        self.setup_ui()
        self.setup_status_timer()

    def load_vm_configs(self):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def get_screen_resolution(self):
        screen = QApplication.primaryScreen()
        size = screen.size()
        return f"{size.width()}x{size.height()}"

    def setup_ui(self):
        self.setWindowTitle("Google VM Control")
        self.setWindowIcon(QIcon.fromTheme("network-server"))
        self.setFixedSize(500, 500)

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Remove the unexpected message box here

        title = QLabel("📟 Google VM Control Panel")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # VM Selection with Status
        vm_layout = QHBoxLayout()
        vm_layout.addWidget(QLabel("Select VM:"))
        self.vm_combo = QComboBox()
        self.vm_combo.currentTextChanged.connect(self.on_vm_selection_changed)
        self.refresh_vm_combo()
        vm_layout.addWidget(self.vm_combo)
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        vm_layout.addWidget(self.settings_btn)
        main_layout.addLayout(vm_layout)

        # VM Status Display
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.vm_status_label = QLabel("Select a VM")
        self.vm_status_label.setFont(QFont("Arial", 11, QFont.Bold))
        self.vm_status_label.setStyleSheet("padding: 5px; border-radius: 3px; background-color: #757575; color: white;")
        status_layout.addWidget(self.vm_status_label)
        status_layout.addStretch()
        
        self.refresh_status_btn = QPushButton("🔄")
        self.refresh_status_btn.setFixedSize(30, 30)
        self.refresh_status_btn.setToolTip("Refresh Status")
        self.refresh_status_btn.clicked.connect(self.refresh_vm_status)
        status_layout.addWidget(self.refresh_status_btn)
        main_layout.addLayout(status_layout)

        self.status_label = QLabel("Ready.")
        self.status_label.setFont(QFont("Arial", 12))
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet(
            "background: #1e1e1e; color: #dcdcdc; font-family: monospace;"
        )
        main_layout.addWidget(self.log_output)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        self.start_vnc_btn = QPushButton("Start with VNC")
        self.start_no_vnc_btn = QPushButton("Start without VNC")
        self.stop_btn = QPushButton("Stop VM")

        for btn in (self.start_vnc_btn, self.start_no_vnc_btn, self.stop_btn):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(40)
            btn.setFont(QFont("Arial", 11))
            btn.setStyleSheet(
                "QPushButton { background-color: #4CAF50; color: white; border:none; border-radius:5px;}"
                "QPushButton:hover { background-color: #45a049;}"
                "QPushButton:pressed { background-color: #3e8e41;}"
            )
            btn_layout.addWidget(btn)

        main_layout.addLayout(btn_layout)

        self.start_vnc_btn.clicked.connect(lambda: self.handle_google_vm_action("start", False))
        self.start_no_vnc_btn.clicked.connect(lambda: self.handle_google_vm_action("start", True))
        self.stop_btn.clicked.connect(lambda: self.handle_google_vm_action("stop", False))

    def setup_status_timer(self):
        """Setup timer for automatic status refresh"""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.refresh_vm_status)
        self.status_timer.start(30000)  # Refresh every 30 seconds

    def on_vm_selection_changed(self):
        """Called when VM selection changes"""
        self.refresh_vm_status()

    def refresh_vm_status(self):
        """Refresh the status of the currently selected VM"""
        current_vm = self.vm_combo.currentData()
        if not current_vm:
            self.vm_status_label.setText("No VM Selected")
            self.vm_status_label.setStyleSheet("padding: 5px; border-radius: 3px; background-color: #757575; color: white;")
            return

        # Don't refresh if an operation is in progress
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            return

        if self.status_worker and self.status_worker.isRunning():
            return

        self.vm_status_label.setText("Checking...")
        self.vm_status_label.setStyleSheet("padding: 5px; border-radius: 3px; background-color: #757575; color: white;")

        self.status_worker = VMStatusWorker(current_vm)
        self.status_worker.status_ready.connect(self.update_vm_status)
        self.status_worker.start()

    def update_vm_status(self, status, color):
        """Update the VM status display"""
        self.vm_status_label.setText(status)
        self.vm_status_label.setStyleSheet(f"padding: 5px; border-radius: 3px; background-color: {color}; color: white;")

    def refresh_vm_combo(self):
        self.vm_combo.clear()
        self.vm_configs = self.load_vm_configs()
        for vm in self.vm_configs:
            self.vm_combo.addItem(f"{vm['name']} ({vm['zone']})", vm)

    def open_settings(self):
        dialog = VMSettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.refresh_vm_combo()

    def handle_google_vm_action(self, action, no_vnc):
        if not self.vm_configs:
            QMessageBox.warning(self, "No VMs", "No VMs configured. Please add VMs in settings.")
            return

        current_vm = self.vm_combo.currentData()
        if not current_vm:
            QMessageBox.warning(self, "No VM Selected", "Please select a VM.")
            return

        self.log_output.clear()
        self.status_label.setText(f"Performing: {action}{' (no VNC)' if no_vnc else ''}...")
        self.progress_bar.setRange(0, 0)

        for btn in (self.start_vnc_btn, self.start_no_vnc_btn, self.stop_btn):
            btn.setDisabled(True)

        resolution = self.get_screen_resolution()
        self.worker = GoogleVMWorker(action, current_vm, no_vnc, resolution)
        self.worker.output.connect(self.append_output)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def append_output(self, text):
        self.log_output.append(text)
        self.status_label.setText(text)

    def on_finished(self, exit_code):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        for btn in (self.start_vnc_btn, self.start_no_vnc_btn, self.stop_btn):
            btn.setDisabled(False)

            # Refresh status after successful operation
        if exit_code == 0:
            QMessageBox.information(self, "Done", "Operation completed successfully.")
            self.status_label.setText("Ready.")
            QTimer.singleShot(2000, self.refresh_vm_status)  # Wait 2 seconds before refreshing
        else:
            QMessageBox.critical(
                self, "Error",
                f"Operation failed with exit code {exit_code}. See log for details."
            )
            self.status_label.setText("Error occurred.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = GoogleVMControlApp()
    gui.show()
    sys.exit(app.exec_())

