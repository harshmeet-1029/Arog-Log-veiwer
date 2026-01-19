"""
Integrity and validation checks for Argo Log Viewer.

Created by: Harshmeet Singh (2024-2026)
Proprietary software - See LICENSE.txt for terms.

This module performs integrity validation on startup.
"""
import json
import logging
import urllib.request
import urllib.error
import hashlib
from typing import Optional, Tuple
from app.config import UpdateConfig

logger = logging.getLogger(__name__)


class IntegrityChecker:
    """Performs software integrity validation."""
    
    # Validation endpoints
    GLOBAL_VALIDATION_URL = "https://api.github.com/repos/harshmeet-1029/Arog-Log-veiwer/contents/.license"
    VERSION_VALIDATION_URL_TEMPLATE = "https://api.github.com/repos/harshmeet-1029/Arog-Log-veiwer/contents/.license-v{version}"
    
    # Secret hash for validation
    REVOCATION_HASH = "f8e7d6c5b4a3d2c1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7"
    
    @staticmethod
    def validate(timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
        """
        Validate software integrity.
        Checks both global and version-specific revocation signals.
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check global kill switch first (affects all versions)
        is_valid, error_msg = IntegrityChecker._check_url(
            IntegrityChecker.GLOBAL_VALIDATION_URL, 
            timeout
        )
        if not is_valid:
            return False, error_msg or "This software has been discontinued. Please contact support. harshmeetsingh010@gmail.com"
        
        # Check version-specific kill switch (affects only this version)
        current_version = UpdateConfig.get_current_version()
        version_url = IntegrityChecker.VERSION_VALIDATION_URL_TEMPLATE.format(version=current_version)
        
        is_valid, error_msg = IntegrityChecker._check_url(version_url, timeout)
        if not is_valid:
            return False, error_msg or f"Version {current_version} has been deprecated. Please update to the latest version from here https://github.com/harshmeet-1029/Arog-Log-veiwer or contact support. harshmeetsingh010@gmail.com"
        
        return True, None
    
    @staticmethod
    def _check_url(url: str, timeout: float) -> Tuple[bool, Optional[str]]:
        """
        Check a specific URL for revocation signal.
        
        Args:
            url: URL to check
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'ArgoLogViewer/1.0',
                    'Accept': 'application/vnd.github.v3+json'
                }
            )
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    return True, None
                
                data = json.loads(response.read().decode('utf-8'))
                
                if 'content' in data:
                    import base64
                    content = base64.b64decode(data['content']).decode('utf-8').strip()
                    
                    result = IntegrityChecker._check_revocation(content)
                    if result['revoked']:
                        return False, result.get('message')
                    
                return True, None
                    
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # File doesn't exist - no revocation signal
                return True, None
            else:
                return True, None
        
        except urllib.error.URLError:
            return True, None
        
        except Exception:
            return True, None
    
    @staticmethod
    def _check_revocation(content: str) -> dict:
        """
        Check if content contains revocation signal.
        
        Args:
            content: Content from validation file
            
        Returns:
            Dict with keys: 'revoked' (bool), 'message' (str, optional)
        """
        try:
            # Try parsing as JSON first
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    # Check for explicit revocation flag
                    if data.get('revoked') == True:
                        custom_msg = data.get('message', None)
                        return {'revoked': True, 'message': custom_msg}
                    
                    # Check for status field
                    if data.get('status') in ['revoked', 'disabled', 'terminated']:
                        custom_msg = data.get('message', None)
                        return {'revoked': True, 'message': custom_msg}
                    
                    # Check for hash match
                    if data.get('hash') == IntegrityChecker.REVOCATION_HASH:
                        custom_msg = data.get('message', None)
                        return {'revoked': True, 'message': custom_msg}
                    
                    # Check for version-specific revocation
                    if 'affected_versions' in data:
                        current_version = UpdateConfig.get_current_version()
                        affected = data['affected_versions']
                        
                        # Check if "all" or current version is in the list
                        if 'all' in affected or current_version in affected:
                            custom_msg = data.get('message', None)
                            return {'revoked': True, 'message': custom_msg}
            
            except json.JSONDecodeError:
                pass
            
            # Check plain text content for keywords
            content_lower = content.lower()
            revocation_keywords = ['revoked', 'terminated', 'disabled', 'kill', 'stop']
            
            for keyword in revocation_keywords:
                if keyword in content_lower:
                    return {'revoked': True, 'message': None}
            
            # Check if content matches the revocation hash
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            if content_hash == IntegrityChecker.REVOCATION_HASH:
                return {'revoked': True, 'message': None}
            
            return {'revoked': False}
            
        except Exception:
            return {'revoked': False}


def check_can_run() -> Tuple[bool, Optional[str]]:
    """
    Check if software is allowed to run.
    
    Returns:
        Tuple of (can_run, error_message)
    """
    return IntegrityChecker.validate()
