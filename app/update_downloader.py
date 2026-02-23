"""
Update downloader for Argo Log Viewer with progress tracking.

Created by: Harshmeet Singh (2024-2026)
Proprietary software - See LICENSE.txt for terms.

This module handles downloading update packages with progress tracking,
checksum verification, and platform-specific installer launching.
"""
import os
import sys
import tempfile
import urllib.request
import urllib.error
import hashlib
import subprocess
import logging
import shutil
from typing import Optional, Dict
from PySide6.QtCore import QObject, Signal, QThread

logger = logging.getLogger(__name__)


def get_downloads_folder() -> str:
    """
    Get the user's Downloads folder path (cross-platform).
    
    Returns:
        Path to Downloads folder. Falls back to temp dir if not found.
    """
    try:
        if sys.platform == 'win32':
            folder = os.environ.get('USERPROFILE', '')
            if folder:
                downloads = os.path.join(folder, 'Downloads')
                if os.path.isdir(downloads):
                    return downloads
        else:
            # macOS and Linux
            downloads = os.path.expanduser('~/Downloads')
            if os.path.isdir(downloads):
                return downloads
            # Linux XDG
            xdg = os.environ.get('XDG_DOWNLOAD_DIR')
            if xdg and os.path.isdir(xdg):
                return xdg
    except Exception as e:
        logger.warning(f"Could not get Downloads folder: {e}")
    return tempfile.gettempdir()


