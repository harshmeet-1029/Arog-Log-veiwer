"""
Runtime metadata detection for Argo Log Viewer.

Created by: Harshmeet Singh (2024-2026)
Proprietary software - See LICENSE.txt for terms.

This module detects installation metadata at runtime when build_metadata.py is not available.
Used as fallback for development builds or when metadata file is missing.
"""
import os
import sys
import platform
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class MetadataDetector:
    """Detects installation metadata at runtime."""
    
    @staticmethod
    def detect() -> Dict[str, str]:
        """
        Detect installation metadata at runtime.
        
        Returns:
            Dictionary with keys: platform, package_type, architecture
        """
        try:
            detected_platform = MetadataDetector._detect_platform()
            detected_architecture = MetadataDetector._detect_architecture()
            detected_package_type = MetadataDetector._detect_package_type(detected_platform)
            
            metadata = {
                'platform': detected_platform,
                'package_type': detected_package_type,
                'architecture': detected_architecture
            }
            
            logger.info(f"Detected runtime metadata: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error detecting metadata: {e}", exc_info=True)
            # Return safe defaults
            return {
                'platform': 'unknown',
                'package_type': 'portable',
                'architecture': 'unknown'
            }
    
    @staticmethod
    def _detect_platform() -> str:
        """
        Detect operating system platform.
        
        Returns:
            One of: windows, macos, linux, unknown
        """
        system = platform.system().lower()
        
        if system == 'windows':
            return 'windows'
        elif system == 'darwin':
            return 'macos'
        elif system == 'linux':
            return 'linux'
        else:
            logger.warning(f"Unknown platform: {system}")
            return 'unknown'
    
    @staticmethod
    def _detect_architecture() -> str:
        """
        Detect system architecture.
        
        Returns:
            One of: amd64, arm64, x86, unknown
        """
        machine = platform.machine().lower()
        
        # Map various architecture names to standard names
        if machine in ('x86_64', 'amd64'):
            return 'amd64'
        elif machine in ('arm64', 'aarch64'):
            return 'arm64'
        elif machine in ('i386', 'i686', 'x86'):
            return 'x86'
        else:
            logger.warning(f"Unknown architecture: {machine}")
            return 'unknown'
    
    @staticmethod
    def _detect_package_type(detected_platform: str) -> str:
        """
        Detect package/installation type based on platform and location.
        
        Args:
            detected_platform: The detected platform (windows, macos, linux)
            
        Returns:
            One of: installer, portable, dmg, zip, deb, unknown
        """
        try:
            if detected_platform == 'windows':
                return MetadataDetector._detect_windows_package_type()
            elif detected_platform == 'macos':
                return MetadataDetector._detect_macos_package_type()
            elif detected_platform == 'linux':
                return MetadataDetector._detect_linux_package_type()
            else:
                return 'portable'  # Safe default
                
        except Exception as e:
            logger.error(f"Error detecting package type: {e}")
            return 'portable'
    
    @staticmethod
    def _detect_windows_package_type() -> str:
        """
        Detect Windows installation type (installer vs portable).
        
        Returns:
            'installer' or 'portable'
        """
        try:
            # Check if installed via Windows installer (typically in Program Files)
            executable_path = sys.executable if getattr(sys, 'frozen', False) else __file__
            
            # Check for common installer locations
            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
            program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')
            local_app_data = os.environ.get('LOCALAPPDATA', '')
            
            if (program_files in executable_path or 
                program_files_x86 in executable_path or
                (local_app_data and local_app_data in executable_path)):
                logger.debug("Detected Windows installer installation")
                return 'installer'
            
            # Check Windows registry for installation
            try:
                import winreg
                key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\ArgoLogViewer"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ):
                    logger.debug("Found registry entry - installer installation")
                    return 'installer'
            except (ImportError, OSError):
                pass
            
            logger.debug("Detected Windows portable installation")
            return 'portable'
            
        except Exception as e:
            logger.error(f"Error detecting Windows package type: {e}")
            return 'portable'
    
    @staticmethod
    def _detect_macos_package_type() -> str:
        """
        Detect macOS installation type (DMG vs ZIP).
        
        Returns:
            'dmg' or 'zip'
        """
        try:
            # Check if running from /Applications (typical for DMG installs)
            if getattr(sys, 'frozen', False):
                executable_path = sys.executable
                bundle_path = os.path.dirname(os.path.dirname(executable_path))  # Go up from MacOS/
                
                if '/Applications/' in bundle_path:
                    logger.debug("Detected macOS DMG installation (in /Applications)")
                    return 'dmg'
                elif bundle_path.endswith('.app'):
                    # It's a .app bundle but not in /Applications
                    # Could be ZIP extract or DMG opened elsewhere
                    logger.debug("Detected macOS app bundle outside /Applications (likely ZIP)")
                    return 'zip'
            
            # Default to DMG (most common)
            logger.debug("Defaulting to DMG for macOS")
            return 'dmg'
            
        except Exception as e:
            logger.error(f"Error detecting macOS package type: {e}")
            return 'dmg'
    
    @staticmethod
    def _detect_linux_package_type() -> str:
        """
        Detect Linux installation type (DEB package vs portable).
        
        Returns:
            'deb' or 'portable'
        """
        try:
            # Check if installed via DEB package
            executable_path = sys.executable if getattr(sys, 'frozen', False) else __file__
            
            # DEB packages typically install to /usr/local/bin or /usr/bin
            if '/usr/local/bin/' in executable_path or '/usr/bin/' in executable_path:
                logger.debug("Detected Linux DEB installation")
                return 'deb'
            
            # Check dpkg database
            try:
                import subprocess
                result = subprocess.run(
                    ['dpkg', '-l', 'argologviewer'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and 'argologviewer' in result.stdout:
                    logger.debug("Found dpkg entry - DEB installation")
                    return 'deb'
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            logger.debug("Detected Linux portable installation")
            return 'portable'
            
        except Exception as e:
            logger.error(f"Error detecting Linux package type: {e}")
            return 'portable'
