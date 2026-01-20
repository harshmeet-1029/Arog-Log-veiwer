"""
Production-grade main window for Argo Log Viewer.
Features: Connection management, console output, pod search, log streaming.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListWidget, QTextEdit, QLineEdit, QLabel, 
    QMessageBox, QSplitter, QGroupBox, QComboBox,
    QMenuBar, QDialog, QDialogButtonBox, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFont, QTextCursor, QPalette, QColor, QAction, 
    QTextDocument, QShortcut, QKeySequence, QIcon
)
from app.ssh.argo_worker import ArgoWorker
from app.ssh.connection_manager import SSHConnectionManager
from app.logging_config import get_logger
from app.config import SecurityConfig, AppConfig, UpdateConfig
from app.update_checker import UpdateChecker, UpdateInfo
from app.themes import get_theme, get_available_theme_names, get_theme_name_from_display
import os
import stat
import sys
import webbrowser
from typing import Optional as Opt_Type

logger = get_logger(__name__)


# NOTE: Theme styling is now managed in app/themes.py
# This makes it easy to add new themes without editing this file!


class MainWindow(QWidget):
    """Main application window for Argo Pod Log Viewer."""
    
    def __init__(self):
        """Initialize the main window with all UI components."""
        super().__init__()
        logger.info("Initializing MainWindow")
        
        self.setWindowTitle("Argo Pod Log Viewer - Production Grade")
        self.resize(1400, 900)
        
        # Set window icon
        self._set_window_icon()
        
        # Connection state
        self.ssh_manager: Optional[SSHConnectionManager] = None
        self.ssh_manager_metrics: Optional[SSHConnectionManager] = None  # Separate connection for metrics
        self.worker: Optional[ArgoWorker] = None
        self.is_connected = False
        
        # Metrics state
        self.current_pod_for_metrics: Optional[str] = None
        self.is_monitoring_metrics = False
        self._last_metrics_update = 0  # Timestamp of last metrics UI update (throttling)
        
        # Stream monitoring state
        self._stream_start_time = None  # Track when log streaming started
        self._last_memory_warning_time = 0  # Track last memory warning
        
        # Update state
        self.pending_update: Opt_Type[UpdateInfo] = None
        
        # Theme state
        self.current_theme = "dark"
        
        # Fullscreen state
        self.is_fullscreen = False
        self.original_parent = None
        
        # Search state
        self.current_search_term = ""
        self.search_occurrences = []
        self.current_occurrence_index = -1
        
        logger.debug("Building UI components")
        self._build_ui()
        self._setup_shortcuts()
        self._set_initial_state()
        self._apply_theme(self.current_theme)
        
        # Check for updates on startup (in background)
        if UpdateConfig.should_check_for_updates():
            self._check_for_updates_background()
        
        logger.info("MainWindow initialization complete")
    
    def _set_window_icon(self):
        """Set the application window icon."""
        try:
            # Determine the base path (different for PyInstaller executable vs script)
            if getattr(sys, 'frozen', False):
                # Running as compiled executable (PyInstaller)
                base_path = sys._MEIPASS
            else:
                # Running as script
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # Try to load icon.ico (Windows) or icon.png (cross-platform)
            icon_paths = [
                os.path.join(base_path, 'app', 'icon.ico'),
                os.path.join(base_path, 'app', 'ICON.png'),
                os.path.join(base_path, 'icon.ico'),
                os.path.join(base_path, 'ICON.png'),
            ]
            
            icon_loaded = False
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    icon = QIcon(icon_path)
                    if not icon.isNull():
                        self.setWindowIcon(icon)
                        logger.info(f"Window icon loaded from: {icon_path}")
                        icon_loaded = True
                        break
            
            if not icon_loaded:
                logger.warning("Could not load window icon - file not found")
        
        except Exception as e:
            logger.error(f"Error setting window icon: {e}", exc_info=True)
    
    def _build_ui(self):
        """Build and layout all UI components."""
        logger.debug("Creating main layout")
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Platform-specific margins - macOS needs more spacing
        is_macos = sys.platform == 'darwin'
        if is_macos:
            main_layout.setContentsMargins(10, 5, 10, 10)  # macOS: extra margins
        else:
            main_layout.setContentsMargins(0, 0, 0, 0)  # Windows/Linux: no margins
        
        # Menu bar at the very top
        menu_bar = self._create_menu_bar()
        main_layout.setMenuBar(menu_bar)
        
        # Add spacing between menu bar and connection controls
        # macOS needs more spacing due to native menu bar rendering
        main_layout.addSpacing(15 if is_macos else 5)
        
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
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts for the application."""
        logger.debug("Setting up keyboard shortcuts")
        
        # Ctrl+F (Windows/Linux) and Cmd+F (macOS) for Find
        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        find_shortcut.activated.connect(self.show_search_bar)
        
        # F3 for Find Next
        find_next_shortcut = QShortcut(QKeySequence.StandardKey.FindNext, self)
        find_next_shortcut.activated.connect(self.find_next)
        
        # Shift+F3 for Find Previous
        find_prev_shortcut = QShortcut(QKeySequence.StandardKey.FindPrevious, self)
        find_prev_shortcut.activated.connect(self.find_previous)
        
        # Escape - smart handler (closes search first, then fullscreen)
        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape_shortcut.activated.connect(self.handle_escape)
        
        # F11 for fullscreen toggle
        fullscreen_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        fullscreen_shortcut.activated.connect(self.toggle_fullscreen)
        
        logger.info("Keyboard shortcuts configured: Ctrl+F/Cmd+F (Find), F3 (Next), Shift+F3 (Previous), Esc (Smart close), F11 (Fullscreen)")
    
    def _get_active_window(self):
        """Get the currently active window (fullscreen or main window)."""
        if self.is_fullscreen and hasattr(self, 'fullscreen_window'):
            return self.fullscreen_window
        return self
    
    def _find_all_occurrences(self, search_text):
        """Find all occurrences of search text and return their positions (start positions)."""
        if not search_text:
            return []
        
        occurrences = []
        document = self.log_output.document()
        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        
        # Find all occurrences
        while True:
            cursor = document.find(search_text, cursor, QTextDocument.FindFlag(0))
            if cursor.isNull():
                break
            # cursor.position() is at the END of the match after find()
            # Store the START position for proper jumping
            start_pos = cursor.position() - len(search_text)
            occurrences.append(start_pos)
        
        return occurrences
    
    def _update_match_counter(self):
        """Update the match counter label."""
        if not self.current_search_term:
            self.match_counter_label.setText("")
            return
        
        total = len(self.search_occurrences)
        if total == 0:
            self.match_counter_label.setText("No matches")
        else:
            current = self.current_occurrence_index + 1 if self.current_occurrence_index >= 0 else 0
            self.match_counter_label.setText(f"{current} of {total}")
    
    def _jump_to_occurrence(self, index):
        """Jump to a specific occurrence by index."""
        if not self.search_occurrences or index < 0 or index >= len(self.search_occurrences):
            return False
        
        start_position = self.search_occurrences[index]
        cursor = self.log_output.textCursor()
        
        # Set cursor to the start of the match
        cursor.setPosition(start_position)
        
        # Select exactly the search term length
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(self.current_search_term))
        
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()
        
        self.current_occurrence_index = index
        self._update_match_counter()
        return True
    
    def handle_escape(self):
        """Smart escape handler - closes search bar first, then fullscreen."""
        if self.log_search_bar.isVisible():
            # If search bar is open, close it
            self.hide_search_bar()
            logger.debug("Escape pressed: closed search bar")
        elif self.is_fullscreen:
            # If in fullscreen and search is not open, exit fullscreen
            self.exit_fullscreen()
            logger.debug("Escape pressed: exited fullscreen")
        else:
            logger.debug("Escape pressed: no action taken")
    
    def handle_search_enter(self):
        """Handle Enter key in search input - acts as 'Next' if search is active."""
        search_text = self.log_search_input.text().strip()
        
        # If search term is the same and we have results, act as "Next"
        if search_text == self.current_search_term and self.search_occurrences:
            self.find_next()
        else:
            # New search term, do initial search
            self.find_in_logs()
    
    def show_search_bar(self):
        """Show the search bar and focus the input field (VS Code style)."""
        if not self.log_search_bar.isVisible():
            self.log_search_bar.setVisible(True)
            logger.debug("Search bar shown")
        self.log_search_input.setFocus()
        self.log_search_input.selectAll()
        logger.debug("Log search input focused")
    
    def hide_search_bar(self):
        """Hide the search bar and clear search (VS Code style)."""
        if self.log_search_bar.isVisible():
            self.log_search_bar.setVisible(False)
            self.clear_log_search()
            self.log_output.setFocus()
            logger.debug("Search bar hidden")
    
    def _focus_log_search(self):
        """Focus the log search input field and select all text."""
        self.log_search_input.setFocus()
        self.log_search_input.selectAll()
        logger.debug("Log search input focused")
    
    def _create_menu_bar(self) -> QMenuBar:
        """Create application menu bar."""
        logger.debug("Creating menu bar")
        menu_bar = QMenuBar(self)

        # About action (top-level, no submenu)
        about_action = QAction("About", self)
        about_action.setStatusTip("About Argo Log Viewer")
        about_action.triggered.connect(self._show_about_dialog)
        menu_bar.addAction(about_action)
        
        # Settings menu
        settings_menu = menu_bar.addMenu("Settings")
        
        ssh_config_settings_action = QAction("Custom SSH Folder...", self)
        ssh_config_settings_action.setStatusTip("Configure custom SSH folder location")
        ssh_config_settings_action.triggered.connect(self._show_ssh_folder_config_dialog)
        settings_menu.addAction(ssh_config_settings_action)
        
        advanced_settings_action = QAction("Advanced Settings...", self)
        advanced_settings_action.setStatusTip("Configure advanced options (log buffer, warnings)")
        advanced_settings_action.triggered.connect(self._show_advanced_settings_dialog)
        settings_menu.addAction(advanced_settings_action)
        
        settings_menu.addSeparator()
        
        check_updates_action = QAction("Check for Updates", self)
        check_updates_action.setStatusTip("Check for application updates")
        check_updates_action.triggered.connect(self._check_for_updates_manual)
        settings_menu.addAction(check_updates_action)
        
        # Help menu with shortcuts
        help_menu = menu_bar.addMenu("Help")
        
        user_guide_action = QAction("📖 User Guide (How to Use)", self)
        user_guide_action.setStatusTip("Complete guide on how to use all features")
        user_guide_action.triggered.connect(self._show_user_guide_dialog)
        help_menu.addAction(user_guide_action)
        
        help_menu.addSeparator()
        
        shortcuts_action = QAction("⌨️ Keyboard Shortcuts", self)
        shortcuts_action.setStatusTip("View keyboard shortcuts")
        shortcuts_action.triggered.connect(self._show_shortcuts_dialog)
        help_menu.addAction(shortcuts_action)
        
        # SSH Configuration Guide
        ssh_config_action = QAction("🔧 SSH Configuration Guide", self)
        ssh_config_action.setStatusTip("View SSH setup instructions for your OS")
        ssh_config_action.triggered.connect(self._show_ssh_config_dialog)
        help_menu.addAction(ssh_config_action)

        return menu_bar
    
    def _create_connection_controls(self) -> QGroupBox:
        """Create connection control section."""
        logger.debug("Creating connection controls")
        
        group = QGroupBox("Connection")
        layout = QHBoxLayout()
        
        # Platform-specific margins - macOS needs more internal spacing
        is_macos = sys.platform == 'darwin'
        if is_macos:
            layout.setContentsMargins(10, 8, 10, 8)  # macOS: extra padding
        else:
            layout.setContentsMargins(5, 5, 5, 5)  # Windows/Linux: compact
        
        layout.setSpacing(10)  # Tighter spacing
        
        # Connection status label (compact)
        self.status_label = QLabel("● Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 11pt;")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Theme selector (compact) - auto-populated from themes.py
        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet("font-size: 9pt;")
        layout.addWidget(theme_label)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(get_available_theme_names())  # Dynamically loaded from themes.py
        self.theme_combo.setMinimumWidth(120)  # Wider for longer theme names
        self.theme_combo.setMinimumHeight(25)
        self.theme_combo.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        layout.addWidget(self.theme_combo)
        
        # Connect button (compact)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.handle_connect)
        self.connect_btn.setMinimumWidth(80)
        self.connect_btn.setMinimumHeight(28)
        self.connect_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.connect_btn)
        
        # Disconnect button (compact)
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.handle_disconnect)
        self.disconnect_btn.setMinimumWidth(90)
        self.disconnect_btn.setMinimumHeight(28)
        self.disconnect_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
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
        
        # Header with pod label, metrics, and fullscreen button
        header_layout = QHBoxLayout()
        
        # Current pod label
        self.current_pod_label = QLabel("No pod selected")
        self.current_pod_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.current_pod_label)
        
        # Compact metrics display (single line, next to pod name)
        self.metrics_label = QLabel("")
        # Color will be set by theme
        self.metrics_label.setVisible(False)
        header_layout.addWidget(self.metrics_label)
        
        # Retry button for metrics (compact, next to metrics)
        self.retry_metrics_btn = QPushButton("🔄")
        self.retry_metrics_btn.setToolTip("Retry fetching metrics")
        self.retry_metrics_btn.setFixedSize(32, 28)  # Fixed size to prevent cutting
        self.retry_metrics_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 0px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.retry_metrics_btn.setVisible(False)
        self.retry_metrics_btn.clicked.connect(self.retry_metrics)
        header_layout.addWidget(self.retry_metrics_btn)
        
        header_layout.addStretch()
        
        # Fullscreen button
        self.fullscreen_btn = QPushButton("⛶ Fullscreen")
        self.fullscreen_btn.setToolTip("Enter fullscreen mode (Logs only)")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_btn.setMinimumWidth(120)
        self.fullscreen_btn.setMinimumHeight(28)
        self.fullscreen_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.fullscreen_btn.setVisible(False)  # Hidden by default
        header_layout.addWidget(self.fullscreen_btn)
        
        layout.addLayout(header_layout)
        
        # Container for search bar and log output (for fullscreen support)
        self.log_container = QWidget()
        log_container_layout = QVBoxLayout(self.log_container)
        log_container_layout.setContentsMargins(0, 0, 0, 0)
        log_container_layout.setSpacing(0)
        
        # Floating search bar (hidden by default, VS Code style)
        self.log_search_bar = QWidget()
        self.log_search_bar.setObjectName("log_search_bar")
        search_bar_layout = QHBoxLayout(self.log_search_bar)
        search_bar_layout.setContentsMargins(5, 5, 5, 5)
        search_bar_layout.setSpacing(5)
        
        search_bar_layout.addWidget(QLabel("Find:"))
        
        self.log_search_input = QLineEdit()
        self.log_search_input.setPlaceholderText("Search in logs...")
        self.log_search_input.returnPressed.connect(self.handle_search_enter)
        self.log_search_input.setMinimumWidth(200)
        search_bar_layout.addWidget(self.log_search_input)
        
        # Match counter label
        self.match_counter_label = QLabel("")
        self.match_counter_label.setStyleSheet("color: gray; font-size: 9pt;")
        search_bar_layout.addWidget(self.match_counter_label)
        
        self.find_prev_btn = QPushButton("↑ Prev")
        self.find_prev_btn.clicked.connect(self.find_previous)
        self.find_prev_btn.setToolTip("Find previous (Shift+F3)")
        self.find_prev_btn.setFixedHeight(25)
        search_bar_layout.addWidget(self.find_prev_btn)
        
        self.find_next_btn = QPushButton("Next ↓")
        self.find_next_btn.clicked.connect(self.find_next)
        self.find_next_btn.setToolTip("Find next (F3)")
        self.find_next_btn.setFixedHeight(25)
        search_bar_layout.addWidget(self.find_next_btn)
        
        self.close_search_btn = QPushButton("Close")
        self.close_search_btn.clicked.connect(self.hide_search_bar)
        self.close_search_btn.setToolTip("Close (Esc)")
        self.close_search_btn.setFixedHeight(25)
        search_bar_layout.addWidget(self.close_search_btn)
        
        search_bar_layout.addStretch()
        
        # Hide search bar by default
        self.log_search_bar.setVisible(False)
        log_container_layout.addWidget(self.log_search_bar)
        
        # Log output text area
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QTextEdit.NoWrap)
        
        # Use monospace font for logs
        log_font = QFont("Courier New", 9)
        self.log_output.setFont(log_font)
        
        # Initialize with unlimited buffer (default behavior)
        # User can change this in Settings > Advanced Settings
        buffer_limit = AppConfig.get_log_buffer_limit()
        if buffer_limit > 0:
            self.log_output.document().setMaximumBlockCount(buffer_limit)
        # else: unlimited (Qt default - no limit)
        
        log_container_layout.addWidget(self.log_output)
        layout.addWidget(self.log_container)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.stop_logs_btn = QPushButton("Stop Log Stream")
        self.stop_logs_btn.clicked.connect(self.stop_log_stream)
        button_layout.addWidget(self.stop_logs_btn)
        
        clear_logs_btn = QPushButton("Clear Logs")
        clear_logs_btn.clicked.connect(lambda: self.log_output.clear())
        button_layout.addWidget(clear_logs_btn)
        
        self.save_logs_btn = QPushButton("💾 Save Logs")
        self.save_logs_btn.clicked.connect(self.save_logs_to_file)
        self.save_logs_btn.setToolTip("Save logs to a text file")
        self.save_logs_btn.setVisible(False)  # Hidden by default
        button_layout.addWidget(self.save_logs_btn)
        
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
        self.fullscreen_btn.setVisible(False)
        self.save_logs_btn.setVisible(False)
        self.metrics_label.setVisible(False)
        self.metrics_label.clear()
        self.retry_metrics_btn.setVisible(False)
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
        self.metrics_label.clear()
        self.metrics_label.setVisible(False)
        self.retry_metrics_btn.setVisible(False)
        self.current_pod_for_metrics = None
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
        
        # Stop any running metrics monitoring
        self.stop_metrics_monitoring()
        
        self.console_output.append("\n=== Disconnecting ===\n")
        
        # Disconnect metrics connection if exists
        if self.ssh_manager_metrics:
            try:
                logger.info("Disconnecting metrics SSH connection")
                self.ssh_manager_metrics.disconnect()
                self.ssh_manager_metrics = None
            except Exception as e:
                logger.warning(f"Error disconnecting metrics SSH: {e}")
        
        # Create disconnect worker for main connection
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
            logger.info("No search keyword provided - fetching all pods instead")
            # If keyword is empty, list all pods (same as refresh)
            self.refresh_pods()
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
        
        # Stop any existing log stream and metrics
        self.stop_log_stream()
        self.stop_metrics_monitoring()
        
        self.log_output.clear()
        self.current_pod_label.setText(f"Viewing logs for: {pod_name}")
        self.current_pod_for_metrics = pod_name
        
        # Update fullscreen label if in fullscreen mode
        if self.is_fullscreen and hasattr(self, 'fullscreen_pod_label'):
            self.fullscreen_pod_label.setText(f"Viewing logs for: {pod_name}")
        
        self.console_output.append(f"\n=== Opening logs for {pod_name} ===\n")
        
        # Create and start worker for logs
        self.worker = ArgoWorker(
            action="logs",
            pod=pod_name,
            ssh_manager=self.ssh_manager
        )
        self.worker.output.connect(self._append_log)
        self.worker.error.connect(self._on_error)
        
        self.stop_logs_btn.setEnabled(True)
        
        # Show fullscreen and save buttons when pod is selected
        self.fullscreen_btn.setVisible(True)
        self.save_logs_btn.setVisible(True)
        
        # Show metrics label and retry button, start auto-monitoring
        self.metrics_label.setVisible(True)
        self.metrics_label.setText("📊 Loading metrics...")
        self.retry_metrics_btn.setVisible(True)
        
        logger.info("Starting logs worker")
        self.worker.start()
        
        # Track stream start time for memory warnings
        import time
        self._stream_start_time = time.time()
        
        # Auto-start metrics monitoring for this pod (non-blocking, won't affect logs)
        # Wait a moment for logs to start, then start metrics in background
        try:
            from PySide6.QtCore import QTimer
            logger.info(f"Scheduling metrics monitoring for: {pod_name}")
            # Start metrics after 2 seconds to let logs stabilize
            QTimer.singleShot(2000, self.start_metrics_monitoring)
        except Exception as e:
            logger.warning(f"Failed to schedule metrics monitoring (logs unaffected): {e}")
            self.metrics_label.setText("⚠️ Metrics unavailable")
    
    def stop_log_stream(self):
        """Stop the current log stream but keep logs visible."""
        if self.worker and self.worker.isRunning():
            logger.info("Stopping log stream")
            self.console_output.append("\n[INFO] Stopping log stream...\n")
            self.worker.stop()
            self.worker.wait(2000)  # Wait up to 2 seconds
            
        # Stop metrics monitoring
        self.stop_metrics_monitoring()
        
        # Disable stop button (no longer streaming)
        self.stop_logs_btn.setEnabled(False)
        self.current_pod_for_metrics = None
        
        # Hide metrics and retry button
        self.metrics_label.setVisible(False)
        self.metrics_label.clear()
        self.retry_metrics_btn.setVisible(False)
        
        # Reset stream tracking
        self._stream_start_time = None
        
        # Keep logs visible, keep pod label, keep fullscreen/save buttons
        # User can still view, save, or fullscreen the stopped logs
    
    def start_metrics_monitoring(self):
        """Start monitoring CPU and memory for the current pod viewing logs.
        
        NOTE: This is a non-critical feature. If it fails, logs will continue to work normally.
        """
        if not self.current_pod_for_metrics:
            logger.warning("No pod selected for metrics monitoring")
            return
        
        # Check if we have a metrics SSH connection
        if not self.ssh_manager_metrics or not self.ssh_manager_metrics.is_connected():
            logger.warning("Metrics SSH connection not available")
            self.metrics_label.setText("│ ⚠️ Metrics unavailable")
            self.metrics_label.setToolTip("Metrics connection not established")
            return
        
        try:
            logger.info(f"Starting metrics monitoring for pod: {self.current_pod_for_metrics}")
            
            # Stop any active metrics monitoring
            self.stop_metrics_monitoring()
            
            # Show fetching state
            self.metrics_label.setText("│ 📊 Fetching...")
            
            # Create and start worker for metrics (using SEPARATE SSH connection)
            self.metrics_worker = ArgoWorker(
                action="metrics",
                pod=self.current_pod_for_metrics,
                ssh_manager=self.ssh_manager_metrics  # Use separate connection!
            )
            self.metrics_worker.metrics.connect(self._update_metrics_display)
            self.metrics_worker.error.connect(self._on_metrics_error)
            
            self.is_monitoring_metrics = True
            
            logger.info("Starting metrics worker (on separate SSH connection)")
            self.metrics_worker.start()
            
        except Exception as e:
            logger.error(f"Failed to start metrics monitoring (logs unaffected): {e}", exc_info=True)
            self.metrics_label.setText("│ ⚠️ Metrics unavailable")
            self.is_monitoring_metrics = False
    
    def stop_metrics_monitoring(self):
        """Stop the current metrics monitoring."""
        if hasattr(self, 'metrics_worker') and self.metrics_worker and self.metrics_worker.isRunning():
            logger.info("Stopping metrics monitoring")
            self.metrics_worker.stop()
            self.metrics_worker.wait(2000)  # Wait up to 2 seconds
            self.is_monitoring_metrics = False
    
    def retry_metrics(self):
        """Manually retry fetching metrics for the current pod."""
        if not self.current_pod_for_metrics:
            logger.warning("No pod selected for metrics retry")
            QMessageBox.warning(self, "No Pod Selected", "Please select a pod first to view metrics.")
            return
        
        logger.info(f"Manual metrics retry requested for pod: {self.current_pod_for_metrics}")
        self.metrics_label.setText("│ 🔄 Retrying...")
        
        # Stop existing metrics monitoring and restart
        self.stop_metrics_monitoring()
        
        # Restart metrics monitoring
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, self.start_metrics_monitoring)  # Quick retry
    
    def _update_metrics_display(self, metrics_text: str):
        """Update the metrics display with new data - compact single line format.
        
        PERFORMANCE: Throttle UI updates to prevent freezing during heavy log streaming.
        """
        import time
        
        # Throttle metrics UI updates to max once per 2 seconds
        # This prevents UI freezing when logs are streaming heavily
        current_time = time.time()
        if current_time - self._last_metrics_update < 2.0:
            # Skip this update, too soon since last one
            return
        
        self._last_metrics_update = current_time
        
        # Parse the metrics to extract CPU and Memory
        lines = metrics_text.strip().split('\n')
        cpu_usage = "N/A"
        memory_usage = "N/A"
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Skip command echoes (lines containing "kubectl" or "top")
            if "kubectl" in line.lower() or line.startswith("$") or line.startswith("#"):
                continue
            
            parts = line.split()
            if len(parts) >= 3:
                # Skip header line
                if parts[0] == "NAME" or "NAME" in line:
                    continue
                
                # Format should be: POD_NAME CPU(cores) MEMORY(bytes)
                # Example: henrys-prod-full-jnkw4-processing-step-1060948657   45m          147Mi
                pod_name_part = parts[0]
                
                # Verify this looks like a pod name (contains hyphens)
                if "-" in pod_name_part and self.current_pod_for_metrics in pod_name_part:
                    cpu_usage = parts[1] if len(parts) > 1 else "N/A"
                    memory_usage = parts[2] if len(parts) > 2 else "N/A"
                    logger.debug(f"Parsed metrics - CPU: {cpu_usage}, Memory: {memory_usage}")
                    break
        
        # Ultra-compact single line format
        metrics_text = f"│ 📊 CPU: {cpu_usage} • Memory: {memory_usage}"
        self.metrics_label.setText(metrics_text)
        
        # Update fullscreen metrics label if in fullscreen mode
        if self.is_fullscreen and hasattr(self, 'fullscreen_metrics_label'):
            self.fullscreen_metrics_label.setText(metrics_text)
    
    def _on_metrics_error(self, error_msg: str):
        """Handle error from metrics worker.
        
        NOTE: Metrics errors do NOT affect log streaming - logs will continue to work.
        """
        logger.warning(f"Metrics worker error (logs unaffected): {error_msg}")
        
        # User-friendly compact error message
        if "Metrics API not available" in error_msg or "Metrics server not available" in error_msg:
            self.metrics_label.setText("│ ⚠️ Metrics server not installed")
            self.metrics_label.setToolTip("Install metrics-server in cluster for resource monitoring. Logs are working normally.")
        else:
            self.metrics_label.setText("│ ⚠️ Metrics unavailable")
            self.metrics_label.setToolTip(f"Error: {error_msg}. Logs are working normally.")
        
        self.is_monitoring_metrics = False
    
    def find_in_logs(self):
        """Find text in the log output (case-insensitive)."""
        search_text = self.log_search_input.text().strip()
        if not search_text:
            logger.warning("No search text provided for log search")
            QMessageBox.warning(self._get_active_window(), "Input Required", "Please enter text to search")
            return
        
        logger.info(f"Searching logs for: '{search_text}' (case-insensitive)")
        
        # Store the search term
        self.current_search_term = search_text
        
        # Find all occurrences
        self.search_occurrences = self._find_all_occurrences(search_text)
        
        if self.search_occurrences:
            # Jump to first occurrence
            self._jump_to_occurrence(0)
            logger.info(f"Found {len(self.search_occurrences)} occurrence(s) of '{search_text}'")
        else:
            logger.info(f"'{search_text}' not found in logs")
            self.current_occurrence_index = -1
            self._update_match_counter()
            QMessageBox.information(self._get_active_window(), "Not Found", f"Text '{search_text}' not found in logs")
    
    def find_next(self):
        """Find the next occurrence of the search text (case-insensitive)."""
        search_text = self.log_search_input.text().strip()
        if not search_text:
            logger.warning("No search text provided for find next")
            QMessageBox.warning(self._get_active_window(), "Input Required", "Please enter text to search")
            return
        
        # If search term changed, do a fresh search
        if search_text != self.current_search_term:
            self.find_in_logs()
            return
        
        # Refresh occurrences to include new log entries
        self.search_occurrences = self._find_all_occurrences(search_text)
        
        if not self.search_occurrences:
            QMessageBox.information(self._get_active_window(), "Not Found", f"Text '{search_text}' not found in logs")
            return
        
        # Move to next occurrence (wrap around if needed)
        next_index = (self.current_occurrence_index + 1) % len(self.search_occurrences)
        self._jump_to_occurrence(next_index)
        
        logger.info(f"Moved to occurrence {next_index + 1} of {len(self.search_occurrences)}")
    
    def find_previous(self):
        """Find the previous occurrence of the search text (case-insensitive)."""
        search_text = self.log_search_input.text().strip()
        if not search_text:
            logger.warning("No search text provided for find previous")
            QMessageBox.warning(self._get_active_window(), "Input Required", "Please enter text to search")
            return
        
        # If search term changed, do a fresh search
        if search_text != self.current_search_term:
            self.find_in_logs()
            return
        
        # Refresh occurrences to include new log entries
        self.search_occurrences = self._find_all_occurrences(search_text)
        
        if not self.search_occurrences:
            QMessageBox.information(self._get_active_window(), "Not Found", f"Text '{search_text}' not found in logs")
            return
        
        # Move to previous occurrence (wrap around if needed)
        prev_index = (self.current_occurrence_index - 1) % len(self.search_occurrences)
        self._jump_to_occurrence(prev_index)
        
        logger.info(f"Moved to occurrence {prev_index + 1} of {len(self.search_occurrences)}")
    
    def clear_log_search(self):
        """Clear the search input and remove any highlights."""
        logger.info("Clearing log search")
        self.log_search_input.clear()
        self.match_counter_label.clear()
        
        # Reset search state
        self.current_search_term = ""
        self.search_occurrences = []
        self.current_occurrence_index = -1
        
        # Clear any text selection/highlighting
        cursor = self.log_output.textCursor()
        cursor.clearSelection()
        self.log_output.setTextCursor(cursor)
    
    def save_logs_to_file(self):
        """Save the current logs to a text file."""
        logger.info("Save logs to file requested")
        
        # Get the current log content
        log_content = self.log_output.toPlainText()
        
        if not log_content:
            QMessageBox.warning(self._get_active_window(), "No Logs", "There are no logs to save.")
            return
        
        # Get the current pod name for default filename
        pod_name = self.current_pod_label.text().replace("Viewing logs for: ", "").replace(":", "-")
        if not pod_name or pod_name == "No pod selected":
            pod_name = "logs"
        
        # Generate default filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{pod_name}_{timestamp}.txt"
        
        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self._get_active_window(),
            "Save Logs",
            default_filename,
            "Text Files (*.txt);;Log Files (*.log);;All Files (*.*)"
        )
        
        if file_path:
            try:
                # Write logs to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                
                # SECURITY: Set secure file permissions (owner read/write only)
                # This prevents other users from reading potentially sensitive logs
                secure_perms = SecurityConfig.get_secure_file_permissions()
                if secure_perms and os.name != 'nt':  # Unix-like systems only
                    try:
                        os.chmod(file_path, secure_perms)
                        logger.info(f"SECURITY: Set secure file permissions {oct(secure_perms)} on {file_path}")
                    except Exception as perm_error:
                        logger.warning(f"Could not set secure file permissions: {perm_error}")
                
                logger.info(f"Logs saved successfully to: {file_path}")
                QMessageBox.information(
                    self._get_active_window(),
                    "Success",
                    f"Logs saved successfully to:\n{file_path}"
                )
            except Exception as e:
                logger.error(f"Error saving logs: {e}")
                QMessageBox.critical(
                    self._get_active_window(),
                    "Error",
                    f"Failed to save logs:\n{str(e)}"
                )
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode for the log viewer."""
        if not self.is_fullscreen:
            # Enter fullscreen
            logger.info("Entering fullscreen mode")
            
            # Store original parent
            self.original_parent = self.log_container.parent()
            
            # Create fullscreen window
            self.fullscreen_window = QWidget(None, Qt.WindowType.Window)
            self.fullscreen_window.setWindowTitle("Live Logs - Fullscreen (Press Esc or F11 to exit)")
            
            # Set fullscreen
            self.fullscreen_window.showFullScreen()
            
            # Move log container to fullscreen window
            fullscreen_layout = QVBoxLayout(self.fullscreen_window)
            fullscreen_layout.setContentsMargins(10, 10, 10, 10)
            
            # Add header with pod name and exit button
            header_layout = QHBoxLayout()
            
            fullscreen_pod_label = QLabel()
            fullscreen_pod_label.setText(self.current_pod_label.text())
            fullscreen_pod_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
            header_layout.addWidget(fullscreen_pod_label)
            self.fullscreen_pod_label = fullscreen_pod_label
            
            # Add metrics label to fullscreen as well
            fullscreen_metrics_label = QLabel()
            fullscreen_metrics_label.setText(self.metrics_label.text())
            # Color based on current theme
            if self.current_theme.lower() == "dark":
                metrics_color = "#ffffff"
            else:
                metrics_color = "#212121"
            fullscreen_metrics_label.setStyleSheet(f"color: {metrics_color}; font-size: 11pt; margin-left: 15px; font-weight: bold;")
            fullscreen_metrics_label.setVisible(self.metrics_label.isVisible())
            header_layout.addWidget(fullscreen_metrics_label)
            self.fullscreen_metrics_label = fullscreen_metrics_label
            
            header_layout.addStretch()
            
            exit_fullscreen_btn = QPushButton("✕ Exit Fullscreen")
            exit_fullscreen_btn.clicked.connect(self.toggle_fullscreen)
            exit_fullscreen_btn.setToolTip("Exit fullscreen (Esc or F11)")
            exit_fullscreen_btn.setMinimumWidth(140)
            exit_fullscreen_btn.setMinimumHeight(30)
            exit_fullscreen_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            header_layout.addWidget(exit_fullscreen_btn)
            
            fullscreen_layout.addLayout(header_layout)
            
            # Reparent log container to fullscreen window
            self.log_container.setParent(self.fullscreen_window)
            fullscreen_layout.addWidget(self.log_container)
            
            # Add shortcuts for fullscreen window
            escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.fullscreen_window)
            escape_shortcut.activated.connect(self.handle_escape)
            
            f11_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self.fullscreen_window)
            f11_shortcut.activated.connect(self.toggle_fullscreen)
            
            # Search shortcuts in fullscreen
            find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self.fullscreen_window)
            find_shortcut.activated.connect(self.show_search_bar)
            
            find_next_shortcut = QShortcut(QKeySequence.StandardKey.FindNext, self.fullscreen_window)
            find_next_shortcut.activated.connect(self.find_next)
            
            find_prev_shortcut = QShortcut(QKeySequence.StandardKey.FindPrevious, self.fullscreen_window)
            find_prev_shortcut.activated.connect(self.find_previous)
            
            # Apply theme to fullscreen window
            theme = ThemeManager.get_theme(self.current_theme)
            self.fullscreen_window.setStyleSheet(theme["stylesheet"])
            
            self.is_fullscreen = True
            self.fullscreen_btn.setText("⛶ Exit Fullscreen")
            
        else:
            # Exit fullscreen
            self.exit_fullscreen()
    
    def exit_fullscreen(self):
        """Exit fullscreen mode."""
        if self.is_fullscreen and hasattr(self, 'fullscreen_window'):
            logger.info("Exiting fullscreen mode")
            
            # Close search bar if open
            self.hide_search_bar()
            
            # Move log container back to original parent
            if self.original_parent:
                # Find the log section group box
                log_section = self.original_parent
                log_section_layout = log_section.layout()
                
                # Re-add log container to original position (after header, before buttons)
                self.log_container.setParent(log_section)
                log_section_layout.insertWidget(1, self.log_container)
            
            # Close and delete fullscreen window
            self.fullscreen_window.close()
            self.fullscreen_window.deleteLater()
            
            self.is_fullscreen = False
            self.fullscreen_btn.setText("⛶ Fullscreen")
    
    # -------------------------
    # Signal Handlers
    # -------------------------
    
    def _on_connected(self):
        """Handle successful connection."""
        logger.info("Connection established signal received")
        self._set_connected_state()
        self.connect_btn.setText("Connect")
        self.console_output.append("\n=== Ready for operations ===\n")
        
        # Create a separate SSH connection for metrics (non-blocking)
        try:
            logger.info("Creating separate SSH connection for metrics monitoring")
            self.console_output.append("[INFO] Setting up metrics monitoring connection...\n")
            
            from PySide6.QtCore import QThread
            
            class MetricsConnectionWorker(QThread):
                def __init__(self, parent):
                    super().__init__(parent)
                    self.ssh_manager = None
                    self.error_msg = None
                
                def run(self):
                    try:
                        from app.ssh.connection_manager import SSHConnectionManager
                        self.ssh_manager = SSHConnectionManager()
                        self.ssh_manager.connect()
                    except Exception as e:
                        self.error_msg = str(e)
            
            self.metrics_connection_worker = MetricsConnectionWorker(self)
            
            def on_metrics_connection_complete():
                if self.metrics_connection_worker.error_msg:
                    logger.warning(f"Failed to create metrics connection: {self.metrics_connection_worker.error_msg}")
                    self.console_output.append("[WARNING] Metrics connection failed - metrics will be unavailable\n")
                elif self.metrics_connection_worker.ssh_manager:
                    self.ssh_manager_metrics = self.metrics_connection_worker.ssh_manager
                    logger.info("Metrics SSH connection established")
                    self.console_output.append("[OK] Metrics monitoring ready\n")
            
            self.metrics_connection_worker.finished.connect(on_metrics_connection_complete)
            self.metrics_connection_worker.start()
            
        except Exception as e:
            logger.warning(f"Failed to setup metrics connection: {e}")
        
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
        """Append text to log output and update search results if active."""
        # Smart scroll: Check if user is actually at the bottom using scrollbar position
        # IMPORTANT: Check BEFORE adding new text, as maximum will change!
        scrollbar = self.log_output.verticalScrollBar()
        was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10  # Allow small margin
        
        # Append the new text
        self.log_output.moveCursor(QTextCursor.MoveOperation.End)
        self.log_output.insertPlainText(text)
        
        # Memory warning check (every 30 minutes)
        self._check_memory_warning()
        
        # PERFORMANCE FIX: Only update search if user has scrolled up or explicitly searching
        # Don't re-index on every log line while streaming (expensive!)
        if self.current_search_term and not was_at_bottom:
            # Only update search when user is actively viewing search results
            old_count = len(self.search_occurrences)
            self.search_occurrences = self._find_all_occurrences(self.current_search_term)
            new_count = len(self.search_occurrences)
            
            # Update the counter display
            self._update_match_counter()
            
            # If we were at a valid occurrence, try to stay there
            if self.current_occurrence_index >= 0 and self.current_occurrence_index < len(self.search_occurrences):
                # Re-highlight the current occurrence to keep selection visible
                self._jump_to_occurrence(self.current_occurrence_index)
            
            if new_count > old_count:
                logger.debug(f"Search results updated: {old_count} -> {new_count} occurrences")
        
        # Smart scroll: Only auto-scroll if user was at bottom before new text arrived
        if was_at_bottom:
            # Scroll to the end
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)
            self.log_output.ensureCursorVisible()
    
    # -------------------------
    # Theme Management
    # -------------------------
    
    def _apply_theme(self, theme_name: str):
        """Apply the selected theme to the application (from themes.py)."""
        logger.info(f"Applying theme: {theme_name}")
        
        # Get theme class from themes.py
        theme_class = get_theme(theme_name)
        
        # Apply main stylesheet
        self.setStyleSheet(theme_class.get_main_stylesheet())
        
        # Update console and log output colors
        console_style = f"""
            QTextEdit {{
                background-color: {theme_class.log_background};
                color: {theme_class.log_text};
            }}
        """
        self.console_output.setStyleSheet(console_style)
        self.log_output.setStyleSheet(console_style)
        
        # Update metrics label color (theme-aware)
        self.metrics_label.setStyleSheet(
            f"color: {theme_class.metrics_text}; "
            f"font-size: 10pt; margin-left: 15px; font-weight: bold;"
        )
        
        # Update status label colors based on connection state (theme-aware)
        if self.is_connected:
            self.status_label.setStyleSheet(f"color: {theme_class.success_color}; font-weight: bold;")
        else:
            self.status_label.setStyleSheet(f"color: {theme_class.error_color}; font-weight: bold;")
    
    def _on_theme_changed(self, display_name: str):
        """Handle theme selection change (receives display name from dropdown)."""
        # Convert display name (e.g., "Dark Mode") to internal name (e.g., "dark")
        theme_name = get_theme_name_from_display(display_name)
        self.current_theme = theme_name
        self._apply_theme(self.current_theme)
        logger.info(f"Theme changed to: {self.current_theme} ({display_name})")
    
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
    
    def _show_shortcuts_dialog(self):
        """Show the Keyboard Shortcuts dialog."""
        logger.info("Showing Keyboard Shortcuts dialog")
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Keyboard Shortcuts")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Separator
        layout.addSpacing(10)
        
        # Shortcuts content
        shortcuts_text = QTextEdit()
        shortcuts_text.setReadOnly(True)
        shortcuts_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
        # Determine platform-specific key
        import platform
        if platform.system() == "Darwin":
            ctrl_key = "Cmd"
        else:
            ctrl_key = "Ctrl"
        
        shortcuts_content = f"""
