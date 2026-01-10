"""
Production-grade main window for Argo Log Viewer.
Features: Connection management, console output, pod search, log streaming.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListWidget, QTextEdit, QLineEdit, QLabel, 
    QMessageBox, QSplitter, QGroupBox, QComboBox,
    QMenuBar, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor, QPalette, QColor, QAction
from app.ssh.argo_worker import ArgoWorker
from app.ssh.connection_manager import SSHConnectionManager
from app.logging_config import get_logger

logger = get_logger(__name__)


class ThemeManager:
    """Manages application themes (Dark/Light mode)."""
    
    @staticmethod
    def get_dark_theme() -> dict:
        """Get dark theme stylesheet and colors."""
        return {
            "stylesheet": """
                QWidget {
                    background-color: #2b2b2b;
                    color: #e0e0e0;
                }
                QMenuBar {
                    background-color: #2b2b2b;
                    color: #e0e0e0;
                    border-bottom: 1px solid #3c3c3c;
                    padding: 3px;
                }
                QMenuBar::item {
                    background-color: transparent;
                    padding: 6px 12px;
                    margin: 2px;
                    border-radius: 4px;
                }
                QMenuBar::item:selected {
                    background-color: #3c3c3c;
                }
                QMenuBar::item:pressed {
                    background-color: #4a4a4a;
                }
                QMenu {
                    background-color: #2b2b2b;
                    color: #e0e0e0;
                    border: 1px solid #3c3c3c;
                    padding: 5px;
                }
                QMenu::item {
                    padding: 8px 25px;
                    border-radius: 3px;
                }
                QMenu::item:selected {
                    background-color: #3c3c3c;
                }
                QGroupBox {
                    border: 1px solid #3c3c3c;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                    font-weight: bold;
                    color: #e0e0e0;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QPushButton {
                    background-color: #3c3c3c;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    padding: 5px 15px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #2a2a2a;
                }
                QPushButton:disabled {
                    background-color: #2b2b2b;
                    color: #666;
                }
                QLineEdit {
                    background-color: #3c3c3c;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    padding: 5px;
                    border-radius: 3px;
                }
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                }
                QListWidget {
                    background-color: #3c3c3c;
                    color: #e0e0e0;
                    border: 1px solid #555;
                }
                QListWidget::item:selected {
                    background-color: #0d47a1;
                }
                QComboBox {
                    background-color: #3c3c3c;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    padding: 5px;
                    border-radius: 3px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #e0e0e0;
                    margin-right: 5px;
                }
                QLabel {
                    color: #e0e0e0;
                }
            """,
            "console_bg": "#1e1e1e",
            "console_fg": "#d4d4d4"
        }
    
    @staticmethod
    def get_light_theme() -> dict:
        """Get light theme stylesheet and colors."""
        return {
            "stylesheet": """
                QWidget {
                    background-color: #f5f5f5;
                    color: #212121;
                }
                QMenuBar {
                    background-color: #f5f5f5;
                    color: #212121;
                    border-bottom: 1px solid #ccc;
                    padding: 3px;
                }
                QMenuBar::item {
                    background-color: transparent;
                    padding: 6px 12px;
                    margin: 2px;
                    border-radius: 4px;
                }
                QMenuBar::item:selected {
                    background-color: #e0e0e0;
                }
                QMenuBar::item:pressed {
                    background-color: #d0d0d0;
                }
                QMenu {
                    background-color: #ffffff;
                    color: #212121;
                    border: 1px solid #ccc;
                    padding: 5px;
                }
                QMenu::item {
                    padding: 8px 25px;
                    border-radius: 3px;
                }
                QMenu::item:selected {
                    background-color: #e0e0e0;
                }
                QGroupBox {
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                    font-weight: bold;
                    color: #212121;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QPushButton {
                    background-color: #ffffff;
                    color: #212121;
                    border: 1px solid #ccc;
                    padding: 5px 15px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #e8e8e8;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
                QPushButton:disabled {
                    background-color: #f5f5f5;
                    color: #999;
                }
                QLineEdit {
                    background-color: #ffffff;
                    color: #212121;
                    border: 1px solid #ccc;
                    padding: 5px;
                    border-radius: 3px;
                }
                QTextEdit {
                    background-color: #ffffff;
                    color: #212121;
                    border: 1px solid #ccc;
                }
                QListWidget {
                    background-color: #ffffff;
                    color: #212121;
                    border: 1px solid #ccc;
                }
                QListWidget::item:selected {
                    background-color: #2196f3;
                    color: #ffffff;
                }
                QComboBox {
                    background-color: #ffffff;
                    color: #212121;
                    border: 1px solid #ccc;
                    padding: 5px;
                    border-radius: 3px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #212121;
                    margin-right: 5px;
                }
                QLabel {
                    color: #212121;
                }
            """,
            "console_bg": "#ffffff",
            "console_fg": "#212121"
        }
    
    @staticmethod
    def get_theme(theme_name: str) -> dict:
        """Get theme by name."""
        if theme_name.lower() == "light":
            return ThemeManager.get_light_theme()
        return ThemeManager.get_dark_theme()


class MainWindow(QWidget):
    """Main application window for Argo Pod Log Viewer."""
    
    def __init__(self):
        """Initialize the main window with all UI components."""
        super().__init__()
        logger.info("Initializing MainWindow")
        
        self.setWindowTitle("Argo Pod Log Viewer - Production Grade")
        self.resize(1400, 900)
        
        # Connection state
        self.ssh_manager: Optional[SSHConnectionManager] = None
        self.worker: Optional[ArgoWorker] = None
        self.is_connected = False
        
        # Theme state
        self.current_theme = "dark"
        
        logger.debug("Building UI components")
        self._build_ui()
        self._set_initial_state()
        self._apply_theme(self.current_theme)
        
        logger.info("MainWindow initialization complete")
    
    def _build_ui(self):
        """Build and layout all UI components."""
        logger.debug("Creating main layout")
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Menu bar at the very top
        menu_bar = self._create_menu_bar()
        main_layout.setMenuBar(menu_bar)
        
        # Connection controls at top
        connection_group = self._create_connection_controls()
        main_layout.addWidget(connection_group)
        
        # Main content area with horizontal splitter for left/right panels
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setHandleWidth(5)
        main_splitter.setChildrenCollapsible(False)
        
        # Left panel: Pod search and list
        pod_section = self._create_pod_section()
        main_splitter.addWidget(pod_section)
        
        # Right panel: Console and logs with vertical splitter
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setHandleWidth(5)
        right_splitter.setChildrenCollapsible(False)
        
        # Top right: Console output
        console_section = self._create_console_section()
        right_splitter.addWidget(console_section)
        
        # Bottom right: Log viewer
        log_section = self._create_log_section()
        right_splitter.addWidget(log_section)
        
        # Set initial sizes for right splitter (console 40%, logs 60%)
        right_splitter.setSizes([300, 450])
        
        main_splitter.addWidget(right_splitter)
        
        # Set initial sizes for main splitter (left 25%, right 75%)
        main_splitter.setSizes([300, 900])
        
        main_layout.addWidget(main_splitter)
        
        logger.info("UI layout complete")
    
    def _create_menu_bar(self) -> QMenuBar:
        """Create application menu bar."""
        logger.debug("Creating menu bar")
        menu_bar = QMenuBar(self)

        # About action (top-level, no submenu)
        about_action = QAction("About Argo Log Viewer", self)
        about_action.setStatusTip("About Argo Log Viewer")
        about_action.triggered.connect(self._show_about_dialog)

        menu_bar.addAction(about_action)
        return menu_bar
    
    def _create_connection_controls(self) -> QGroupBox:
        """Create connection control section."""
        logger.debug("Creating connection controls")
        
        group = QGroupBox("Connection")
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)  # Smaller margins
        layout.setSpacing(10)  # Tighter spacing
        
        # Connection status label (compact)
        self.status_label = QLabel("● Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 11pt;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Theme selector (compact)
        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet("font-size: 9pt;")
        layout.addWidget(theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setMaximumWidth(80)
        self.theme_combo.setMinimumHeight(25)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        layout.addWidget(self.theme_combo)
        
        # Connect button (compact)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.handle_connect)
        self.connect_btn.setFixedSize(80, 28)
        layout.addWidget(self.connect_btn)
        
        # Disconnect button (compact)
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.handle_disconnect)
        self.disconnect_btn.setFixedSize(90, 28)
        layout.addWidget(self.disconnect_btn)
        
        group.setLayout(layout)
        group.setMaximumHeight(60)  # Limit height
        return group
    
    def _create_pod_section(self) -> QGroupBox:
        """Create pod search and list section."""
        logger.debug("Creating pod section")
        
        group = QGroupBox("Pod Search")
        layout = QVBoxLayout()
        
        # Refresh button at top
        refresh_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 Refresh All Pods")
        self.refresh_btn.clicked.connect(self.refresh_pods)
        self.refresh_btn.setToolTip("Re-fetch all running pods from argo namespace")
        refresh_layout.addWidget(self.refresh_btn)
        layout.addLayout(refresh_layout)
        
        # Search input
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Keyword:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter pod name pattern (e.g., workflow-)")
        self.search_input.returnPressed.connect(self.fetch_pods)
        search_layout.addWidget(self.search_input)
        
        layout.addLayout(search_layout)
        
        # Fetch button
        self.fetch_btn = QPushButton("Search Pods")
        self.fetch_btn.clicked.connect(self.fetch_pods)
        layout.addWidget(self.fetch_btn)
        
        # Pod list
        layout.addWidget(QLabel("Pods (double-click to view logs):"))
        self.pod_list = QListWidget()
        self.pod_list.itemDoubleClicked.connect(self.open_logs)
        layout.addWidget(self.pod_list)
        
        group.setLayout(layout)
        return group
    
    def _create_console_section(self) -> QGroupBox:
        """Create console output section."""
        logger.debug("Creating console section")
        
        group = QGroupBox("Console Output")
        layout = QVBoxLayout()
        
        # Console text area
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setLineWrapMode(QTextEdit.NoWrap)
        
        # Use monospace font for console
        console_font = QFont("Courier New", 9)
        self.console_output.setFont(console_font)
        
        layout.addWidget(self.console_output)
        
        # Clear console button
        clear_console_btn = QPushButton("Clear Console")
        clear_console_btn.clicked.connect(lambda: self.console_output.clear())
        layout.addWidget(clear_console_btn)
        
        group.setLayout(layout)
        return group
    
    def _create_log_section(self) -> QGroupBox:
        """Create log viewer section."""
        logger.debug("Creating log section")
        
        group = QGroupBox("Live Logs")
        layout = QVBoxLayout()
        
        # Current pod label
        self.current_pod_label = QLabel("No pod selected")
        self.current_pod_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.current_pod_label)
        
        # Log output text area
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QTextEdit.NoWrap)
        
        # Use monospace font for logs
        log_font = QFont("Courier New", 9)
        self.log_output.setFont(log_font)
        
        layout.addWidget(self.log_output)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.stop_logs_btn = QPushButton("Stop Log Stream")
        self.stop_logs_btn.clicked.connect(self.stop_log_stream)
        button_layout.addWidget(self.stop_logs_btn)
        
        clear_logs_btn = QPushButton("Clear Logs")
        clear_logs_btn.clicked.connect(lambda: self.log_output.clear())
        button_layout.addWidget(clear_logs_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        group.setLayout(layout)
        return group
    
    def _set_initial_state(self):
        """Set initial UI state (disconnected)."""
        logger.debug("Setting initial UI state")
        self.is_connected = False
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.fetch_btn.setEnabled(False)
        self.search_input.setEnabled(False)
        self.pod_list.setEnabled(False)
        self.stop_logs_btn.setEnabled(False)
        self.status_label.setText("● Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 11pt;")
    
    def _set_connected_state(self):
        """Update UI for connected state."""
        logger.debug("Setting connected UI state")
        self.is_connected = True
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.pod_list.setEnabled(True)
        self.status_label.setText("● Connected")
        self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 11pt;")
    
    def _set_disconnected_state(self):
        """Update UI for disconnected state."""
        logger.debug("Setting disconnected UI state")
        self._set_initial_state()
        self.pod_list.clear()
        self.log_output.clear()
        self.current_pod_label.setText("No pod selected")
    
    # -------------------------
    # Action Handlers
    # -------------------------
    
    def handle_connect(self):
        """Handle connect button click."""
        logger.info("Connect button clicked")
        
        self.console_output.clear()
        self.console_output.append("=== Initiating SSH connection ===\n")
        
        # Create SSH manager if not exists
        if not self.ssh_manager:
            logger.debug("Creating new SSH connection manager")
            self.ssh_manager = SSHConnectionManager()
        
        # Create and start worker
        self.worker = ArgoWorker(action="connect", ssh_manager=self.ssh_manager)
        self.worker.output.connect(self._append_console)
        self.worker.connected.connect(self._on_connected)
        self.worker.pods.connect(self._on_pods_received)  # ← CONNECT PODS SIGNAL!
        self.worker.error.connect(self._on_error)
        
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")
        
        logger.info("Starting connection worker")
        self.worker.start()
    
    def handle_disconnect(self):
        """Handle disconnect button click."""
        logger.info("Disconnect button clicked")
        
        # Stop any running log stream
        self.stop_log_stream()
        
        self.console_output.append("\n=== Disconnecting ===\n")
        
        # Create disconnect worker
        self.worker = ArgoWorker(action="disconnect", ssh_manager=self.ssh_manager)
        self.worker.output.connect(self._append_console)
        self.worker.disconnected.connect(self._on_disconnected)
        
        self.disconnect_btn.setEnabled(False)
        logger.info("Starting disconnect worker")
        self.worker.start()
    
    def refresh_pods(self):
        """Refresh the pod list by fetching all running pods again."""
        logger.info("Refresh pods requested")
        
        if not self.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect first before refreshing pods")
            return
        
        # Stop any active log streaming first to free up the SSH shell
        if self.worker and self.worker.isRunning():
            logger.info("Stopping active log stream before refreshing pods")
            self.console_output.append("\n[INFO] Stopping active operations before refresh...\n")
            self.worker.stop()
            self.worker.wait(2000)  # Wait up to 2 seconds for graceful stop
            self.stop_logs_btn.setEnabled(False)
        
        self.pod_list.clear()
        self.console_output.append("\n=== Refreshing pod list ===\n")
        
        # Create worker to list all pods (similar to connect action)
        self.worker = ArgoWorker(action="list_all_pods", ssh_manager=self.ssh_manager)
        self.worker.output.connect(self._append_console)
        self.worker.pods.connect(self._on_pods_received)
        self.worker.error.connect(self._on_error)
        
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Refreshing...")
        
        logger.info("Starting refresh worker")
        self.worker.start()
    
    def fetch_pods(self):
        """Fetch pods matching the search keyword."""
        logger.info("Fetch pods requested")
        
        keyword = self.search_input.text().strip()
        if not keyword:
            logger.warning("No search keyword provided")
            QMessageBox.warning(self, "Input Required", "Please enter a search keyword")
            return
        
        # Stop any active log streaming first to free up the SSH shell
        if self.worker and self.worker.isRunning():
            logger.info("Stopping active log stream before fetching pods")
            self.console_output.append("\n[INFO] Stopping active operations before search...\n")
            self.worker.stop()
            self.worker.wait(2000)  # Wait up to 2 seconds for graceful stop
            self.stop_logs_btn.setEnabled(False)
        
        logger.info(f"Fetching pods with keyword: '{keyword}'")
        self.pod_list.clear()
        self.console_output.append(f"\n=== Fetching pods matching '{keyword}' ===\n")
        
        # Create and start worker
        self.worker = ArgoWorker(
            action="list_pods",
            search=keyword,
            ssh_manager=self.ssh_manager
        )
        self.worker.output.connect(self._append_console)
        self.worker.pods.connect(self._on_pods_received)
        self.worker.error.connect(self._on_error)
        
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching...")
        
        logger.info("Starting list_pods worker")
        self.worker.start()
    
    def open_logs(self, item):
        """Open live logs for the selected pod."""
        pod_name = item.text()
        logger.info(f"Opening logs for pod: '{pod_name}'")
        
        # Stop any existing log stream
        self.stop_log_stream()
        
        self.log_output.clear()
        self.current_pod_label.setText(f"Viewing logs for: {pod_name}")
        self.console_output.append(f"\n=== Opening logs for {pod_name} ===\n")
        
        # Create and start worker
        self.worker = ArgoWorker(
            action="logs",
            pod=pod_name,
            ssh_manager=self.ssh_manager
        )
        self.worker.output.connect(self._append_log)
        self.worker.error.connect(self._on_error)
        
        self.stop_logs_btn.setEnabled(True)
        
        logger.info("Starting logs worker")
        self.worker.start()
    
    def stop_log_stream(self):
        """Stop the current log stream."""
        if self.worker and self.worker.isRunning():
            logger.info("Stopping log stream")
            self.console_output.append("\n[INFO] Stopping log stream...\n")
            self.worker.stop()
            self.worker.wait(2000)  # Wait up to 2 seconds
            self.stop_logs_btn.setEnabled(False)
            self.current_pod_label.setText("Log stream stopped")
    
    # -------------------------
    # Signal Handlers
    # -------------------------
    
    def _on_connected(self):
        """Handle successful connection."""
        logger.info("Connection established signal received")
        self._set_connected_state()
        self.connect_btn.setText("Connect")
        self.console_output.append("\n=== Ready for operations ===\n")
        QMessageBox.information(self, "Connected", "SSH connection established successfully!")
    
    def _on_disconnected(self):
        """Handle disconnection."""
        logger.info("Disconnection signal received")
        self._set_disconnected_state()
        self.ssh_manager = None
        self.console_output.append("\n=== Disconnected ===\n")
    
    def _on_pods_received(self, pods):
        """Handle received pod list."""
        logger.info(f"Received {len(pods)} pods")
        self.pod_list.addItems(pods)
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Search Pods")
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 Refresh All Pods")
        
        if not pods:
            QMessageBox.information(self, "No Results", "No pods found matching the search keyword")
    
    def _on_error(self, error_msg):
        """Handle error from worker."""
        logger.error(f"Worker error: {error_msg}")
        QMessageBox.critical(self, "Error", error_msg)
        
        # Re-enable buttons
        self.connect_btn.setEnabled(not self.is_connected)
        self.connect_btn.setText("Connect")
        self.fetch_btn.setEnabled(self.is_connected)
        self.fetch_btn.setText("Fetch Pods")
    
    def _append_console(self, text):
        """Append text to console output."""
        self.console_output.moveCursor(QTextCursor.MoveOperation.End)
        self.console_output.insertPlainText(text)
        self.console_output.moveCursor(QTextCursor.MoveOperation.End)
    
    def _append_log(self, text):
        """Append text to log output."""
        self.log_output.moveCursor(QTextCursor.MoveOperation.End)
        self.log_output.insertPlainText(text)
        self.log_output.moveCursor(QTextCursor.MoveOperation.End)
    
    # -------------------------
    # Theme Management
    # -------------------------
    
    def _apply_theme(self, theme_name: str):
        """Apply the selected theme to the application."""
        logger.info(f"Applying theme: {theme_name}")
        theme = ThemeManager.get_theme(theme_name)
        self.setStyleSheet(theme["stylesheet"])
        
        # Update console and log output colors
        console_style = f"""
            QTextEdit {{
                background-color: {theme["console_bg"]};
                color: {theme["console_fg"]};
            }}
        """
        self.console_output.setStyleSheet(console_style)
        self.log_output.setStyleSheet(console_style)
        
        # Update status label colors based on connection state
        if self.is_connected:
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def _on_theme_changed(self, theme_name: str):
        """Handle theme selection change."""
        self.current_theme = theme_name.lower()
        self._apply_theme(self.current_theme)
        logger.info(f"Theme changed to: {self.current_theme}")
    
    # -------------------------
    # About Dialog
    # -------------------------
    
    def _show_about_dialog(self):
        """Show the About dialog with developer information."""
        logger.info("Showing About dialog")
        
        dialog = QDialog(self)
        dialog.setWindowTitle("About Argo Log Viewer")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # App title
        title_label = QLabel("Argo Pod Log Viewer")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel("Version 1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: gray;")
        layout.addWidget(version_label)
        
        # Separator
        layout.addSpacing(10)
        
        # Description
        desc_label = QLabel(
            "A production-grade desktop application for viewing\n"
            "Argo Workflow logs through SSH connections."
        )
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Separator
        layout.addSpacing(15)
        
        # Developer info
        dev_label = QLabel("Developer")
        dev_font = QFont()
        dev_font.setBold(True)
        dev_label.setFont(dev_font)
        layout.addWidget(dev_label)
        
        name_label = QLabel("Harshmeet Singh")
        layout.addWidget(name_label)
        
        # Separator
        layout.addSpacing(10)
        
        # Contact info
        contact_label = QLabel("Contact")
        contact_label.setFont(dev_font)
        layout.addWidget(contact_label)
        
        email1_label = QLabel('📧 <a href="mailto:harshmeetsingh010@gmail.com">harshmeetsingh010@gmail.com</a>')
        email1_label.setOpenExternalLinks(True)
        email1_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(email1_label)
        
        email2_label = QLabel('📧 <a href="mailto:harshmeet.singh@netcoreunbxd.com">harshmeet.singh@netcoreunbxd.com</a>')
        email2_label.setOpenExternalLinks(True)
        email2_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(email2_label)
        
        # Separator
        layout.addSpacing(15)
        
        # Copyright
        copyright_label = QLabel(f"© 2024-2026 Harshmeet Singh. All rights reserved.")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(copyright_label)
        
        # OK button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        # Apply current theme to dialog
        if self.current_theme == "dark":
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    color: #e0e0e0;
                }
                QLabel a {
                    color: #4a9eff;
                }
            """)
        
        dialog.exec()
    
    # -------------------------
    # Window Close Event
    # -------------------------
    
    def closeEvent(self, event):
        """Handle window close event - cleanup connections."""
        logger.info("Window close event triggered")
        
        # Stop any running worker
        if self.worker and self.worker.isRunning():
            logger.info("Stopping active worker thread")
            self.worker.stop()
            self.worker.wait(2000)
        
        # Disconnect SSH
        if self.ssh_manager and self.ssh_manager.is_connected():
            logger.info("Disconnecting SSH connection")
            try:
                self.ssh_manager.disconnect()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        logger.info("Window closed, application exiting")
        event.accept()
