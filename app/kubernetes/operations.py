"""
Kubernetes operations module for safe, read-only cluster interactions.
All operations are executed through the established SSH connection.
"""
import re
import shlex
from typing import List, Callable, Optional
from app.ssh.connection_manager import SSHConnectionManager
from app.logging_config import get_logger

logger = get_logger(__name__)


class KubernetesOperations:
    """
    Provides safe, read-only Kubernetes operations.
    
    SECURITY: All commands are read-only (get, logs).
    NO WRITE OPERATIONS (apply, delete, exec, scale, etc.)
    """
    
    NAMESPACE = "argo"
    
    # Whitelist of allowed kubectl commands (read-only)
    ALLOWED_COMMANDS = {'get', 'logs', 'describe'}
    
    def __init__(self, ssh_manager: SSHConnectionManager):
        """
        Initialize Kubernetes operations with SSH connection manager.
        
        Args:
            ssh_manager: Established SSH connection manager
        """
        self.ssh = ssh_manager
        logger.info("KubernetesOperations initialized")
    
    @staticmethod
    def _strip_ansi_codes(text: str) -> str:
        """
        Strip ANSI escape codes (colors, formatting) from text.
        
        Args:
            text: Text potentially containing ANSI codes
            
        Returns:
            Clean text without ANSI codes
        """
        # Pattern matches ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def list_all_pods(self) -> str:
        """
        List ALL pods in the argo namespace (no filtering).
        
        Returns:
            Raw output from kubectl get pods command
            
        Raises:
            RuntimeError: If SSH connection is not established
        """
        logger.info(f"Listing all pods in namespace '{self.NAMESPACE}'")
        
        # Build kubectl command - filter for Running pods only
        command = f"kubectl get pods -n {self.NAMESPACE} --field-selector=status.phase=Running"
        logger.debug(f"Executing: {command}")
        
        try:
            output = self.ssh.execute_command(command, timeout=10.0)
            # Strip ANSI color codes
            clean_output = self._strip_ansi_codes(output)
            logger.debug(f"Received output: {len(clean_output)} bytes")
            logger.info("Successfully retrieved all running pods")
            return clean_output
        
        except Exception as e:
            logger.error(f"Error listing all pods: {e}", exc_info=True)
            raise RuntimeError(f"Failed to list pods: {e}")
    
    def list_pods(self, search_keyword: str) -> List[str]:
        """
        List pods in the argo namespace matching a keyword.
        
        Args:
            search_keyword: Keyword to filter pods (used with grep)
            
        Returns:
            List of pod names matching the keyword
            
        Raises:
            RuntimeError: If SSH connection is not established
            ValueError: If search keyword is invalid
        """
        if not search_keyword or not search_keyword.strip():
            raise ValueError("Search keyword cannot be empty")
        
        # Sanitize search keyword to prevent command injection
        safe_keyword = self._sanitize_grep_pattern(search_keyword)
        logger.info(f"Listing pods with keyword: '{search_keyword}' (sanitized: '{safe_keyword}')")
        
        # Build kubectl command with grep
        command = f"kubectl get pods -n {self.NAMESPACE} --no-headers | grep {shlex.quote(safe_keyword)}"
        logger.debug(f"Executing: {command}")
        
        try:
            output = self.ssh.execute_command(command, timeout=10.0)
            # Strip ANSI color codes from output
            clean_output = self._strip_ansi_codes(output)
            logger.debug(f"Received output: {len(clean_output)} bytes")
            
            # Parse pod names from output
            pods = self._parse_pod_list(clean_output)
            logger.info(f"Found {len(pods)} pods matching '{search_keyword}'")
            
            return pods
        
        except Exception as e:
            logger.error(f"Error listing pods: {e}", exc_info=True)
            raise RuntimeError(f"Failed to list pods: {e}")
    
    def stream_pod_logs(
        self, 
        pod_name: str, 
        output_callback: Callable[[str], None],
        stop_check: Optional[Callable[[], bool]] = None,
        follow: bool = True,
        tail_lines: Optional[int] = None
    ) -> None:
        """
        Stream logs from a pod in real-time.
        
        Args:
            pod_name: Name of the pod
            output_callback: Function to receive log output
            stop_check: Optional function that returns True to stop streaming
            follow: Whether to follow logs in real-time (-f flag)
            tail_lines: Optional number of lines to tail
            
        Raises:
            RuntimeError: If SSH connection is not established
            ValueError: If pod name is invalid
        """
        if not pod_name or not pod_name.strip():
            raise ValueError("Pod name cannot be empty")
        
        # Sanitize pod name
        safe_pod_name = self._sanitize_pod_name(pod_name)
        logger.info(f"Streaming logs for pod: '{safe_pod_name}'")
        
        # Build kubectl logs command
        cmd_parts = [
            "kubectl logs",
            shlex.quote(safe_pod_name),
            f"-n {self.NAMESPACE}"
        ]
        
        if follow:
            cmd_parts.append("-f")
        
        if tail_lines:
            cmd_parts.append(f"--tail={tail_lines}")
        
        command = " ".join(cmd_parts)
        logger.debug(f"Executing: {command}")
        
        try:
            self.ssh.execute_streaming_command(
                command=command,
                output_callback=output_callback,
                stop_check=stop_check
            )
            logger.info(f"Log streaming completed for pod '{safe_pod_name}'")
        
        except Exception as e:
            logger.error(f"Error streaming logs: {e}", exc_info=True)
            raise RuntimeError(f"Failed to stream logs: {e}")
    
    def get_pod_details(self, pod_name: str) -> str:
        """
        Get detailed information about a pod.
        
        Args:
            pod_name: Name of the pod
            
        Returns:
            Pod details as string
            
        Raises:
            RuntimeError: If SSH connection is not established
            ValueError: If pod name is invalid
        """
        if not pod_name or not pod_name.strip():
            raise ValueError("Pod name cannot be empty")
        
        safe_pod_name = self._sanitize_pod_name(pod_name)
        logger.info(f"Getting details for pod: '{safe_pod_name}'")
        
        command = f"kubectl describe pod {shlex.quote(safe_pod_name)} -n {self.NAMESPACE}"
        logger.debug(f"Executing: {command}")
        
        try:
            output = self.ssh.execute_command(command, timeout=10.0)
            logger.info(f"Retrieved pod details ({len(output)} bytes)")
            return output
        
        except Exception as e:
            logger.error(f"Error getting pod details: {e}", exc_info=True)
            raise RuntimeError(f"Failed to get pod details: {e}")
    
    # -------------------------
    # Private Helper Methods
    # -------------------------
    
    def _sanitize_grep_pattern(self, pattern: str) -> str:
        """
        Sanitize grep pattern to prevent command injection.
        
        Args:
            pattern: User-provided grep pattern
            
        Returns:
            Sanitized pattern
        """
        # Remove potentially dangerous characters
        # Allow: alphanumeric, dash, underscore, dot
        sanitized = ''.join(c for c in pattern if c.isalnum() or c in '-_.')
        
        if not sanitized:
            raise ValueError("Invalid search pattern - no valid characters")
        
        logger.debug(f"Sanitized pattern: '{pattern}' -> '{sanitized}'")
        return sanitized
    
    def _sanitize_pod_name(self, pod_name: str) -> str:
        """
        Sanitize pod name to prevent command injection.
        
        Args:
            pod_name: User-provided pod name
            
        Returns:
            Sanitized pod name
        """
        # Kubernetes pod names follow RFC 1123 DNS label standard:
        # - lowercase alphanumeric characters, '-' or '.'
        # - must start and end with alphanumeric
        sanitized = ''.join(c for c in pod_name if c.isalnum() or c in '-.')
        
        if not sanitized:
            raise ValueError("Invalid pod name - no valid characters")
        
        if sanitized != pod_name:
            logger.warning(f"Pod name sanitized: '{pod_name}' -> '{sanitized}'")
        
        return sanitized
    
    def _parse_pod_list(self, output: str) -> List[str]:
        """
        Parse kubectl get pods output to extract pod names.
        
        Args:
            output: Raw kubectl output
            
        Returns:
            List of pod names
        """
        pods = []
        lines = output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip command echo and prompts
            if line.startswith('kubectl') or line.endswith('$') or line.endswith('#'):
                continue
            
            # Pod name is the first column
            parts = line.split()
            if parts:
                pod_name = parts[0]
                # Validate it looks like a pod name
                if self._looks_like_pod_name(pod_name):
                    pods.append(pod_name)
                    logger.debug(f"Found pod: {pod_name}")
        
        return pods
    
    def _looks_like_pod_name(self, name: str) -> bool:
        """
        Check if a string looks like a valid Kubernetes pod name.
        
        Args:
            name: String to check
            
        Returns:
            True if it looks like a pod name
        """
        # Basic validation: should contain alphanumeric and possibly dashes
        if not name:
            return False
        
        # Should not be empty and should contain at least one alphanumeric
        if not any(c.isalnum() for c in name):
            return False
        
        # Should not start with special characters
        if name[0] in '-_.':
            return False
        
        return True
