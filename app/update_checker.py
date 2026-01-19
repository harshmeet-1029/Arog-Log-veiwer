"""
OTA (Over-The-Air) Update Checker for Argo Log Viewer.

Created by: Harshmeet Singh (2024-2026)
Proprietary software - See LICENSE.txt for terms.

This module handles checking for application updates from a remote server.
"""
import json
import logging
import urllib.request
import urllib.error
import os
import sys
import platform
import tempfile
import subprocess
from typing import Optional, Dict, Any
from packaging import version
from app.config import UpdateConfig, AppConfig

logger = logging.getLogger(__name__)


class UpdateInfo:
    """Information about an available update."""
    
    def __init__(self, version: str, download_url: str, release_notes: str, is_critical: bool = False, 
                 asset_name: str = None, asset_url: str = None):
        """
        Initialize update information.
        
        Args:
            version: Version string (e.g., "1.1.0")
            download_url: URL to download page (GitHub releases)
            release_notes: Release notes/changelog
            is_critical: Whether this is a critical security update
            asset_name: Name of the downloadable asset for this OS
            asset_url: Direct download URL for the asset
        """
        self.version = version
        self.download_url = download_url
        self.release_notes = release_notes
        self.is_critical = is_critical
        self.asset_name = asset_name
        self.asset_url = asset_url
    
    def __repr__(self):
        return f"UpdateInfo(version={self.version}, is_critical={self.is_critical}, asset={self.asset_name})"


