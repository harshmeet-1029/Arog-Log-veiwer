import sys
import logging
import os
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.logging_config import setup_logging, get_logger

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
    
    try:
        logger.debug("Creating QApplication instance")
        app = QApplication(sys.argv)
        app.setApplicationName("Argo Log Viewer")
        logger.info(f"Application name set to: {app.applicationName()}")
        
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


if __name__ == "__main__":
    main()
