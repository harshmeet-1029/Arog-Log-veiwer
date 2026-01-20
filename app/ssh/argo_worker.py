"""
Production-grade worker thread for SSH/Kubernetes operations.
Provides non-blocking background execution with proper lifecycle management.
"""
from typing import Optional
from PySide6.QtCore import QThread, Signal
from app.ssh.connection_manager import SSHConnectionManager
from app.kubernetes.operations import KubernetesOperations
from app.logging_config import get_logger

logger = get_logger(__name__)


class ArgoWorker(QThread):
    """
    Worker thread for SSH and Kubernetes operations.
    
    Manages connection lifecycle and executes operations in background.
    """
    
    # Signals for UI communication
    output = Signal(str)           # General output (logs, console messages)
    pods = Signal(list)            # List of pod names
    error = Signal(str)            # Error messages
    connected = Signal()           # Connection established
    disconnected = Signal()        # Connection closed
    metrics = Signal(str)          # Pod metrics (CPU/Memory utilization)
    
    def __init__(
        self, 
        action: str,
        search: Optional[str] = None,
        pod: Optional[str] = None,
        ssh_manager: Optional[SSHConnectionManager] = None
    ):
        """
        Initialize the worker thread.
        
        Args:
            action: Action to perform ('connect', 'list_pods', 'logs', 'disconnect', 'metrics')
            search: Optional search keyword for list_pods
            pod: Optional pod name for logs/metrics action
            ssh_manager: Optional existing SSH connection manager (for reuse)
        """
        super().__init__()
        self.action = action
        self.search = search
        self.pod = pod
        self.ssh_manager = ssh_manager
        self._should_stop = False
        
        logger.info(f"ArgoWorker created: action={action}, search={search}, pod={pod}")
    
    def run(self):
        """Main thread execution - dispatches to appropriate action handler."""
        logger.info(f"ArgoWorker thread started for action: {self.action}")
        
        try:
            if self.action == "connect":
                self._handle_connect()
            elif self.action == "list_all_pods":
                self._handle_list_all_pods()
            elif self.action == "list_pods":
                self._handle_list_pods()
            elif self.action == "logs":
                self._handle_logs()
            elif self.action == "metrics":
                self._handle_metrics()
            elif self.action == "disconnect":
                self._handle_disconnect()
            else:
                error_msg = f"Unknown action: {self.action}"
                logger.error(error_msg)
                self.error.emit(error_msg)
        
        except Exception as e:
            logger.error(f"Unhandled exception in ArgoWorker: {e}", exc_info=True)
            self.error.emit(f"Unexpected error: {str(e)}")
        
        finally:
            logger.info(f"ArgoWorker thread completed for action: {self.action}")
    
    def stop(self):
        """Request the worker to stop gracefully."""
        logger.info("Stop requested for ArgoWorker")
        self._should_stop = True
    
    def should_stop(self) -> bool:
        """Check if worker should stop."""
        return self._should_stop
    
    # -------------------------
    # Helper Methods
    # -------------------------
    
    def _parse_pod_names(self, kubectl_output: str) -> list:
        """
        Parse pod names from kubectl get pods output.
        
        Args:
            kubectl_output: Raw output from kubectl get pods
            
        Returns:
            List of pod names
        """
        pod_names = []
        lines = kubectl_output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip header line
            if line.startswith('NAME') and 'READY' in line:
                continue
            
            # Skip command echoes and prompts
            if line.startswith('kubectl') or line.endswith('$') or line.endswith('#'):
                continue
            
            # Pod name is the first column
            parts = line.split()
            if parts and len(parts) >= 1:
                pod_name = parts[0]
                # Basic validation - should look like a pod name
                if pod_name and not pod_name.startswith('[') and '-' in pod_name:
                    pod_names.append(pod_name)
                    logger.debug(f"Parsed pod: {pod_name}")
        
        return pod_names
    
    # -------------------------
    # Action Handlers
    # -------------------------
    
    def _handle_connect(self):
        """Handle SSH connection establishment."""
        logger.info("Handling connect action")
        
        try:
            if self.ssh_manager and self.ssh_manager.is_connected():
                logger.info("Already connected, skipping")
                self.output.emit("[INFO] Already connected\n")
                self.connected.emit()
                return
            
            # Create new connection manager if not provided
            if not self.ssh_manager:
                logger.debug("Creating new SSH connection manager")
                self.ssh_manager = SSHConnectionManager(
                    output_callback=lambda text: self.output.emit(text)
                )
            else:
                # Update output callback
                self.ssh_manager.output_callback = lambda text: self.output.emit(text)
            
            # Establish connection
            self.ssh_manager.connect()
            
            logger.info("Connection established successfully")
            
            # Automatically list all pods after successful connection
            try:
                logger.info("Auto-listing all pods after successful connection")
                self.output.emit("\n[INFO] Listing all running pods in namespace 'argo'...\n")
                self.output.emit("[CMD] kubectl get pods -n argo --field-selector=status.phase=Running\n")
                
                k8s = KubernetesOperations(self.ssh_manager)
                pods_output = k8s.list_all_pods()
                
                # Display the output in console
                self.output.emit(pods_output)
                if not pods_output.strip().endswith('\n'):
                    self.output.emit('\n')
                
                # Parse pod names and emit to pod list
                pod_names = self._parse_pod_names(pods_output)
                if pod_names:
                    self.output.emit(f"[OK] Found {len(pod_names)} running pods\n")
                    self.pods.emit(pod_names)  # Send to UI pod list
                    logger.info(f"Emitted {len(pod_names)} pods to UI")
                else:
                    self.output.emit("[INFO] No running pods found\n")
                
            except Exception as pod_error:
                logger.warning(f"Failed to auto-list pods: {pod_error}")
                self.output.emit(f"[WARNING] Could not list pods: {str(pod_error)}\n")
            
            # Emit connected signal regardless of pod listing result
            self.connected.emit()
        
        except Exception as e:
            logger.error(f"Connection failed: {e}", exc_info=True)
            error_msg = f"Connection failed: {str(e)}"
            self.output.emit(f"[ERROR] {error_msg}\n")
            self.error.emit(error_msg)
    
    def _handle_list_all_pods(self):
        """Handle listing all running pods (refresh action)."""
        logger.info("Handling list_all_pods action (refresh)")
        
        try:
            if not self.ssh_manager or not self.ssh_manager.is_connected():
                raise RuntimeError("Not connected. Please connect first.")
            
            self.output.emit("[INFO] Fetching all running pods...\n")
            self.output.emit("[CMD] kubectl get pods -n argo --field-selector=status.phase=Running\n")
            
            k8s = KubernetesOperations(self.ssh_manager)
            pods_output = k8s.list_all_pods()
            
            # Display output in console
            self.output.emit(pods_output)
            if not pods_output.strip().endswith('\n'):
                self.output.emit('\n')
            
            # Parse and emit pod names
            pod_names = self._parse_pod_names(pods_output)
            if pod_names:
                self.output.emit(f"[OK] Found {len(pod_names)} running pods\n")
                self.pods.emit(pod_names)
                logger.info(f"Emitted {len(pod_names)} pods to UI")
            else:
                self.output.emit("[INFO] No running pods found\n")
                self.pods.emit([])
        
        except Exception as e:
            logger.error(f"Failed to list all pods: {e}", exc_info=True)
            error_msg = f"Failed to refresh pods: {str(e)}"
            self.output.emit(f"[ERROR] {error_msg}\n")
            self.error.emit(error_msg)
    
    def _handle_list_pods(self):
        """Handle pod listing action."""
        logger.info(f"Handling list_pods action with search: {self.search}")
        
        try:
            if not self.ssh_manager or not self.ssh_manager.is_connected():
                raise RuntimeError("Not connected. Please connect first.")
            
            # Create Kubernetes operations handler
            k8s = KubernetesOperations(self.ssh_manager)
            
            # Emit command being executed
            self.output.emit(f"[CMD] kubectl get pods -n argo | grep {self.search}\n")
            
            # List pods
            pods = k8s.list_pods(self.search)
            
            if not pods:
                logger.info("No pods found matching criteria")
                self.output.emit(f"[INFO] No pods found matching '{self.search}'\n")
                self.pods.emit([])
            else:
                logger.info(f"Found {len(pods)} pods")
                self.output.emit(f"[OK] Found {len(pods)} pods\n")
                self.pods.emit(pods)
        
        except Exception as e:
            logger.error(f"Failed to list pods: {e}", exc_info=True)
            error_msg = f"Failed to list pods: {str(e)}"
            self.output.emit(f"[ERROR] {error_msg}\n")
            self.error.emit(error_msg)
    
    def _handle_logs(self):
        """Handle log streaming action."""
        logger.info(f"Handling logs action for pod: {self.pod}")
        
        try:
            if not self.ssh_manager or not self.ssh_manager.is_connected():
                raise RuntimeError("Not connected. Please connect first.")
            
            # Create Kubernetes operations handler
            k8s = KubernetesOperations(self.ssh_manager)
            
            # Emit command being executed
            self.output.emit(f"[CMD] kubectl logs {self.pod} -n argo -f\n")
            self.output.emit("[INFO] Streaming logs... (close app or select another pod to stop)\n\n")
            
            # Stream logs
            k8s.stream_pod_logs(
                pod_name=self.pod,
                output_callback=lambda text: self.output.emit(text),
                stop_check=self.should_stop
            )
            
            logger.info("Log streaming completed")
            self.output.emit("\n[INFO] Log streaming stopped\n")
        
        except Exception as e:
            logger.error(f"Failed to stream logs: {e}", exc_info=True)
            error_msg = f"Failed to stream logs: {str(e)}"
            self.output.emit(f"[ERROR] {error_msg}\n")
            self.error.emit(error_msg)
    
    def _handle_metrics(self):
        """Handle pod metrics action (CPU/Memory monitoring).
        
        NOTE: This runs in a separate thread from logs and will not affect log streaming.
        """
        logger.info(f"Handling metrics action for pod: {self.pod} (independent thread)")
        
        try:
            if not self.ssh_manager or not self.ssh_manager.is_connected():
                raise RuntimeError("Not connected. Please connect first.")
            
            if not self.pod:
                raise ValueError("Pod name is required for metrics")
            
            # Create Kubernetes operations handler
            k8s = KubernetesOperations(self.ssh_manager)
            
            # Get metrics in a loop until stopped (silent operation)
            import time
            failed_attempts = 0
            max_failed_attempts = 7  # Allow 7 retries before giving up
            
            while not self._should_stop:
                try:
                    logger.debug(f"Fetching metrics for {self.pod} (attempt {failed_attempts + 1})")
                    metrics_output = k8s.get_pod_metrics(self.pod)
                    
                    # Emit metrics to UI (separate signal from logs)
                    self.metrics.emit(metrics_output)
                    
                    # Reset failed attempts on success
                    failed_attempts = 0
                    
                    # Wait 10 seconds before next refresh (increased for better performance)
                    # This prevents excessive UI updates and SSH commands
                    for _ in range(100):  # Check every 0.1s for faster response to stop
                        if self._should_stop:
                            break
                        time.sleep(0.1)
                    
                except Exception as e:
                    error_msg = str(e)
                    failed_attempts += 1
                    logger.warning(f"Metrics fetch failed (attempt {failed_attempts}/{max_failed_attempts}): {error_msg}")
                    
                    # Check if metrics-server is definitely not available (hard errors)
                    is_hard_error = (
                        "Metrics server not available" in error_msg or
                        "Metrics API not available" in error_msg or
                        "metrics.k8s.io" in error_msg
                    )
                    
                    # Check if pod is too new (soft error - should retry)
                    is_pod_too_new = (
                        "Pod too new" in error_msg or
                        "not ready" in error_msg.lower() or
                        "not yet available" in error_msg.lower() or
                        "metrics collecting" in error_msg.lower()
                    )
                    
                    # If hard error, give up immediately
                    if is_hard_error:
                        self.error.emit("Metrics server not installed in cluster")
                        break
                    
                    # If pod too new, show helpful message and retry
                    if is_pod_too_new:
                        if failed_attempts < max_failed_attempts:
                            # Still retrying - show wait message
                            self.metrics.emit("⏳ Pod too new, waiting for metrics... (~30s)")
                            retry_delay = 3  # Fixed 3s delay for new pods
                            logger.debug(f"Pod too new, retrying in {retry_delay}s (attempt {failed_attempts}/{max_failed_attempts})...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            # Max retries reached
                            self.error.emit("Pod is too new - metrics need ~60s to become available")
                            break
                    
                    # If max attempts reached for other errors, give up
                    if failed_attempts >= max_failed_attempts:
                        if "timed out" in error_msg.lower():
                            self.error.emit("Metrics unavailable - command timed out after 7 retries")
                        else:
                            self.error.emit(f"Metrics unavailable after {max_failed_attempts} attempts")
                        break
                    
                    # Temporary error - wait and retry
                    retry_delay = min(2 * failed_attempts, 5)  # Progressive delay: 2s, 4s, 5s, 5s...
                    logger.debug(f"Retrying metrics fetch in {retry_delay}s (attempt {failed_attempts}/{max_failed_attempts})...")
                    time.sleep(retry_delay)
            
            logger.info("Metrics monitoring stopped (logs unaffected)")
        
        except Exception as e:
            logger.error(f"Failed to start metrics monitoring (logs unaffected): {e}", exc_info=True)
            error_msg = f"Metrics unavailable: {str(e)}"
            self.error.emit(error_msg)
    
    def _handle_disconnect(self):
        """Handle disconnection action."""
        logger.info("Handling disconnect action")
        
        try:
            if self.ssh_manager:
                self.ssh_manager.disconnect()
            
            logger.info("Disconnected successfully")
            self.disconnected.emit()
        
        except Exception as e:
            logger.error(f"Disconnect failed: {e}", exc_info=True)
            error_msg = f"Disconnect failed: {str(e)}"
            self.output.emit(f"[ERROR] {error_msg}\n")
            self.error.emit(error_msg)
