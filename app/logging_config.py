"""
Centralized logging configuration for Argo Log Viewer application.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_level=logging.DEBUG, log_to_file=False):
    """
    Configure logging for the entire application.
    
    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to a file in addition to console
    """
    # Create logs directory if it doesn't exist
    if log_to_file:
        # Determine log directory
        # 1. Try local logs folder first (development mode)
        # 2. Use user home directory for installed app or if local is not writable
        
        is_frozen = getattr(sys, 'frozen', False)
        
        # Determine the project root directory
        if is_frozen:
            # If frozen, use the executable's directory or temp dir (not used for log_dir calculation below usually)
            base_dir = Path(sys.executable).parent
        else:
            # If script, use the project root (parent of app directory)
            # This file is in app/logging_config.py, so parent.parent is project root
            base_dir = Path(__file__).resolve().parent.parent

        log_dir = base_dir / "logs"
        use_user_dir = is_frozen
        
        if not use_user_dir:
            try:
                log_dir.mkdir(exist_ok=True)
                # Test write permission
                test_file = log_dir / ".test_write"
                test_file.touch()
                test_file.unlink()
            except (OSError, PermissionError):
                use_user_dir = True
        
        if use_user_dir:
            log_dir = Path.home() / ".argo-log-viewer" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"argo_log_viewer_{timestamp}.log"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if enabled)
    if log_to_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
        logging.info(f"Logging initialized. Log file: {log_file}")
    else:
        logging.info("Logging initialized (console only)")
    
    # Log system information
    logging.debug(f"Python version: {sys.version}")
    logging.debug(f"Platform: {sys.platform}")
    
    return root_logger


def get_logger(name):
    """
    Get a logger instance for a specific module.
    
    Args:
        name: The name of the module (typically __name__)
    
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)