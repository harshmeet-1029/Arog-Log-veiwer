# Security Documentation

## Overview

This document outlines the security features, considerations, and best practices for the Argo Log Viewer application.

## Security Features Implemented

### 1. SSH Connection Security

#### Host Key Verification
- **Protection Against**: Man-in-the-Middle (MITM) attacks
- **Implementation**: Uses `paramiko.WarningPolicy()` by default instead of blindly accepting all SSH keys
- **Configuration**: Can enable strict host key checking via environment variable
- **Environment Variable**: `ARGO_STRICT_HOST_KEY_CHECKING=true`

**Recommendation**: For production environments, enable strict host key checking and properly manage your `~/.ssh/known_hosts` file.

```bash
export ARGO_STRICT_HOST_KEY_CHECKING=true
```

#### SSH Key Authentication
- Uses SSH key-based authentication (configured in `~/.ssh/config`)
- No passwords are stored or transmitted
- Keys are loaded from your standard SSH configuration

### 2. Command Injection Prevention

#### Input Sanitization
All user inputs are sanitized before being used in commands:

**Pod Names:**
- Validates RFC 1123 DNS label standard
- Only allows alphanumeric, dash, and dot characters
- Must start and end with alphanumeric characters
- Maximum 253 characters (Kubernetes limit)

**Search Keywords:**
- Removes all special shell characters
- Only allows alphanumeric, dash, underscore, and dot
- Prevents patterns starting with dash (could be interpreted as command options)

**Implementation:**
- `_sanitize_pod_name()` in `app/kubernetes/operations.py`
- `_sanitize_grep_pattern()` in `app/kubernetes/operations.py`
- Uses `shlex.quote()` for additional shell escaping

### 3. Log Injection Prevention

#### Safe Logging
- All user inputs are sanitized before logging
- Control characters and newlines are removed to prevent log forgery
- Long strings are truncated to prevent log flooding
- Errors are sanitized to prevent information leakage

**Implementation:**
- `sanitize_for_logging()` function in `app/kubernetes/operations.py`

### 4. Read-Only Operations

The application implements **read-only** Kubernetes operations only:

**Allowed Commands:**
- `kubectl get` - List resources
- `kubectl logs` - View logs
- `kubectl describe` - Get resource details

**Prohibited Commands:**
- `kubectl apply` - Create/update resources
- `kubectl delete` - Delete resources
- `kubectl exec` - Execute commands in pods
- `kubectl scale` - Scale resources
- Any other write operations

### 5. Secure File Permissions

When saving logs to files:
- Files are created with restrictive permissions: `0600` (owner read/write only)
- Prevents other users from reading potentially sensitive log data
- Unix-like systems only (Linux, macOS)

### 6. Configuration Security

#### Externalized Configuration
Hardcoded credentials and connection details have been removed. Configuration is loaded from environment variables:

**Environment Variables:**
- `ARGO_JUMP_HOST` - Jump host hostname (default: "usejump")
- `ARGO_INTERNAL_HOST` - Internal server IP/hostname (default: "10.0.34.231")
- `ARGO_SERVICE_ACCOUNT` - Service account username (default: "solutions01-prod-us-east-1-eks")
- `ARGO_NAMESPACE` - Kubernetes namespace (default: "argo")
- `SSH_CONFIG_PATH` - SSH config file path (default: "~/.ssh/config")
- `ARGO_LOG_SANITIZATION` - Enable log sanitization (default: "true")
- `ARGO_STRICT_HOST_KEY_CHECKING` - Strict SSH host key checking (default: "false")

**Example Configuration:**
```bash
export ARGO_JUMP_HOST="my-jump-server"
export ARGO_INTERNAL_HOST="192.168.1.100"
export ARGO_SERVICE_ACCOUNT="my-k8s-user"
export ARGO_NAMESPACE="production"
export ARGO_STRICT_HOST_KEY_CHECKING=true
```

## Security Best Practices

### For Users

