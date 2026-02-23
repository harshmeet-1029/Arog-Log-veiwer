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
from typing import Optional, Dict, Any
from packaging import version
from app.config import UpdateConfig, AppConfig

logger = logging.getLogger(__name__)


class UpdateInfo:
    """Information about an available update."""
    
    def __init__(self, version: str, download_url: str, release_notes: str, is_critical: bool = False,
                 asset_url: Optional[str] = None, file_size: Optional[int] = None, 
                 file_name: Optional[str] = None, checksum_url: Optional[str] = None):
        """
        Initialize update information.
        
        Args:
            version: Version string (e.g., "1.1.0")
            download_url: URL to releases page (for browser fallback)
            release_notes: Release notes/changelog
            is_critical: Whether this is a critical security update
            asset_url: Direct download URL for the specific asset (NEW)
            file_size: Size of the file in bytes (NEW)
            file_name: Name of the file (NEW)
            checksum_url: URL to CHECKSUMS.txt file (NEW)
        """
        self.version = version
        self.download_url = download_url
        self.release_notes = release_notes
        self.is_critical = is_critical
        self.asset_url = asset_url
        self.file_size = file_size
        self.file_name = file_name
        self.checksum_url = checksum_url
    
    def __repr__(self):
        return f"UpdateInfo(version={self.version}, is_critical={self.is_critical}, file_name={self.file_name})"


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
            
            # Get installation metadata
            from app.config import AppConfig
            metadata = AppConfig.get_installation_metadata()
            logger.debug(f"Installation metadata: {metadata}")
            
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
                logger.debug(f"Update server response: {data.get('tag_name')}")
                
                # Parse response
                update_info = UpdateChecker._parse_update_response(data, metadata)
                
                if update_info is None:
                    logger.info("No update information available from server")
                    return None
                
                # Check if version is newer
                if UpdateChecker._is_newer_version(update_info.version, current_ver):
                    logger.info(f"Update available: {update_info.version} (asset: {update_info.file_name})")
                    
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
    def _parse_update_response(data: Dict[str, Any], metadata: dict) -> Optional[UpdateInfo]:
        """
        Parse update server response and match assets.
        
        Supports GitHub Releases API format and custom format.
        
        Args:
            data: JSON response from server
            metadata: Installation metadata for asset matching
            
        Returns:
            UpdateInfo or None if parsing fails
        """
        try:
            # GitHub Releases API format
            if 'tag_name' in data:
                version_str = data['tag_name'].lstrip('v')  # Remove 'v' prefix if present
                
                # Use the GitHub release page URL for fallback
                download_url = data.get('html_url', '')
                
                release_notes = data.get('body', 'No release notes available')
                is_critical = 'critical' in data.get('name', '').lower() or 'security' in release_notes.lower()
                
                # Get assets list
                assets = data.get('assets', [])
                
                # Match asset for this platform
                matched_asset = UpdateChecker._match_asset_for_platform(assets, metadata)
                
                # Get checksum URL
                checksum_url = UpdateChecker._get_checksum_url(data)
                
                if matched_asset:
                    return UpdateInfo(
                        version=version_str,
                        download_url=download_url,  # Fallback browser URL
                        release_notes=release_notes,
                        is_critical=is_critical,
                        asset_url=matched_asset.get('browser_download_url'),
                        file_size=matched_asset.get('size'),
                        file_name=matched_asset.get('name'),
                        checksum_url=checksum_url
                    )
                else:
                    # No matching asset - return basic info (will open browser)
                    logger.warning("No matching asset found for this platform")
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
    def _match_asset_for_platform(assets: list, metadata: dict) -> Optional[Dict[str, Any]]:
        """
        Find the matching asset for the current platform and installation type.
        
        Args:
            assets: List of asset dictionaries from GitHub API
            metadata: Installation metadata (platform, package_type, architecture)
            
        Returns:
            Matching asset dictionary with keys: name, browser_download_url, size
            or None if no match found
        """
        platform = metadata.get('platform', '').lower()
        package_type = metadata.get('package_type', '').lower()
        architecture = metadata.get('architecture', '').lower()
        
        logger.debug(f"Looking for asset matching: platform={platform}, package={package_type}, arch={architecture}")
        
        # Build filename patterns to match
        # Examples:
        # Windows-Installer.exe, Windows-Portable.exe
        # macOS-AppleSilicon.dmg, macOS-AppleSilicon.zip
        # Linux-Installer.deb, Linux-Portable
        
        patterns = []
        
        if platform == 'windows':
            if package_type == 'installer':
                patterns.append('Windows-Installer.exe')
            elif package_type == 'portable':
                patterns.append('Windows-Portable.exe')
        
        elif platform == 'macos':
            # Match architecture (arm64 = Apple Silicon, amd64/x86_64 = Intel)
            if architecture in ('arm64', 'aarch64'):
                if package_type == 'dmg':
                    patterns.append('macOS-AppleSilicon.dmg')
                elif package_type == 'zip':
                    patterns.append('macOS-AppleSilicon.zip')
            else:  # Intel
                if package_type == 'dmg':
                    patterns.append('macOS-Intel.dmg')
                elif package_type == 'zip':
                    patterns.append('macOS-Intel.zip')
        
        elif platform == 'linux':
            if package_type == 'deb':
                patterns.append('Linux-Installer.deb')
            elif package_type == 'portable':
                patterns.append('Linux-Portable')
        
        if not patterns:
            logger.warning(f"No patterns generated for platform={platform}, package={package_type}")
            return None
        
        logger.debug(f"Searching for patterns: {patterns}")
        
        # Search through assets for a match
        for asset in assets:
            asset_name = asset.get('name', '')
            for pattern in patterns:
                if pattern in asset_name:
                    logger.info(f"Found matching asset: {asset_name}")
                    return {
                        'name': asset_name,
                        'browser_download_url': asset.get('browser_download_url'),
                        'size': asset.get('size', 0)
                    }
        
        logger.warning(f"No matching asset found for patterns: {patterns}")
        logger.debug(f"Available assets: {[a.get('name') for a in assets]}")
        return None
    
    @staticmethod
    def _get_checksum_url(release_data: Dict[str, Any]) -> Optional[str]:
        """
        Find CHECKSUMS.txt URL in release assets.
        
        Args:
            release_data: GitHub release data
            
        Returns:
            URL to CHECKSUMS.txt or None
        """
        assets = release_data.get('assets', [])
        for asset in assets:
            if asset.get('name') == 'CHECKSUMS.txt':
                return asset.get('browser_download_url')
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