<h3>🔍 Search in Logs</h3>
<table cellpadding="5" cellspacing="0" style="width: 100%;">
    <tr>
        <td style="width: 40%;"><b>{ctrl_key}+F</b></td>
        <td>Show/hide search bar</td>
    </tr>
    <tr>
        <td><b>Enter</b></td>
        <td>Find text (when in search field)</td>
    </tr>
    <tr>
        <td><b>F3</b></td>
        <td>Find next occurrence</td>
    </tr>
    <tr>
        <td><b>Shift+F3</b></td>
        <td>Find previous occurrence</td>
    </tr>
    <tr>
        <td><b>Escape</b></td>
        <td>Close search bar</td>
    </tr>
</table>

<h3>🖥️ View Controls</h3>
<table cellpadding="5" cellspacing="0" style="width: 100%;">
    <tr>
        <td style="width: 40%;"><b>F11</b></td>
        <td>Toggle fullscreen mode for logs</td>
    </tr>
    <tr>
        <td><b>Escape</b></td>
        <td>Exit fullscreen mode</td>
    </tr>
</table>

<h3>📋 General Actions</h3>
<table cellpadding="5" cellspacing="0" style="width: 100%;">
    <tr>
        <td style="width: 40%;"><b>Double-click</b></td>
        <td>Open logs for selected pod</td>
    </tr>
    <tr>
        <td><b>Enter</b></td>
        <td>Execute search/action in focused field</td>
    </tr>
