"""
Production-grade SSH connection manager.
Maintains stateful SSH chain: Windows -> usejump -> 10.0.34.231 -> sudo su -
"""
import re
import time
import os
import shlex
import subprocess
import paramiko
from typing import Optional, Callable
from app.logging_config import get_logger
from app.config import SSHConfig, SecurityConfig

logger = get_logger(__name__)


class SSHConnectionManager:
    """
    Manages a stateful SSH connection chain with prompt detection.
    
    ECR flow:
    1. SSH to jump host (usejump)
    2. SSH to internal server (10.0.34.231)
    3. sudo su - solutions01-prod-us-east-1-eks
    4. Execute kubectl commands in that context

    GCP flow:
    1. Validate GCP SSH command from env/secret
    2. Execute kubectl commands through gcloud ssh --command
    """
    
    # Prompt patterns to detect command completion
    PROMPT_PATTERNS = [
        r'[\$#]\s*$',           # Standard bash prompt ending with $ or #
        r']\$\s*$',             # Prompt like [user@host]$
        r'>\s*$',               # Simple > prompt
    ]
    
    def __init__(
        self,
        output_callback: Optional[Callable[[str], None]] = None,
        provider: Optional[str] = None,
    ):
        """
        Initialize the SSH connection manager.
        
        Args:
            output_callback: Optional callback to receive command output for display
        """
        self.client: Optional[paramiko.SSHClient] = None
        self.shell: Optional[paramiko.Channel] = None
        self.connected = False
        self.output_callback = output_callback
        self.provider = (provider or SSHConfig.get_connection_provider()).upper()
        logger.info(f"SSHConnectionManager initialized (provider={self.provider})")
    
    def connect(self) -> None:
        """
        Establish the complete SSH chain and sudo context.
        
        Raises:
            paramiko.AuthenticationException: If SSH authentication fails
            paramiko.SSHException: If SSH connection fails
            RuntimeError: If command execution or prompt detection fails
        """
        if self.connected:
            logger.warning("Already connected, skipping connection")
            return
        
        try:
            if self.provider == "GCP":
                self._connect_gcp()
                return

            self._emit_output("[INFO] Initializing SSH connection...\n")
            logger.info("Starting SSH connection sequence")
            
            # Load SSH config
            ssh_config_path = SSHConfig.get_ssh_config_path()
            ssh_config = paramiko.SSHConfig()
            if os.path.exists(ssh_config_path):
                logger.debug(f"Loading SSH config from {ssh_config_path}")
                with open(ssh_config_path) as f:
                    ssh_config.parse(f)
            else:
                logger.warning(f"SSH config not found at {ssh_config_path}")
            
            # Get connection parameters from config (not hardcoded)
            jump_host = SSHConfig.get_jump_host()
            internal_host = SSHConfig.get_internal_host()
            service_account = SSHConfig.get_service_account()
            
            # Step 1: Connect to jump host
            self._emit_output(f"[CMD] ssh {jump_host}\n")
            logger.info(f"Step 1: Connecting to jump host '{jump_host}'")
            
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            # SECURITY: Use WarningPolicy instead of AutoAddPolicy to prevent MITM attacks
            # This will warn about unknown hosts but still connect (better than blindly accepting)
            # For production, consider using RejectPolicy and manage known_hosts properly
            if SecurityConfig.get_strict_host_key_checking():
                logger.info("SECURITY: Strict host key checking enabled - using RejectPolicy")
                self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
            else:
                logger.warning("SECURITY: Using WarningPolicy for host keys - consider enabling strict checking")
                self.client.set_missing_host_key_policy(paramiko.WarningPolicy())
            
            # Get connection parameters from SSH config
            host_config = ssh_config.lookup(jump_host)
            hostname = host_config.get("hostname", jump_host)
            port = int(host_config.get("port", 22))
            username = host_config.get("user", None)
            identity_file = host_config.get("identityfile", None)
            
            logger.debug(f"Attempting SSH connection to '{hostname}' (port {port}) as user '{username}'")
            
            # Build connection parameters
            connect_kwargs = {
                "hostname": hostname,
                "port": port,
            }
            if username:
                connect_kwargs["username"] = username
            if identity_file:
                # identity_file is a list in paramiko's SSH config
                if isinstance(identity_file, list) and identity_file:
                    key_path = os.path.expanduser(identity_file[0])
                    
                    # If using custom SSH folder, also check there
                    custom_ssh_folder = SSHConfig.get_ssh_folder()
                    if not os.path.exists(key_path) and custom_ssh_folder:
                        # Try to find the key in custom SSH folder
                        key_basename = os.path.basename(key_path)
                        custom_key_path = os.path.join(custom_ssh_folder, key_basename)
                        if os.path.exists(custom_key_path):
                            key_path = custom_key_path
                            logger.debug(f"Using key from custom SSH folder: {key_path}")
                    
                    if os.path.exists(key_path):
                        connect_kwargs["key_filename"] = key_path
                        logger.debug(f"Using identity file: {key_path}")
                    else:
                        logger.warning(f"Identity file not found: {key_path}")
            
            self.client.connect(**connect_kwargs)
            logger.info("✓ Successfully connected to jump host")
            self._emit_output("[OK] Connected to jump host\n")
            
            # Step 2: Invoke interactive shell
            logger.debug("Invoking interactive shell")
            self.shell = self.client.invoke_shell()
            self.shell.settimeout(0.5)  # Non-blocking with timeout
            logger.debug("Interactive shell invoked")
            
            # Wait for initial prompt
            self._wait_for_prompt(timeout=5.0)
            logger.info("✓ Received initial prompt from jump host")
            
            # Step 3: SSH to internal server
            self._emit_output(f"[CMD] ssh {internal_host}\n")
            logger.info(f"Step 2: Connecting to internal server {internal_host}")
            
            self._send_command(f"ssh {internal_host}")
            self._wait_for_prompt(timeout=10.0)
            logger.info("✓ Successfully connected to internal server")
            self._emit_output("[OK] Connected to internal server\n")
            
            # Step 4: sudo su to service account
            self._emit_output(f"[CMD] sudo su - {service_account}\n")
            logger.info(f"Step 3: Switching to {service_account} user")
            
            self._send_command(f"sudo su - {service_account}")
            self._wait_for_prompt(timeout=5.0)
            logger.info("✓ Successfully switched to service account")
            self._emit_output(f"[OK] Switched to {service_account}\n")
            
            self.connected = True
            logger.info("SSH connection chain established successfully")
            self._emit_output("[SUCCESS] Connection established. Ready for kubectl commands.\n\n")
            
        except paramiko.AuthenticationException as e:
            logger.error(f"SSH authentication failed: {e}", exc_info=True)
            self._cleanup()
            raise
        
        except paramiko.SSHException as e:
            logger.error(f"SSH connection error: {e}", exc_info=True)
            self._cleanup()
            raise
        
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}", exc_info=True)
            self._cleanup()
            raise RuntimeError(f"Connection failed: {e}")

    def _connect_gcp(self) -> None:
        """
        Validate GCP SSH access and mark the manager connected.
        Commands are executed via gcloud ssh --command in execute_command().
        """
        gcp_cmd = SSHConfig.get_gcp_ssh_command()
        if not gcp_cmd:
            raise RuntimeError(
                "GCP mode requires ARGO_GCP_SSH_COMMAND in env/secrets. "
                "Set it and reconnect."
            )
        self._emit_output("[INFO] Initializing GCP SSH connection...\n")
        self._emit_output("[INFO] Using GCP SSH command from env/secrets\n")
        logger.info("Starting GCP connection validation")

        try:
            if "--command" in gcp_cmd:
                raise RuntimeError(
                    "ARGO_GCP_SSH_COMMAND must not include --command. "
                    "Provide only the base gcloud ssh command."
                )

            probe_cmd = gcp_cmd
            probe_cmd = f'{probe_cmd} --command "echo gcp-ssh-ready"'

            result = subprocess.run(
                probe_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=90,
            )
            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                stdout = (result.stdout or "").strip()
                detail = stderr or stdout or "unknown gcloud error"
                raise RuntimeError(f"GCP SSH validation failed: {detail}")

            self.connected = True
            self._emit_output("[OK] GCP connection validated\n")
            self._emit_output("[SUCCESS] Connection established. Ready for kubectl commands.\n\n")
            logger.info("GCP connection validated successfully")
        except Exception as e:
            logger.error(f"GCP connection validation failed: {e}", exc_info=True)
            self._cleanup()
            raise RuntimeError(f"Connection failed: {e}")
    
    def disconnect(self) -> None:
        """Cleanly close the SSH connection."""
        if not self.connected:
            logger.debug("Not connected, nothing to disconnect")
            return
        
        logger.info("Disconnecting SSH connection")
        self._emit_output("\n[INFO] Disconnecting...\n")
        
        self._cleanup()
        self.connected = False
        logger.info("✓ Disconnected successfully")
        self._emit_output("[OK] Disconnected\n")
    
    def execute_command(self, command: str, timeout: float = 5.0) -> str:
        """
        Execute a command in the established SSH context.
        
        Args:
            command: The command to execute
            timeout: Maximum time to wait for command completion
            
        Returns:
            Command output as string
            
        Raises:
            RuntimeError: If not connected or command execution fails
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")

        if self.provider == "GCP":
            return self._execute_gcp_command(command, timeout)
        
        # Drain any pending output from previous commands (CRITICAL for clean output)
        if self.shell and self.shell.recv_ready():
            try:
                dropped = 0
                while self.shell.recv_ready():
                    data = self.shell.recv(4096)
                    dropped += len(data)
                if dropped > 0:
                    logger.warning(f"Drained {dropped} bytes of stale shell output before executing '{command}'")
            except Exception as e:
                logger.warning(f"Error draining shell: {e}")
        
        logger.info(f"Executing command: {command}")
        self._send_command(command)
        
        output = self._wait_for_prompt(timeout=timeout)
        logger.debug(f"Command output received ({len(output)} bytes)")
        
        return output

    def _execute_gcp_command(self, command: str, timeout: float = 10.0) -> str:
        """Execute one command through gcloud ssh --command."""
        logger.info(f"Executing GCP command: {command}")
        shell_cmd = self._build_gcp_shell_command(command)
        result = subprocess.run(
            shell_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=max(timeout, 10.0),
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout or "unknown gcloud command error"
            raise RuntimeError(f"GCP command failed: {detail}")
        return result.stdout or ""
    
    def execute_streaming_command(
        self, 
        command: str, 
        output_callback: Callable[[str], None],
        stop_check: Optional[Callable[[], bool]] = None
    ) -> None:
        """
        Execute a long-running command and stream output.
        
        Args:
            command: The command to execute (e.g., kubectl logs -f)
            output_callback: Function to receive streaming output
            stop_check: Optional function that returns True when streaming should stop
            
        Raises:
            RuntimeError: If not connected
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")

        if self.provider == "GCP":
            self._execute_gcp_streaming_command(command, output_callback, stop_check)
            return
        
        logger.info(f"Executing streaming command: {command}")
        self._send_command(command)
        
        # Give command time to start
        time.sleep(0.5)
        
        logger.info("Entering streaming mode")
        chunk_count = 0
        total_bytes = 0
        
        while True:
            # Check if we should stop
            if stop_check and stop_check():
                logger.info("Stop requested, sending Ctrl+C")
                self.shell.send('\x03')  # Send Ctrl+C
                time.sleep(0.5)
                # Drain any remaining output
                try:
                    while self.shell.recv_ready():
                        self.shell.recv(4096)
                except:
                    pass
                logger.info("Streaming stopped")
                break
            
            # Read available data
            try:
                if self.shell.recv_ready():
                    data = self.shell.recv(65536).decode(errors="ignore")
                    chunk_count += 1
                    total_bytes += len(data)
                    
                    logger.debug(f"Received chunk #{chunk_count} ({len(data)} bytes, total: {total_bytes})")
                    output_callback(data)
                else:
                    # Small sleep to prevent busy-waiting
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error during streaming: {e}", exc_info=True)
                break

    def _execute_gcp_streaming_command(
        self,
        command: str,
        output_callback: Callable[[str], None],
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Execute streaming command through gcloud ssh --command."""
        logger.info(f"Executing GCP streaming command: {command}")
        shell_cmd = self._build_gcp_shell_command(command)
        proc = subprocess.Popen(
            shell_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        try:
            while True:
                if stop_check and stop_check():
                    logger.info("Stop requested for GCP streaming command")
                    proc.terminate()
                    break

                if proc.stdout is None:
                    break

                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
                    continue

                output_callback(line)
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

        if proc.returncode not in (0, None):
            raise RuntimeError(f"GCP streaming command failed with code {proc.returncode}")
    
    def is_connected(self) -> bool:
        """Check if the connection is active."""
        if self.provider == "GCP":
            return self.connected
        return self.connected and self.shell and not self.shell.closed
    
    # -------------------------
    # Private Helper Methods
    # -------------------------
    
    def _send_command(self, command: str) -> None:
        """
        Send a command to the shell.
        
        Args:
            command: Command to send
        """
        logger.debug(f"Sending: {command}")
        self.shell.send(command + "\n")
    
    def _wait_for_prompt(self, timeout: float = 5.0) -> str:
        """
        Wait for shell prompt, indicating command completion.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            All output received before prompt
            
        Raises:
            RuntimeError: If prompt not detected within timeout
        """
        logger.debug(f"Waiting for prompt (timeout={timeout}s)")
        buffer = ""
        start_time = time.time()
        last_activity = start_time
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"Timeout waiting for prompt after {timeout}s")
                logger.debug(f"Buffer content (last 200 chars): {buffer[-200:]}")
                raise RuntimeError(f"Timeout waiting for shell prompt after {timeout}s")
            
            try:
                if self.shell.recv_ready():
                    chunk = self.shell.recv(4096).decode(errors="ignore")
                    buffer += chunk
                    last_activity = time.time()
                    logger.debug(f"Received {len(chunk)} bytes")
                else:
                    # If no activity for 1 second, check for prompt
                    if time.time() - last_activity > 1.0:
                        # Check if buffer ends with a prompt pattern
                        for pattern in self.PROMPT_PATTERNS:
                            if re.search(pattern, buffer.splitlines()[-1] if buffer.splitlines() else ""):
                                logger.debug("Prompt detected")
                                return buffer
                    
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error reading from shell: {e}", exc_info=True)
                raise
    
    def _cleanup(self) -> None:
        """Clean up SSH resources."""
        logger.debug("Cleaning up SSH resources")
        
        if self.shell:
            try:
                self.shell.close()
                logger.debug("Shell closed")
            except Exception as e:
                logger.warning(f"Error closing shell: {e}")
            self.shell = None
        
        if self.client:
            try:
                self.client.close()
                logger.debug("Client closed")
            except Exception as e:
                logger.warning(f"Error closing client: {e}")
            self.client = None

    def _build_gcp_shell_command(self, remote_command: str) -> str:
        """
        Build a full gcloud command that executes remote_command as the target
        service account.
        """
        base_cmd = SSHConfig.get_gcp_ssh_command()
        service_account = SSHConfig.get_gcp_service_account()

        wrapped_remote = (
            f"sudo su - {shlex.quote(service_account)} -c {shlex.quote(remote_command)}"
        )

        if "--command" in base_cmd:
            raise RuntimeError(
                "ARGO_GCP_SSH_COMMAND must not include --command. "
                "Provide only the base gcloud ssh command."
            )

        return f"{base_cmd} --command {shlex.quote(wrapped_remote)}"
    
    def _emit_output(self, text: str) -> None:
        """
        Emit output to callback if configured.
        
        Args:
            text: Text to emit
        """
        if self.output_callback:
            self.output_callback(text)
