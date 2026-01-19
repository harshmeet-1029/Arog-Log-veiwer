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
    
    def __init__(self, version: str, download_url: str, release_notes: str, is_critical: bool = False):
        """
        Initialize update information.
        
        Args:
            version: Version string (e.g., "1.1.0")
            download_url: URL to download the update
            release_notes: Release notes/changelog
            is_critical: Whether this is a critical security update
        """
        self.version = version
        self.download_url = download_url
        self.release_notes = release_notes
        self.is_critical = is_critical
    
    def __repr__(self):
        return f"UpdateInfo(version={self.version}, is_critical={self.is_critical})"


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
                download_url = None
                
                # Use the GitHub release page URL instead of direct download
                # This allows users to choose their platform manually
                if 'html_url' in data:
                    download_url = data['html_url']  # GitHub releases page
                
                release_notes = data.get('body', 'No release notes available')
                is_critical = 'critical' in data.get('name', '').lower() or 'security' in release_notes.lower()
                
                if download_url:
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
