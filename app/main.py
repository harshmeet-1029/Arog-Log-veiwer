"""
Argo Log Viewer - Main Application Entry Point

Created by: Harshmeet Singh (2024-2026)
Licensed under the MIT License - See LICENSE.txt for details
"""
import sys
import logging
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from app.ui.main_window import MainWindow
from app.logging_config import setup_logging, get_logger
from app.integrity_check import check_can_run

# Initialize logger for this module
logger = get_logger(__name__)


def is_frozen():
    """
    Check if application is running as compiled executable (PyInstaller).
    
    Returns:
        bool: True if running as .exe, False if running as .py
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def main():
    """
    Main entry point for the Argo Log Viewer application.
    Initializes logging, creates the Qt application, and starts the main window.
    """
    # Determine if we should log to file (disable for .exe)
    log_to_file = not is_frozen()
    
    # Setup logging with DEBUG level
    setup_logging(log_level=logging.DEBUG, log_to_file=log_to_file)
    
    if is_frozen():
        logger.info("Running as compiled executable - file logging disabled")
    else:
        logger.info("Running as Python script - file logging enabled")
    
    logger.info("=" * 80)
    logger.info("Starting Argo Log Viewer application")
    logger.info("=" * 80)
    
    # Perform integrity check before starting
    can_run, error_message = check_can_run()
    if not can_run:
        logger.critical("Integrity check failed - application cannot run")
        logger.critical(f"Reason: {error_message}")
        
        # Show error dialog if running with GUI
        try:
            app = QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "Software Error",
                error_message or "This software is no longer authorized to run."
            )
        except:
            pass
        
        sys.exit(1)
    
    logger.info("Integrity check passed")
    
    try:
        logger.debug("Creating QApplication instance")
        app = QApplication(sys.argv)
        app.setApplicationName("Argo Log Viewer")
        logger.info(f"Application name set to: {app.applicationName()}")
        
        # Set application icon
        _set_application_icon(app)
        
        logger.debug("Creating MainWindow instance")
        window = MainWindow()
        logger.debug(f"MainWindow created with size: {window.size()}")
        
        logger.debug("Showing MainWindow")
        window.show()
        logger.info("MainWindow displayed successfully")
        
        logger.info("Entering Qt event loop")
        exit_code = app.exec()
        logger.info(f"Qt event loop exited with code: {exit_code}")
        
        logger.info("Application shutdown complete")
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Fatal error in main(): {e}", exc_info=True)
        sys.exit(1)


def _set_application_icon(app):
    """
    Set the application icon for the QApplication.
    This affects the taskbar icon on Windows and dock icon on macOS.
    """
    try:
        # Determine the base path (different for PyInstaller executable vs script)
        if getattr(sys, 'frozen', False):
            # Running as compiled executable (PyInstaller)
            base_path = sys._MEIPASS
        else:
            # Running as script
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        # Try to load icon.ico (Windows) or icon.png (cross-platform)
        icon_paths = [
            os.path.join(base_path, 'icon.ico'),
            os.path.join(base_path, 'ICON.png'),
            os.path.join(base_path, 'app', 'icon.ico'),
            os.path.join(base_path, 'app', 'ICON.png'),
        ]
        
        icon_loaded = False
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    app.setWindowIcon(icon)
                    logger.info(f"Application icon loaded from: {icon_path}")
                    icon_loaded = True
                    break
        
        if not icon_loaded:
            logger.warning("Could not load application icon - file not found")
    
    except Exception as e:
        logger.error(f"Error setting application icon: {e}", exc_info=True)


if __name__ == "__main__":
    main()