</table>

<h3>💡 Tips</h3>
<ul>
    <li>Search is <b>case-insensitive</b> by default</li>
    <li>Search bar appears on demand ({ctrl_key}+F) - VS Code style</li>
    <li>Use fullscreen (F11) to maximize log viewing area</li>
    <li>All shortcuts work in both normal and fullscreen modes</li>
    <li>Search wraps around from end to beginning</li>
</ul>
        """
        
        shortcuts_text.setHtml(shortcuts_content)
        layout.addWidget(shortcuts_text)
        
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
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                    border: 1px solid #3c3c3c;
                }
                QLabel a {
                    color: #4a9eff;
                }
            """)
        else:
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                    color: #212121;
                }
                QTextEdit {
                    background-color: #fafafa;
                    color: #212121;
                    border: 1px solid #ccc;
                }
            """)
        
        dialog.exec()
    
    def _show_ssh_config_dialog(self):
        """Show the SSH Configuration Guide dialog."""
        logger.info("Showing SSH Configuration Guide dialog")
        
        dialog = QDialog(self)
        dialog.setWindowTitle("SSH Configuration Guide")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("SSH Configuration Guide")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Separator
        layout.addSpacing(10)
        
        # SSH Config content
        ssh_config_text = QTextEdit()
        ssh_config_text.setReadOnly(True)
        ssh_config_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        
        # Detect current OS
        import platform
        current_os = platform.system()
        
        # Determine theme-specific colors
        if self.current_theme == "dark":
            table_bg = "#3c3c3c"
            table_border = "#555"
            code_bg = "#2b2b2b"
            code_fg = "#4af626"
            highlight_color = "#2196f3"
            text_color = "#e0e0e0"
            hr_color = "#555"
        else:
            table_bg = "#f5f5f5"
            table_border = "#ccc"
            code_bg = "#f0f0f0"
            code_fg = "#c7254e"
            highlight_color = "#2196f3"
            text_color = "#212121"
            hr_color = "#ddd"
        
        ssh_config_content = f"""