class UpdateDownloader(QObject):
    """Downloads update packages with progress tracking."""
    
    # Signals
    progress = Signal(int, int, float)  # bytes_downloaded, total_bytes, speed_mbps
    completed = Signal(str)  # downloaded file path
    error = Signal(str)  # error message
    
    def __init__(self, url: str, file_name: str, file_size: int, download_dir: Optional[str] = None, parent=None):
        """
        Initialize update downloader.
        
        Args:
            url: URL to download from
            file_name: Name of the file
            file_size: Expected file size in bytes
            download_dir: Where to save the file. None = temp folder (for installers).
                          Pass get_downloads_folder() for portable so user keeps the file.
            parent: Parent QObject
        """
        super().__init__(parent)
        self.url = url
        self.file_name = file_name
        self.file_size = file_size
        self.download_dir = download_dir  # None = use temp
        self.cancelled = False
        self.dest_path = None
        
    def cancel(self):
        """Cancel the download."""
        self.cancelled = True
        logger.info("Download cancelled by user")
    
    def download(self):
        """
        Download the file with progress tracking.
        
        Emits progress, completed, or error signals.
        """
        try:
            # Portable → Downloads folder so user can keep the file.
            # Installer/DMG/DEB → temp folder (we run it and don't need to keep it).
            save_dir = self.download_dir if self.download_dir else tempfile.gettempdir()
            if not os.path.isdir(save_dir):
                os.makedirs(save_dir, exist_ok=True)
            
            if not self._check_disk_space(save_dir, self.file_size):
                self.error.emit(f"Insufficient disk space. Need {self.file_size / (1024*1024):.1f} MB")
                return
            
            # Create destination path
            self.dest_path = os.path.join(save_dir, self.file_name)
            logger.info(f"Downloading {self.url} to {self.dest_path}")
            
            # Download with progress
            req = urllib.request.Request(
                self.url,
                headers={'User-Agent': 'ArgoLogViewer-Updater'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                # Verify content length
                content_length = int(response.headers.get('Content-Length', 0))
                if content_length != self.file_size:
                    logger.warning(f"Content-Length mismatch: expected {self.file_size}, got {content_length}")
                
                total_bytes = content_length or self.file_size
                downloaded_bytes = 0
                chunk_size = 8192  # 8 KB chunks
                
                import time
                start_time = time.time()
                last_update_time = start_time
                last_downloaded_bytes = 0
                
                with open(self.dest_path, 'wb') as f:
                    while True:
                        if self.cancelled:
                            f.close()
                            if os.path.exists(self.dest_path):
                                os.remove(self.dest_path)
                            logger.info("Download cancelled, temp file removed")
                            return
                        
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        
                        # Calculate speed (update every 0.5 seconds)
                        current_time = time.time()
                        if current_time - last_update_time >= 0.5:
                            time_delta = current_time - last_update_time
                            bytes_delta = downloaded_bytes - last_downloaded_bytes
                            speed_mbps = (bytes_delta / time_delta) / (1024 * 1024)  # MB/s
                            
                            self.progress.emit(downloaded_bytes, total_bytes, speed_mbps)
                            
                            last_update_time = current_time
                            last_downloaded_bytes = downloaded_bytes
                
                # Final progress update
                elapsed_time = time.time() - start_time
                average_speed = (downloaded_bytes / elapsed_time) / (1024 * 1024) if elapsed_time > 0 else 0
                self.progress.emit(downloaded_bytes, total_bytes, average_speed)
                
                logger.info(f"Download complete: {downloaded_bytes} bytes in {elapsed_time:.1f}s ({average_speed:.2f} MB/s)")
                
                # Verify file size
                actual_size = os.path.getsize(self.dest_path)
                if actual_size != total_bytes:
                    self.error.emit(f"File size mismatch: expected {total_bytes}, got {actual_size}")
                    os.remove(self.dest_path)
                    return
                
                self.completed.emit(self.dest_path)
                
        except urllib.error.URLError as e:
            logger.error(f"Network error during download: {e}")
            self.error.emit(f"Network error: {str(e)}")
            if self.dest_path and os.path.exists(self.dest_path):
                os.remove(self.dest_path)
        
        except Exception as e:
            logger.error(f"Error downloading update: {e}", exc_info=True)
            self.error.emit(f"Download error: {str(e)}")
            if self.dest_path and os.path.exists(self.dest_path):
                os.remove(self.dest_path)
    
    @staticmethod
    def _check_disk_space(path: str, required_bytes: int) -> bool:
        """
        Check if there's enough disk space.
        
        Args:
            path: Directory path to check
            required_bytes: Required space in bytes
            
        Returns:
            True if enough space available
        """
        try:
            if sys.platform == 'win32':
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(path),
                    None,
                    None,
                    ctypes.pointer(free_bytes)
                )
                available = free_bytes.value
            else:
                stat = os.statvfs(path)
                available = stat.f_bavail * stat.f_frsize
            
            # Add 10 MB buffer
            required_with_buffer = required_bytes + (10 * 1024 * 1024)
            
            logger.debug(f"Disk space check: {available / (1024*1024):.1f} MB available, {required_with_buffer / (1024*1024):.1f} MB required")
            return available >= required_with_buffer
            
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return True  # Assume it's okay if we can't check
    
    @staticmethod
    def verify_checksum(file_path: str, expected_checksum: str) -> bool:
        """
        Verify file SHA-256 checksum.
        
        Args:
            file_path: Path to file
            expected_checksum: Expected SHA-256 hash (hex string)
            
        Returns:
            True if checksum matches
        """
        try:
            logger.info(f"Verifying checksum for {file_path}")
            
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            
            calculated = sha256_hash.hexdigest().lower()
            expected = expected_checksum.lower().strip()
            
            if calculated == expected:
                logger.info("✓ Checksum verification passed")
                return True
            else:
                logger.error(f"✗ Checksum mismatch! Expected: {expected}, Got: {calculated}")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying checksum: {e}")
            return False
    
    @staticmethod
    def download_checksums(checksum_url: str) -> Optional[Dict[str, str]]:
        """
        Download and parse CHECKSUMS.txt file.
        
        Args:
            checksum_url: URL to CHECKSUMS.txt
            
        Returns:
            Dictionary mapping filenames to their SHA-256 hashes
        """
        try:
            logger.info(f"Downloading checksums from {checksum_url}")
            
            req = urllib.request.Request(
                checksum_url,
                headers={'User-Agent': 'ArgoLogViewer-Updater'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8')
            
            # Parse checksums (format: "hash  filename")
            checksums = {}
            for line in content.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 2:
                    hash_value = parts[0]
                    filename = ' '.join(parts[1:])  # Handle filenames with spaces
                    checksums[filename] = hash_value
            
            logger.info(f"Loaded {len(checksums)} checksums")
            return checksums
            
        except Exception as e:
            logger.error(f"Error downloading checksums: {e}")
            return None


class UpdateDownloaderThread(QThread):
    """Thread wrapper for UpdateDownloader."""
    
    progress = Signal(int, int, float)
    completed = Signal(str)
    error = Signal(str)
    
    def __init__(self, url: str, file_name: str, file_size: int, download_dir: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.downloader = UpdateDownloader(url, file_name, file_size, download_dir=download_dir)
        
        # Connect signals
        self.downloader.progress.connect(self.progress.emit)
        self.downloader.completed.connect(self.completed.emit)
        self.downloader.error.connect(self.error.emit)
    
    def run(self):
        """Run the download."""
        self.downloader.download()
    
    def cancel(self):
        """Cancel the download."""
        self.downloader.cancel()


class InstallerLauncher:
    """Platform-specific installer launcher."""
    
    @staticmethod
    def launch(file_path: str, metadata: dict) -> Dict[str, any]:
        """
        Launch installer or prepare installation based on platform.
        
        Args:
            file_path: Path to downloaded file
            metadata: Installation metadata (platform, package_type)
            
        Returns:
            Dictionary with keys:
            - success: bool
            - action: str ('launched', 'prepared', 'instructions_shown')
            - message: str (user-facing message)
            - needs_manual: bool (requires manual steps)
        """
        platform = metadata.get('platform', '').lower()
        package_type = metadata.get('package_type', '').lower()
        
        try:
            if platform == 'windows':
                return InstallerLauncher._launch_windows(file_path, package_type)
            elif platform == 'macos':
                return InstallerLauncher._launch_macos(file_path, package_type)
            elif platform == 'linux':
                return InstallerLauncher._launch_linux(file_path, package_type)
            else:
                return {
                    'success': False,
                    'action': 'error',
                    'message': f'Unsupported platform: {platform}',
                    'needs_manual': True
                }
                
        except Exception as e:
            logger.error(f"Error launching installer: {e}", exc_info=True)
            return {
                'success': False,
                'action': 'error',
                'message': f'Error: {str(e)}',
                'needs_manual': True
            }
    
    @staticmethod
    def _launch_windows(file_path: str, package_type: str) -> Dict[str, any]:
        """
        Launch Windows installer or show portable instructions.
        
        Args:
            file_path: Path to .exe file
            package_type: 'installer' or 'portable'
            
        Returns:
            Result dictionary
        """
        if package_type == 'installer':
            try:
                logger.info(f"Launching Windows installer: {file_path}")
                # Launch installer (it will run after this app closes)
                subprocess.Popen([file_path], shell=False)
                
                return {
                    'success': True,
                    'action': 'launched',
                    'message': '✓ Installer launched successfully!\n\n'
                              'The installer will open when you close this app.\n\n'
                              'Click OK to close Argo Log Viewer and complete the update.',
                    'needs_manual': False
                }
                
            except Exception as e:
                logger.error(f"Error launching Windows installer: {e}")
                return {
                    'success': False,
                    'action': 'error',
                    'message': f'Could not launch installer automatically.\n\n'
                              f'Error: {str(e)}\n\n'
                              f'Please run manually:\n{file_path}',
                    'needs_manual': True
                }
        
        else:  # portable
            return {
                'success': True,
                'action': 'prepared',
                'message': f'✓ Update downloaded successfully!\n\n'
                          f'Location:\n{file_path}\n\n'
                          f'To update:\n'
                          f'1. Close this application\n'
                          f'2. Replace your old ArgoLogViewer.exe with the new one\n'
                          f'3. Run the new version\n\n'
                          f'The file is in your Downloads folder.',
                'needs_manual': True
            }
    
    @staticmethod
    def _launch_macos(file_path: str, package_type: str) -> Dict[str, any]:
        """
        Prepare macOS installation (DMG mount or ZIP extract).
        
        Args:
            file_path: Path to .dmg or .zip file
            package_type: 'dmg' or 'zip'
            
        Returns:
            Result dictionary
        """
        try:
            if package_type == 'dmg':
                logger.info(f"Preparing macOS DMG: {file_path}")
                
                # Remove quarantine attribute
                try:
                    subprocess.run(['xattr', '-cr', file_path], check=False, capture_output=True)
                    logger.info("Removed quarantine attribute from DMG")
                except Exception as e:
                    logger.warning(f"Could not remove quarantine: {e}")
                
                # Mount DMG
                try:
                    result = subprocess.run(
                        ['hdiutil', 'attach', file_path],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    logger.info(f"DMG mounted successfully")
                    
                    # Find mount point (usually /Volumes/Argo Log Viewer...)
                    mount_point = None
                    for line in result.stdout.split('\n'):
                        if '/Volumes/' in line:
                            parts = line.split('/Volumes/')
                            if len(parts) > 1:
                                mount_point = '/Volumes/' + parts[1].strip()
                                break
                    
                    # Open Finder to mounted volume
                    if mount_point:
                        subprocess.run(['open', mount_point], check=False)
                    
                except Exception as e:
                    logger.error(f"Error mounting DMG: {e}")
                    return {
                        'success': False,
                        'action': 'error',
                        'message': f'Could not mount DMG: {str(e)}\n\nPlease open manually: {file_path}',
                        'needs_manual': True
                    }
                
                return {
                    'success': True,
                    'action': 'prepared',
                    'message': f'✓ Update downloaded and prepared!\n\n'
                              f'The DMG has been mounted and is ready to install.\n\n'
                              f'To complete installation:\n\n'
                              f'1. Click OK to close this app\n'
                              f'2. Drag ArgoLogViewer to Applications folder (replace the old version)\n'
                              f'3. Open System Settings → Privacy & Security\n'
                              f'4. Scroll down and click "Open Anyway"\n'
                              f'5. Confirm by clicking "Open"\n\n'
                              f'(Same steps as when you first installed the app!)\n\n'
                              f'DMG Location: {file_path}',
                    'needs_manual': True
                }
            
            elif package_type == 'zip':
                logger.info(f"Preparing macOS ZIP: {file_path}")
                
                # Extract ZIP
                extract_dir = os.path.join(tempfile.gettempdir(), 'ArgoLogViewer_Update')
                os.makedirs(extract_dir, exist_ok=True)
                
                try:
                    shutil.unpack_archive(file_path, extract_dir)
                    logger.info(f"ZIP extracted to {extract_dir}")
                    
                    # Find .app bundle
                    app_path = None
                    for item in os.listdir(extract_dir):
                        if item.endswith('.app'):
                            app_path = os.path.join(extract_dir, item)
                            break
                    
                    if app_path:
                        # Remove quarantine
                        try:
                            subprocess.run(['xattr', '-cr', app_path], check=False, capture_output=True)
                            logger.info("Removed quarantine attribute from app")
                        except Exception as e:
                            logger.warning(f"Could not remove quarantine: {e}")
                        
                        # Open Finder to location
                        subprocess.run(['open', '-R', app_path], check=False)
                    
                except Exception as e:
                    logger.error(f"Error extracting ZIP: {e}")
                    return {
                        'success': False,
                        'action': 'error',
                        'message': f'Could not extract ZIP: {str(e)}\n\nPlease extract manually: {file_path}',
                        'needs_manual': True
                    }
                
                return {
                    'success': True,
                    'action': 'prepared',
                    'message': f'✓ Update downloaded and extracted!\n\n'
                              f'The app bundle has been extracted and is ready to install.\n\n'
                              f'To complete installation:\n\n'
                              f'1. Click OK to close this app\n'
                              f'2. Move ArgoLogViewer.app to your Applications folder\n'
                              f'3. Open System Settings → Privacy & Security\n'
                              f'4. Scroll down and click "Open Anyway"\n'
                              f'5. Confirm by clicking "Open"\n\n'
                              f'(Same steps as when you first installed the app!)\n\n'
                              f'The file is in your Downloads folder:\n{extract_dir}',
                    'needs_manual': True
                }
            
        except Exception as e:
            logger.error(f"Error preparing macOS update: {e}", exc_info=True)
            return {
                'success': False,
                'action': 'error',
                'message': f'Error preparing update: {str(e)}',
                'needs_manual': True
            }
    
    @staticmethod
    def _launch_linux(file_path: str, package_type: str) -> Dict[str, any]:
        """
        Prepare Linux installation (DEB or portable).
        
        Args:
            file_path: Path to .deb or binary file
            package_type: 'deb' or 'portable'
            
        Returns:
            Result dictionary
        """
        if package_type == 'deb':
            # Try to launch graphical package installer if available
            install_cmd = None
            
            # Try pkexec (graphical sudo prompt)
            if shutil.which('pkexec'):
                install_cmd = ['pkexec', 'dpkg', '-i', file_path]
            
            if install_cmd:
                try:
                    logger.info(f"Launching DEB installer: {' '.join(install_cmd)}")
                    subprocess.Popen(install_cmd)
                    
                    return {
                        'success': True,
                        'action': 'launched',
                        'message': '✓ Package installer launched!\n\n'
                                  'A graphical password prompt will appear.\n'
                                  'Enter your password to complete the installation.\n\n'
                                  'Click OK to close Argo Log Viewer.',
                        'needs_manual': False
                    }
                    
                except Exception as e:
                    logger.warning(f"Could not launch graphical installer: {e}")
            
            # Fall back to showing command
            return {
                'success': True,
                'action': 'prepared',
                'message': f'✓ Update downloaded to Downloads folder!\n\n'
                          f'Run this command in terminal to install:\n\n'
                          f'sudo dpkg -i {file_path}\n\n'
                          f'Or:\n'
                          f'• Click "Copy Command" below\n'
                          f'• Open a terminal\n'
                          f'• Paste and press Enter\n'
                          f'• Enter your password when prompted\n\n'
                          f'Alternatively, you can navigate to Downloads\n'
                          f'and double-click the .deb file to install graphically.',
                'needs_manual': True,
                'install_command': f'sudo dpkg -i {file_path}'
            }
        
        else:  # portable
            return {
                'success': True,
                'action': 'prepared',
                'message': f'✓ Update downloaded successfully!\n\n'
                          f'Location:\n{file_path}\n\n'
                          f'To update:\n\n'
                          f'1. Open a terminal in your Downloads folder\n'
                          f'2. Make executable:\n'
                          f'   chmod +x {os.path.basename(file_path)}\n'
                          f'3. Replace your old binary with this one\n'
                          f'4. Run the new version\n\n'
                          f'The file is in your Downloads folder.',
                'needs_manual': True
            }

