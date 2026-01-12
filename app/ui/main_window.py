"""
Production-grade main window for Argo Log Viewer.
Features: Connection management, console output, pod search, log streaming.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListWidget, QTextEdit, QLineEdit, QLabel, 
    QMessageBox, QSplitter, QGroupBox, QComboBox,
    QMenuBar, QDialog, QDialogButtonBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFont, QTextCursor, QPalette, QColor, QAction, 
    QTextDocument, QShortcut, QKeySequence
)
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
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                    border-bottom: 1px solid #3c3c3c;
                    margin-bottom: 10px;
                    padding: 8px 10px;
                    spacing: 5px;
                }
                QMenuBar::item {
                    background-color: transparent;
                    padding: 8px 15px;
                    margin: 0px 2px;
                    border-radius: 4px;
                }
                QMenuBar::item:selected {
                    background-color: #3c3c3c;
                    border-bottom: 1px solid #3c3c3c;
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
                /* VS Code style search bar */
                #log_search_bar {
                    background-color: #2b2b2b;
                    border: 1px solid #0d47a1;
                    border-radius: 3px;
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
                    background-color: #ffffff;
                    color: #212121;
                    border-bottom: 1px solid #2196f3;
                    margin-bottom: 10px;
                    padding: 10px 10px;
                    spacing: 5px;
                }
                QMenuBar::item {
                    background-color: transparent;
                    padding: 8px 15px;
                    margin: 0px 2px;
                    border-radius: 4px;
                }
                QMenuBar::item:selected {
                    background-color: #e0e0e0;
                    border-bottom: 2px solid #2196f3;
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
                /* VS Code style search bar */
                #log_search_bar {
                    background-color: #f5f5f5;
                    border: 1px solid #2196f3;
                    border-radius: 3px;
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
        
        # Help menu with shortcuts
        help_menu = menu_bar.addMenu("Help")
        
        shortcuts_action = QAction("Keyboard Shortcuts", self)
        shortcuts_action.setStatusTip("View keyboard shortcuts")
        shortcuts_action.triggered.connect(self._show_shortcuts_dialog)
        help_menu.addAction(shortcuts_action)

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
        
        # Header with pod label and fullscreen button
        header_layout = QHBoxLayout()
        
        # Current pod label
        self.current_pod_label = QLabel("No pod selected")
        self.current_pod_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.current_pod_label)
        
        header_layout.addStretch()
        
        # Fullscreen button
        self.fullscreen_btn = QPushButton("⛶ Fullscreen")
        self.fullscreen_btn.setToolTip("Enter fullscreen mode (Logs only)")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_btn.setFixedSize(120, 28)
        self.fullscreen_btn.setVisible(False)  # Hidden by default
        header_layout.addWidget(self.fullscreen_btn)
        
        layout.addLayout(header_layout)
        
        # Container for log output and floating search bar
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
        
        # Update fullscreen label if in fullscreen mode
        if self.is_fullscreen and hasattr(self, 'fullscreen_pod_label'):
            self.fullscreen_pod_label.setText(f"Viewing logs for: {pod_name}")
        
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
        
        # Show fullscreen and save buttons when pod is selected
        self.fullscreen_btn.setVisible(True)
        self.save_logs_btn.setVisible(True)
        
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
            
            # Update fullscreen label if in fullscreen mode
            if self.is_fullscreen and hasattr(self, 'fullscreen_pod_label'):
                self.fullscreen_pod_label.setText("Log stream stopped")
    
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
            
            header_layout.addStretch()
            
            exit_fullscreen_btn = QPushButton("✕ Exit Fullscreen")
            exit_fullscreen_btn.clicked.connect(self.toggle_fullscreen)
            exit_fullscreen_btn.setToolTip("Exit fullscreen (Esc or F11)")
            exit_fullscreen_btn.setFixedSize(140, 30)
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
        # Store current cursor position to maintain it
        cursor = self.log_output.textCursor()
        was_at_end = cursor.position() >= self.log_output.document().characterCount() - 10
        
        # Append the new text
        self.log_output.moveCursor(QTextCursor.MoveOperation.End)
        self.log_output.insertPlainText(text)
        
        # If there's an active search, update occurrences
        if self.current_search_term:
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
        else:
            # No active search, just move to end if we were there
            if was_at_end:
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
    <li>Search bar appears on demand (Ctrl+F) - VS Code style</li>
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
    
    # -------------------------
    # Window Close Event
    # -------------------------
    
    def closeEvent(self, event):
        """Handle window close event - cleanup connections."""
        logger.info("Window close event triggered")
        
        # Exit fullscreen if active
        if self.is_fullscreen:
            self.exit_fullscreen()
        
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
