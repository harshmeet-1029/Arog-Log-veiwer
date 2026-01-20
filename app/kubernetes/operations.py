"""
Kubernetes operations module for safe, read-only cluster interactions.
All operations are executed through the established SSH connection.
"""
import re
import shlex
from typing import List, Callable, Optional
from app.ssh.connection_manager import SSHConnectionManager
from app.logging_config import get_logger
from app.config import KubernetesConfig, SecurityConfig

logger = get_logger(__name__)


def sanitize_for_logging(text: str, max_length: int = 200) -> str:
    """
    Sanitize text for safe logging (prevent log injection attacks).
    
    SECURITY: This prevents log injection by:
    1. Removing newlines and control characters
    2. Truncating long strings
    3. Escaping special characters
    
    Args:
        text: Text to sanitize
        max_length: Maximum length to log
        
    Returns:
        Sanitized text safe for logging
    """
    if not text:
        return ""
    
    # Remove control characters (including newlines, carriage returns, tabs)
    sanitized = ''.join(c if c.isprintable() or c in ' \t' else '?' for c in text)
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized


class KubernetesOperations:
    """
    Provides safe, read-only Kubernetes operations.
    
    SECURITY: All commands are read-only (get, logs).
    NO WRITE OPERATIONS (apply, delete, exec, scale, etc.)
    """
    
    def __init__(self, ssh_manager: SSHConnectionManager):
        """
        Initialize Kubernetes operations with SSH connection manager.
        
        Args:
            ssh_manager: Established SSH connection manager
        """
        self.ssh = ssh_manager
        # Load namespace from config instead of hardcoding
        self.namespace = KubernetesConfig.get_namespace()
        logger.info(f"KubernetesOperations initialized with namespace: {self.namespace}")
    
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
        logger.info(f"Listing all pods in namespace '{self.namespace}'")
        
        # Build kubectl command - filter for Running pods only
        command = f"kubectl get pods -n {self.namespace} --field-selector=status.phase=Running"
        logger.debug(f"Executing: {command}")
        
        try:
            output = self.ssh.execute_command(command, timeout=10.0)
            # Strip ANSI color codes
            clean_output = self._strip_ansi_codes(output)
            logger.debug(f"Received output: {len(clean_output)} bytes")
            logger.info("Successfully retrieved all running pods")
            return clean_output
        
        except Exception as e:
            # SECURITY: Sanitize error messages before logging
            safe_error = sanitize_for_logging(str(e))
            logger.error(f"Error listing all pods: {safe_error}", exc_info=True)
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
        
        # SECURITY: Sanitize for logging
        safe_keyword_log = sanitize_for_logging(search_keyword)
        logger.info(f"Listing pods with keyword: '{safe_keyword_log}' (sanitized: '{safe_keyword}')")
        
        # Build kubectl command with grep
        command = f"kubectl get pods -n {self.namespace} --no-headers | grep {shlex.quote(safe_keyword)}"
        logger.debug(f"Executing: {command}")
        
        try:
            output = self.ssh.execute_command(command, timeout=10.0)
            # Strip ANSI color codes from output
            clean_output = self._strip_ansi_codes(output)
            logger.debug(f"Received output: {len(clean_output)} bytes")
            
            # Parse pod names from output
            pods = self._parse_pod_list(clean_output)
            logger.info(f"Found {len(pods)} pods matching '{safe_keyword_log}'")
            
            return pods
        
        except Exception as e:
            # SECURITY: Sanitize error messages before logging
            safe_error = sanitize_for_logging(str(e))
            logger.error(f"Error listing pods: {safe_error}", exc_info=True)
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
        
        # SECURITY: Sanitize for logging
        safe_pod_name_log = sanitize_for_logging(pod_name)
        logger.info(f"Streaming logs for pod: '{safe_pod_name_log}'")
        
        # Build kubectl logs command
        cmd_parts = [
            "kubectl logs",
            shlex.quote(safe_pod_name),
            f"-n {self.namespace}"
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
            logger.info(f"Log streaming completed for pod '{safe_pod_name_log}'")
        
        except Exception as e:
            # SECURITY: Sanitize error messages before logging
            safe_error = sanitize_for_logging(str(e))
            logger.error(f"Error streaming logs: {safe_error}", exc_info=True)
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
        
        # SECURITY: Sanitize for logging
        safe_pod_name_log = sanitize_for_logging(pod_name)
        logger.info(f"Getting details for pod: '{safe_pod_name_log}'")
        
        command = f"kubectl describe pod {shlex.quote(safe_pod_name)} -n {self.namespace}"
        logger.debug(f"Executing: {command}")
        
        try:
            output = self.ssh.execute_command(command, timeout=10.0)
            logger.info(f"Retrieved pod details ({len(output)} bytes)")
            return output
        
        except Exception as e:
            # SECURITY: Sanitize error messages before logging
            safe_error = sanitize_for_logging(str(e))
            logger.error(f"Error getting pod details: {safe_error}", exc_info=True)
            raise RuntimeError(f"Failed to get pod details: {e}")
    
    def get_pod_metrics(self, pod_name: str) -> str:
        """
        Get real-time CPU and memory metrics for a specific pod.
        
        Uses kubectl top pod command to retrieve current resource utilization.
        Requires metrics-server to be installed in the cluster.
        
        Args:
            pod_name: Name of the pod
            
        Returns:
            Pod metrics as string (CPU and memory usage)
            
        Raises:
            RuntimeError: If SSH connection is not established or metrics-server is not available
            ValueError: If pod name is invalid
        """
        if not pod_name or not pod_name.strip():
            raise ValueError("Pod name cannot be empty")
        
        safe_pod_name = self._sanitize_pod_name(pod_name)
        
        # SECURITY: Sanitize for logging
        safe_pod_name_log = sanitize_for_logging(pod_name)
        logger.debug(f"Getting metrics for pod: '{safe_pod_name_log}'")
        
        # Clean command without timeout (we have separate SSH connection now)
        command = f"kubectl top pod {shlex.quote(safe_pod_name)} -n {self.namespace} --no-headers"
        logger.debug(f"Executing: {command}")
        
        try:
            output = self.ssh.execute_command(command, timeout=8.0)
            # Strip ANSI color codes
            clean_output = self._strip_ansi_codes(output).strip()
            
            logger.debug(f"Raw metrics output: {repr(clean_output[:200])}")
            
            # Check for specific error messages from kubectl top
            if "error" in clean_output.lower():
                # Check if it's a "pod not found" vs "metrics not available" error
                if "not found" in clean_output.lower():
                    logger.warning(f"Pod not found: {safe_pod_name_log}")
                    raise RuntimeError("Pod not found")
                elif "metrics not available" in clean_output.lower() or "not yet available" in clean_output.lower():
                    # Pod exists but metrics aren't ready yet (too new or recently restarted)
                    logger.debug(f"Metrics not yet available for pod (likely too new): {safe_pod_name_log}")
                    raise RuntimeError("Pod too new - metrics not ready (wait 15-60s)")
                else:
                    logger.warning(f"Metrics error: {clean_output[:100]}")
                    raise RuntimeError("Metrics server not available")
            
            if not clean_output:
                # Empty response - could be metrics-server issue or pod too new
                logger.debug(f"Empty metrics response for pod: {safe_pod_name_log}")
                raise RuntimeError("Metrics not available yet - pod may be too new")
            
            # Remove command echoes if present
            lines = clean_output.split('\n')
            result_lines = []
            for line in lines:
                line = line.strip()
                # Skip command echoes and prompts
                if line and not line.startswith('kubectl') and not line.endswith('$') and not line.endswith('#'):
                    result_lines.append(line)
            
            clean_output = '\n'.join(result_lines)
            logger.debug(f"Cleaned metrics output: {repr(clean_output)}")
            
            # Final validation - should have some data
            if not clean_output or len(clean_output) < 5:
                raise RuntimeError("Pod too new - metrics collecting (wait ~30s)")
            
            return clean_output
        
        except TimeoutError:
            logger.warning(f"SSH timeout for metrics request: {safe_pod_name_log}")
            raise RuntimeError("Metrics request timed out")
        
        except Exception as e:
            # SECURITY: Sanitize error messages before logging
            safe_error = sanitize_for_logging(str(e))
            logger.warning(f"Error getting pod metrics: {safe_error}")
            
            if "timeout" in safe_error.lower() or "Timeout" in str(e):
                raise RuntimeError("Metrics request timed out")
            
            # Pass through our specific error messages
            if "Pod too new" in str(e) or "not ready" in str(e).lower() or "not yet available" in str(e).lower():
                raise  # Re-raise with original message
            
            raise RuntimeError(f"Metrics unavailable: {e}")
    
    # -------------------------
    # Private Helper Methods
    # -------------------------
    
    def _sanitize_grep_pattern(self, pattern: str) -> str:
        """
        Sanitize grep pattern to prevent command injection.
        
        SECURITY: This function prevents command injection by:
        1. Removing all special shell characters
        2. Limiting to alphanumeric, dash, underscore, dot only
        3. Validating the result is not empty
        
        Args:
            pattern: User-provided grep pattern
            
        Returns:
            Sanitized pattern
            
        Raises:
            ValueError: If pattern contains no valid characters
        """
        # Strip leading/trailing whitespace
        pattern = pattern.strip()
        
        # Check for empty pattern
        if not pattern:
            raise ValueError("Search pattern cannot be empty")
        
        # Remove ALL potentially dangerous characters
        # Allow ONLY: alphanumeric, dash, underscore, dot
        # This prevents command injection through special shell characters: ; | & $ ` \ " ' ( ) < > * ? [ ] { } !
        sanitized = ''.join(c for c in pattern if c.isalnum() or c in '-_.')
        
        if not sanitized:
            raise ValueError("Invalid search pattern - contains no valid characters")
        
        # Additional safety: ensure pattern doesn't start with a dash (could be interpreted as grep option)
        if sanitized.startswith('-'):
            logger.warning(f"Pattern starts with dash, prepending safe character: '{sanitized}'")
            sanitized = 'x' + sanitized
        
        logger.debug(f"Sanitized grep pattern: '{pattern}' -> '{sanitized}'")
        return sanitized
    
    def _sanitize_pod_name(self, pod_name: str) -> str:
        """
        Sanitize pod name to prevent command injection.
        
        SECURITY: Kubernetes pod names follow RFC 1123 DNS label standard.
        This function validates and sanitizes to prevent command injection.
        
        Args:
            pod_name: User-provided pod name
            
        Returns:
            Sanitized pod name
            
        Raises:
            ValueError: If pod name is invalid or contains dangerous characters
        """
        # Strip leading/trailing whitespace
        pod_name = pod_name.strip()
        
        # Check for empty pod name
        if not pod_name:
            raise ValueError("Pod name cannot be empty")
        
        # Kubernetes pod names follow RFC 1123 DNS label standard:
        # - lowercase alphanumeric characters, '-' or '.'
        # - must start and end with alphanumeric character
        # - maximum 253 characters
        
        # Remove ALL potentially dangerous characters
        sanitized = ''.join(c for c in pod_name if c.isalnum() or c in '-.')
        
        if not sanitized:
            raise ValueError("Invalid pod name - contains no valid characters")
        
        # Validate starts and ends with alphanumeric
        if not sanitized[0].isalnum():
            raise ValueError(f"Invalid pod name - must start with alphanumeric character")
        
        if not sanitized[-1].isalnum():
            raise ValueError(f"Invalid pod name - must end with alphanumeric character")
        
        # Check length (Kubernetes limit)
        if len(sanitized) > 253:
            raise ValueError(f"Invalid pod name - exceeds maximum length of 253 characters")
        
        # Warn if sanitization changed the name
        if sanitized != pod_name:
            logger.warning(f"SECURITY: Pod name sanitized: '{pod_name}' -> '{sanitized}'")
        
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