<h3>📁 SSH Credential Locations by Operating System</h3>

<p><b>Current System Detected:</b> <span style="color: {highlight_color};">{current_os}</span></p>

<hr style="border: 1px solid {hr_color};">

<h4>🪟 <b>Windows</b></h4>
<table cellpadding="8" cellspacing="0" style="width: 100%; background-color: {table_bg}; border: 1px solid {table_border};">
    <tr>
        <td style="width: 35%;"><b>SSH Config File:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">C:\\Users\\YourUsername\\.ssh\\config</code></td>
    </tr>
    <tr>
        <td><b>Private Keys:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">C:\\Users\\YourUsername\\.ssh\\id_rsa</code><br>
            <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">C:\\Users\\YourUsername\\.ssh\\id_ed25519</code></td>
    </tr>
    <tr>
        <td><b>Public Keys:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">C:\\Users\\YourUsername\\.ssh\\id_rsa.pub</code><br>
            <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">C:\\Users\\YourUsername\\.ssh\\id_ed25519.pub</code></td>
    </tr>
    <tr>
        <td><b>Known Hosts:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">C:\\Users\\YourUsername\\.ssh\\known_hosts</code></td>
    </tr>
    <tr>
        <td><b>Shortcut:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">%USERPROFILE%\\.ssh\\</code></td>
    </tr>
