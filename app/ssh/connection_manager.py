"""
Production-grade SSH connection manager.
Maintains stateful SSH chain: Windows -> usejump -> 10.0.34.231 -> sudo su -
"""
import re
import socket
import time
import os
import subprocess
import paramiko
from typing import Optional, Callable
from app.logging_config import get_logger
from app.config import SSHConfig, SecurityConfig, AppConfig

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
    1. gcloud compute start-iap-tunnel  →  localhost:PORT
    2. paramiko.SSHClient.connect(localhost, PORT)  →  persistent shell
    3. sudo -i -u <service_account>  (once, at connect time)
    4. Execute kubectl commands through the live shell — fast, no new subprocess
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
        self.client: Optional[paramiko.SSHClient] = None
        self.shell: Optional[paramiko.Channel] = None
        self.connected = False
        self.output_callback = output_callback
        self.provider = (provider or SSHConfig.get_connection_provider()).upper()
        self._gcp_iap_proc: Optional[subprocess.Popen] = None
        self._gcp_iap_port: Optional[int] = None
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
                if isinstance(identity_file, list) and identity_file:
                    key_path = os.path.expanduser(identity_file[0])

                    custom_ssh_folder = SSHConfig.get_ssh_folder()
                    if not os.path.exists(key_path) and custom_ssh_folder:
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
            self.shell.settimeout(0.5)
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
        Open an IAP tunnel via `gcloud compute start-iap-tunnel`, then connect
        paramiko over localhost:PORT. This pays the tunnel+SSH cost once at connect
        time; all subsequent commands run through the live shell (~1-3s instead of 15-30s).
        No external ssh binary, no ControlMaster, no plink — works on Windows/Linux/macOS.
        """
        username = AppConfig.get_gcp_os_login_username()
        if not username:
            raise RuntimeError("GCP_USERNAME_NOT_SET")

        self._emit_output("[INFO] Initializing GCP SSH connection...\n")
        self._emit_output(f"[INFO] Connecting as: {username}\n")
        logger.info("Starting GCP IAP tunnel + paramiko connection")

        try:
            self._cleanup_gcp_iap()

            port = self._find_free_port()
            tunnel_cmd = (
                f"gcloud compute start-iap-tunnel {SSHConfig.GCP_VM} 22 "
                f"--local-host-port=localhost:{port} --zone={SSHConfig.GCP_ZONE}"
            )
            logger.info(f"Starting IAP tunnel on localhost:{port}")
            self._gcp_iap_proc = subprocess.Popen(
                tunnel_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self._gcp_iap_port = port

            if not self._wait_for_iap_tunnel(port, timeout=60):
                # Capture any error output from the tunnel process
                tunnel_out = ""
                if self._gcp_iap_proc and self._gcp_iap_proc.stdout:
                    try:
                        tunnel_out = self._gcp_iap_proc.stdout.read(2000)
                    except Exception:
                        pass
                raise RuntimeError(
                    f"IAP tunnel did not become ready within 60 seconds. "
                    f"gcloud output: {tunnel_out.strip() or '(none)'}"
                )

            # Connect paramiko over the tunnel — pure Python, no ssh binary needed
            self._emit_output("[INFO] IAP tunnel ready, establishing SSH...\n")
            self.client = paramiko.SSHClient()
            # GCP generates ephemeral host keys per tunnel session; AutoAddPolicy is
            # safe here because the connection is local-only (localhost:port)
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                "localhost",
                port=port,
                username=username,
                key_filename=self._find_gcp_ssh_key(),
                look_for_keys=True,
                allow_agent=True,
                timeout=30,
            )
            logger.info("Paramiko connected over IAP tunnel")

            self.shell = self.client.invoke_shell()
            self.shell.settimeout(0.5)
            self._wait_for_prompt(timeout=15.0)  # drain login banner

            # Switch to the service account that has kubectl access (once, at connect time)
            sa = SSHConfig.get_gcp_service_account()
            self._emit_output(f"[INFO] Switching to {sa}...\n")
            self._send_command(f"sudo -i -u {sa}")
            self._wait_for_prompt(timeout=20.0)

            self.connected = True
            self._emit_output("[OK] GCP connection established\n")
            self._emit_output("[SUCCESS] Connection established. Ready for kubectl commands.\n\n")
            logger.info("GCP paramiko shell ready — subsequent commands reuse this connection")

        except Exception as e:
            logger.error(f"GCP connection failed: {e}", exc_info=True)
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

    def execute_command(self, command: str, timeout: float = 60.0) -> str:
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

    def _execute_gcp_command(self, command: str, timeout: float = 60.0) -> str:
        """Send command through the live paramiko shell and return output."""
        logger.info(f"Executing GCP command: {command}")
        # Drain any stale output before sending
        if self.shell and self.shell.recv_ready():
            while self.shell.recv_ready():
                self.shell.recv(4096)
        self._send_command(command)
        return self._wait_for_prompt(timeout=max(timeout, 60.0))

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

        # Both GCP (paramiko shell) and ECR use the same shell streaming path
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
                except Exception:
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
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error during streaming: {e}", exc_info=True)
                break

    def is_connected(self) -> bool:
        """Check if the connection is active."""
        return self.connected and self.shell is not None and not self.shell.closed

    # -------------------------
    # Private Helper Methods
    # -------------------------

    def _send_command(self, command: str) -> None:
        logger.debug(f"Sending: {command}")
        self.shell.send(command + "\n")

    def _wait_for_prompt(self, timeout: float = 5.0) -> str:
        """
        Wait for shell prompt, indicating command completion.
        Returns all output received before the prompt.
        Raises RuntimeError if prompt not detected within timeout.
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
                    if time.time() - last_activity > 1.0:
                        for pattern in self.PROMPT_PATTERNS:
                            if re.search(pattern, buffer.splitlines()[-1] if buffer.splitlines() else ""):
                                logger.debug("Prompt detected")
                                return buffer
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error reading from shell: {e}", exc_info=True)
                raise

    def _find_gcp_ssh_key(self) -> Optional[str]:
        """
        Return the path to the GCP SSH private key that gcloud manages.
        gcloud stores it as ~/.ssh/google_compute_engine (non-standard name that
        paramiko's look_for_keys scan misses). Falls back to None so paramiko
        continues trying other keys/agent.
        """
        candidate = os.path.join(os.path.expanduser("~"), ".ssh", "google_compute_engine")
        if os.path.isfile(candidate):
            logger.debug(f"Using GCP SSH key: {candidate}")
            return candidate
        logger.warning("GCP SSH key not found at ~/.ssh/google_compute_engine — trying agent/default keys")
        return None

    def _find_free_port(self) -> int:
        """Return an OS-assigned free TCP port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            return s.getsockname()[1]

    def _wait_for_iap_tunnel(self, port: int, timeout: float = 60.0) -> bool:
        """Poll until the IAP tunnel's local port accepts TCP connections."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._gcp_iap_proc and self._gcp_iap_proc.poll() is not None:
                return False  # tunnel process died early
            try:
                with socket.create_connection(("localhost", port), timeout=1):
                    logger.info(f"IAP tunnel ready on localhost:{port}")
                    return True
            except OSError:
                time.sleep(0.5)
        return False

    def _cleanup_gcp_iap(self) -> None:
        """Terminate the IAP tunnel background process."""
        proc = self._gcp_iap_proc
        self._gcp_iap_proc = None
        self._gcp_iap_port = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _cleanup(self) -> None:
        """Clean up all SSH and tunnel resources."""
        logger.debug("Cleaning up SSH resources")
        self._cleanup_gcp_iap()

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

    def _emit_output(self, text: str) -> None:
        if self.output_callback:
            self.output_callback(text)
