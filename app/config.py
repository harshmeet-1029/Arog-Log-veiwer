"""
Configuration management for Argo Log Viewer.

Created by: Harshmeet Singh (2024-2026)
Licensed under the MIT License - See LICENSE.txt for details

SECURITY: This module externalizes hardcoded credentials and connection details.
In production, consider using environment variables or a secure vault.
"""
import os
import json
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SSHConfig:
    """SSH connection configuration."""
    
    # Default configuration (can be overridden by environment variables)
    DEFAULT_JUMP_HOST = "usejump"
    DEFAULT_INTERNAL_HOST = "10.0.34.231"
    DEFAULT_SERVICE_ACCOUNT = "solutions01-prod-us-east-1-eks"
    
    @staticmethod
    def get_jump_host() -> str:
        """
        Get jump host from environment or use default.
        
        Environment variable: ARGO_JUMP_HOST
        
        Returns:
            Jump host hostname or alias
        """
        host = os.getenv("ARGO_JUMP_HOST", SSHConfig.DEFAULT_JUMP_HOST)
        logger.debug(f"Using jump host: {host}")
        return host
    
    @staticmethod
    def get_internal_host() -> str:
        """
        Get internal host IP/hostname from environment or use default.
        
        Environment variable: ARGO_INTERNAL_HOST
        
        Returns:
            Internal host IP or hostname
        """
        host = os.getenv("ARGO_INTERNAL_HOST", SSHConfig.DEFAULT_INTERNAL_HOST)
        logger.debug(f"Using internal host: {host}")
        return host
    
    @staticmethod
    def get_service_account() -> str:
        """
        Get service account username from environment or use default.
        
        Environment variable: ARGO_SERVICE_ACCOUNT
        
        Returns:
            Service account username
        """
        account = os.getenv("ARGO_SERVICE_ACCOUNT", SSHConfig.DEFAULT_SERVICE_ACCOUNT)
        logger.debug(f"Using service account: {account}")
        return account
    
    @staticmethod
    def get_ssh_config_path() -> str:
        """
        Get SSH config file path.
        
        Environment variable: SSH_CONFIG_PATH
        
        Returns:
            Path to SSH config file
        """
        # Check for custom SSH folder first
        custom_ssh_folder = AppConfig.get_custom_ssh_folder()
        if custom_ssh_folder and os.path.exists(custom_ssh_folder):
            custom_config_path = os.path.join(custom_ssh_folder, "config")
            if os.path.exists(custom_config_path):
                logger.info(f"Using custom SSH config: {custom_config_path}")
                return custom_config_path
            else:
                logger.warning(f"Custom SSH folder set but config not found: {custom_config_path}")
        
        # Fall back to default path
        default_path = os.path.expanduser("~/.ssh/config")
        path = os.getenv("SSH_CONFIG_PATH", default_path)
        logger.debug(f"Using SSH config: {path}")
        return path
    
    @staticmethod
    def get_ssh_folder() -> str:
        """
        Get SSH folder path (directory containing config, keys, etc.)
        
        Returns:
            Path to SSH folder
        """
        # Check for custom SSH folder first
        custom_ssh_folder = AppConfig.get_custom_ssh_folder()
        if custom_ssh_folder and os.path.exists(custom_ssh_folder):
            logger.info(f"Using custom SSH folder: {custom_ssh_folder}")
            return custom_ssh_folder
        
        # Fall back to default
        default_folder = os.path.expanduser("~/.ssh")
        logger.debug(f"Using default SSH folder: {default_folder}")
        return default_folder


class KubernetesConfig:
    """Kubernetes operations configuration."""
    
    # Default namespace for operations
    DEFAULT_NAMESPACE = "argo"
    
    # Allowed kubectl commands (read-only operations)
    ALLOWED_COMMANDS = frozenset(['get', 'logs', 'describe'])
    
    @staticmethod
    def get_namespace() -> str:
        """
        Get Kubernetes namespace from environment or use default.
        
        Environment variable: ARGO_NAMESPACE
        
        Returns:
            Kubernetes namespace
        """
        namespace = os.getenv("ARGO_NAMESPACE", KubernetesConfig.DEFAULT_NAMESPACE)
        logger.debug(f"Using namespace: {namespace}")
        return namespace
    
    @staticmethod
    def is_command_allowed(command: str) -> bool:
        """
        Check if a kubectl command is allowed.
        
        Args:
            command: The kubectl command to check
            
        Returns:
            True if command is allowed, False otherwise
        """
        return command in KubernetesConfig.ALLOWED_COMMANDS


class SecurityConfig:
    """Security-related configuration."""
    
    @staticmethod
    def get_log_sanitization_enabled() -> bool:
        """
        Check if log sanitization is enabled.
        
        Environment variable: ARGO_LOG_SANITIZATION
        
        Returns:
            True if log sanitization is enabled
        """
        enabled = os.getenv("ARGO_LOG_SANITIZATION", "true").lower() in ('true', '1', 'yes')
        logger.debug(f"Log sanitization enabled: {enabled}")
        return enabled
    
    @staticmethod
    def get_strict_host_key_checking() -> bool:
        """
        Check if strict host key checking is enabled.
        
        Environment variable: ARGO_STRICT_HOST_KEY_CHECKING
        
        Returns:
            True if strict host key checking is enabled
        """
        enabled = os.getenv("ARGO_STRICT_HOST_KEY_CHECKING", "false").lower() in ('true', '1', 'yes')
        logger.debug(f"Strict host key checking enabled: {enabled}")
        return enabled
    
    @staticmethod
    def get_secure_file_permissions() -> Optional[int]:
        """
        Get secure file permissions for saved logs.
        
        Returns:
            File permissions as octal integer (e.g., 0o600 for rw-------)
        """
        # Default: owner read/write only (0o600 = 384 decimal)
        return 0o600