</table>

<p><b>Windows Command to Open SSH Directory:</b></p>
<pre style="background-color: {code_bg}; color: {code_fg}; padding: 10px; border-radius: 5px;">cd %USERPROFILE%\\.ssh
notepad config</pre>

<hr style="border: 1px solid {hr_color};">

<h4>🐧 <b>Linux</b></h4>
<table cellpadding="8" cellspacing="0" style="width: 100%; background-color: {table_bg}; border: 1px solid {table_border};">
    <tr>
        <td style="width: 35%;"><b>SSH Config File:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/home/yourusername/.ssh/config</code></td>
    </tr>
    <tr>
        <td><b>Private Keys:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/home/yourusername/.ssh/id_rsa</code><br>
            <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/home/yourusername/.ssh/id_ed25519</code></td>
    </tr>
    <tr>
        <td><b>Public Keys:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/home/yourusername/.ssh/id_rsa.pub</code><br>
            <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/home/yourusername/.ssh/id_ed25519.pub</code></td>
    </tr>
    <tr>
        <td><b>Known Hosts:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/home/yourusername/.ssh/known_hosts</code></td>
    </tr>
    <tr>
        <td><b>Shortcut:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">~/.ssh/</code></td>
    </tr>
</table>

<p><b>Linux Commands:</b></p>
<pre style="background-color: {code_bg}; color: {code_fg}; padding: 10px; border-radius: 5px;">cd ~/.ssh
ls -la
nano config  # or vim config</pre>

<hr style="border: 1px solid {hr_color};">

<h4>🍎 <b>macOS</b></h4>
<table cellpadding="8" cellspacing="0" style="width: 100%; background-color: {table_bg}; border: 1px solid {table_border};">
    <tr>
        <td style="width: 35%;"><b>SSH Config File:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/Users/YourUsername/.ssh/config</code></td>
    </tr>
    <tr>
        <td><b>Private Keys:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/Users/YourUsername/.ssh/id_rsa</code><br>
            <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/Users/YourUsername/.ssh/id_ed25519</code></td>
    </tr>
    <tr>
        <td><b>Public Keys:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/Users/YourUsername/.ssh/id_rsa.pub</code><br>
            <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/Users/YourUsername/.ssh/id_ed25519.pub</code></td>
    </tr>
    <tr>
        <td><b>Known Hosts:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">/Users/YourUsername/.ssh/known_hosts</code></td>
    </tr>
    <tr>
        <td><b>Shortcut:</b></td>
        <td><code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">~/.ssh/</code></td>
    </tr>
</table>

<p><b>macOS Commands:</b></p>
<pre style="background-color: {code_bg}; color: {code_fg}; padding: 10px; border-radius: 5px;">cd ~/.ssh
ls -la
open -e config  # Opens in TextEdit</pre>

<hr style="border: 1px solid {hr_color};">

<h3>📝 Sample SSH Config File</h3>

<p>Create or edit <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">~/.ssh/config</code> (or <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">%USERPROFILE%\\.ssh\\config</code> on Windows):</p>

<pre style="background-color: {code_bg}; color: {code_fg}; padding: 10px; border-radius: 5px; font-family: 'Courier New', monospace;"># Jump Host Configuration
Host usejump
    HostName jump.example.com
    User your-username
    Port 22
    IdentityFile ~/.ssh/id_rsa
    
# Alternative Host
Host myjump
    HostName 192.168.1.100
    User admin
    IdentityFile ~/.ssh/id_ed25519</pre>

<hr style="border: 1px solid {hr_color};">

<h3>🔑 Generating SSH Keys</h3>

<p><b>All Operating Systems (in terminal/command prompt):</b></p>

<pre style="background-color: {code_bg}; color: {code_fg}; padding: 10px; border-radius: 5px;"># RSA 4096-bit (widely compatible)
ssh-keygen -t rsa -b 4096 -C "your-email@example.com"

# Ed25519 (modern, recommended)
ssh-keygen -t ed25519 -C "your-email@example.com"</pre>

<hr style="border: 1px solid {hr_color};">

<h3>🔒 Setting Correct Permissions</h3>

<h4>Linux/macOS:</h4>
<pre style="background-color: {code_bg}; color: {code_fg}; padding: 10px; border-radius: 5px;">chmod 700 ~/.ssh
chmod 600 ~/.ssh/config
chmod 600 ~/.ssh/id_rsa
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_rsa.pub
chmod 644 ~/.ssh/known_hosts</pre>

