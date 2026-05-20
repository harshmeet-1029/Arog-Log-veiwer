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
                
                # Create a batch script that waits for this app to close, then launches installer
                batch_script = os.path.join(os.path.dirname(file_path), 'launch_installer.bat')
                with open(batch_script, 'w') as f:
                    f.write(f'''@echo off
timeout /t 2 /nobreak >nul
start "" "{file_path}"
del "%~f0"
''')
                
                # Launch the batch script (will wait 2 seconds, then launch installer)
                subprocess.Popen([batch_script], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
                
                return {
                    'success': True,
                    'action': 'launched',
                    'message': 'Installer will launch in 2 seconds...',
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
    def _get_current_app_path() -> Optional[str]:
        """
        Return the path to the running .app bundle, e.g. /Applications/ArgoLogViewer.app
        Returns None if not running as a frozen .app.
        """
        if not getattr(sys, 'frozen', False):
            return None
        exe = sys.executable  # …/ArgoLogViewer.app/Contents/MacOS/ArgoLogViewer-Installer
        marker = '.app/Contents/MacOS/'
        idx = exe.find(marker)
        if idx == -1:
            return None
        return exe[:idx + 4]  # up to and including ".app"

    @staticmethod
    def _launch_macos(file_path: str, package_type: str) -> Dict[str, any]:
        """
        Auto-install macOS update via a background shell script.

        DMG flow: mount → copy .app over current install → unmount → relaunch
        ZIP flow: extract → copy .app over current install → relaunch

        If the current install path cannot be determined we fall back to
        opening Finder so the user can drag manually.
        """
        try:
            current_app = InstallerLauncher._get_current_app_path()
            logger.info(f"Current .app path: {current_app}")

            if package_type == 'dmg':
                logger.info(f"Preparing macOS DMG: {file_path}")

                # Strip quarantine from the DMG itself
                subprocess.run(['xattr', '-cr', file_path], check=False, capture_output=True)

                # Mount silently (-nobrowse keeps Finder from popping open)
                try:
                    result = subprocess.run(
                        ['hdiutil', 'attach', file_path, '-nobrowse'],
                        capture_output=True, text=True, check=True
                    )
                except Exception as e:
                    logger.error(f"Error mounting DMG: {e}")
                    return {
                        'success': False,
                        'action': 'error',
                        'message': f'Could not mount DMG: {str(e)}\n\nPlease open manually:\n{file_path}',
                        'needs_manual': True
                    }

                # Parse mount point from hdiutil output
                mount_point = None
                for line in result.stdout.split('\n'):
                    if '/Volumes/' in line:
                        mount_point = '/Volumes/' + line.split('/Volumes/')[-1].strip()
                        break
                logger.info(f"DMG mounted at: {mount_point}")

                # Find .app inside the DMG
                app_in_dmg = None
                if mount_point and os.path.isdir(mount_point):
                    for item in os.listdir(mount_point):
                        if item.endswith('.app'):
                            app_in_dmg = os.path.join(mount_point, item)
                            break

                if app_in_dmg and current_app:
                    # --- AUTOMATIC INSTALL ---
                    # Write a background script: wait for app to quit → replace → relaunch.
                    # sleep 3 gives the app enough time to close completely before we
                    # delete and replace the bundle.
                    script_path = '/tmp/argo_macos_update.sh'
                    with open(script_path, 'w') as f:
                        f.write(f"""#!/bin/bash
sleep 3

rm -rf "{current_app}"
cp -R "{app_in_dmg}" "{current_app}"

# Strip quarantine so macOS doesn't block the relaunch
xattr -cr "{current_app}" 2>/dev/null || true

# Unmount DMG and clean up
hdiutil detach "{mount_point}" -quiet 2>/dev/null || true
rm -f "{file_path}"
rm -f "$0"

open "{current_app}"
""")
                    os.chmod(script_path, 0o755)
                    subprocess.Popen(['bash', script_path])

                    # No 'message' key - _install_update will quit immediately
                    # without showing a dialog, so the 3-second window is safe.
                    return {
                        'success': True,
                        'action': 'launched',
                        'needs_manual': False
                    }

                else:
                    # Fallback: open Finder so user can drag manually
                    if mount_point:
                        subprocess.run(['open', mount_point], check=False)
                    return {
                        'success': True,
                        'action': 'prepared',
                        'message': (
                            'The update DMG has been mounted.\n\n'
                            'To complete the update:\n'
                            '1. Click OK to close this app\n'
                            '2. Drag ArgoLogViewer.app to your Applications folder\n'
                            '   (click Replace when asked)\n\n'
                            f'DMG location: {file_path}'
                        ),
                        'needs_manual': True
                    }

            elif package_type == 'zip':
                logger.info(f"Preparing macOS ZIP: {file_path}")

                extract_dir = os.path.join(tempfile.gettempdir(), 'ArgoLogViewer_Update')
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir)
                os.makedirs(extract_dir)

                try:
                    shutil.unpack_archive(file_path, extract_dir)
                    logger.info(f"ZIP extracted to {extract_dir}")
                except Exception as e:
                    logger.error(f"Error extracting ZIP: {e}")
                    return {
                        'success': False,
                        'action': 'error',
                        'message': f'Could not extract ZIP: {str(e)}\n\nPlease extract manually:\n{file_path}',
                        'needs_manual': True
                    }

                # Find .app inside the extracted folder
                app_in_zip = None
                for item in os.listdir(extract_dir):
                    if item.endswith('.app'):
                        app_in_zip = os.path.join(extract_dir, item)
                        break

                if app_in_zip and current_app:
                    # --- AUTOMATIC INSTALL ---
                    script_path = '/tmp/argo_macos_update.sh'
                    with open(script_path, 'w') as f:
                        f.write(f"""#!/bin/bash
sleep 3

rm -rf "{current_app}"
cp -R "{app_in_zip}" "{current_app}"
xattr -cr "{current_app}" 2>/dev/null || true

rm -rf "{extract_dir}"
rm -f "{file_path}"
rm -f "$0"

open "{current_app}"
""")
                    os.chmod(script_path, 0o755)
                    subprocess.Popen(['bash', script_path])

                    return {
                        'success': True,
                        'action': 'launched',
                        'needs_manual': False
                    }

                else:
                    # Fallback: open Finder at extract location
                    if app_in_zip:
                        subprocess.run(['open', '-R', app_in_zip], check=False)
                    return {
                        'success': True,
                        'action': 'prepared',
                        'message': (
                            'The update has been extracted.\n\n'
                            'To complete the update:\n'
                            '1. Click OK to close this app\n'
                            '2. Move the new ArgoLogViewer.app to replace the old one\n\n'
                            f'Extracted to: {extract_dir}'
                        ),
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
            # Write terminal install script (used by pkexec and terminal fallback)
            terminal_script = '/tmp/argo_deb_terminal.sh'
            with open(terminal_script, 'w') as f:
                f.write(f"""#!/bin/bash
echo "Installing Argo Log Viewer update..."
sudo dpkg -i "{file_path}"
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    rm -f "{file_path}"
    echo ""
    echo "Installation complete! You can close this window."
else
    echo ""
    echo "Installation failed (exit code $EXIT_CODE). Try: sudo dpkg -i {file_path}"
fi
rm -f "$0"
read -p "Press Enter to close..."
""")
            os.chmod(terminal_script, 0o755)

            # 1. Try pkexec (native Linux with polkit/GUI)
            if shutil.which('pkexec'):
                try:
                    logger.info(f"Trying pkexec for DEB install: {file_path}")
                    pkexec_script = '/tmp/argo_deb_pkexec.sh'
                    with open(pkexec_script, 'w') as f:
                        f.write(f"""#!/bin/bash
pkexec dpkg -i "{file_path}"
rm -f "{file_path}"
rm -f "$0"
""")
                    os.chmod(pkexec_script, 0o755)
                    subprocess.Popen(['bash', pkexec_script])
                    return {
                        'success': True,
                        'action': 'launched',
                        'needs_manual': False
                    }
                except Exception as e:
                    logger.warning(f"pkexec failed: {e}")

            # 2. Try opening a terminal emulator (works in WSL GUI, GNOME, KDE, etc.)
            terminal_candidates = [
                ['x-terminal-emulator', '-e', f'bash {terminal_script}'],
                ['gnome-terminal', '--', 'bash', terminal_script],
                ['xfce4-terminal', '-e', f'bash {terminal_script}'],
                ['konsole', '-e', f'bash {terminal_script}'],
                ['xterm', '-e', f'bash {terminal_script}'],
                ['lxterminal', '-e', f'bash {terminal_script}'],
            ]
            for cmd in terminal_candidates:
                if shutil.which(cmd[0]):
                    try:
                        logger.info(f"Opening terminal {cmd[0]} for DEB install")
                        subprocess.Popen(cmd)
                        return {
                            'success': True,
                            'action': 'launched',
                            'needs_manual': False,
                            'message': 'A terminal window will open to install the update.\n\nEnter your password when prompted.\nThe .deb file will be deleted automatically.'
                        }
                    except Exception as e:
                        logger.warning(f"Terminal {cmd[0]} failed: {e}")

            # 3. Last resort - show manual command
            return {
                'success': True,
                'action': 'prepared',
                'message': f'Update downloaded to your Downloads folder.\n\n'
                          f'Run this command in a terminal to install:\n\n'
                          f'sudo dpkg -i {file_path}\n\n'
                          f'After installing, you can delete the .deb file.',
                'needs_manual': True,
                'install_command': f'sudo dpkg -i "{file_path}"'
            }
        
        else:  # portable
            # chmod +x automatically
            try:
                import stat as stat_module
                current_perms = os.stat(file_path).st_mode
                os.chmod(file_path, current_perms | stat_module.S_IEXEC | stat_module.S_IXGRP | stat_module.S_IXOTH)
                logger.info(f"Made portable binary executable: {file_path}")
            except Exception as e:
                logger.warning(f"Could not chmod: {e}")

            import sys
            file_name = os.path.basename(file_path)
            current_exe = sys.executable

            # Check if the current binary is in a stable system path
            stable_prefixes = ('/usr/', '/opt/', '/bin/', '/sbin/')
            home_bin_prefixes = (
                os.path.expanduser('~/bin/'),
                os.path.expanduser('~/.local/bin/'),
            )
            all_stable = stable_prefixes + home_bin_prefixes
            in_stable_path = any(current_exe.startswith(p) for p in all_stable)

            if in_stable_path:
                # User has the binary installed in a proper location -
                # tell them to replace it there so the app launcher icon keeps working
                return {
                    'success': True,
                    'action': 'prepared',
                    'message': f'Update downloaded to:\n{file_path}\n\n'
                              f'You are running from a system path:\n{current_exe}\n\n'
                              f'To update and keep your app launcher icon working,\n'
                              f'replace the old binary with the new one:\n\n'
                              f'  sudo mv "{file_path}" "{current_exe}"\n'
                              f'  sudo chmod +x "{current_exe}"\n\n'
                              f'Then relaunch the app from your usual location.',
                    'needs_manual': True,
                    'install_command': f'sudo mv "{file_path}" "{current_exe}" && sudo chmod +x "{current_exe}"'
                }
            else:
                # Running from Downloads or a temp location - just tell them to run it
                return {
                    'success': True,
                    'action': 'prepared',
                    'message': f'Update downloaded to:\n{file_path}\n\n'
                              f'How to run it:\n\n'
                              f'Option A - Terminal (recommended):\n'
                              f'  cd ~/Downloads\n'
                              f'  chmod +x {file_name}\n'
                              f'  ./{file_name}\n\n'
                              f'Option B - File Manager:\n'
                              f'  Right-click the file\n'
                              f'  Properties > Permissions\n'
                              f'  Check "Allow executing as program"\n'
                              f'  Then double-click to launch',
                    'needs_manual': True
                }