class UpdateDownloader:
    """Handles downloading and installing updates."""
    
    @staticmethod
    def get_current_os() -> str:
        """
        Detect current operating system.
        
        Returns:
            'windows', 'macos', or 'linux'
        """
        system = platform.system().lower()
        if system == 'darwin':
            return 'macos'
        elif system == 'windows':
            return 'windows'
        else:
            return 'linux'
    
    @staticmethod
    def is_running_portable() -> bool:
        """
        Detect if currently running as portable version.
        
        Returns:
            True if portable, False if installed version
        """
        current_os = UpdateDownloader.get_current_os()
        
        if current_os == 'windows':
            # Installer: Runs from "C:\Program Files\Argo Log Viewer\..."
            # Portable: Runs from anywhere else (Downloads, Desktop, etc.)
            exe_path = sys.executable.lower()
            
            # Check if running from Program Files (installer)
            if 'program files' in exe_path or 'program files (x86)' in exe_path:
                logger.info("Detected: Installed version (Program Files)")
                return False
            
            # Check if filename contains "portable"
            if 'portable' in exe_path:
                logger.info("Detected: Portable version (filename contains 'portable')")
                return True
            
            # If not in Program Files and not explicitly portable, assume portable
            logger.info(f"Detected: Portable version (not in Program Files): {exe_path}")
            return True
        
        elif current_os == 'linux':
            # Installer (.deb): Runs from /usr/local/bin/ or /usr/bin/
            # Portable: Runs from anywhere else
            exe_path = sys.executable.lower()
            
            if exe_path.startswith('/usr/local/bin/') or exe_path.startswith('/usr/bin/'):
                logger.info("Detected: Installed version (system bin directory)")
                return False
            
            # Check if filename contains "portable"
            if 'portable' in exe_path:
                logger.info("Detected: Portable version (filename contains 'portable')")
                return True
            
            logger.info(f"Detected: Portable version (not in system directories): {exe_path}")
            return True
        
        elif current_os == 'macos':
            # macOS always installs to /Applications - no portable version
            return False
        
        return False
    
    @staticmethod
    def get_asset_for_os(assets: list) -> Optional[Dict[str, str]]:
        """
        Find the correct asset for current OS from GitHub release assets.
        Automatically detects if user is running portable or installer version
        and downloads the matching format.
        
        Args:
            assets: List of asset dictionaries from GitHub API
            
        Returns:
            Dict with 'name' and 'browser_download_url' or None
        """
        current_os = UpdateDownloader.get_current_os()
        is_portable = UpdateDownloader.is_running_portable()
        
        logger.info(f"Finding asset for OS: {current_os}, Portable: {is_portable}")
        
        for asset in assets:
            name = asset.get('name', '').lower()
            
            # Windows: Match current version type (portable vs installer)
            if current_os == 'windows':
                if is_portable and 'portable.exe' in name and name.endswith('.exe'):
                    logger.info(f"Selected portable version: {asset['name']}")
                    return {
                        'name': asset['name'],
                        'url': asset['browser_download_url']
                    }
                elif not is_portable and 'installer.exe' in name and name.endswith('.exe'):
                    logger.info(f"Selected installer version: {asset['name']}")
                    return {
                        'name': asset['name'],
                        'url': asset['browser_download_url']
                    }
            
            # macOS: Always .dmg (no portable version)
            elif current_os == 'macos':
                if '.dmg' in name and name.endswith('.dmg'):
                    logger.info(f"Selected macOS DMG: {asset['name']}")
                    return {
                        'name': asset['name'],
                        'url': asset['browser_download_url']
                    }
            
            # Linux: Match current version type (portable vs .deb)
            elif current_os == 'linux':
                if is_portable and 'portable' in name and not name.endswith('.deb'):
                    logger.info(f"Selected portable binary: {asset['name']}")
                    return {
                        'name': asset['name'],
                        'url': asset['browser_download_url']
                    }
                elif not is_portable and 'installer.deb' in name and name.endswith('.deb'):
                    logger.info(f"Selected DEB package: {asset['name']}")
                    return {
                        'name': asset['name'],
                        'url': asset['browser_download_url']
                    }
        
        # Fallback: If exact match not found, try alternative formats
        logger.warning(f"Exact match not found, trying fallback for {current_os}")
        
        for asset in assets:
            name = asset.get('name', '').lower()
            
            if current_os == 'windows' and '.exe' in name and name.endswith('.exe'):
                logger.info(f"Fallback: Selected Windows exe: {asset['name']}")
                return {
                    'name': asset['name'],
                    'url': asset['browser_download_url']
                }
            elif current_os == 'macos' and '.zip' in name and name.endswith('.zip'):
                logger.info(f"Fallback: Selected macOS ZIP: {asset['name']}")
                return {
                    'name': asset['name'],
                    'url': asset['browser_download_url']
                }
            elif current_os == 'linux' and ('portable' in name or '.deb' in name):
                logger.info(f"Fallback: Selected Linux package: {asset['name']}")
                return {
                    'name': asset['name'],
                    'url': asset['browser_download_url']
                }
        
        logger.error(f"No compatible asset found for {current_os}")
        return None
    
    @staticmethod
    def download_update(download_url: str, progress_callback=None) -> Optional[str]:
        """
        Download update file.
        
        Args:
            download_url: URL to download from
            progress_callback: Optional callback(bytes_downloaded, total_bytes)
            
        Returns:
            Path to downloaded file or None on failure
        """
        try:
            # Create temp directory for download
            temp_dir = tempfile.gettempdir()
            
            # Extract filename from URL
            filename = download_url.split('/')[-1]
            filepath = os.path.join(temp_dir, filename)
            
            logger.info(f"Downloading update to: {filepath}")
            
            # Download with progress
            req = urllib.request.Request(
                download_url,
                headers={'User-Agent': 'ArgoLogViewer-Updater'}
            )
            
            with urllib.request.urlopen(req, timeout=300) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                
                with open(filepath, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)
            
            logger.info(f"Download complete: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error downloading update: {e}", exc_info=True)
            return None
    
    @staticmethod
    def install_update(filepath: str) -> bool:
        """
        Install the downloaded update.
        
        Args:
            filepath: Path to downloaded installer
            
        Returns:
            True if installation started successfully
        """
        try:
            current_os = UpdateDownloader.get_current_os()
            
            logger.info(f"Installing update from: {filepath}")
            
            if current_os == 'windows':
                # Windows: Launch .exe installer
                if filepath.endswith('.exe'):
                    # Launch installer and exit current app
                    subprocess.Popen([filepath])
                    return True
            
            elif current_os == 'macos':
                # macOS: Cannot auto-install due to Gatekeeper (unsigned app)
                # User must manually install with Gatekeeper bypass
                logger.info("macOS detected - manual installation required due to Gatekeeper")
                return False  # Return False to show manual instructions
            
            elif current_os == 'linux':
                # Linux: Open with system default application
                # For .deb files, this typically opens the software center
                # For portable binaries, we just make them executable
                if filepath.endswith('.deb'):
                    # Open with default handler (usually Software Center/GDebi)
                    subprocess.Popen(['xdg-open', filepath])
                    return True
                else:
                    # Portable binary - just make it executable
                    os.chmod(filepath, 0o755)
                    logger.info(f"Made portable binary executable: {filepath}")
                    return False  # Return False to show manual instructions
            
            logger.warning(f"Unsupported installer format: {filepath}")
            return False
            
        except Exception as e:
            logger.error(f"Error installing update: {e}", exc_info=True)
            return False