<h4>Windows:</h4>
<p>Windows handles permissions differently. If using OpenSSH for Windows:</p>
<pre style="background-color: {code_bg}; color: {code_fg}; padding: 10px; border-radius: 5px;">icacls %USERPROFILE%\\.ssh\\id_rsa /inheritance:r
icacls %USERPROFILE%\\.ssh\\id_rsa /grant:r "%USERNAME%:R"</pre>

<hr style="border: 1px solid {hr_color};">

<h3>✅ Quick Setup Checklist</h3>

<ol>
    <li>✓ SSH directory exists (<code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">~/.ssh</code> or <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">%USERPROFILE%\\.ssh</code>)</li>
    <li>✓ SSH keys generated (private and public key pair)</li>
    <li>✓ SSH config file created with jump host configuration</li>
    <li>✓ Public key added to remote servers' <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">authorized_keys</code></li>
    <li>✓ Correct permissions set on SSH files</li>
    <li>✓ Test connection manually: <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">ssh usejump</code></li>
</ol>

<hr style="border: 1px solid {hr_color};">

<h3>🆘 Troubleshooting</h3>

<table cellpadding="8" cellspacing="0" style="width: 100%; border: 1px solid {table_border};">
    <tr style="background-color: {table_bg};">
        <td style="width: 40%; border: 1px solid {table_border};"><b>Problem:</b> Permission denied (publickey)</td>
        <td style="border: 1px solid {table_border};"><b>Solution:</b> Add your public key to remote server's <code style="background-color: {code_bg}; color: {code_fg}; padding: 2px 4px;">~/.ssh/authorized_keys</code></td>
    </tr>
    <tr>
        <td style="border: 1px solid {table_border};"><b>Problem:</b> Host key verification failed</td>
        <td style="border: 1px solid {table_border};"><b>Solution:</b> Connect manually first to verify and add host key</td>
    </tr>
    <tr style="background-color: {table_bg};">
        <td style="border: 1px solid {table_border};"><b>Problem:</b> Config file not found</td>
        <td style="border: 1px solid {table_border};"><b>Solution:</b> Create it manually in the SSH directory</td>
    </tr>
    <tr>
        <td style="border: 1px solid {table_border};"><b>Problem:</b> Bad permissions error</td>
        <td style="border: 1px solid {table_border};"><b>Solution:</b> Run the permission commands above</td>
    </tr>
</table>

<hr style="border: 1px solid {hr_color};">