1. **SSH Key Management**
   - Use strong SSH keys (RSA 4096-bit or Ed25519)
   - Protect your private keys with passphrases
   - Never share your private keys
   - Regularly rotate SSH keys

2. **Host Key Verification**
   - Verify SSH host keys on first connection
   - Enable strict host key checking in production
   - Maintain your `~/.ssh/known_hosts` file

3. **Environment Security**
   - Run the application in a secure environment
   - Don't run as root/administrator unless necessary
   - Keep your system and dependencies updated

4. **Log Files**
   - Protect saved log files (they may contain sensitive data)
   - Regularly clean up old log files
   - Don't share logs containing sensitive information

5. **Network Security**
   - Use secure networks when connecting to production systems
   - Consider VPN when accessing from untrusted networks
   - Be aware of network monitoring/logging

### For Administrators

1. **SSH Server Configuration**
   - Disable password authentication
   - Use key-based authentication only
   - Configure proper firewall rules
   - Monitor SSH access logs
   - Implement rate limiting for SSH connections

2. **Kubernetes RBAC**
   - Grant minimal required permissions
   - Use service accounts with read-only access
   - Implement namespace-level isolation
   - Regularly audit RBAC policies

3. **Jump Host Security**
   - Harden jump host configuration
   - Implement multi-factor authentication (MFA)
   - Monitor and log all access
   - Regular security updates

4. **Network Segmentation**
   - Isolate production networks
   - Use bastion/jump hosts properly
   - Implement network ACLs
   - Monitor network traffic

## Known Limitations

### 1. Host Key Policy
By default, the application uses `WarningPolicy()` which warns about unknown hosts but still connects. For maximum security, enable strict host key checking.

### 2. Logging
Debug logs may contain detailed system information. In production:
- Disable file logging for compiled executables (already implemented)
- Protect log files with appropriate permissions
- Consider centralizing logs to a secure logging system

### 3. SSH Connection Chain
The application establishes a multi-hop SSH connection. Each hop in the chain is a potential security consideration:
- Windows/WSL → Jump Host → Internal Server → Service Account
- Ensure each hop is properly secured

### 4. GUI Application
As a GUI application:
- No built-in authentication mechanism
- Physical/local access security is assumed
- Credentials are system-level (SSH keys)

## Vulnerability Reporting

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email security concerns to: harshmeet.singh@netcoreunbxd.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work to address confirmed vulnerabilities promptly.

## Security Audit History

### Version 1.0.0 (January 2026)
- Initial security review conducted
- Fixed SSH `AutoAddPolicy` vulnerability (CRITICAL)
- Strengthened command injection prevention (HIGH)
- Removed hardcoded credentials (HIGH)
- Added log injection prevention (MEDIUM)
- Implemented secure file permissions (MEDIUM)
- Created comprehensive security documentation

## Compliance Considerations

### Data Protection
- Application does not store credentials
- SSH keys managed by operating system
- Logs may contain sensitive data - handle appropriately
- No telemetry or external data transmission

### Audit Trail
- All operations are logged locally
- SSH connections logged by system SSH
- Kubernetes operations logged by cluster audit logs

## Future Security Enhancements

Planned security improvements:

1. **Certificate-Based Authentication**
   - Support for SSH certificate authorities
   - Automated key rotation

2. **Audit Logging**
   - Centralized audit logging
   - Tamper-evident logs

3. **Session Management**
   - Connection timeouts
   - Automatic session cleanup

4. **Advanced Input Validation**
   - More sophisticated command validation
   - Context-aware input sanitization

5. **Security Scanning**
   - Regular dependency vulnerability scanning
   - Automated security testing

## References

- [OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
- [CWE-78: Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- [CWE-117: Log Injection](https://cwe.mitre.org/data/definitions/117.html)
- [SSH Best Practices](https://www.ssh.com/academy/ssh/security)
- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/overview/)

## License

This security documentation is part of the Argo Log Viewer project.
© 2024-2026 Harshmeet Singh. All rights reserved.