class UpdateChecker:
    """Handles checking for application updates."""
    
    @staticmethod
    def check_for_updates(timeout: float = 10.0) -> Optional[UpdateInfo]:
        """
        Check if a newer version is available.
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            UpdateInfo if update is available, None otherwise
        """
        try:
            current_ver = UpdateConfig.get_current_version()
            server_url = UpdateConfig.get_update_server_url()
            
            logger.info(f"Checking for updates (current version: {current_ver})")
            logger.debug(f"Update server: {server_url}")
            
            # Make HTTP request to update server
            req = urllib.request.Request(
                server_url,
                headers={'User-Agent': f'ArgoLogViewer/{current_ver}'}
            )
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    logger.warning(f"Update check failed with status: {response.status}")
                    return None
                
                data = json.loads(response.read().decode('utf-8'))
                logger.debug(f"Update server response: {data}")
                
                # Parse response based on server type
                update_info = UpdateChecker._parse_update_response(data)
                
                if update_info is None:
                    logger.info("No update information available from server")
                    return None
                
                # Check if version is newer
                if UpdateChecker._is_newer_version(update_info.version, current_ver):
                    logger.info(f"Update available: {update_info.version}")
                    
                    # Check if user has skipped this version
                    skip_version = AppConfig.get_skip_version()
                    if skip_version == update_info.version and not update_info.is_critical:
                        logger.info(f"User has skipped version {skip_version}")
                        return None
                    
                    return update_info
                else:
                    logger.info("Application is up to date")
                    return None
                    
        except urllib.error.URLError as e:
            logger.warning(f"Network error checking for updates: {e}")
            return None
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from update server: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error checking for updates: {e}", exc_info=True)
            return None
    
    @staticmethod
    def _parse_update_response(data: Dict[str, Any]) -> Optional[UpdateInfo]:
        """
        Parse update server response.
        
        Supports GitHub Releases API format and custom format.
        
        Args:
            data: JSON response from server
            
        Returns:
            UpdateInfo or None if parsing fails
        """
        try:
            # GitHub Releases API format
            if 'tag_name' in data:
                version_str = data['tag_name'].lstrip('v')  # Remove 'v' prefix if present
                download_url = data.get('html_url', '')  # GitHub releases page
                
                release_notes = data.get('body', 'No release notes available')
                is_critical = 'critical' in data.get('name', '').lower() or 'security' in release_notes.lower()
                
                # Find the correct asset for current OS
                assets = data.get('assets', [])
                asset_info = UpdateDownloader.get_asset_for_os(assets)
                
                if asset_info:
                    logger.info(f"Found asset for current OS: {asset_info['name']}")
                    return UpdateInfo(
                        version=version_str,
                        download_url=download_url,
                        release_notes=release_notes,
                        is_critical=is_critical,
                        asset_name=asset_info['name'],
                        asset_url=asset_info['url']
                    )
                else:
                    logger.warning("No asset found for current OS")
                    # Still return update info but without asset
                    return UpdateInfo(
                        version=version_str,
                        download_url=download_url,
                        release_notes=release_notes,
                        is_critical=is_critical
                    )
            
            # Custom format
            elif 'version' in data:
                return UpdateInfo(
                    version=data['version'],
                    download_url=data.get('download_url', ''),
                    release_notes=data.get('release_notes', 'No release notes available'),
                    is_critical=data.get('is_critical', False)
                )
            
            logger.warning("Update response format not recognized")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing update response: {e}")
            return None
    
    @staticmethod
    def _is_newer_version(remote_version: str, current_version: str) -> bool:
        """
        Compare version strings.
        
        Args:
            remote_version: Version from update server
            current_version: Current application version
            
        Returns:
            True if remote version is newer
        """
        try:
            return version.parse(remote_version) > version.parse(current_version)
        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            return False
    
    @staticmethod
    def mark_update_checked() -> None:
        """Mark that we've checked for updates (updates timestamp)."""
        import time
        AppConfig.set_last_update_check(time.time())
        logger.debug("Marked update check timestamp")