<p style="text-align: center; color: gray; font-size: 9pt;">
<b>Need more help?</b> Contact: harshmeet.singh@netcoreunbxd.com
</p>
        """
        
        ssh_config_text.setHtml(ssh_config_content)
        layout.addWidget(ssh_config_text)
        
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
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                    border: 1px solid #3c3c3c;
                }
                QLabel a {
                    color: #4a9eff;
                }
            """)
        else:
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                    color: #212121;
                }
                QTextEdit {
                    background-color: #fafafa;
                    color: #212121;
                    border: 1px solid #ccc;
                }
            """)
        
        dialog.exec()
    
    def _show_ssh_folder_config_dialog(self):
        """Show the SSH folder configuration dialog."""
        logger.info("Showing SSH folder configuration dialog")
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom SSH Folder Configuration")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(300)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Custom SSH Folder")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Explanation
        explanation = QLabel(
            "You can configure a custom SSH folder that contains your SSH config file, "
            "private keys, and other SSH-related files. This is useful if you have SSH "
            "configurations in a non-standard location.\n\n"
            "The folder should contain:\n"
            "• config file (SSH configuration)\n"
            "• Private keys (e.g., id_rsa, id_ed25519)\n"
            "• known_hosts file\n\n"
            "If not set, the default ~/.ssh folder will be used."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: gray; font-size: 10pt;")
        layout.addWidget(explanation)
        
        # Current configuration
        current_ssh_folder = AppConfig.get_custom_ssh_folder()
        current_label = QLabel(f"Current: {current_ssh_folder if current_ssh_folder else 'Default (~/.ssh)'}")
        current_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(current_label)
        
        # Folder selector
        folder_layout = QHBoxLayout()
        folder_label = QLabel("SSH Folder:")
        folder_layout.addWidget(folder_label)
        
        folder_path_input = QLineEdit()
        folder_path_input.setText(current_ssh_folder if current_ssh_folder else "")
        folder_path_input.setPlaceholderText("Select a folder or leave empty for default")
        folder_layout.addWidget(folder_path_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setMinimumWidth(100)
        browse_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        browse_btn.clicked.connect(
            lambda: self._browse_for_ssh_folder(folder_path_input)
        )
        folder_layout.addWidget(browse_btn)
        
        layout.addLayout(folder_layout)
        
        # Remove button
        remove_btn = QPushButton("Remove Custom Folder (Use Default)")
        remove_btn.clicked.connect(lambda: folder_path_input.clear())
        layout.addWidget(remove_btn)
        
        # Validation status
        validation_label = QLabel("")
        validation_label.setWordWrap(True)
        layout.addWidget(validation_label)
        
        # Validate on text change
        def validate_folder():
            path = folder_path_input.text().strip()
            if not path:
                validation_label.setText("✓ Will use default SSH folder (~/.ssh)")
                validation_label.setStyleSheet("color: green;")
                return True
            
            if not os.path.exists(path):
                validation_label.setText("✗ Folder does not exist")
                validation_label.setStyleSheet("color: red;")
                return False
            
            if not os.path.isdir(path):
                validation_label.setText("✗ Path is not a directory")
                validation_label.setStyleSheet("color: red;")
                return False
            
            # Check for config file
            config_path = os.path.join(path, "config")
            if not os.path.exists(config_path):
                validation_label.setText("⚠ Warning: No 'config' file found in this folder")
                validation_label.setStyleSheet("color: orange;")
                return True  # Allow but warn
            
            validation_label.setText("✓ Valid SSH folder")
            validation_label.setStyleSheet("color: green;")
            return True
        
        folder_path_input.textChanged.connect(lambda: validate_folder())
        validate_folder()  # Initial validation
        
        layout.addSpacing(10)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        
        def on_accept():
            path = folder_path_input.text().strip()
            if path and not validate_folder():
                QMessageBox.warning(dialog, "Invalid Folder", "Please select a valid SSH folder")
                return
            
            # Save configuration
            if path:
                AppConfig.set_custom_ssh_folder(path)
                logger.info(f"Custom SSH folder set to: {path}")
                QMessageBox.information(
                    dialog,
                    "Configuration Saved",
                    f"Custom SSH folder has been set to:\n{path}\n\n"
                    "This will be used for the next SSH connection."
                )
            else:
                AppConfig.set_custom_ssh_folder(None)
                logger.info("Custom SSH folder removed, using default")
                QMessageBox.information(
                    dialog,
                    "Configuration Saved",
                    "Custom SSH folder has been removed.\n\n"
                    "The default ~/.ssh folder will be used."
                )
            
            dialog.accept()
        
        button_box.accepted.connect(on_accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        # Apply current theme to dialog
        if self.current_theme == "dark":
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    color: #e0e0e0;
                }
                QLineEdit {
                    background-color: #3c3c3c;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    padding: 5px;
                }
            """)
        
        dialog.exec()
    
    def _browse_for_ssh_folder(self, input_widget: QLineEdit):
        """Open folder browser for SSH folder selection."""
        current_path = input_widget.text().strip()
        if not current_path or not os.path.exists(current_path):
            current_path = os.path.expanduser("~")
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select SSH Folder",
            current_path,
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            input_widget.setText(folder)
            logger.debug(f"Selected SSH folder: {folder}")
    
    # -------------------------
    # Update Checking Methods
    # -------------------------
    
    def _check_for_updates_background(self):
        """Check for updates in the background (non-blocking)."""
        from PySide6.QtCore import QThread
        
        logger.info("Starting background update check")
        
        class UpdateCheckThread(QThread):
            def __init__(self, parent):
                super().__init__(parent)
                self.update_info = None
            
            def run(self):
                self.update_info = UpdateChecker.check_for_updates()
                UpdateChecker.mark_update_checked()
        
        self.update_thread = UpdateCheckThread(self)
        self.update_thread.finished.connect(self._on_update_check_complete)
        self.update_thread.start()
    
    def _on_update_check_complete(self):
        """Handle completion of background update check."""
        if hasattr(self, 'update_thread'):
            update_info = self.update_thread.update_info
            if update_info:
                logger.info(f"Update available: {update_info.version}")
                self.pending_update = update_info
                self._show_update_notification(update_info)
            else:
                logger.info("No updates available")
    
    def _check_for_updates_manual(self):
        """Manually check for updates (triggered by user)."""
        logger.info("Manual update check requested")
        
        # Show temporary message in console
        self.console_output.append("\n[INFO] Checking for updates...\n")
        
        # Check in background
        from PySide6.QtCore import QThread
        
        class UpdateCheckThread(QThread):
            def __init__(self, parent):
                super().__init__(parent)
                self.update_info = None
                self.error = None
            
            def run(self):
                try:
                    self.update_info = UpdateChecker.check_for_updates()
                    UpdateChecker.mark_update_checked()
                except Exception as e:
                    self.error = str(e)
        
        self.manual_update_thread = UpdateCheckThread(self)
        self.manual_update_thread.finished.connect(self._on_manual_update_check_complete)
        self.manual_update_thread.start()
    
    def _on_manual_update_check_complete(self):
        """Handle completion of manual update check."""
        if hasattr(self, 'manual_update_thread'):
            if self.manual_update_thread.error:
                QMessageBox.critical(
                    self,
                    "Update Check Failed",
                    f"Failed to check for updates:\n{self.manual_update_thread.error}"
                )
                return
            
            update_info = self.manual_update_thread.update_info
            if update_info:
                logger.info(f"Update available: {update_info.version}")
                self.pending_update = update_info
                self._show_update_dialog(update_info)
            else:
                QMessageBox.information(
                    self,
                    "Up to Date",
                    f"You are running the latest version ({UpdateConfig.get_current_version()})."
                )
    
    def _show_update_notification(self, update_info: UpdateInfo):
        """Show a non-intrusive update notification."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Update Available")
        msg_box.setIcon(QMessageBox.Icon.Information)
        
        if update_info.is_critical:
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText(f"⚠️ Critical Update Available: v{update_info.version}")
        else:
            msg_box.setText(f"Update Available: v{update_info.version}")
        
        msg_box.setInformativeText(
            f"A new version of Argo Log Viewer is available.\n\n"
            f"Current version: {UpdateConfig.get_current_version()}\n"
            f"New version: {update_info.version}\n\n"
            "Would you like to download it now?"
        )
        
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No
        )
        
        if not update_info.is_critical:
            skip_btn = msg_box.addButton("Skip This Version", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        result = msg_box.exec()
        
        if result == QMessageBox.StandardButton.Yes:
            self._download_update(update_info)
        elif msg_box.clickedButton() == skip_btn if not update_info.is_critical else False:
            AppConfig.set_skip_version(update_info.version)
            logger.info(f"User skipped version {update_info.version}")
    
    def _show_update_dialog(self, update_info: UpdateInfo):
        """Show detailed update dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Update Available")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        if update_info.is_critical:
            title_label = QLabel(f"⚠️ Critical Update Available")
            title_label.setStyleSheet("color: orange; font-weight: bold; font-size: 14pt;")
        else:
            title_label = QLabel(f"New Version Available: v{update_info.version}")
            title_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        
        layout.addWidget(title_label)
        
        # Version info
        version_info = QLabel(
            f"Current version: {UpdateConfig.get_current_version()}\n"
            f"New version: {update_info.version}"
        )
        layout.addWidget(version_info)
        
        # Release notes
        notes_label = QLabel("Release Notes:")
        notes_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(notes_label)
        
        notes_text = QTextEdit()
        notes_text.setReadOnly(True)
        notes_text.setPlainText(update_info.release_notes)
        notes_text.setMaximumHeight(200)
        layout.addWidget(notes_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        download_btn = QPushButton("Download Update")
        download_btn.clicked.connect(lambda: self._download_update(update_info))
        download_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(download_btn)
        
        if not update_info.is_critical:
            skip_btn = QPushButton("Skip This Version")
            skip_btn.clicked.connect(lambda: AppConfig.set_skip_version(update_info.version))
            skip_btn.clicked.connect(dialog.accept)
            button_layout.addWidget(skip_btn)
        
        later_btn = QPushButton("Remind Me Later")
        later_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(later_btn)
        
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # Apply current theme to dialog
        if self.current_theme == "dark":
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                    color: #e0e0e0;
                }
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                    border: 1px solid #3c3c3c;
                }
            """)
        
        dialog.exec()
    
    def _download_update(self, update_info: UpdateInfo):
        """Open browser to GitHub releases page."""
        logger.info(f"Opening GitHub releases page: {update_info.download_url}")
        try:
            webbrowser.open(update_info.download_url)
            QMessageBox.information(
                self,
                "Opening Releases Page",
                "Your browser will open the GitHub releases page.\n\n"
                "Please download the correct version for your platform:\n"
                "• Windows: .exe file\n"
                "• macOS: .dmg or .zip file\n"
                "• Linux: Linux binary\n\n"
                "After downloading, install and restart the application."
            )
        except Exception as e:
            logger.error(f"Error opening releases page: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Could not open releases page:\n{update_info.download_url}\n\n"
                "Please visit GitHub manually to download the update."
            )
    
    def _check_memory_warning(self):
        """Check if we should show a memory warning for long-running streams."""
        if not AppConfig.get_show_memory_warnings():
            return
        
        if not self._stream_start_time:
            return
        
        import time
        current_time = time.time()
        stream_duration = current_time - self._stream_start_time
        
        # Show warning every 30 minutes (1800 seconds)
        time_since_last_warning = current_time - self._last_memory_warning_time
        
        if stream_duration > 1800 and time_since_last_warning > 1800:
            # Get line count
            line_count = self.log_output.document().blockCount()
            
            # Only warn if there are many lines
            if line_count > 10000:
                self._last_memory_warning_time = current_time
                self._show_memory_warning(stream_duration, line_count)
    
    def _show_memory_warning(self, duration_seconds: float, line_count: int):
        """Show memory warning dialog for long-running streams."""
        hours = int(duration_seconds / 3600)
        minutes = int((duration_seconds % 3600) / 60)
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Long-Running Stream Detected")
        msg.setText(f"This log stream has been running for {hours}h {minutes}m")
        msg.setInformativeText(
            f"Current log lines: {line_count:,}\n\n"
            f"Long streams use more memory. You can:\n"
            f"• Save logs now and restart stream\n"
            f"• Continue streaming (unlimited logs)\n"
            f"• Configure buffer limit in Settings > Advanced"
        )
        
        save_btn = msg.addButton("Save Logs Now", QMessageBox.ButtonRole.ActionRole)
        continue_btn = msg.addButton("Continue Streaming", QMessageBox.ButtonRole.AcceptRole)
        settings_btn = msg.addButton("Settings", QMessageBox.ButtonRole.ActionRole)
        dont_show_btn = msg.addButton("Don't Show Again", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        
        clicked = msg.clickedButton()
        if clicked == save_btn:
            self.save_current_logs()
        elif clicked == settings_btn:
            self._show_advanced_settings_dialog()
        elif clicked == dont_show_btn:
            AppConfig.set_show_memory_warnings(False)
    
    def _show_advanced_settings_dialog(self):
        """Show advanced settings dialog for log buffer and warnings."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced Settings")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # Description
        desc = QLabel(
            "<b>Log Buffer Settings</b><br>"
            "Configure how logs are managed during streaming."
        )
        layout.addWidget(desc)
        
        # Buffer limit option
        from PySide6.QtWidgets import QRadioButton, QSpinBox
        
        buffer_group = QGroupBox("Log Buffer Limit")
        buffer_layout = QVBoxLayout()
        
        current_limit = AppConfig.get_log_buffer_limit()
        
        unlimited_radio = QRadioButton("Unlimited (Keep all logs)")
        unlimited_radio.setChecked(current_limit == 0)
        buffer_layout.addWidget(unlimited_radio)
        
        limited_radio = QRadioButton("Limited (For very long streams)")
        limited_radio.setChecked(current_limit > 0)
        buffer_layout.addWidget(limited_radio)
        
        limit_spin = QSpinBox()
        limit_spin.setMinimum(10)  # Allow very small values for testing
        limit_spin.setMaximum(1000000)
        limit_spin.setSingleStep(100)  # Smaller steps for fine control
        # Default to a reasonable value (50k lines) when switching to Limited mode
        limit_spin.setValue(current_limit if current_limit > 0 else 50000)
        limit_spin.setSuffix(" lines")
        limit_spin.setEnabled(current_limit > 0)
        buffer_layout.addWidget(limit_spin)
        
        limited_radio.toggled.connect(limit_spin.setEnabled)
        
        info_label = QLabel(
            "<small>"
            "<b>Unlimited:</b> Keeps all logs (default - recommended for complete log saving)<br>"
            "<b>Limited:</b> Keeps only recent lines (saves memory for 24hr+ streams)"
            "</small>"
        )
        info_label.setWordWrap(True)
        buffer_layout.addWidget(info_label)
        
        buffer_group.setLayout(buffer_layout)
        layout.addWidget(buffer_group)
        
        # Memory warnings option
        from PySide6.QtWidgets import QCheckBox
        
        warnings_group = QGroupBox("Memory Warnings")
        warnings_layout = QVBoxLayout()
        
        show_warnings_check = QCheckBox("Show warnings for long-running streams")
        show_warnings_check.setChecked(AppConfig.get_show_memory_warnings())
        warnings_layout.addWidget(show_warnings_check)
        
        warnings_info = QLabel(
            "<small>If enabled, you'll be notified every 30 minutes when streaming "
            "logs for extended periods.</small>"
        )
        warnings_info.setWordWrap(True)
        warnings_layout.addWidget(warnings_info)
        
        warnings_group.setLayout(warnings_layout)
        layout.addWidget(warnings_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Save settings
            if unlimited_radio.isChecked():
                new_limit = 0
            else:
                new_limit = limit_spin.value()
            
            AppConfig.set_log_buffer_limit(new_limit)
            AppConfig.set_show_memory_warnings(show_warnings_check.isChecked())
            
            # Apply buffer limit to current log output
            if new_limit > 0:
                self.log_output.document().setMaximumBlockCount(new_limit)
            else:
                self.log_output.document().setMaximumBlockCount(0)  # unlimited
            
            QMessageBox.information(
                self,
                "Settings Saved",
                "Advanced settings have been saved successfully."
            )
    
    def _show_user_guide_dialog(self):
        """Show comprehensive user guide with all features."""
        dialog = QDialog(self)
        dialog.setWindowTitle("User Guide - How to Use Argo Log Viewer")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        
        # Create text browser for scrollable content
        from PySide6.QtWidgets import QTextBrowser
        guide = QTextBrowser()
        guide.setOpenExternalLinks(True)
        
        # Get theme-aware HTML styles from themes.py
        theme_class = get_theme(self.current_theme)
        html_styles = theme_class.get_user_guide_html_style()
        
        # Build HTML with theme-aware styling
        guide.setHtml(f"""
        <html>
        <head>
            {html_styles}
        </head>
        <body>
            <h1>📖 Argo Log Viewer - Complete User Guide</h1>
            
            <h2>🚀 Getting Started</h2>
            <div class="feature">
                <h3>1. Connection Setup</h3>
                <div class="step">
                    <b>Step 1:</b> Click <b>"Connect"</b> button<br>
                    <b>Step 2:</b> Wait for SSH connection to establish<br>
                    <b>Step 3:</b> Console will show "Connected successfully"<br>
                    <b>Status:</b> Green dot indicates connected
                </div>
                <div class="tip">
                    <b>💡 Tip:</b> Make sure your SSH config is set up properly. 
                    See <b>Help > SSH Configuration Guide</b> for details.
                </div>
            </div>
            
            <div class="feature">
                <h3>2. Viewing Pod Logs</h3>
                <div class="step">
                    <b>Step 1:</b> Click <b>"Refresh Pods"</b> to load pods<br>
                    <b>Step 2:</b> Use search box to filter pods by name<br>
                    <b>Step 3:</b> Double-click a pod to view its logs<br>
                    <b>Result:</b> Logs stream in real-time
                </div>
            </div>
            
            <h2>🎯 Core Features</h2>
            
            <div class="feature">
                <h3>📊 Real-Time Resource Monitoring</h3>
                <p><b>What it shows:</b> CPU and Memory usage for the selected pod</p>
                <p><b>Where:</b> Next to pod name in log header</p>
                <p><b>Update frequency:</b> Every 10 seconds</p>
                <p><b>Retry:</b> Click 🔄 button to manually refresh metrics</p>
                <div class="tip">
                    <b>Note:</b> New pods need ~60 seconds before metrics are available.
                    If metrics show "Not available", wait a moment and click retry.
                </div>
            </div>
            
            <div class="feature">
                <h3>🔍 Log Search</h3>
                <p><b>Open search:</b> Press <code>Ctrl+F</code> (Windows/Linux) or <code>Cmd+F</code> (Mac)</p>
                <p><b>Enter search term:</b> Type in search box</p>
                <p><b>Navigate:</b> Use ↑↓ buttons or press <code>Enter</code> for next match</p>
                <p><b>Case-sensitive:</b> Check the "Match Case" option</p>
                <p><b>Close:</b> Press <code>Esc</code> or click X</p>
                <div class="tip">
                    <b>💡 Tip:</b> Search works on all logs, even while streaming.
                    Results update as new logs arrive (when scrolled up).
                </div>
            </div>
            
            <div class="feature">
                <h3>💾 Saving Logs</h3>
                <p><b>When:</b> Available when viewing logs</p>
                <p><b>How:</b> Click <b>"Save Logs"</b> button</p>
                <p><b>Choose location:</b> Select where to save the .txt file</p>
                <p><b>What's saved:</b> All logs currently visible (complete history)</p>
                <div class="tip">
                    <b>💡 Tip:</b> Logs are saved with secure permissions (600).
                    You can save even after stopping the stream.
                </div>
            </div>
            
            <div class="feature">
                <h3>⛶ Fullscreen Mode</h3>
                <p><b>Enter:</b> Click <b>"Fullscreen"</b> button</p>
                <p><b>Features:</b> Logs-only view with search and metrics</p>
                <p><b>Exit:</b> Press <code>Esc</code> or click <b>"Exit Fullscreen"</b></p>
                <div class="tip">
                    <b>💡 Tip:</b> Perfect for presentations or focused debugging!
                </div>
            </div>
            
            <div class="feature">
                <h3>⏹️ Stop Logs</h3>
                <p><b>What it does:</b> Stops live streaming</p>
                <p><b>What it keeps:</b> All existing logs remain visible</p>
                <p><b>What it hides:</b> Metrics and retry button</p>
                <p><b>Still available:</b> Save, Search, Fullscreen</p>
                <div class="tip">
                    <b>💡 Use case:</b> Stop streaming to save current logs, then select another pod.
                </div>
            </div>
            
            <h2>🎨 Customization</h2>
            
            <div class="feature">
                <h3>Theme Selection</h3>
                <p><b>Options:</b> Dark Mode (default), Light Mode, High Contrast</p>
                <p><b>Where:</b> Theme selector at top-right</p>
                <p><b>Effect:</b> Changes all UI colors instantly</p>
            </div>
            
            <div class="feature">
                <h3>Custom SSH Folder</h3>
                <p><b>Where:</b> Settings > Custom SSH Folder</p>
                <p><b>Use case:</b> Use non-default SSH config location</p>
                <p><b>Example:</b> Work SSH config vs Personal SSH config</p>
            </div>
            
            <div class="feature">
                <h3>Advanced Settings</h3>
                <p><b>Where:</b> Settings > Advanced Settings</p>
                <p><b>Options:</b></p>
                <ul>
                    <li><b>Log Buffer:</b> Unlimited (default) or Limited for 24hr+ streams</li>
                    <li><b>Memory Warnings:</b> Get notified for long-running streams</li>
                </ul>
                <div class="tip">
                    <b>💡 Recommendation:</b> Keep "Unlimited" for complete log saving.
                    Use "Limited" only if you run into memory issues with very long streams.
                </div>
            </div>
            
            <h2>🔧 Keyboard Shortcuts</h2>
            <div class="feature">
                <table>
                    <tr>
                        <th>Action</th>
                        <th>Windows/Linux</th>
                        <th>macOS</th>
                    </tr>
                    <tr>
                        <td>Open Search</td>
                        <td><code>Ctrl+F</code></td>
                        <td><code>Cmd+F</code></td>
                    </tr>
                    <tr>
                        <td>Next Search Result</td>
                        <td><code>Enter</code> or <code>F3</code></td>
                        <td><code>Enter</code> or <code>Cmd+G</code></td>
                    </tr>
                    <tr>
                        <td>Previous Search Result</td>
                        <td><code>Shift+F3</code></td>
                        <td><code>Shift+Cmd+G</code></td>
                    </tr>
                    <tr>
                        <td>Close Search</td>
                        <td><code>Esc</code></td>
                        <td><code>Esc</code></td>
                    </tr>
                    <tr>
                        <td>Exit Fullscreen</td>
                        <td><code>Esc</code></td>
                        <td><code>Esc</code></td>
                    </tr>
                </table>
            </div>
            
            <h2>⚠️ Troubleshooting</h2>
            
            <div class="feature">
                <h3>Connection Issues</h3>
                <p><b>Problem:</b> Can't connect to server</p>
                <p><b>Solutions:</b></p>
                <ul>
                    <li>Check SSH config file exists (~/.ssh/config)</li>
                    <li>Verify jump host and internal host are correct</li>
                    <li>Test SSH connection manually in terminal</li>
                    <li>See <b>Help > SSH Configuration Guide</b></li>
                </ul>
            </div>
            
            <div class="feature">
                <h3>Metrics Not Available</h3>
                <p><b>Possible causes:</b></p>
                <ul>
                    <li><b>Pod too new:</b> Wait 60 seconds and click retry 🔄</li>
                    <li><b>Metrics server not installed:</b> Contact cluster admin</li>
                    <li><b>Pod not running:</b> Check pod status</li>
                </ul>
            </div>
            
            <div class="feature">
                <h3>Logs Slow/Lagging</h3>
                <p><b>Solutions:</b></p>
                <ul>
                    <li>Disable search while streaming (close search bar)</li>
                    <li>Set log buffer limit (Settings > Advanced)</li>
                    <li>Save logs and restart stream</li>
                </ul>
            </div>
            
            <div class="feature">
                <h3>Memory Warnings</h3>
                <p><b>Cause:</b> Stream running for 30+ minutes with 10k+ lines</p>
                <p><b>Options:</b></p>
                <ul>
                    <li>Save logs and continue (recommended)</li>
                    <li>Set buffer limit for auto-cleanup</li>
                    <li>Disable warnings (Settings > Advanced)</li>
                </ul>
            </div>
            
            <h2>🔄 Updates</h2>
            <div class="feature">
                <h3>Automatic Update Checks</h3>
                <p><b>When:</b> Every time app opens</p>
                <p><b>Notification:</b> Yellow banner if update available</p>
                <p><b>Manual check:</b> Settings > Check for Updates</p>
                <p><b>Installation:</b></p>
                <ul>
                    <li><b>Windows:</b> Auto-downloads and launches installer</li>
                    <li><b>macOS:</b> Manual install instructions provided</li>
                    <li><b>Linux:</b> Manual install instructions provided</li>
                </ul>
                <div class="warning">
                    <b>⚠️ Your data is safe:</b> Updates never delete your configuration or settings!
                </div>
            </div>
            
            <h2>📚 Additional Resources</h2>
            <ul>
                <li><b>GitHub:</b> <a href="https://github.com/harshmeet-1029/Arog-Log-veiwer">github.com/harshmeet-1029/Arog-Log-veiwer</a></li>
                <li><b>Keyboard Shortcuts:</b> Help > Keyboard Shortcuts</li>
                <li><b>SSH Setup:</b> Help > SSH Configuration Guide</li>
            </ul>
            
            <h2>💡 Tips & Best Practices</h2>
            <div class="feature">
                <ol>
                    <li><b>Search Efficiently:</b> Close search when not needed for better performance</li>
                    <li><b>Save Regularly:</b> Save important logs before switching pods</li>
                    <li><b>Use Fullscreen:</b> Perfect for demos and debugging sessions</li>
                    <li><b>Monitor Resources:</b> Watch CPU/Memory to spot issues early</li>
                    <li><b>Update Regularly:</b> New features and fixes arrive frequently</li>
                </ol>
            </div>
            
            <div style="margin-top: 40px; padding: 20px; border: 2px solid #27ae60; border-radius: 5px;">
                <h3>🎉 You're all set!</h3>
                <p>If you have questions or need help, check the other Help menu options or visit the GitHub repository.</p>
                <p><b>Happy log viewing!</b> 🚀</p>
            </div>
        </body>
        </html>
        """)
        
        layout.addWidget(guide)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    # -------------------------
    # Window Close Event
    # -------------------------
    
    def closeEvent(self, event):
        """Handle window close event - cleanup connections."""
        logger.info("Window close event triggered")
        
        # Exit fullscreen if active
        if self.is_fullscreen:
            self.exit_fullscreen()
        
        # Stop any running metrics worker
        if hasattr(self, 'metrics_worker') and self.metrics_worker and self.metrics_worker.isRunning():
            logger.info("Stopping metrics worker thread")
            self.metrics_worker.stop()
            self.metrics_worker.wait(2000)
        
        # Stop any running worker
        if self.worker and self.worker.isRunning():
            logger.info("Stopping active worker thread")
            self.worker.stop()
            self.worker.wait(2000)
        
        # Disconnect metrics SSH
        if self.ssh_manager_metrics and self.ssh_manager_metrics.is_connected():
            logger.info("Disconnecting metrics SSH connection")
            try:
                self.ssh_manager_metrics.disconnect()
            except Exception as e:
                logger.error(f"Error during metrics SSH cleanup: {e}")
        
        # Disconnect main SSH
        if self.ssh_manager and self.ssh_manager.is_connected():
            logger.info("Disconnecting main SSH connection")
            try:
                self.ssh_manager.disconnect()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        logger.info("Window closed, application exiting")
        event.accept()
