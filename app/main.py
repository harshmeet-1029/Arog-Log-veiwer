"""
Argo Log Viewer - Main Application Entry Point

Created by: Harshmeet Singh (2024-2026)

This software is proprietary and subject to the terms in LICENSE.txt.
Unauthorized use, modification, or distribution is strictly prohibited.
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


def global_exception_hook(exc_type, exc_value, exc_traceback):
    """
    Global exception hook to catch unhandled exceptions and log them.
    Also shows a graphical error message to the user.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Allow Ctrl+C to exit normally
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Try to show error dialog
    try:
        app = QApplication.instance()
        if app:
            error_msg = f"An unexpected error occurred:\n{exc_value}\n\nPlease check the logs for details."
            QMessageBox.critical(None, "Critical Error", error_msg)
    except:
        pass


def main():
    """
    Main entry point for the Argo Log Viewer application.
    Initializes logging, creates the Qt application, and starts the main window.
    """
    # Disable file logging completely (as requested: no logs stored for EXE users)
    log_to_file = False
    
    # Setup logging with DEBUG level
    setup_logging(log_level=logging.DEBUG, log_to_file=log_to_file)
    
    # Install global exception hook
    sys.excepthook = global_exception_hook
    
    if is_frozen():
        logger.info("Running as compiled executable")
    else:
        logger.info("Running as Python script - file logging enabled")
    
    logger.info("=" * 80)
    logger.info("Starting Argo Log Viewer application")
    logger.info("=" * 80)
    
    # Perform integrity check before starting
    can_run, error_message = check_can_run()
    if not can_run:
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


def _get_icon_path() -> str:
    """Return the best available icon file path, or empty string if not found."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(base_path, 'ICON.png'),
        os.path.join(base_path, 'app', 'ICON.png'),
        os.path.join(base_path, 'icon.ico'),
        os.path.join(base_path, 'app', 'icon.ico'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ''


def _set_application_icon(app):
    """
    Set the application icon for the QApplication.
    This affects the taskbar icon on Windows and dock icon on macOS.
    On Linux portable, also installs a local .desktop file for GNOME integration.
    """
    try:
        icon_path = _get_icon_path()
        if icon_path:
            icon = QIcon(icon_path)
            if not icon.isNull():
                app.setWindowIcon(icon)
                logger.info(f"Application icon loaded from: {icon_path}")
            else:
                logger.warning(f"QIcon is null for: {icon_path}")
        else:
            logger.warning("Could not load application icon - file not found")

        # On Linux portable builds, only register a .desktop file if the binary
        # is in a stable system location (e.g. /usr/local/bin, /opt, ~/bin).
        # Running from Downloads or /tmp is temporary — registering there causes
        # a broken app launcher entry after the file is deleted/moved.
        if sys.platform.startswith('linux') and getattr(sys, 'frozen', False) and icon_path:
            exe = sys.executable
            stable_prefixes = ('/usr/', '/opt/', '/bin/', '/sbin/',
                               os.path.expanduser('~/bin'),
                               os.path.expanduser('~/.local/bin'))
            if any(exe.startswith(p) for p in stable_prefixes):
                _register_linux_portable_icon(icon_path)
            else:
                logger.info(
                    f"Skipping .desktop registration — binary is not in a stable location: {exe}"
                )

    except Exception as e:
        logger.error(f"Error setting application icon: {e}", exc_info=True)


def _register_linux_portable_icon(icon_src: str):
    """
    Install a local .desktop file and icon for the Linux portable build so
    GNOME/KDE shows the correct icon in the dock, alt-tab, and file manager.
    Uses the bundled app/argologviewer.desktop as a template.
    Safe to call on every launch — skips if already up to date.
    """
    try:
        import shutil
        import stat
        import subprocess

        app_id = "argologviewer-portable"
        local_apps = os.path.expanduser("~/.local/share/applications")
        local_icons = os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps")
        os.makedirs(local_apps, exist_ok=True)
        os.makedirs(local_icons, exist_ok=True)

        # Install icon
        icon_dest = os.path.join(local_icons, f"{app_id}.png")
        if not os.path.exists(icon_dest) or os.path.getmtime(icon_src) > os.path.getmtime(icon_dest):
            shutil.copy2(icon_src, icon_dest)
            logger.info(f"Installed portable icon: {icon_dest}")

        # Build .desktop content from the bundled template file
        # (app/argologviewer.desktop is bundled via --add-data="app:app")
        exe_path = sys.executable
        template_path = os.path.join(sys._MEIPASS, "app", "argologviewer.desktop")
        if os.path.exists(template_path):
            with open(template_path, "r") as f:
                template = f.read()
            desktop_content = "\n".join(
                f"Exec={exe_path}" if line.startswith("Exec=") else
                f"Icon={app_id}" if line.startswith("Icon=") else line
                for line in template.splitlines()
            ) + "\n"
        else:
            # Fallback if template not found
            desktop_content = (
                "[Desktop Entry]\nVersion=1.0\nType=Application\n"
                "Name=Argo Log Viewer\nComment=View Argo Workflow pod logs via SSH\n"
                f"Exec={exe_path}\nIcon={app_id}\nTerminal=false\n"
                "StartupNotify=true\nCategories=Development;Utility;\n"
            )

        desktop_path = os.path.join(local_apps, f"{app_id}.desktop")
        existing = open(desktop_path).read() if os.path.exists(desktop_path) else ""
        if existing != desktop_content:
            with open(desktop_path, "w") as f:
                f.write(desktop_content)
            os.chmod(desktop_path, os.stat(desktop_path).st_mode | stat.S_IEXEC)
            logger.info(f"Installed portable .desktop file: {desktop_path}")

        # Tell GNOME which .desktop file belongs to this window
        QApplication.setDesktopFileName(app_id)

        # Refresh caches (best-effort, silent)
        for cmd in [
            ["update-desktop-database", local_apps],
            ["gtk-update-icon-cache", "-q", "-t", "-f", os.path.expanduser("~/.local/share/icons/hicolor")],
        ]:
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"Could not register portable icon: {e}")


if __name__ == "__main__":
    main()