class AppConfig:
    """Application configuration with persistence."""
    
    _config_file = None
    
    @staticmethod
    def get_config_file_path() -> Path:
        """Get the path to the configuration file."""
        if AppConfig._config_file:
            return AppConfig._config_file
        
        # Store config in user's home directory
        config_dir = Path.home() / ".argo-log-viewer"
        config_dir.mkdir(exist_ok=True)
        AppConfig._config_file = config_dir / "config.json"
        return AppConfig._config_file
    
    @staticmethod
    def load_config() -> dict:
        """Load configuration from file."""
        config_path = AppConfig.get_config_file_path()
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    logger.debug(f"Loaded config from {config_path}")
                    return config
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return {}
        return {}
    
    @staticmethod
    def save_config(config: dict) -> None:
        """Save configuration to file."""
        config_path = AppConfig.get_config_file_path()
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved config to {config_path}")
            
            # Set secure permissions on config file (Unix-like systems)
            if os.name != 'nt':
                os.chmod(config_path, 0o600)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    @staticmethod
    def get_custom_ssh_folder() -> Optional[str]:
        """Get custom SSH folder path if configured."""
        config = AppConfig.load_config()
        ssh_folder = config.get('custom_ssh_folder')
        if ssh_folder:
            logger.debug(f"Using custom SSH folder: {ssh_folder}")
        return ssh_folder
    
    @staticmethod
    def set_custom_ssh_folder(folder_path: Optional[str]) -> None:
        """Set custom SSH folder path."""
        config = AppConfig.load_config()
        if folder_path:
            config['custom_ssh_folder'] = folder_path
            logger.info(f"Set custom SSH folder to: {folder_path}")
        else:
            config.pop('custom_ssh_folder', None)
            logger.info("Removed custom SSH folder configuration")
        AppConfig.save_config(config)
    
    @staticmethod
    def get_last_update_check() -> Optional[float]:
        """Get timestamp of last update check."""
        config = AppConfig.load_config()
        return config.get('last_update_check')
    
    @staticmethod
    def set_last_update_check(timestamp: float) -> None:
        """Set timestamp of last update check."""
        config = AppConfig.load_config()
        config['last_update_check'] = timestamp
        AppConfig.save_config(config)
    
    @staticmethod
    def get_skip_version() -> Optional[str]:
        """Get version to skip for updates."""
        config = AppConfig.load_config()
        return config.get('skip_update_version')
    
    @staticmethod
    def set_skip_version(version: Optional[str]) -> None:
        """Set version to skip for updates."""
        config = AppConfig.load_config()
        if version:
            config['skip_update_version'] = version
        else:
            config.pop('skip_update_version', None)
        AppConfig.save_config(config)


class UpdateConfig:
    """OTA Update configuration."""
    
    # Update server URL (GitHub Releases - public repo, no token needed!)
    UPDATE_SERVER_URL = os.getenv(
        "ARGO_UPDATE_SERVER_URL",
        "https://api.github.com/repos/harshmeet-1029/Arog-Log-veiwer/releases/latest"
    )
    
    # Check for updates on startup
    CHECK_ON_STARTUP = os.getenv("ARGO_CHECK_UPDATES_ON_STARTUP", "true").lower() in ('true', '1', 'yes')
    
    # Update check interval in seconds (default: 24 hours)
    UPDATE_CHECK_INTERVAL = int(os.getenv("ARGO_UPDATE_CHECK_INTERVAL", str(24 * 60 * 60)))
    
    @staticmethod
    def _read_version_from_pyproject() -> Optional[str]:
        """
        Read version from pyproject.toml file.
        
        Returns:
            Version string if found, None otherwise
        """
        try:
            # Get the project root directory (where pyproject.toml should be)
            current_file = Path(__file__)
            project_root = current_file.parent.parent  # Go up from app/ to project root
            pyproject_path = project_root / "pyproject.toml"
            
            if not pyproject_path.exists():
                logger.debug(f"pyproject.toml not found at {pyproject_path}")
                return None
            
            with open(pyproject_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Look for version = "x.y.z" in pyproject.toml
                    if line.startswith('version') and '=' in line:
                        # Extract version string between quotes
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            version_str = parts[1].strip().strip('"').strip("'")
                            logger.info(f"Read version from pyproject.toml: {version_str}")
                            return version_str
            
            logger.warning("Version not found in pyproject.toml")
            return None
            
        except Exception as e:
            logger.warning(f"Error reading version from pyproject.toml: {e}")
            return None
    
    @staticmethod
    def get_current_version() -> str:
        """
        Get current application version.
        
        Reads from pyproject.toml if available (during development),
        falls back to default version for frozen/bundled builds.
        
        Returns:
            Version string (e.g., "1.0.0")
        """
        # Try to read from pyproject.toml first
        version = UpdateConfig._read_version_from_pyproject()
        
        # Fall back to default version if pyproject.toml not available
        # This happens when the app is frozen (PyInstaller) or installed
        if version is None:
            version = "1.0.0"  # Fallback version
            logger.debug(f"Using fallback version: {version}")
        
        return version
    
    @staticmethod
    def get_update_server_url() -> str:
        """Get update server URL."""
        return UpdateConfig.UPDATE_SERVER_URL
    
    @staticmethod
    def should_check_for_updates() -> bool:
        """Check if we should check for updates based on interval."""
        if not UpdateConfig.CHECK_ON_STARTUP:
            return False
        
        last_check = AppConfig.get_last_update_check()
        if last_check is None:
            return True
        
        import time
        elapsed = time.time() - last_check
        return elapsed >= UpdateConfig.UPDATE_CHECK_INTERVAL
