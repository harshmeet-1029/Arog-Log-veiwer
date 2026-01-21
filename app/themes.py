"""
Theme Management System for Argo Log Viewer.

This file contains all theme definitions (Dark, Light, High Contrast).
Easy to add new themes - just copy a theme class and modify colors!

Created by: Harshmeet Singh (2024-2026)
"""
from pathlib import Path
import tempfile


# Generate checkbox icons
def _get_checkbox_icon_path():
    """Get path to checkmark icon, create if doesn't exist."""
    icon_dir = Path(tempfile.gettempdir()) / "argo_log_viewer_icons"
    icon_dir.mkdir(exist_ok=True)
    icon_path = icon_dir / "checkmark.png"
    
    if not icon_path.exists():
        from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
        from PySide6.QtCore import Qt
        
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Draw checkmark
        painter.drawLine(4, 8, 7, 11)
        painter.drawLine(7, 11, 12, 4)
        
        painter.end()
        pixmap.save(str(icon_path))
    
    return str(icon_path).replace('\\', '/')


def _get_radio_icon_path():
    """Get path to radio dot icon, create if doesn't exist."""
    icon_dir = Path(tempfile.gettempdir()) / "argo_log_viewer_icons"
    icon_dir.mkdir(exist_ok=True)
    icon_path = icon_dir / "radio_dot.png"
    
    if not icon_path.exists():
        from PySide6.QtGui import QPixmap, QPainter, QColor
        from PySide6.QtCore import Qt, QRect
        
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#4a9eff"))
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Draw inner circle
        painter.drawEllipse(QRect(4, 4, 8, 8))
        
        painter.end()
        pixmap.save(str(icon_path))
    
    return str(icon_path).replace('\\', '/')



