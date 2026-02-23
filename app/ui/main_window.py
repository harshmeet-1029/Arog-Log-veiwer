"""
Production-grade main window for Argo Log Viewer.
Features: Connection management, console output, pod search, log streaming.
"""
from typing import Optional
from collections import deque
from functools import lru_cache
import tempfile
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListWidget, QTextEdit, QLineEdit, QLabel, 
    QMessageBox, QSplitter, QGroupBox, QComboBox,
    QMenuBar, QDialog, QDialogButtonBox, QFileDialog, QSizePolicy,
    QMenu, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QFont, QTextCursor, QPalette, QColor, QAction, 
    QTextDocument, QShortcut, QKeySequence, QIcon,
    QTextCharFormat, QTextBlockFormat
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
        
        # CRITICAL: Cleanup orphaned temp files from previous crashes
        self._cleanup_orphaned_temp_files()
        
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
        self._is_streaming_logs = False  # Track if actively streaming logs (CRASH PROTECTION)
        
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
        
        # PERFORMANCE: Hybrid disk+memory strategy for 2GB RAM with unlimited logs
        self.log_lines = deque(maxlen=50000)  # Keep last 50k lines in memory (UI display)
        self._log_append_batch = []  # Batch log lines before UI update
        self._batch_timer = None  # Timer for batch processing
        self._search_cache_text = ""  # Cache for search optimization
        
        # DISK BUFFERING: Optional disk streaming (only for unlimited mode)
        self._disk_buffering_enabled = False  # Only enable for unlimited logs
        self._disk_log_file = None  # Temp file handle for streaming logs
        self._disk_log_path = None  # Path to temp log file
        self._disk_log_lines_count = 0  # Total lines written to disk
        self._ui_lines_count = 0  # Lines currently in UI
        self._disk_buffer_ram_cache = []  # RAM buffer before disk write (reduces SSD wear)
        self._disk_buffer_cache_size = 100  # Write to disk every 100 lines (reduces writes)
        self._max_disk_file_size = 1024 * 1024 * 500  # 500MB max per log file (prevents huge files)
        
        # SMART SCROLL: On-demand loading for perfect UX
        self._ui_start_line = 0  # First line number shown in UI (0-based)
        self._ui_end_line = 0  # Last line number shown in UI
        self._load_more_chunk_size = 10000  # Load 10k lines at a time
        self._max_ui_lines = 200000  # Max lines in UI (200k for better UX on 2GB+ RAM systems)
        
        # Auto-reconnect settings
        self.auto_reconnect_enabled = AppConfig.get_auto_reconnect()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.reconnect_timer = None
        
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
        """
        Find all occurrences of search text with caching optimization.
        Uses document text hash to avoid re-scanning unchanged content.
        """
        if not search_text:
            return []
        
        try:
            # PERFORMANCE: Check cache first
            current_text = self.log_output.toPlainText()
            cache_key = f"{search_text}:{len(current_text)}"
            
            if cache_key == self._search_cache_text and hasattr(self, '_cached_occurrences'):
                logger.debug("Using cached search results")
                return self._cached_occurrences
            
            occurrences = []
            document = self.log_output.document()
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            
            # PERFORMANCE: Limit search iterations to prevent hang
            max_iterations = 50000  # Safety limit
            iterations = 0
            
            while iterations < max_iterations:
                cursor = document.find(search_text, cursor, QTextDocument.FindFlag(0))
                if cursor.isNull():
                    break
                start_pos = cursor.position() - len(search_text)
                occurrences.append(start_pos)
                iterations += 1
            
            if iterations >= max_iterations:
                logger.warning(f"Search hit iteration limit at {max_iterations} matches")
            
            # Cache results
            self._search_cache_text = cache_key
            self._cached_occurrences = occurrences
            
            return occurrences
            
        except Exception as e:
            logger.error(f"Error finding occurrences: {e}", exc_info=True)
            return []
    
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
        logger.debug(f"handle_escape called - search_visible={self.log_search_bar.isVisible()}, is_fullscreen={self.is_fullscreen}")
        
        if hasattr(self, 'log_search_bar') and self.log_search_bar.isVisible():
            # If search bar is open, close it
            self.hide_search_bar()
            logger.debug("Escape pressed: closed search bar")
        elif self.is_fullscreen:
            # If in fullscreen and search is not open, exit fullscreen
            logger.debug("Escape pressed: attempting to exit fullscreen")
            self.exit_fullscreen()
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
        
        # Auto-reconnect option
        self.auto_reconnect_action = QAction("Enable Auto-Reconnect", self)
        self.auto_reconnect_action.setCheckable(True)
        self.auto_reconnect_action.setChecked(self.auto_reconnect_enabled)
        self.auto_reconnect_action.setStatusTip("Automatically reconnect on connection loss")
        self.auto_reconnect_action.triggered.connect(self._toggle_auto_reconnect)
        settings_menu.addAction(self.auto_reconnect_action)
        
        settings_menu.addSeparator()
        
        check_updates_action = QAction("Check for Updates", self)
        check_updates_action.setStatusTip("Check for application updates")
        check_updates_action.triggered.connect(self._check_for_updates_manual)
        settings_menu.addAction(check_updates_action)
        
        install_info_action = QAction("Show Installation Info", self)
        install_info_action.setStatusTip("View installation type and metadata")
        install_info_action.triggered.connect(self._show_installation_info)
        settings_menu.addAction(install_info_action)
        
        settings_menu.addSeparator()
        
        reset_settings_action = QAction("⚠️ Reset to Defaults...", self)
        reset_settings_action.setStatusTip("Reset all settings to default values")
        reset_settings_action.triggered.connect(self._reset_settings_to_defaults)
        settings_menu.addAction(reset_settings_action)
        
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
        self.retry_metrics_btn.setToolTip("Start/Refresh Metrics")
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
        # Stop metrics button (visible only while metrics are fetching)
        self.stop_metrics_btn = QPushButton("⏹")
        self.stop_metrics_btn.setToolTip("Stop metrics")
        self.stop_metrics_btn.setFixedSize(32, 28)
        self.stop_metrics_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 0px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.stop_metrics_btn.setVisible(False)
        self.stop_metrics_btn.clicked.connect(self._stop_metrics_clicked)
        header_layout.addWidget(self.stop_metrics_btn)
        
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
        self.log_search_input.setMinimumWidth(300)  # Made significantly wider
        search_bar_layout.addWidget(self.log_search_input)
        
        # Match counter label
        self.match_counter_label = QLabel("")
        self.match_counter_label.setStyleSheet("color: gray; font-size: 9pt;")
        search_bar_layout.addWidget(self.match_counter_label)
        
        self.find_prev_btn = QPushButton("↑ Prev")
        self.find_prev_btn.clicked.connect(self.find_previous)
        self.find_prev_btn.setToolTip("Find previous (Shift+F3)")
        self.find_prev_btn.setFixedWidth(80) # Wider button
        self.find_prev_btn.setFixedHeight(28) # Taller button
        search_bar_layout.addWidget(self.find_prev_btn)
        
        self.find_next_btn = QPushButton("Next ↓")
        self.find_next_btn.clicked.connect(self.find_next)
        self.find_next_btn.setToolTip("Find next (F3)")
        self.find_next_btn.setFixedWidth(80) # Wider button
        self.find_next_btn.setFixedHeight(28) # Taller button
        search_bar_layout.addWidget(self.find_next_btn)
        
        self.close_search_btn = QPushButton("Close")
        self.close_search_btn.clicked.connect(self.hide_search_bar)
        self.close_search_btn.setToolTip("Close (Esc)")
        self.close_search_btn.setFixedWidth(80) # Wider button
        self.close_search_btn.setFixedHeight(28) # Taller button
        search_bar_layout.addWidget(self.close_search_btn)
        
        search_bar_layout.addStretch()
        
        # Hide search bar by default
        self.log_search_bar.setVisible(False)
        log_container_layout.addWidget(self.log_search_bar)
        
        # SMART SCROLL: Load older logs bar (for unlimited mode with disk buffering)
        self.load_older_bar = QWidget()
        self.load_older_bar.setStyleSheet("""
            QWidget {
                background-color: rgba(74, 158, 255, 0.15);
                border: 1px solid rgba(74, 158, 255, 0.3);
                border-radius: 4px;
                padding: 5px;
            }
        """)
        load_older_layout = QHBoxLayout(self.load_older_bar)
        load_older_layout.setContentsMargins(10, 5, 10, 5)
        
        self.load_older_label = QLabel("📄 Older logs available on disk")
        self.load_older_label.setStyleSheet("font-weight: bold; color: #4a9eff;")
        load_older_layout.addWidget(self.load_older_label)
        
        load_older_layout.addStretch()
        
        self.load_older_btn = QPushButton("⬆ Load 10,000 Older Lines")
        self.load_older_btn.setToolTip("Load older logs from disk buffer")
        self.load_older_btn.clicked.connect(self._load_older_logs)
        self.load_older_btn.setMinimumHeight(28)
        load_older_layout.addWidget(self.load_older_btn)
        
        self.load_all_btn = QPushButton("⬆⬆ Load All")
        self.load_all_btn.setToolTip("Load all logs from disk (may be slow for huge logs)")
        self.load_all_btn.clicked.connect(self._load_all_logs)
        self.load_all_btn.setMinimumHeight(28)
        load_older_layout.addWidget(self.load_all_btn)
        
        # Hidden by default
        self.load_older_bar.setVisible(False)
        log_container_layout.addWidget(self.load_older_bar)
        
        # Log output text area
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QTextEdit.NoWrap)
        self.log_output.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_output.customContextMenuRequested.connect(self._show_log_context_menu)
        
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
        self.stop_metrics_btn.setVisible(False)
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
        
        # Stop any running metrics monitoring (and hide UI)
        self.stop_metrics_monitoring(hide_ui=True)
        
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
            
        # FORCE STOP EVERYTHING - CRITICAL FOR STABILITY
        # 1. Stop metrics monitoring (and wait, hide UI)
        self.stop_metrics_monitoring(hide_ui=True)
        
        # 2. Stop log stream (and wait) - this now also disconnects signals
        self.stop_log_stream()
        
        # 3. Stop any existing worker thread manually to prevent "QThread Destroyed" crash
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            logger.info("Force stopping existing worker thread")
            
            # CRITICAL: Disconnect all signals first to prevent late callbacks
            try:
                self.worker.output.disconnect()
                self.worker.pods.disconnect()
                self.worker.error.disconnect()
                logger.debug("Disconnected all worker signals before stopping")
            except Exception as e:
                logger.debug(f"Could not disconnect worker signals: {e}")
            
            self.worker.stop()
            if not self.worker.wait(3000):  # Wait up to 3 seconds
                logger.warning("Worker thread did not stop gracefully, forcing termination")
                self.worker.terminate() # Last resort
                self.worker.wait()
        
        self.pod_list.clear()
        self.console_output.append("\n=== Refreshing pod list ===\n")
        
        # Disable buttons mutually
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Refreshing...")
        self.fetch_btn.setEnabled(False)
        
        # Create worker to list all pods (similar to connect action)
        self.worker = ArgoWorker(action="list_all_pods", ssh_manager=self.ssh_manager)
        self.worker.output.connect(self._append_console)
        self.worker.pods.connect(self._on_pods_received)
        self.worker.error.connect(self._on_error)
        
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
        
        if not self.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect first before searching pods")
            return

        # FORCE STOP EVERYTHING - CRITICAL FOR STABILITY
        # 1. Stop metrics monitoring (and wait, hide UI)
        self.stop_metrics_monitoring(hide_ui=True)
        
        # 2. Stop log stream (and wait) - this now also disconnects signals
        self.stop_log_stream()
        
        # 3. Stop any existing worker thread manually to prevent "QThread Destroyed" crash
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            logger.info("Force stopping existing worker thread")
            
            # CRITICAL: Disconnect all signals first to prevent late callbacks
            try:
                self.worker.output.disconnect()
                self.worker.pods.disconnect()
                self.worker.error.disconnect()
                logger.debug("Disconnected all worker signals before stopping")
            except Exception as e:
                logger.debug(f"Could not disconnect worker signals: {e}")
            
            self.worker.stop()
            if not self.worker.wait(3000):  # Wait up to 3 seconds
                logger.warning("Worker thread did not stop gracefully, forcing termination")
                self.worker.terminate() # Last resort
                self.worker.wait()
        
        logger.info(f"Fetching pods with keyword: '{keyword}'")
        self.pod_list.clear()
        self.console_output.append(f"\n=== Fetching pods matching '{keyword}' ===\n")
        
        # Disable buttons mutually
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching...")
        self.refresh_btn.setEnabled(False)
        
        # Create and start worker
        self.worker = ArgoWorker(
            action="list_pods",
            search=keyword,
            ssh_manager=self.ssh_manager
        )
        self.worker.output.connect(self._append_console)
        self.worker.pods.connect(self._on_pods_received)
        self.worker.error.connect(self._on_error)
        
        logger.info("Starting list_pods worker")
        self.worker.start()
    
    def open_logs(self, item):
        """
        Open live logs for the selected pod with disk buffering.
        
        MEMORY OPTIMIZATION: Streams ALL logs to disk, shows recent 50k in UI.
        This allows unlimited logs on 2GB RAM!
        """
        pod_name = item.text()
        logger.info(f"Opening logs for pod: '{pod_name}'")
        
        # Stop any existing log stream and metrics
        self.stop_log_stream()
        self.stop_metrics_monitoring()
        
        # Initialize disk buffer for unlimited log storage
        self._init_disk_buffer(pod_name)
        
        # Reset UI tracking for smart scrolling
        self._ui_start_line = 0
        self._ui_end_line = 0
        self._ui_lines_count = 0
        self.load_older_bar.setVisible(False)  # Hide load older bar initially
        
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
        
        # Show metrics label and retry button, but DO NOT auto-start
        # User must click refresh to start metrics (CRASH PROOFING)
        self.metrics_label.setVisible(True)
        self.metrics_label.setText("│ 📊 Click Refresh to load metrics")
        self.retry_metrics_btn.setVisible(True)
        
        logger.info("Starting logs worker")
        self.worker.start()
        
        # Track stream start time for memory warnings
        import time
        self._stream_start_time = time.time()
        
        # Mark that we're actively streaming (CRASH PROTECTION flag)
        self._is_streaming_logs = True
        
        # Auto-start metrics monitoring REMOVED for stability
        # User initiates it manually via refresh button
    
    def stop_log_stream(self):
        """
        Stop the current log stream but keep logs visible.
        
        NOTE: Closes disk buffer but keeps file for potential save operation.
        CRITICAL: Properly disconnects signals and cleans up timers to prevent crashes.
        """
        # CRITICAL: Clear streaming flag IMMEDIATELY to stop any pending operations
        self._is_streaming_logs = False
        
        # CRITICAL: Stop and clear batch timer FIRST to prevent queued updates
        if self._batch_timer and self._batch_timer.isActive():
            logger.debug("Stopping batch timer")
            self._batch_timer.stop()
        
        # CRITICAL: Clear any pending batches to prevent late UI updates
        if self._log_append_batch:
            logger.debug(f"Clearing {len(self._log_append_batch)} pending log batches")
            self._log_append_batch.clear()
        
        # CRITICAL: Disconnect worker signals BEFORE stopping to prevent race conditions
        if self.worker and self.worker.isRunning():
            logger.info("Stopping log stream and disconnecting signals")
            self.console_output.append("\n[INFO] Stopping log stream...\n")
            
            try:
                # Disconnect all signals to prevent any further updates
                self.worker.output.disconnect()
                logger.debug("Disconnected worker.output signal")
            except Exception as e:
                logger.debug(f"Could not disconnect worker.output: {e}")
            
            try:
                self.worker.error.disconnect()
                logger.debug("Disconnected worker.error signal")
            except Exception as e:
                logger.debug(f"Could not disconnect worker.error: {e}")
            
            # Now stop the worker
            self.worker.stop()
            if not self.worker.wait(2000):  # Wait up to 2 seconds
                logger.warning("Log stream worker did not stop gracefully, forcing termination")
                self.worker.terminate()
                self.worker.wait()
            
        # Stop metrics monitoring (and hide UI)
        self.stop_metrics_monitoring(hide_ui=True)
        
        # Close disk buffer (keeps file for potential save)
        self._close_disk_buffer()
        
        # Disable stop button (no longer streaming)
        self.stop_logs_btn.setEnabled(False)
        self.current_pod_for_metrics = None
        
        # Hide metrics and retry/stop buttons
        self.metrics_label.setVisible(False)
        self.metrics_label.clear()
        self.retry_metrics_btn.setVisible(False)
        self.stop_metrics_btn.setVisible(False)
        
        # Reset stream tracking (flag already cleared at start)
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
            
        # Check if refresh or search is in progress
        if not self.refresh_btn.isEnabled() or not self.fetch_btn.isEnabled():
            logger.info("Skipping metrics start because refresh/search is in progress")
            return
        
        # Check if we have a metrics SSH connection
        if not self.ssh_manager_metrics or not self.ssh_manager_metrics.is_connected():
            reason = "Not initialized" if not self.ssh_manager_metrics else "Disconnected"
            logger.warning(f"Metrics SSH connection not available ({reason})")
            self.console_output.append(f"[WARNING] Metrics connection unavailable ({reason}). Attempting to reconnect...\n")
            
            self.metrics_label.setText("│ 🔄 Reconnecting metrics...")
            self.metrics_label.setToolTip("Re-establishing metrics connection...")
            self.metrics_label.setVisible(True)
            self.retry_metrics_btn.setVisible(False)
            self.stop_metrics_btn.setVisible(False)
            
            # Attempt to reconnect metrics SSH
            self._connect_metrics_ssh()
            return
        
        try:
            logger.info(f"Starting metrics monitoring for pod: {self.current_pod_for_metrics}")
            
            # Stop any active metrics monitoring (and hide UI to prevent flicker)
            self.stop_metrics_monitoring(hide_ui=True)
            
            # Show fetching state
            self.metrics_label.setVisible(True)
            self.retry_metrics_btn.setVisible(True)
            self.metrics_label.setText("│ 📊 Fetching...")
            
            # Create and start worker for metrics (using SEPARATE SSH connection)
            self.metrics_worker = ArgoWorker(
                action="metrics",
                pod=self.current_pod_for_metrics,
                ssh_manager=self.ssh_manager_metrics  # Use separate connection!
            )
            self.metrics_worker.metrics.connect(self._update_metrics_display)
            self.metrics_worker.error.connect(self._on_metrics_error)
            self.metrics_worker.finished.connect(self._on_metrics_worker_finished)
            
            self.is_monitoring_metrics = True
            self.stop_metrics_btn.setVisible(True)
            
            logger.info("Starting metrics worker (on separate SSH connection)")
            self.metrics_worker.start()
            
        except Exception as e:
            logger.error(f"Failed to start metrics monitoring (logs unaffected): {e}", exc_info=True)
            self.metrics_label.setText("│ ⚠️ Metrics unavailable")
            self.is_monitoring_metrics = False
            self.stop_metrics_btn.setVisible(False)
    
    def stop_metrics_monitoring(self, hide_ui=False):
        """
        Stop the current metrics monitoring.
        
        Args:
            hide_ui: If True, hide the metrics UI elements completely.
        """
        if hasattr(self, 'metrics_worker') and self.metrics_worker and self.metrics_worker.isRunning():
            logger.info("Stopping metrics monitoring")
            
            # CRITICAL: Disconnect all signals first to prevent late callbacks
            try:
                self.metrics_worker.metrics.disconnect()
                self.metrics_worker.error.disconnect()
                self.metrics_worker.finished.disconnect(self._on_metrics_worker_finished)
                logger.debug("Disconnected metrics worker signals")
            except Exception as e:
                logger.debug(f"Could not disconnect metrics worker signals: {e}")
            
            self.metrics_worker.stop()
            if not self.metrics_worker.wait(2000):  # Wait up to 2 seconds
                logger.warning("Metrics worker did not stop gracefully, forcing termination")
                self.metrics_worker.terminate()
                self.metrics_worker.wait()
            self.is_monitoring_metrics = False
            
        # Reset UI
        try:
            if hide_ui:
                self.metrics_label.setVisible(False)
                self.retry_metrics_btn.setVisible(False)
                self.stop_metrics_btn.setVisible(False)
                self.metrics_label.clear()
                # Clear fullscreen metrics if exists
                if hasattr(self, 'fullscreen_metrics_label'):
                    self.fullscreen_metrics_label.clear()
            else:
                self.metrics_label.setText("│ 📊 Click Refresh to load metrics")
                self.retry_metrics_btn.setVisible(True)
                self.stop_metrics_btn.setVisible(False)
        except:
            pass
    
    def _on_metrics_worker_finished(self):
        """Sync UI when metrics worker thread exits (stop button, state). Ignores stale worker."""
        if self.sender() is not getattr(self, "metrics_worker", None):
            return
        self.is_monitoring_metrics = False
        self.stop_metrics_btn.setVisible(False)
    
    def _stop_metrics_clicked(self):
        """Stop fetching metrics; last value stays visible until next refresh."""
        logger.info("User requested to stop metrics")
        self.stop_metrics_monitoring(hide_ui=False)
    
    def retry_metrics(self):
        """Manually start or retry fetching metrics for the current pod."""
        if not self.current_pod_for_metrics:
            logger.warning("No pod selected for metrics retry")
            QMessageBox.warning(self, "No Pod Selected", "Please select a pod first to view metrics.")
            return
        
        logger.info(f"Manual metrics start/retry requested for pod: {self.current_pod_for_metrics}")
        
        # Stop existing metrics monitoring and restart
        self.stop_metrics_monitoring()
        
        self.metrics_label.setText("│ 🔄 Starting metrics...")
        
        # Restart metrics monitoring
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, self.start_metrics_monitoring)  # Quick retry
    
    def _update_metrics_display(self, metrics_text: str):
        """
        Update the metrics display with crash protection and optimized throttling.
        
        PERFORMANCE: Throttle UI updates to max once per 2 seconds to prevent freezing.
        """
        try:
            # Ignore late/stray callbacks after user stopped metrics (avoids work and races)
            if not self.is_monitoring_metrics:
                return
            import time
            
            # Throttle metrics UI updates to max once per 2 seconds
            current_time = time.time()
            if current_time - self._last_metrics_update < 2.0:
                return  # Skip this update, too soon
            
            self._last_metrics_update = current_time
            
            # Parse metrics - extract CPU and Memory
            lines = metrics_text.strip().split('\n')
            cpu_usage = "N/A"
            memory_usage = "N/A"
            found_match = False
            
            for line in lines[:50]:  # PERFORMANCE: Limit parsing to first 50 lines
                line = line.strip()
                
                if not line or "kubectl" in line.lower() or line.startswith(("$", "#")):
                    continue
                
                parts = line.split()
                if len(parts) >= 3 and parts[0] != "NAME" and "NAME" not in line:
                    pod_name_part = parts[0]
                    
                    # Verify we have a current pod selected before checking string inclusion
                    if not self.current_pod_for_metrics:
                        continue
                        
                    if "-" in pod_name_part and self.current_pod_for_metrics in pod_name_part:
                        cpu_usage = parts[1] if len(parts) > 1 else "N/A"
                        memory_usage = parts[2] if len(parts) > 2 else "N/A"
                        logger.debug(f"Parsed metrics - CPU: {cpu_usage}, Memory: {memory_usage}")
                        found_match = True
                        break
            
            # Only update UI if we found metrics for the CURRENT pod
            if not found_match:
                # If we didn't find a match, it might be old data for a previous pod. Ignore it.
                return

            # Ultra-compact display format
            metrics_text = f"│ 📊 CPU: {cpu_usage} • Memory: {memory_usage}"
            self.metrics_label.setText(metrics_text)
            
            # Update fullscreen metrics if active
            if self.is_fullscreen and hasattr(self, 'fullscreen_metrics_label'):
                self.fullscreen_metrics_label.setText(metrics_text)
                
        except Exception as e:
            logger.error(f"Error updating metrics display: {e}", exc_info=True)
            try:
                self.metrics_label.setText("│ ⚠️ Metrics error")
            except:
                pass  # Fail silently
    
    def _on_metrics_error(self, error_msg: str):
        """
        Handle metrics worker error with crash protection.
        
        NOTE: Metrics errors do NOT affect log streaming.
        """
        try:
            # Ignore late/stray callbacks after user stopped metrics
            if not self.is_monitoring_metrics:
                return
            logger.warning(f"Metrics worker error (logs unaffected): {error_msg}")
            
            # User-friendly error message
            if "Metrics API not available" in error_msg or "Metrics server not available" in error_msg:
                self.metrics_label.setText("│ ⚠️ Metrics server not installed")
                self.metrics_label.setToolTip("Install metrics-server in cluster for resource monitoring. Logs are working normally.")
            else:
                self.metrics_label.setText("│ ⚠️ Metrics unavailable")
                self.metrics_label.setToolTip(f"Error: {error_msg}. Logs are working normally.")
            
            self.is_monitoring_metrics = False
            self.stop_metrics_btn.setVisible(False)
            
        except Exception as e:
            logger.error(f"Error in _on_metrics_error: {e}", exc_info=True)
    
    def find_in_logs(self):
        """
        Find text in the log output (case-insensitive).
        
        SMART SEARCH: If disk buffer exists with older logs, offers to search ALL logs!
        """
        search_text = self.log_search_input.text().strip()
        if not search_text:
            logger.warning("No search text provided for log search")
            QMessageBox.warning(self._get_active_window(), "Input Required", "Please enter text to search")
            return
        
        logger.info(f"Searching logs for: '{search_text}' (case-insensitive)")
        
        # Check if we have older logs on disk not shown in UI
        has_older_logs = (self._disk_buffering_enabled and 
                         self._disk_log_path and 
                         self._disk_log_path.exists() and 
                         self._ui_start_line > 0)
        
        if has_older_logs:
            # Offer to search ALL logs (including disk)
            reply = QMessageBox.question(
                self._get_active_window(),
                "Search Scope",
                f"You have {self._ui_start_line:,} older lines on disk not currently displayed.\n\n"
                f"Search in:\n"
                f"• UI Only ({self._ui_lines_count:,} visible lines) - Fast\n"
                f"• ALL Logs ({self._disk_log_lines_count:,} total lines) - May take a few seconds\n\n"
                f"Search all logs?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Search ALL logs (UI + disk)
                self._search_all_logs(search_text)
                return
        
        # Search UI only (fast path)
        self._search_ui_logs(search_text)
    
    def _search_ui_logs(self, search_text: str):
        """Search only currently visible logs in UI (fast)."""
        # Store the search term
        self.current_search_term = search_text
        
        # Find all occurrences in UI
        self.search_occurrences = self._find_all_occurrences(search_text)
        
        if self.search_occurrences:
            # Jump to first occurrence
            self._jump_to_occurrence(0)
            logger.info(f"Found {len(self.search_occurrences)} occurrence(s) in UI")
        else:
            logger.info(f"'{search_text}' not found in visible logs")
            self.current_occurrence_index = -1
            self._update_match_counter()
            
            # Smart tip: Only suggest loading older logs if the button is actually visible
            tip_msg = ""
            if self.load_older_bar.isVisible():
                tip_msg = "\n\nTip: Use 'Load Older Logs' to search older logs."
            
            QMessageBox.information(
                self._get_active_window(), 
                "Not Found in Visible Logs", 
                f"Text '{search_text}' not found in currently visible logs.{tip_msg}"
            )
    
    def _search_all_logs(self, search_text: str):
        """
        Search ALL logs including disk buffer (slower but complete).
        
        Shows progress bar and loads matching sections into UI.
        """
        try:
            if not self._disk_log_path or not self._disk_log_path.exists():
                self._search_ui_logs(search_text)
                return
            
            logger.info(f"Searching ALL logs ({self._disk_log_lines_count:,} lines) for: '{search_text}'")
            
            # Show progress dialog
            from PySide6.QtWidgets import QProgressDialog
            progress = QProgressDialog(
                f"Searching all logs for '{search_text}'...", 
                "Cancel", 
                0, 
                self._disk_log_lines_count, 
                self._get_active_window()
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(500)
            
            # Search disk file line by line
            first_match_line = -1
            total_matches = 0
            search_lower = search_text.lower()
            
            with open(self._disk_log_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f):
                    if progress.wasCanceled():
                        logger.info("Search cancelled by user")
                        progress.close()
                        return
                    
                    # Case-insensitive search
                    if search_lower in line.lower():
                        total_matches += 1
                        if first_match_line < 0:
                            first_match_line = line_num
                    
                    # Update progress every 1000 lines
                    if line_num % 1000 == 0:
                        progress.setValue(line_num)
            
            progress.close()
            
            if total_matches > 0:
                # Found matches! Load the section with first match
                logger.info(f"Found {total_matches} matches, first at line {first_match_line + 1}")
                
                # Determine range to load (centered around first match)
                load_start = max(0, first_match_line - 5000)  # 5k lines before
                load_end = min(self._disk_log_lines_count, first_match_line + 45000)  # 45k lines after (total 50k)
                
                # Load this range into UI
                logger.info(f"Loading lines {load_start + 1:,} to {load_end:,} to show match")
                
                # Read the range from disk
                text_to_load = self._read_log_lines_from_disk(load_start, load_end)
                
                # Replace UI content with this range
                self.log_output.clear()
                self.log_output.setPlainText(text_to_load)
                
                # Update tracking
                self._ui_start_line = load_start
                self._ui_end_line = load_end
                self._ui_lines_count = self.log_output.document().blockCount()
                
                # Update load older bar
                self._update_load_older_bar()
                
                # Now search in the loaded content
                self.current_search_term = search_text
                self.search_occurrences = self._find_all_occurrences(search_text)
                
                if self.search_occurrences:
                    self._jump_to_occurrence(0)
                    
                    # Show success message
                    QMessageBox.information(
                        self._get_active_window(),
                        "Search Complete",
                        f"Found {total_matches:,} total matches in all logs.\n\n"
                        f"Loaded lines {load_start + 1:,} to {load_end:,} showing first match.\n"
                        f"Use Next/Previous to navigate."
                    )
                
            else:
                # No matches found anywhere
                logger.info(f"'{search_text}' not found in any logs")
                QMessageBox.information(
                    self._get_active_window(),
                    "Not Found",
                    f"Text '{search_text}' not found in any of the {self._disk_log_lines_count:,} log lines."
                )
                
        except Exception as e:
            logger.error(f"Error searching all logs: {e}", exc_info=True)
            QMessageBox.critical(
                self._get_active_window(),
                "Search Error",
                f"Error searching logs: {str(e)}"
            )
    
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
        """
        Save ALL logs to file (from disk buffer if available).
        
        2GB RAM OPTIMIZATION: If disk buffer exists, saves complete logs (unlimited!),
        otherwise saves UI content (recent 50k).
        """
        logger.info("Save logs to file requested")
        
        # Check if we have disk buffer with full logs
        has_disk_buffer = (self._disk_log_path and 
                           self._disk_log_path.exists() and 
                           self._disk_log_lines_count > 0)
        
        # Get log content source
        if has_disk_buffer:
            logger.info(f"Saving FULL logs from disk buffer ({self._disk_log_lines_count:,} lines)")
            log_source = "disk"  # Will read from disk
        else:
            logger.info("Saving logs from UI (recent lines only)")
            # FIX: Extract text block by block to avoid Qt's paragraph spacing
            # Qt's toPlainText() adds extra newlines between text blocks
            document = self.log_output.document()
            blocks = []
            block = document.begin()
            while block.isValid():
                blocks.append(block.text())
                block = block.next()
            log_content = "\n".join(blocks)
            log_source = "ui"
            
            if not log_content:
                QMessageBox.warning(self._get_active_window(), "No Logs", "There are no logs to save.")
                return
        
        # Get pod name for default filename
        pod_name = self.current_pod_label.text().replace("Viewing logs for: ", "").split("│")[0].strip()
        pod_name = pod_name.replace(":", "-")
        if not pod_name or pod_name == "No pod selected":
            pod_name = "logs"
        
        # Generate default filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{pod_name}_{timestamp}.txt"
        
        # Prepare dialog title
        title = "Save All Logs" if has_disk_buffer else "Save Logs"
        if has_disk_buffer:
            title += f" ({self._disk_log_lines_count:,} lines)"
        
        # Open file dialog
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self._get_active_window(),
            title,
            default_filename,
            "Text Files (*.txt);;HTML Files (*.html);;Log Files (*.log);;All Files (*.*)"
        )
        
        if file_path:
            try:
                # Determine format
                is_html = file_path.endswith('.html') or 'HTML' in selected_filter
                
                if log_source == "disk":
                    # Copy from disk buffer (complete logs!)
                    with open(self._disk_log_path, 'r', encoding='utf-8') as src:
                        if is_html:
                            # Read and convert to HTML
                            log_content = src.read()
                            html_content = self._generate_html_log_export(log_content, pod_name)
                            with open(file_path, 'w', encoding='utf-8') as dst:
                                dst.write(html_content)
                        else:
                            # Direct copy (most efficient!)
                            with open(file_path, 'w', encoding='utf-8') as dst:
                                # Copy in chunks for memory efficiency
                                while True:
                                    chunk = src.read(1024 * 1024)  # 1MB chunks
                                    if not chunk:
                                        break
                                    dst.write(chunk)
                    
                    logger.info(f"Saved {self._disk_log_lines_count:,} lines from disk buffer")
                else:
                    # Save from UI content
                    if is_html:
                        html_content = self._generate_html_log_export(log_content, pod_name)
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                    else:
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
    
    def _generate_html_log_export(self, log_content: str, pod_name: str) -> str:
        """Generate HTML export with log level highlighting."""
        from datetime import datetime
        import html
        import re
        
        # Check if we're in limited mode
        limit = AppConfig.get_log_buffer_limit()
        warning_html = ""
        if limit > 0:
            warning_html = f"""
            <div class="warning">
                <strong>⚠️ Limited Mode Active:</strong> Only the most recent {limit} lines were saved. 
                Older logs were discarded to save memory. 
                Switch to 'Unlimited' mode in Settings to capture full history.
            </div>
            """
        
        # HTML template with styling
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Logs: {pod_name}</title>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            background-color: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            margin: 0;
        }}
        .header {{
            background-color: #2d2d2d;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            color: #4a9eff;
            font-size: 24px;
        }}
        .header p {{
            margin: 5px 0 0 0;
            color: #888;
            font-size: 14px;
        }}
        .logs {{
            background-color: #1e1e1e;
            padding: 15px;
            border: 1px solid #3c3c3c;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
            line-height: 1.4;
        }}
        .warning {{
            background-color: #3e2723;
            border-left: 5px solid #ff5722;
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 4px;
            color: #ffcc80;
        }}
        /* Only ERROR and WARN are highlighted (not INFO/DEBUG) */
        .error {{ color: #ff6b6b; font-weight: bold; }}
        .warn {{ color: #ffa726; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 Logs: {pod_name}</h1>
        <p>Generated: {timestamp}</p>
        <p>Total Lines: {total_lines} | Errors: {errors} | Warnings: {warnings}</p>
    </div>
    {warning_html}
    <div class="logs">{highlighted_logs}</div>
</body>
</html>"""
        
        # Count statistics (using word boundaries for accuracy)
        lines = log_content.split('\n')
        total_lines = len(lines)
        errors = sum(1 for line in lines if re.search(r'\b(ERROR|FATAL|CRITICAL|EXCEPTION)\b', line.upper()))
        warnings = sum(1 for line in lines if re.search(r'\b(WARN|WARNING)\b', line.upper()))
        
        # Highlight each line (ONLY critical levels: ERROR/WARN)
        highlighted_lines = []
        for line in lines:
            escaped_line = html.escape(line)
            line_upper = line.upper()
            
            # Use word boundaries to avoid false positives
            if re.search(r'\b(ERROR|FATAL|CRITICAL|EXCEPTION)\b', line_upper):
                highlighted_lines.append(f'<span class="error">{escaped_line}</span>')
            elif re.search(r'\b(WARN|WARNING)\b', line_upper):
                highlighted_lines.append(f'<span class="warn">{escaped_line}</span>')
            else:
                # No highlighting for INFO/DEBUG (too common, creates clutter)
                highlighted_lines.append(escaped_line)
        
        highlighted_logs = '\n'.join(highlighted_lines)
        
        # Fill template
        html_output = html_template.format(
            pod_name=html.escape(pod_name),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_lines=total_lines,
            errors=errors,
            warnings=warnings,
            highlighted_logs=highlighted_logs
        )
        
        return html_output
    
    def _show_log_context_menu(self, position):
        """Show context menu for log output."""
        menu = QMenu(self)
        
        # Copy actions
        cursor = self.log_output.textCursor()
        has_selection = cursor.hasSelection()
        
        copy_action = menu.addAction("📋 Copy")
        copy_action.setEnabled(has_selection)
        copy_action.triggered.connect(lambda: self.log_output.copy())
        
        copy_line_action = menu.addAction("📄 Copy Current Line")
        copy_line_action.triggered.connect(self._copy_current_line)
        
        copy_all_action = menu.addAction("📚 Copy All Logs")
        copy_all_action.triggered.connect(self._copy_all_logs)
        
        menu.addSeparator()
        
        # Select all
        select_all_action = menu.addAction("⬜ Select All")
        select_all_action.triggered.connect(self.log_output.selectAll)
        
        menu.addSeparator()
        
        # Save option
        save_action = menu.addAction("💾 Save Logs...")
        save_action.triggered.connect(self.save_logs_to_file)
        
        # Show menu at cursor position
        menu.exec(self.log_output.mapToGlobal(position))
    
    def _copy_current_line(self):
        """Copy the line under the cursor."""
        cursor = self.log_output.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        line_text = cursor.selectedText()
        
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(line_text)
        
        logger.debug(f"Copied line to clipboard: {line_text[:50]}...")
    
    def _copy_all_logs(self):
        """Copy all logs to clipboard."""
        from PySide6.QtWidgets import QApplication
        
        # FIX: Extract text block by block to avoid Qt's paragraph spacing
        # Qt's toPlainText() adds extra newlines between text blocks
        document = self.log_output.document()
        blocks = []
        block = document.begin()
        while block.isValid():
            blocks.append(block.text())
            block = block.next()
        log_content = "\n".join(blocks)
        
        clipboard = QApplication.clipboard()
        clipboard.setText(log_content)
        
        logger.info("Copied all logs to clipboard")
    
    def _toggle_auto_reconnect(self, checked: bool):
        """Toggle auto-reconnect feature."""
        self.auto_reconnect_enabled = checked
        AppConfig.set_auto_reconnect(checked)
        self.reconnect_attempts = 0  # Reset counter
        logger.info(f"Auto-reconnect {'enabled' if checked else 'disabled'}")
        
        QMessageBox.information(
            self,
            "Auto-Reconnect",
            f"Auto-reconnect {'enabled' if checked else 'disabled'}!\n\n"
            f"{'The app will automatically try to reconnect if the SSH connection is lost.' if checked else 'You will need to manually reconnect if the connection is lost.'}"
        )
    
    def _reset_settings_to_defaults(self):
        """Reset all settings to default values with confirmation."""
        logger.info("Reset to defaults requested")
        
        # Confirmation dialog
        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setWindowTitle("Reset to Defaults")
        confirm.setText("Are you sure you want to reset all settings to defaults?")
        confirm.setInformativeText(
            "This will reset:\n"
            "• Theme (Dark Mode)\n"
            "• Auto-Reconnect (ON)\n"
            "• Log Buffer Limit (Unlimited)\n"
            "• Memory Warnings (ON)\n"
            "• Custom SSH Folder (Default)\n\n"
            "Your SSH connection settings will NOT be affected.\n"
            "A restart will be required for changes to take effect."
        )
        confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        
        result = confirm.exec()
        
        if result == QMessageBox.StandardButton.Yes:
            try:
                logger.info("Resetting all settings to defaults")
                
                # Reset all settings to defaults
                # AppConfig.set_theme("dark") # Theme is not stored in AppConfig yet
                AppConfig.set_auto_reconnect(True)
                AppConfig.set_log_buffer_limit(0)  # Unlimited
                AppConfig.set_show_memory_warnings(True)
                # Note: SSH folder is separate, not reset
                
                logger.info("Settings reset to defaults successfully")
                
                # Success message with restart options
                restart_box = QMessageBox(self)
                restart_box.setWindowTitle("Settings Reset")
                restart_box.setText("All settings have been reset to defaults!")
                restart_box.setInformativeText("Close the app now to apply changes, or keep working and they will apply the next time you open the app.")
                restart_box.setIcon(QMessageBox.Icon.Information)
                
                restart_now_btn = restart_box.addButton("Close now", QMessageBox.ButtonRole.AcceptRole)
                restart_later_btn = restart_box.addButton("Keep working", QMessageBox.ButtonRole.RejectRole)
                restart_box.setDefaultButton(restart_now_btn)
                
                restart_box.exec()
                
                if restart_box.clickedButton() == restart_now_btn:
                    logger.info("Closing application after settings reset (user chose Close now)")
                    self.close()
                else:
                    logger.info("User chose to keep working; changes apply on next launch")
                
            except Exception as e:
                logger.error(f"Error resetting settings: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to reset settings:\n{str(e)}"
                )
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode for the log viewer."""
        if not self.is_fullscreen:
            # Enter fullscreen
            logger.info("Entering fullscreen mode")
            
            # SET FULLSCREEN FLAG FIRST (before any events can fire)
            self.is_fullscreen = True
            self.fullscreen_btn.setText("⛶ Exit Fullscreen")
            
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
            exit_fullscreen_btn.clicked.connect(self.exit_fullscreen)
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
            f11_shortcut.activated.connect(self.exit_fullscreen)
            
            # Search shortcuts in fullscreen
            find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self.fullscreen_window)
            find_shortcut.activated.connect(self.show_search_bar)
            
            find_next_shortcut = QShortcut(QKeySequence.StandardKey.FindNext, self.fullscreen_window)
            find_next_shortcut.activated.connect(self.find_next)
            
            find_prev_shortcut = QShortcut(QKeySequence.StandardKey.FindPrevious, self.fullscreen_window)
            find_prev_shortcut.activated.connect(self.find_previous)
            
            # Apply theme to fullscreen window
            theme = get_theme(self.current_theme)
            self.fullscreen_window.setStyleSheet(theme.get_stylesheet())
            
            logger.debug("Fullscreen mode entered successfully")
            
        else:
            # Exit fullscreen
            self.exit_fullscreen()
    
    def exit_fullscreen(self):
        """Exit fullscreen mode."""
        logger.debug(f"exit_fullscreen called - is_fullscreen={self.is_fullscreen}, has_window={hasattr(self, 'fullscreen_window')}")
        
        if not self.is_fullscreen:
            logger.warning("exit_fullscreen called but not in fullscreen mode")
            return
        
        if not hasattr(self, 'fullscreen_window'):
            logger.warning("exit_fullscreen called but fullscreen_window doesn't exist")
            self.is_fullscreen = False
            return
        
        try:
            logger.info("Exiting fullscreen mode")
            
            # Close search bar if open
            if hasattr(self, 'log_search_bar') and self.log_search_bar.isVisible():
                self.hide_search_bar()
            
            # Move log container back to original parent
            if hasattr(self, 'original_parent') and self.original_parent:
                logger.debug("Restoring log container to original parent")
                log_section = self.original_parent
                log_section_layout = log_section.layout()
                
                # Re-add log container to original position (after header, before buttons)
                self.log_container.setParent(log_section)
                log_section_layout.insertWidget(1, self.log_container)
            
            # Close and delete fullscreen window
            logger.debug("Closing fullscreen window")
            self.fullscreen_window.close()
            self.fullscreen_window.deleteLater()
            
            # Update state
            self.is_fullscreen = False
            self.fullscreen_btn.setText("⛶ Fullscreen")
            logger.info("Successfully exited fullscreen mode")
            
        except Exception as e:
            logger.error(f"Error exiting fullscreen: {e}")
            # Ensure state is reset even if there was an error
            self.is_fullscreen = False
            self.fullscreen_btn.setText("⛶ Fullscreen")
    
    def _connect_metrics_ssh(self):
        """Establish a separate SSH connection for metrics."""
        try:
            # Check if already connecting
            if hasattr(self, 'metrics_connection_worker') and self.metrics_connection_worker and self.metrics_connection_worker.isRunning():
                logger.info("Metrics connection already in progress")
                return

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
                    self.console_output.append(f"[WARNING] Metrics connection failed: {self.metrics_connection_worker.error_msg}\n")
                    self.metrics_label.setText("│ ⚠️ Metrics unavailable")
                elif self.metrics_connection_worker.ssh_manager:
                    self.ssh_manager_metrics = self.metrics_connection_worker.ssh_manager
                    logger.info("Metrics SSH connection established")
                    self.console_output.append("[OK] Metrics monitoring ready\n")
                    
                    # If user was waiting for metrics (reconnecting), show success
                    if "Reconnecting" in self.metrics_label.text():
                        self.metrics_label.setText("│ 📊 Click Refresh to load metrics")
                        self.retry_metrics_btn.setVisible(True)
            
            self.metrics_connection_worker.finished.connect(on_metrics_connection_complete)
            self.metrics_connection_worker.start()
            
        except Exception as e:
            logger.warning(f"Failed to setup metrics connection: {e}")

    # -------------------------
    # Signal Handlers
    # -------------------------
    
    def _on_connected(self):
        """Handle successful connection with crash protection."""
        try:
            logger.info("Connection established signal received")
            self._set_connected_state()
            self.connect_btn.setText("Connect")
            self.console_output.append("\n=== Ready for operations ===\n")
            
            # Reset reconnect counter on successful connection
            self.reconnect_attempts = 0
            
            # Create a separate SSH connection for metrics (non-blocking)
            # ENABLED: Metrics monitoring with separate SSH connection
            try:
                # Delay start slightly to allow main connection to stabilize
                QTimer.singleShot(1000, self._connect_metrics_ssh)
            except Exception as e:
                logger.warning(f"Failed to setup metrics connection: {e}")
            
            QMessageBox.information(self, "Connected", "SSH connection established successfully!")
            
        except Exception as e:
            logger.error(f"Error in _on_connected: {e}", exc_info=True)
    
    def _on_disconnected(self):
        """Handle disconnection with crash protection."""
        try:
            logger.info("Disconnection signal received")
            self._set_disconnected_state()
            self.ssh_manager = None
            self.console_output.append("\n=== Disconnected ===\n")
        except Exception as e:
            logger.error(f"Error in _on_disconnected: {e}", exc_info=True)
    
    def _on_pods_received(self, pods):
        """Handle received pod list with crash protection."""
        try:
            logger.info(f"Received {len(pods)} pods")
            self.pod_list.addItems(pods)
            self.fetch_btn.setEnabled(True)
            self.fetch_btn.setText("Search Pods")
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setText("🔄 Refresh All Pods")
            
            if not pods:
                QMessageBox.information(self, "No Results", "No pods found matching the search keyword")
        except Exception as e:
            logger.error(f"Error in _on_pods_received: {e}", exc_info=True)
    
    def _on_error(self, error_msg):
        """Handle error from worker with crash protection and optional auto-reconnect."""
        try:
            logger.error(f"Worker error: {error_msg}")
            
            # Reset refreshing state if applicable
            self.refresh_btn.setEnabled(self.is_connected)
            self.refresh_btn.setText("🔄 Refresh All Pods")
            
            # Check if this is an SSH connection error
            is_ssh_error = any(keyword in error_msg.lower() for keyword in 
                              ['connection', 'ssh', 'timeout', 'broken pipe', 'lost connection'])
            
            if "getaddrinfo failed" in error_msg:
                QMessageBox.critical(self, "Connection Error", 
                    "Failed to resolve server address (DNS Error).\n\n"
                    "Possible causes:\n"
                    "1. VPN is disconnected\n"
                    "2. Internet connection issue\n"
                    "3. Invalid hostname in config\n\n"
                    "Please check your connection and try again.")
            elif is_ssh_error and self.auto_reconnect_enabled and self.reconnect_attempts < self.max_reconnect_attempts:
                # Attempt auto-reconnect
                self.reconnect_attempts += 1
                logger.info(f"Auto-reconnect attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")
                
                # Show notification instead of error dialog
                self.console_output.append(f"\n⚠️ Connection lost. Auto-reconnecting ({self.reconnect_attempts}/{self.max_reconnect_attempts})...\n")
                
                # Schedule reconnect after 3 seconds
                if self.reconnect_timer:
                    self.reconnect_timer.stop()
                
                self.reconnect_timer = QTimer(self)
                self.reconnect_timer.setSingleShot(True)
                self.reconnect_timer.timeout.connect(self._attempt_reconnect)
                self.reconnect_timer.start(3000)  # 3 seconds delay
            else:
                # Show error dialog
                QMessageBox.critical(self, "Error", error_msg)
                
                # Reset reconnect counter
                self.reconnect_attempts = 0
            
            # Re-enable buttons
            self.connect_btn.setEnabled(not self.is_connected)
            self.connect_btn.setText("Connect")
            self.fetch_btn.setEnabled(self.is_connected)
            self.fetch_btn.setText("Fetch Pods")
            self.refresh_btn.setEnabled(self.is_connected)
            self.refresh_btn.setText("🔄 Refresh All Pods")
        except Exception as e:
            logger.error(f"Error in _on_error handler: {e}", exc_info=True)
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to SSH."""
        logger.info("Attempting to reconnect...")
        self.console_output.append("🔄 Reconnecting...\n")
        
        # Mark as disconnected first
        self.is_connected = False
        self._set_disconnected_state()
        
        # Try to reconnect with the same credentials
        # This will trigger the connect flow again
        QTimer.singleShot(500, self.handle_connect)
    
    def _append_console(self, text):
        """Append text to console output with crash protection."""
        try:
            self.console_output.moveCursor(QTextCursor.MoveOperation.End)
            self.console_output.insertPlainText(text)
            self.console_output.moveCursor(QTextCursor.MoveOperation.End)
        except Exception as e:
            logger.error(f"Error appending console: {e}", exc_info=True)
    
    # -------------------------
    # Disk Buffer Management (2GB RAM Optimization)
    # -------------------------
    
    def _cleanup_orphaned_temp_files(self):
        """
        Cleanup orphaned temp files from previous crashes.
        
        CRITICAL: Prevents 2GB temp file accumulation!
        Removes files older than 24 hours or from dead PIDs.
        """
        try:
            temp_dir = Path(tempfile.gettempdir()) / "argo_log_viewer_buffers"
            if not temp_dir.exists():
                return
            
            import time
            current_time = time.time()
            cleaned_count = 0
            cleaned_size = 0
            
            for file in temp_dir.glob("logs_*.txt"):
                try:
                    # Get file age
                    file_age = current_time - file.stat().st_mtime
                    file_size = file.stat().st_size
                    
                    # Delete if older than 24 hours
                    if file_age > 86400:  # 24 hours in seconds
                        file.unlink()
                        cleaned_count += 1
                        cleaned_size += file_size
                        logger.info(f"Deleted old temp file: {file.name} ({file_size / 1024 / 1024:.1f} MB, age: {file_age / 3600:.1f}h)")
                        continue
                    
                    # Extract PID from filename and check if process still running
                    try:
                        pid_str = file.stem.split('_')[-1]
                        pid = int(pid_str)
                        
                        # Check if PID is current process (skip it)
                        if pid == os.getpid():
                            continue
                        
                        # Try to check if process exists (works on Unix and Windows)
                        try:
                            if os.name == 'nt':  # Windows
                                import subprocess
                                result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                                       capture_output=True, text=True)
                                process_exists = str(pid) in result.stdout
                            else:  # Unix/Linux
                                os.kill(pid, 0)  # Doesn't actually kill, just checks
                                process_exists = True
                        except (ProcessLookupError, PermissionError):
                            process_exists = False
                        except:
                            process_exists = True  # Assume exists if we can't check
                        
                        # Delete if process doesn't exist (orphaned file)
                        if not process_exists:
                            file.unlink()
                            cleaned_count += 1
                            cleaned_size += file_size
                            logger.info(f"Deleted orphaned temp file from dead PID {pid}: {file.name} ({file_size / 1024 / 1024:.1f} MB)")
                            
                    except (ValueError, IndexError):
                        # Couldn't parse PID, skip file
                        pass
                        
                except Exception as e:
                    logger.warning(f"Error checking temp file {file}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"Cleanup summary: Removed {cleaned_count} orphaned temp files ({cleaned_size / 1024 / 1024:.1f} MB)")
            else:
                logger.debug("No orphaned temp files to clean")
                
        except Exception as e:
            logger.warning(f"Error during temp file cleanup: {e}")
    
    def _init_disk_buffer(self, pod_name: str):
        """
        Initialize disk buffer ONLY if unlimited logs mode is enabled.
        
        SMART BUFFERING:
        - Limited logs (1000 lines) → No disk, use QTextEdit limit (fast!)
        - Unlimited logs → Disk buffering with RAM cache (SSD-friendly!)
        """
        try:
            # Close existing buffer if any
            self._close_disk_buffer()
            
            # Check if we should use disk buffering
            log_limit = AppConfig.get_log_buffer_limit()
            
            if log_limit > 0:
                # LIMITED MODE: User wants only X lines
                logger.info(f"Limited log mode ({log_limit} lines) - disk buffering DISABLED")
                self._disk_buffering_enabled = False
                
                # Set QTextEdit to limit directly (most efficient!)
                self.log_output.document().setMaximumBlockCount(log_limit)
                
                # WARN USER: Limited mode does not save history!
                self.console_output.append(
                    f"\n⚠️ WARNING: Limited Mode Active ({log_limit} lines).\n"
                    "   • Only the most recent {log_limit} lines are kept.\n"
                    "   • Older logs are DELETED permanently to save RAM.\n"
                    "   • 'Save Logs' will only save what is currently visible.\n"
                    "   • To save EVERYTHING, switch to 'Unlimited' in Settings > Advanced.\n"
                )
                return
            
            # UNLIMITED MODE: Enable disk buffering
            self._disk_buffering_enabled = True
            self.log_output.document().setMaximumBlockCount(0)  # Remove UI limit
            
            # Check available disk space before creating file
            temp_dir = Path(tempfile.gettempdir()) / "argo_log_viewer_buffers"
            temp_dir.mkdir(exist_ok=True)
            
            # Check disk space (require at least 1GB free)
            import shutil
            disk_stats = shutil.disk_usage(temp_dir)
            free_gb = disk_stats.free / (1024 ** 3)
            
            if free_gb < 1.0:
                logger.warning(f"Low disk space ({free_gb:.1f} GB) - disk buffering DISABLED")
                self._disk_buffering_enabled = False
                QMessageBox.warning(
                    self,
                    "Low Disk Space",
                    f"Only {free_gb:.1f} GB free. Disk buffering disabled.\n"
                    "Logs limited to UI display (50k lines)."
                )
                return
            
            # Create temp file for this pod's logs
            safe_pod_name = "".join(c for c in pod_name if c.isalnum() or c in ('-', '_'))
            self._disk_log_path = temp_dir / f"logs_{safe_pod_name}_{os.getpid()}.txt"
            
            # Open file with large buffer (8KB) to reduce write frequency (SSD-friendly!)
            self._disk_log_file = open(self._disk_log_path, 'w', encoding='utf-8', buffering=8192)
            self._disk_log_lines_count = 0
            self._ui_lines_count = 0
            self._disk_buffer_ram_cache = []  # Reset RAM cache
            
            logger.info(f"✓ Disk buffer initialized: {self._disk_log_path}")
            logger.info(f"✓ Mode: Unlimited logs to disk ({free_gb:.1f} GB available)")
            logger.info(f"✓ SSD protection: RAM cache buffering (write every {self._disk_buffer_cache_size} lines)")
            
        except Exception as e:
            logger.error(f"Error initializing disk buffer: {e}", exc_info=True)
            self._disk_buffering_enabled = False
            self._disk_log_file = None
    
    def _close_disk_buffer(self):
        """
        Close disk buffer and flush remaining RAM cache.
        
        IMPORTANT: Ensures all buffered lines are written before closing!
        """
        try:
            if self._disk_log_file:
                # CRITICAL: Flush remaining RAM cache to disk before closing!
                if self._disk_buffer_ram_cache:
                    try:
                        cached_text = "".join(self._disk_buffer_ram_cache)
                        self._disk_log_file.write(cached_text)
                        self._disk_log_file.flush()
                        self._disk_buffer_ram_cache.clear()
                        logger.debug(f"Flushed final {len(self._disk_buffer_ram_cache)} cached writes to disk")
                    except Exception as e:
                        logger.error(f"Error flushing final cache: {e}")
                
                self._disk_log_file.close()
                
                if self._disk_log_path and self._disk_log_path.exists():
                    file_size_mb = self._disk_log_path.stat().st_size / 1024 / 1024
                    logger.info(f"✓ Closed disk buffer: {self._disk_log_lines_count:,} lines ({file_size_mb:.1f} MB)")
                
            # Keep the file for potential "Save All" and "Load Older" features
            # Will be cleaned up on app exit or next startup
            
            self._disk_log_file = None
            self._disk_buffering_enabled = False
            
        except Exception as e:
            logger.error(f"Error closing disk buffer: {e}", exc_info=True)
    
    def _update_load_older_bar(self):
        """
        Update the load older logs bar visibility and text.
        
        Shows bar if there are older logs not currently displayed in UI.
        """
        try:
            if not self._disk_buffering_enabled or not self._disk_log_path or not self._disk_log_path.exists():
                self.load_older_bar.setVisible(False)
                return
            
            # Check if there are older logs not shown
            if self._ui_start_line > 0:
                older_lines = self._ui_start_line
                self.load_older_label.setText(
                    f"📄 {older_lines:,} older lines available on disk "
                    f"(Showing lines {self._ui_start_line + 1:,} to {self._ui_end_line:,} of {self._disk_log_lines_count:,})"
                )
                self.load_older_bar.setVisible(True)
                logger.debug(f"Load older bar visible: {older_lines:,} older lines available")
            else:
                self.load_older_bar.setVisible(False)
                
        except Exception as e:
            logger.error(f"Error updating load older bar: {e}", exc_info=True)
            self.load_older_bar.setVisible(False)
    
    def _load_older_logs(self):
        """
        Load older logs from disk buffer (10k lines at a time).
        
        SMART SCROLLING: Loads older logs on demand for perfect UX!
        """
        try:
            if not self._disk_log_path or not self._disk_log_path.exists():
                QMessageBox.warning(self, "No Older Logs", "No older logs available on disk.")
                return
            
            if self._ui_start_line <= 0:
                QMessageBox.information(self, "All Loaded", "All logs are already loaded in the UI.")
                return
            
            logger.info(f"Loading older logs: start={self._ui_start_line}, chunk={self._load_more_chunk_size}")
            
            # Calculate how many lines to load
            lines_to_load = min(self._load_more_chunk_size, self._ui_start_line)
            new_start = self._ui_start_line - lines_to_load
            
            # Read the specific range from disk file
            older_text = self._read_log_lines_from_disk(new_start, self._ui_start_line)
            
            if not older_text:
                QMessageBox.warning(self, "Load Error", "Could not load older logs from disk.")
                return
            
            # Insert at the beginning of the text editor
            cursor = self.log_output.textCursor()
            cursor.beginEditBlock()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.insertText(older_text)
            cursor.endEditBlock()
            
            # Update tracking
            self._ui_start_line = new_start
            self._ui_lines_count = self.log_output.document().blockCount()
            
            # Trim bottom if UI has too many lines (keep memory under control)
            if self._ui_lines_count > self._max_ui_lines:
                lines_to_remove = self._ui_lines_count - self._max_ui_lines
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.beginEditBlock()
                for _ in range(lines_to_remove):
                    cursor.movePosition(QTextCursor.MoveOperation.Up, QTextCursor.MoveMode.KeepAnchor)
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                cursor.endEditBlock()
                
                self._ui_end_line -= lines_to_remove
                self._ui_lines_count = self.log_output.document().blockCount()
                logger.debug(f"Trimmed {lines_to_remove:,} lines from bottom to maintain {self._max_ui_lines:,} line limit")
            
            # Update UI
            self._update_load_older_bar()
            logger.info(f"✓ Loaded {lines_to_load:,} older lines (now showing {self._ui_start_line + 1:,} to {self._ui_end_line:,})")
            
            # Keep scroll position at top (user wanted to see older logs)
            self.log_output.moveCursor(QTextCursor.MoveOperation.Start)
            self.log_output.ensureCursorVisible()
            
        except Exception as e:
            logger.error(f"Error loading older logs: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load older logs: {str(e)}")
    
    def _load_all_logs(self):
        """
        Load ALL logs from disk into UI.
        
        WARNING: May be slow for huge logs! Shows confirmation for large files.
        """
        try:
            if not self._disk_log_path or not self._disk_log_path.exists():
                QMessageBox.warning(self, "No Logs", "No logs available on disk.")
                return
            
            total_lines = self._disk_log_lines_count
            lines_to_load = self._ui_start_line  # Lines not currently shown
            
            if lines_to_load <= 0:
                QMessageBox.information(self, "All Loaded", "All logs are already loaded.")
                return
            
            # Warn for huge logs
            if total_lines > 100000:
                file_size_mb = self._disk_log_path.stat().st_size / 1024 / 1024
                reply = QMessageBox.question(
                    self,
                    "Load All Logs?",
                    f"This will load {total_lines:,} lines ({file_size_mb:.1f} MB) into memory.\n\n"
                    f"This may take a few seconds and use ~{total_lines * 0.002:.0f} MB of RAM.\n\n"
                    "Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            
            logger.info(f"Loading ALL logs: {lines_to_load:,} lines from disk")
            
            # Show progress (for large files)
            from PySide6.QtWidgets import QProgressDialog
            progress = QProgressDialog("Loading all logs from disk...", "Cancel", 0, lines_to_load, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(500)  # Show after 500ms
            
            # Read older logs in chunks
            chunk_size = 50000
            all_text = []
            
            for offset in range(0, lines_to_load, chunk_size):
                if progress.wasCanceled():
                    logger.info("Load all cancelled by user")
                    return
                
                end = min(offset + chunk_size, lines_to_load)
                chunk_text = self._read_log_lines_from_disk(offset, end)
                if chunk_text:
                    all_text.append(chunk_text)
                
                progress.setValue(end)
            
            progress.close()
            
            # Combine and insert
            older_text = "".join(all_text)
            cursor = self.log_output.textCursor()
            cursor.beginEditBlock()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.insertText(older_text)
            cursor.endEditBlock()
            
            # Update tracking
            self._ui_start_line = 0
            self._ui_end_line = self._disk_log_lines_count
            self._ui_lines_count = self.log_output.document().blockCount()
            
            # Update UI
            self._update_load_older_bar()
            logger.info(f"✓ Loaded ALL {lines_to_load:,} lines (total: {self._ui_lines_count:,} lines in UI)")
            
            # Move to top
            self.log_output.moveCursor(QTextCursor.MoveOperation.Start)
            self.log_output.ensureCursorVisible()
            
            QMessageBox.information(self, "Loaded", f"Successfully loaded all {total_lines:,} lines into UI!")
            
        except Exception as e:
            logger.error(f"Error loading all logs: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load all logs: {str(e)}")
    
    def _read_log_lines_from_disk(self, start_line: int, end_line: int) -> str:
        """
        Read specific line range from disk buffer file.
        
        Args:
            start_line: Starting line number (0-based, inclusive)
            end_line: Ending line number (0-based, exclusive)
        
        Returns:
            Text content of the specified line range
        """
        try:
            if not self._disk_log_path or not self._disk_log_path.exists():
                return ""
            
            result_lines = []
            
            with open(self._disk_log_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f):
                    if line_num >= end_line:
                        break
                    if line_num >= start_line:
                        result_lines.append(line)
            
            return "".join(result_lines)
            
        except Exception as e:
            logger.error(f"Error reading lines {start_line}-{end_line} from disk: {e}", exc_info=True)
            return ""
    
    def _append_log(self, text):
        """
        Append text to log output with crash protection and batching.
        Uses deque for efficient memory management and batches updates for performance.
        """
        try:
            # CRITICAL: Double-check streaming state to prevent late arrivals after stop
            if not self._is_streaming_logs:
                logger.debug("Ignoring log append - not actively streaming")
                return
            
            # CRITICAL: Check if worker is still active to prevent late arrivals after stop
            if not self.worker or not self.worker.isRunning():
                logger.debug("Ignoring log append - worker not active")
                return
            
            # Add to deque for efficient line management
            for line in text.splitlines(keepends=True):
                if line.strip():  # Only add non-empty lines
                    self.log_lines.append(line)
            
            # Add to batch for UI update
            self._log_append_batch.append(text)
            
            # If batch size is small, schedule batch processing
            if len(self._log_append_batch) < 10:
                if not self._batch_timer:
                    self._batch_timer = QTimer(self)
                    self._batch_timer.setSingleShot(True)
                    self._batch_timer.timeout.connect(self._flush_log_batch)
                if not self._batch_timer.isActive():
                    self._batch_timer.start(50)  # Flush after 50ms
                return
            
            # If batch is large enough, flush immediately
            self._flush_log_batch()
            
        except Exception as e:
            logger.error(f"Error appending log: {e}", exc_info=True)
            # Try to at least show the error
            try:
                self.log_output.append(f"\n⚠️ [Log Error: {str(e)}]\n")
            except:
                pass  # Fail silently to prevent cascading crashes
    
    def _flush_log_batch(self):
        """
        Flush batched log updates to UI and disk efficiently.
        
        MEMORY OPTIMIZATION FOR 2GB RAM:
        - Writes ALL logs to disk (unlimited storage)
        - Keeps only recent 50k lines in UI (low memory)
        - User gets unlimited logs without RAM constraints!
        
        CRASH PROTECTION: Checks if streaming is still active before updating UI.
        """
        try:
            if not self._log_append_batch:
                return
            
            # CRITICAL: Triple-check if we should still be processing logs
            # This prevents crashes when stop is called while timer is queued
            if not self._is_streaming_logs:
                logger.debug("Aborting flush - not actively streaming")
                self._log_append_batch.clear()
                return
            
            if not self.worker or not self.worker.isRunning():
                logger.debug("Aborting flush - worker not active")
                self._log_append_batch.clear()
                return
            
            # Stop the timer if active
            if self._batch_timer and self._batch_timer.isActive():
                self._batch_timer.stop()
            
            # Combine all batched text
            combined_text = "".join(self._log_append_batch)
            self._log_append_batch.clear()
            
            # STEP 1: Write to disk buffer (ONLY if disk buffering enabled)
            if self._disk_buffering_enabled and self._disk_log_file:
                try:
                    # Add to RAM cache first (SSD WEAR PROTECTION!)
                    self._disk_buffer_ram_cache.append(combined_text)
                    lines_written = combined_text.count('\n')
                    self._disk_log_lines_count += lines_written
                    
                    # Only write to disk when RAM cache is full (reduces writes!)
                    if len(self._disk_buffer_ram_cache) >= self._disk_buffer_cache_size:
                        # Check file size before writing (prevent huge files!)
                        current_size = self._disk_log_path.stat().st_size if self._disk_log_path.exists() else 0
                        
                        if current_size >= self._max_disk_file_size:
                            logger.warning(f"Disk buffer reached max size ({current_size / 1024 / 1024:.1f} MB) - stopping disk writes")
                            self._close_disk_buffer()
                            self._disk_buffering_enabled = False
                            
                            # Notify user
                            if hasattr(self, 'current_pod_label'):
                                current_text = self.current_pod_label.text().split("│")[0].strip()
                                self.current_pod_label.setText(f"{current_text} │ ⚠️ Disk limit reached ({self._disk_log_lines_count:,} lines saved)")
                        else:
                            # Combine cache and write to disk
                            cached_text = "".join(self._disk_buffer_ram_cache)
                            self._disk_log_file.write(cached_text)
                            self._disk_log_file.flush()  # Ensure written
                            self._disk_buffer_ram_cache.clear()  # Clear RAM cache
                            
                            # Log progress every 10k lines
                            if self._disk_log_lines_count % 10000 < lines_written:
                                file_size_mb = current_size / 1024 / 1024
                                logger.debug(f"Disk buffer: {self._disk_log_lines_count:,} lines ({file_size_mb:.1f} MB, {self._disk_buffer_cache_size} writes cached)")
                        
                except Exception as e:
                    logger.error(f"Error writing to disk buffer: {e}")
                    self._disk_buffering_enabled = False
            
            # STEP 2: Update UI (only recent logs for performance)
            scrollbar = self.log_output.verticalScrollBar()
            was_at_bottom = scrollbar.value() >= scrollbar.maximum() - 10
            
            # Use QTextCursor in batch mode
            cursor = self.log_output.textCursor()
            cursor.beginEditBlock()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(combined_text)
            cursor.endEditBlock()
            
            # Update UI line counter
            self._ui_lines_count = self.log_output.document().blockCount()
            
            # STEP 3: MEMORY PROTECTION - Trim UI (ONLY for unlimited/disk buffer mode)
            # NOTE: Limited mode uses QTextEdit's setMaximumBlockCount (more efficient)
            if self._disk_buffering_enabled:
                doc = self.log_output.document()
                
                # Update UI end line tracker (what's the last line shown?)
                self._ui_end_line = self._disk_log_lines_count
                
                # Trim if UI has too many lines (Option B: 100k limit for better UX)
                if doc.blockCount() > 100000:
                    lines_to_trim = 10000
                    logger.info(f"UI at 100k lines, trimming {lines_to_trim:,} oldest (keeping newest 90k). Total on disk: {self._disk_log_lines_count:,}")
                    
                    # Remove oldest lines from UI (keeps newest)
                    cursor.movePosition(QTextCursor.MoveOperation.Start)
                    cursor.beginEditBlock()
                    for _ in range(lines_to_trim):
                        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                        cursor.removeSelectedText()
                        cursor.deleteChar()  # Remove newline
                    cursor.endEditBlock()
                    
                    self._ui_lines_count = doc.blockCount()
                    
                    # Update UI start line tracker (oldest line now shown)
                    self._ui_start_line += lines_to_trim
                    
                    logger.debug(f"UI now shows lines {self._ui_start_line + 1:,} to {self._ui_end_line:,} of {self._disk_log_lines_count:,}")
                    
                    # Update "Load Older" bar visibility
                    self._update_load_older_bar()
                    
                    # Update label to show disk buffer status
                    if hasattr(self, 'current_pod_label'):
                        current_text = self.current_pod_label.text().split("│")[0].strip()
                        self.current_pod_label.setText(
                            f"{current_text} │ 💾 {self._disk_log_lines_count:,} lines total "
                            f"(showing {self._ui_start_line + 1:,}-{self._ui_end_line:,})"
                        )
            
            # Memory warning check (every 30 minutes)
            self._check_memory_warning()
            
            # PERFORMANCE: Only update search if actively searching
            if self.current_search_term and not was_at_bottom:
                # Invalidate search cache
                self._search_cache_text = ""
                # Only update search when user is viewing results
                old_count = len(self.search_occurrences)
                self.search_occurrences = self._find_all_occurrences(self.current_search_term)
                new_count = len(self.search_occurrences)
                
                self._update_match_counter()
                
                if self.current_occurrence_index >= 0 and self.current_occurrence_index < len(self.search_occurrences):
                    self._jump_to_occurrence(self.current_occurrence_index)
                
                if new_count > old_count:
                    logger.debug(f"Search results updated: {old_count} -> {new_count} occurrences")
            
            # Smart scroll: Only auto-scroll if user was at bottom
            if was_at_bottom:
                self.log_output.moveCursor(QTextCursor.MoveOperation.End)
                self.log_output.ensureCursorVisible()
                
        except Exception as e:
            logger.error(f"Error flushing log batch: {e}", exc_info=True)
            # Clear batch to prevent infinite loops
            self._log_append_batch.clear()
    
    # -------------------------
    # Theme Management
    # -------------------------
    
    def _apply_theme(self, theme_name: str):
        """Apply the selected theme to the application (from themes.py)."""
        logger.info(f"Applying theme: {theme_name}")
        
        # Get theme class from themes.py
        theme_class = get_theme(theme_name)
        
        # Apply main stylesheet
        self.setStyleSheet(theme_class.get_stylesheet())
        
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
        
        # Link color based on theme
        if self.current_theme == "dark":
            link_color = "#4a9eff"
        else:
            link_color = "#0066cc"
            
        email1_label = QLabel(f'📧 <a href="mailto:harshmeetsingh010@gmail.com" style="color: {link_color}; text-decoration: none;">harshmeetsingh010@gmail.com</a>')
        email1_label.setOpenExternalLinks(True)
        email1_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(email1_label)
        
        email2_label = QLabel(f'📧 <a href="mailto:harshmeet.singh@netcoreunbxd.com" style="color: {link_color}; text-decoration: none;">harshmeet.singh@netcoreunbxd.com</a>')
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
                QLabel {
                    color: #e0e0e0;
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
                QLabel {
                    color: #212121;
                }
                QLabel a {
                    color: #0066cc;
                    text-decoration: none;
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
    
    def _show_installation_info(self):
        """Show current installation metadata and allow refreshing."""
        logger.info("Showing installation info")
        
        # Get current metadata
        metadata = AppConfig.get_installation_metadata()
        
        # Build info message
        platform = metadata.get('platform', 'Unknown')
        package_type = metadata.get('package_type', 'Unknown')
        architecture = metadata.get('architecture', 'Unknown')
        version = metadata.get('version', 'Unknown')
        source = metadata.get('source', 'Unknown')
        
        message = (
            f"<b>Current Installation Details:</b><br><br>"
            f"<b>Platform:</b> {platform}<br>"
            f"<b>Package Type:</b> {package_type}<br>"
            f"<b>Architecture:</b> {architecture}<br>"
            f"<b>Version:</b> {version}<br>"
            f"<b>Detection Source:</b> {source}<br><br>"
            f"<i>If this looks incorrect, click 'Refresh Detection' to re-detect.</i>"
        )
        
        from PySide6.QtWidgets import QMessageBox, QPushButton
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Installation Information")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Information)
        
        # Add custom buttons
        refresh_btn = msg_box.addButton("Refresh Detection", QMessageBox.ActionRole)
        close_btn = msg_box.addButton("Close", QMessageBox.RejectRole)
        
        msg_box.exec()
        
        # Check which button was clicked
        if msg_box.clickedButton() == refresh_btn:
            self._refresh_installation_metadata()
    
    def _refresh_installation_metadata(self):
        """Force re-detection of installation metadata."""
        logger.info("Refreshing installation metadata")
        
        # Clear cached metadata
        config_path = AppConfig.get_config_path()
        try:
            import json
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Remove installation_metadata if present
            if 'installation_metadata' in config_data:
                del config_data['installation_metadata']
                
                with open(config_path, 'w') as f:
                    json.dump(config_data, f, indent=2)
                
                logger.info("Cleared cached installation metadata")
        except Exception as e:
            logger.error(f"Failed to clear cached metadata: {e}")
        
        # Force re-detection
        from app.metadata_detector import MetadataDetector
        new_metadata = MetadataDetector.detect()
        
        # Save to config
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            config_data['installation_metadata'] = new_metadata
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Re-detected and saved metadata: {new_metadata}")
        except Exception as e:
            logger.error(f"Failed to save new metadata: {e}")
        
        # Show new info
        from PySide6.QtWidgets import QMessageBox
        
        platform = new_metadata.get('platform', 'Unknown')
        package_type = new_metadata.get('package_type', 'Unknown')
        architecture = new_metadata.get('architecture', 'Unknown')
        
        message = (
            f"<b>Re-detected Installation:</b><br><br>"
            f"<b>Platform:</b> {platform}<br>"
            f"<b>Package Type:</b> {package_type}<br>"
            f"<b>Architecture:</b> {architecture}<br><br>"
            f"<i>Metadata refreshed successfully!</i>"
        )
        
        QMessageBox.information(
            self,
            "Metadata Refreshed",
            message
        )
            
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
        """Show a non-intrusive update notification with download details."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Update Available")
        msg_box.setIcon(QMessageBox.Icon.Information)
        
        if update_info.is_critical:
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText(f"⚠️ Critical Update Available: v{update_info.version}")
        else:
            msg_box.setText(f"Update Available: v{update_info.version}")
        
        # Build informative text with file details
        info_text = (
            f"A new version of Argo Log Viewer is available.\n\n"
            f"Current version: {UpdateConfig.get_current_version()}\n"
            f"New version: {update_info.version}\n"
        )
        
        # Add file details if available
        if update_info.file_name:
            info_text += f"\nPackage: {update_info.file_name}"
        if update_info.file_size:
            size_mb = update_info.file_size / (1024 * 1024)
            info_text += f"\nSize: {size_mb:.1f} MB"
        
        info_text += "\n\nWould you like to download and install it now?"
        
        msg_box.setInformativeText(info_text)
        
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
        """Download and install update."""
        logger.info(f"Starting update download: {update_info.version}")
        
        # Check if we have a direct asset URL
        if not update_info.asset_url:
            # Fall back to browser if no direct download available
            logger.warning("No direct download URL, falling back to browser")
            try:
                webbrowser.open(update_info.download_url)
                QMessageBox.information(
                    self,
                    "Opening Releases Page",
                    "Your browser will open the GitHub releases page.\n\n"
                    "Please download the correct version for your platform."
                )
            except Exception as e:
                logger.error(f"Error opening releases page: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Could not open releases page:\n{update_info.download_url}"
                )
            return
        
        # Show progress dialog
        self._show_download_progress_dialog(update_info)
    
    def _show_download_progress_dialog(self, update_info: UpdateInfo):
        """Show download progress dialog and start download."""
        from PySide6.QtWidgets import QProgressDialog
        from app.update_downloader import UpdateDownloaderThread, get_downloads_folder
        
        # Portable builds + DEB → save to Downloads so user can keep the file.
        # Installer (Windows) and DMG (macOS) → save to temp (we launch/mount it immediately).
        metadata = AppConfig.get_installation_metadata()
        package_type = (metadata.get('package_type') or '').lower()
        is_portable_or_deb = package_type in ('portable', 'zip', 'deb')
        download_dir = get_downloads_folder() if is_portable_or_deb else None
        
        # Create progress dialog
        progress_dialog = QProgressDialog(
            f"Downloading {update_info.file_name}...",
            "Cancel",
            0,
            100,
            self
        )
        progress_dialog.setWindowTitle(f"Downloading Update v{update_info.version}")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumWidth(500)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        
        # Create downloader thread
        self.download_thread = UpdateDownloaderThread(
            update_info.asset_url,
            update_info.file_name,
            update_info.file_size,
            download_dir=download_dir
        )
        
        # Connect signals
        def on_progress(downloaded, total, speed):
            if total > 0:
                percent = int((downloaded / total) * 100)
                progress_dialog.setValue(percent)
                
                # Update label with details
                downloaded_mb = downloaded / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                progress_dialog.setLabelText(
                    f"Downloading {update_info.file_name}...\n\n"
                    f"Progress: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({percent}%)\n"
                    f"Speed: {speed:.2f} MB/s"
                )
        
        def on_completed(file_path):
            progress_dialog.close()
            logger.info(f"Download completed: {file_path}")
            
            # Verify checksum if available
            if update_info.checksum_url:
                self._verify_and_install(file_path, update_info)
            else:
                logger.warning("No checksum URL, skipping verification")
                self._install_update(file_path, update_info)
        
        def on_error(error_msg):
            progress_dialog.close()
            logger.error(f"Download error: {error_msg}")
            QMessageBox.critical(
                self,
                "Download Failed",
                f"Failed to download update:\n\n{error_msg}"
            )
        
        def on_cancel():
            if hasattr(self, 'download_thread'):
                self.download_thread.cancel()
                logger.info("User cancelled download")
        
        self.download_thread.progress.connect(on_progress)
        self.download_thread.completed.connect(on_completed)
        self.download_thread.error.connect(on_error)
        progress_dialog.canceled.connect(on_cancel)
        
        # Start download
        self.download_thread.start()
        progress_dialog.exec()
    
    def _verify_and_install(self, file_path: str, update_info: UpdateInfo):
        """Verify checksum and install update."""
        from PySide6.QtWidgets import QProgressDialog
        from app.update_downloader import UpdateDownloader
        
        # Show verification progress
        verify_dialog = QProgressDialog(
            "Verifying download integrity...",
            None,
            0,
            0,
            self
        )
        verify_dialog.setWindowTitle("Verifying Update")
        verify_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        verify_dialog.setCancelButton(None)
        verify_dialog.show()
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._do_verification(file_path, update_info, verify_dialog))
    
    def _do_verification(self, file_path: str, update_info: UpdateInfo, verify_dialog):
        """Perform checksum verification."""
        from app.update_downloader import UpdateDownloader
        
        try:
            # Download checksums
            checksums = UpdateDownloader.download_checksums(update_info.checksum_url)
            
            if not checksums:
                verify_dialog.close()
                logger.warning("Could not download checksums")
                
                # Ask user if they want to proceed anyway
                reply = QMessageBox.question(
                    self,
                    "Verification Warning",
                    "Could not verify download integrity (checksums unavailable).\n\n"
                    "Do you want to proceed with installation anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._install_update(file_path, update_info)
                return
            
            # Get expected checksum
            expected_checksum = checksums.get(update_info.file_name)
            
            if not expected_checksum:
                verify_dialog.close()
                logger.warning(f"No checksum found for {update_info.file_name}")
                
                reply = QMessageBox.question(
                    self,
                    "Verification Warning",
                    f"No checksum found for {update_info.file_name}.\n\n"
                    "Do you want to proceed anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._install_update(file_path, update_info)
                return
            
            # Verify checksum
            is_valid = UpdateDownloader.verify_checksum(file_path, expected_checksum)
            verify_dialog.close()
            
            if is_valid:
                logger.info("✓ Checksum verification passed")
                self._install_update(file_path, update_info)
            else:
                logger.error("✗ Checksum verification failed")
                QMessageBox.critical(
                    self,
                    "Verification Failed",
                    "Download integrity check failed!\n\n"
                    "The downloaded file may be corrupted or tampered with.\n"
                    "Please try downloading again."
                )
                # Clean up
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        except Exception as e:
            verify_dialog.close()
            logger.error(f"Error during verification: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Verification Error",
                f"Error verifying download:\n\n{str(e)}"
            )
    
    def _install_update(self, file_path: str, update_info: UpdateInfo):
        """Install the downloaded update."""
        from app.update_downloader import InstallerLauncher
        from app.config import AppConfig
        
        logger.info(f"Installing update from {file_path}")
        
        # Get installation metadata
        metadata = AppConfig.get_installation_metadata()
        
        # Launch installer
        result = InstallerLauncher.launch(file_path, metadata)
        
        if result['success']:
            if result['action'] == 'launched':
                # Installer launched - show confirmation and exit
                reply = QMessageBox.information(
                    self,
                    "Update Ready",
                    result['message'],
                    QMessageBox.StandardButton.Ok
                )
                
                # Exit application
                from PySide6.QtWidgets import QApplication
                QApplication.quit()
            
            elif result['action'] == 'prepared':
                # Manual steps needed - show instructions
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Update Ready")
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setText(result['message'])
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                
                # Add copy button for Linux command if available
                if 'install_command' in result:
                    copy_btn = msg_box.addButton("Copy Command", QMessageBox.ButtonRole.ActionRole)
                    
                    def copy_command():
                        from PySide6.QtWidgets import QApplication
                        QApplication.clipboard().setText(result['install_command'])
                    
                    copy_btn.clicked.connect(copy_command)
                
                msg_box.exec()
                
                # Exit if needs manual steps
                if result.get('needs_manual'):
                    from PySide6.QtWidgets import QApplication
                    QApplication.quit()
        else:
            # Error occurred
            QMessageBox.critical(
                self,
                "Installation Error",
                result['message']
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
            self.save_logs_to_file()
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
        
        # Warning label for limited mode
        self.warning_label = QLabel(
            "⚠️ <b>Warning:</b> Older logs will be permanently deleted to save memory.<br>"
            "Only the most recent lines will be kept."
        )
        self.warning_label.setStyleSheet("color: #ff9800; font-size: 9pt; margin-top: 5px;")
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(current_limit > 0)  # Show if limited is selected
        buffer_layout.addWidget(self.warning_label)
        
        # Connect toggle to warning visibility
        limited_radio.toggled.connect(self.warning_label.setVisible)
        
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
        
        # Cleanup disk buffers
        self._close_disk_buffer()
        
        # Clean up temp buffer files on exit
        try:
            temp_dir = Path(tempfile.gettempdir()) / "argo_log_viewer_buffers"
            if temp_dir.exists():
                for file in temp_dir.glob(f"logs_*_{os.getpid()}.txt"):
                    try:
                        file.unlink()
                        logger.debug(f"Deleted temp buffer: {file}")
                    except Exception as e:
                        logger.warning(f"Could not delete temp buffer {file}: {e}")
        except Exception as e:
            logger.warning(f"Error cleaning up temp buffers: {e}")
        
        logger.info("Window closed, application exiting")
        event.accept()
