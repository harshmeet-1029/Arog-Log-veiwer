"""
Configuration management for Argo Log Viewer.

SECURITY: This module externalizes hardcoded credentials and connection details.
In production, consider using environment variables or a secure vault.
"""
import os
import logging
from typing import Optional

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
        default_path = os.path.expanduser("~/.ssh/config")
        path = os.getenv("SSH_CONFIG_PATH", default_path)
        logger.debug(f"Using SSH config: {path}")
        return path


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