class BaseTheme:
    """Base theme class with common properties."""
    
    # Theme identification
    name = "Base"
    display_name = "Base Theme"
    
    # Window and widget colors
    background_color = "#2b2b2b"
    text_color = "#e0e0e0"
    border_color = "#3c3c3c"
    
    # UI Element colors
    button_background = "#3c3c3c"
    button_hover = "#4a4a4a"
    input_background = "#1e1e1e"
    input_border = "#555555"
    
    # Status colors
    success_color = "#4caf50"
    warning_color = "#ff9800"
    error_color = "#f44336"
    info_color = "#2196f3"
    
    # Accent colors
    primary_accent = "#3498db"
    secondary_accent = "#1abc9c"
    
    # Log output colors
    log_background = "#1e1e1e"
    log_text = "#e0e0e0"
    
    # Metrics colors
    metrics_text = "#ffffff"
    
    @classmethod
    def get_main_stylesheet(cls) -> str:
        """Get the main application stylesheet."""
        # Get icon paths
        checkmark_icon = _get_checkbox_icon_path()
        radio_icon = _get_radio_icon_path()
        
        return f"""
            QWidget {{
                background-color: {cls.background_color};
                color: {cls.text_color};
            }}
            QMenuBar {{
                background-color: {cls.input_background};
                color: {cls.text_color};
                border-bottom: 1px solid {cls.border_color};
                margin-bottom: 10px;
                padding: 8px 10px;
                spacing: 5px;
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QMenuBar::item:selected {{
                background-color: {cls.button_hover};
            }}
            QMenuBar::item:pressed {{
                background-color: {cls.primary_accent};
                color: white;
            }}
            QMenu {{
                background-color: {cls.background_color};
                color: {cls.text_color};
                border: 1px solid {cls.border_color};
                padding: 5px;
            }}
            QMenu::item {{
                padding: 8px 25px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {cls.button_hover};
            }}
            QPushButton {{
                background-color: {cls.button_background};
                color: {cls.text_color};
                border: 1px solid {cls.border_color};
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {cls.button_hover};
                border-color: {cls.primary_accent};
            }}
            QPushButton:pressed {{
                background-color: {cls.primary_accent};
                color: white;
            }}
            QPushButton:disabled {{
                background-color: {cls.background_color};
                color: #666666;
                border-color: #444444;
            }}
            QLineEdit, QTextEdit {{
                background-color: {cls.input_background};
                color: {cls.text_color};
                border: 1px solid {cls.input_border};
                border-radius: 4px;
                padding: 5px;
                selection-background-color: {cls.primary_accent};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {cls.primary_accent};
            }}
            QListWidget {{
                background-color: {cls.input_background};
                color: {cls.text_color};
                border: 1px solid {cls.input_border};
                border-radius: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 4px 8px;
                border: none;
                outline: none;
            }}
            QListWidget::item:hover {{
                background-color: {cls.button_hover};
            }}
            QListWidget::item:selected {{
                background-color: {cls.primary_accent};
                color: white;
                border: none;
                outline: none;
            }}
            QListWidget::item:focus {{
                outline: none;
                border: none;
            }}
            QGroupBox {{
                border: 2px solid {cls.border_color};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 15px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 5px 10px;
                background-color: {cls.background_color};
                border-radius: 3px;
            }}
            QLabel {{
                color: {cls.text_color};
            }}
            QComboBox {{
                background-color: {cls.button_background};
                color: {cls.text_color};
                border: 1px solid {cls.border_color};
                border-radius: 4px;
                padding: 5px 10px;
                min-width: 100px;
            }}
            QComboBox:hover {{
                border-color: {cls.primary_accent};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 5px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid {cls.text_color};
            }}
            QComboBox QAbstractItemView {{
                background-color: {cls.background_color};
                color: {cls.text_color};
                border: 1px solid {cls.border_color};
                selection-background-color: {cls.primary_accent};
            }}
            QScrollBar:vertical {{
                background: {cls.input_background};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {cls.button_background};
                min-height: 20px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {cls.button_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QCheckBox {{
                spacing: 10px;
                color: {cls.text_color};
                font-weight: 500;
            }}
            QCheckBox::indicator {{
                width: 22px;
                height: 22px;
                border: 2px solid {cls.border_color};
                border-radius: 4px;
                background-color: {cls.input_background};
            }}
            QCheckBox::indicator:checked {{
                background-color: {cls.primary_accent};
                border: 2px solid {cls.primary_accent};
                image: url({checkmark_icon});
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {cls.input_background};
                border: 2px solid {cls.border_color};
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {cls.button_hover};
                border: 2px solid {cls.button_hover};
            }}
            QCheckBox::indicator:hover {{
                border-color: {cls.primary_accent};
            }}
            QRadioButton {{
                spacing: 10px;
                color: {cls.text_color};
                font-weight: 500;
            }}
            QRadioButton::indicator {{
                width: 22px;
                height: 22px;
                border: 2px solid {cls.border_color};
                border-radius: 11px;
                background-color: {cls.input_background};
            }}
            QRadioButton::indicator:checked {{
                background-color: {cls.input_background};
                border: 2px solid {cls.primary_accent};
                image: url({radio_icon});
            }}
            QRadioButton::indicator:unchecked {{
                background-color: {cls.input_background};
                border: 2px solid {cls.border_color};
            }}
            QRadioButton::indicator:checked:hover {{
                border: 2px solid {cls.button_hover};
            }}
            QRadioButton::indicator:hover {{
                border-color: {cls.primary_accent};
            }}
            QSpinBox {{
                background-color: {cls.input_background};
                color: {cls.text_color};
                border: 1px solid {cls.input_border};
                border-radius: 4px;
                padding: 5px;
            }}
            QSpinBox:focus {{
                border-color: {cls.primary_accent};
            }}
        """
    
    @classmethod
    def get_user_guide_html_style(cls) -> str:
        """Get HTML styles for User Guide (theme-aware)."""
        return f"""
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    line-height: 1.6; 
                    padding: 20px;
                    color: {cls.text_color};
                }}
                h1 {{ 
                    color: {cls.primary_accent}; 
                    border-bottom: 2px solid {cls.primary_accent}; 
                    padding-bottom: 10px; 
                }}
                h2 {{ 
                    color: {cls.primary_accent}; 
                    margin-top: 25px; 
                }}
                h3 {{ 
                    color: {cls.secondary_accent}; 
                    margin-top: 20px; 
                }}
                .feature {{ 
                    border: 2px solid {cls.primary_accent}; 
                    padding: 15px; 
                    margin: 10px 0; 
                    border-radius: 5px; 
                }}
                .step {{ 
                    margin-left: 20px; 
                    margin-bottom: 10px; 
                }}
                .tip {{ 
                    border-left: 4px solid {cls.warning_color}; 
                    padding: 10px; 
                    margin: 10px 0; 
                    opacity: 0.9; 
                }}
                .warning {{ 
                    border-left: 4px solid {cls.error_color}; 
                    padding: 10px; 
                    margin: 10px 0; 
                    opacity: 0.9; 
                }}
                code {{ 
                    border: 1px solid {cls.border_color}; 
                    padding: 2px 6px; 
                    border-radius: 3px; 
                    font-family: monospace;
                    background: rgba(127, 140, 141, 0.1);
                }}
                table {{ 
                    border-collapse: collapse; 
                    width: 100%; 
                    margin: 10px 0; 
                }}
                th {{ 
                    border: 1px solid {cls.primary_accent}; 
                    padding: 8px; 
                    background: rgba(52, 152, 219, 0.2); 
                }}
                td {{ 
                    border: 1px solid {cls.border_color}; 
                    padding: 8px; 
                }}
                tr:nth-child(even) {{ 
                    background: rgba(127, 140, 141, 0.1); 
                }}
                ul, ol {{
                    margin-left: 20px;
                }}
            </style>
        """


class DarkTheme(BaseTheme):
    """Dark theme - default and most popular."""
    
    name = "dark"
    display_name = "Dark Mode"
    
    # Dark backgrounds
    background_color = "#2b2b2b"
    text_color = "#e0e0e0"
    border_color = "#3c3c3c"
    
    # Inputs and buttons
    button_background = "#3c3c3c"
    button_hover = "#4a4a4a"
    input_background = "#1e1e1e"
    input_border = "#555555"
    
    # Status colors
    success_color = "#4caf50"
    warning_color = "#ff9800"
    error_color = "#f44336"
    info_color = "#2196f3"
    
    # Accents
    primary_accent = "#3498db"
    secondary_accent = "#1abc9c"
    
    # Logs
    log_background = "#1e1e1e"
    log_text = "#e0e0e0"
    
    # Metrics
    metrics_text = "#ffffff"


class LightTheme(BaseTheme):
    """Light theme - for bright environments."""
    
    name = "light"
    display_name = "Light Mode"
    
    # Light backgrounds
    background_color = "#f5f5f5"
    text_color = "#212121"
    border_color = "#cccccc"
    
    # Inputs and buttons
    button_background = "#e0e0e0"
    button_hover = "#d0d0d0"
    input_background = "#ffffff"
    input_border = "#bdbdbd"
    
    # Status colors
    success_color = "#388e3c"
    warning_color = "#f57c00"
    error_color = "#d32f2f"
    info_color = "#1976d2"
    
    # Accents
    primary_accent = "#2196f3"
    secondary_accent = "#009688"
    
    # Logs
    log_background = "#ffffff"
    log_text = "#212121"
    
    # Metrics
    metrics_text = "#000000"


class HighContrastTheme(BaseTheme):
    """High contrast theme - for accessibility."""
    
    name = "high_contrast"
    display_name = "High Contrast"
    
    # High contrast backgrounds
    background_color = "#000000"
    text_color = "#ffffff"
    border_color = "#ffffff"
    
    # Inputs and buttons
    button_background = "#1a1a1a"
    button_hover = "#333333"
    input_background = "#000000"
    input_border = "#ffffff"
    
    # Status colors (brighter for contrast)
    success_color = "#00ff00"
    warning_color = "#ffff00"
    error_color = "#ff0000"
    info_color = "#00ffff"
    
    # Accents (very bright)
    primary_accent = "#00bfff"
    secondary_accent = "#00ff7f"
    
    # Logs
    log_background = "#000000"
    log_text = "#ffffff"
    
    # Metrics
    metrics_text = "#ffffff"


# Theme registry - add new themes here!
AVAILABLE_THEMES = {
    "dark": DarkTheme,
    "light": LightTheme,
    "high_contrast": HighContrastTheme,
}


def get_theme(theme_name: str) -> BaseTheme:
    """
    Get a theme by name.
    
    Args:
        theme_name: Theme identifier (e.g., "dark", "light")
        
    Returns:
        Theme class (defaults to DarkTheme if not found)
    """
    return AVAILABLE_THEMES.get(theme_name.lower(), DarkTheme)


def get_available_theme_names() -> list:
    """
    Get list of available theme display names.
    
    Returns:
        List of theme display names (e.g., ["Dark Mode", "Light Mode"])
    """
    return [theme.display_name for theme in AVAILABLE_THEMES.values()]


def get_theme_name_from_display(display_name: str) -> str:
    """
    Get theme internal name from display name.
    
    Args:
        display_name: Display name (e.g., "Dark Mode")
        
    Returns:
        Internal name (e.g., "dark")
    """
    for name, theme in AVAILABLE_THEMES.items():
        if theme.display_name == display_name:
            return name
    return "dark"  # Default


# HOW TO ADD A NEW THEME:
# 
# 1. Create a new class that inherits from BaseTheme:
#
#    class BlueTheme(BaseTheme):
#        name = "blue"
#        display_name = "Blue Ocean"
#        
#        background_color = "#0d1b2a"
#        text_color = "#e0e1dd"
#        primary_accent = "#1b4965"
#        # ... override other colors ...
#
# 2. Add it to AVAILABLE_THEMES:
#
#    AVAILABLE_THEMES = {
#        "dark": DarkTheme,
#        "light": LightTheme,
#        "high_contrast": HighContrastTheme,
#        "blue": BlueTheme,  # <-- Add here
#    }
#
# 3. That's it! The theme will automatically appear in the UI!
