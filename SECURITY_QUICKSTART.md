# Quick Start - Security Configuration

## For Immediate Use (Development)

The application works out of the box with default settings. However, for production use, follow the security hardening steps below.

## Security Hardening (Production)

### 1. Configure Environment Variables

Create a file to set your environment variables (or add to your shell profile):

```bash
# Copy the example configuration
cp env.example .env

# Edit with your values
nano .env  # or use your preferred editor
```

**Minimum Production Settings:**
```bash
export ARGO_STRICT_HOST_KEY_CHECKING=true
export ARGO_JUMP_HOST="your-jump-host"
export ARGO_INTERNAL_HOST="your-k8s-server-ip"
export ARGO_SERVICE_ACCOUNT="your-service-account"
```

### 2. Set Up SSH Keys

Ensure your SSH keys are properly configured:

```bash
# Generate SSH key if you don't have one (RSA 4096-bit recommended)
ssh-keygen -t rsa -b 4096 -C "your-email@example.com"

# Or use Ed25519 (more modern)
ssh-keygen -t ed25519 -C "your-email@example.com"

# Add your public key to authorized servers
ssh-copy-id -i ~/.ssh/id_rsa.pub your-jump-host
```

### 3. Configure SSH Config

Edit your `~/.ssh/config`:

```
Host usejump
    HostName your-jump-server.example.com
    User your-username
    IdentityFile ~/.ssh/id_rsa
    Port 22

# Add other hosts as needed
```

### 4. Verify Host Keys

**IMPORTANT**: Manually verify SSH host keys on first connection:

```bash
# Connect manually first to verify and add host keys
ssh usejump

# Verify the fingerprint matches your server's actual fingerprint
# (Check with your system administrator)
```

### 5. Load Environment Variables

Before running the application:

```bash
# Source your environment file
source .env

# Or export variables manually
export ARGO_STRICT_HOST_KEY_CHECKING=true
export ARGO_JUMP_HOST="your-jump-host"
# ... other variables
```

### 6. Run the Application

```bash
# For development
python -m app.main

# Or run the compiled executable
./dist/ArgoLogViewer
```

## Security Checklist

Before deploying to production:

- [ ] SSH keys generated and deployed
- [ ] SSH config properly configured
- [ ] Host keys verified and added to known_hosts
- [ ] Strict host key checking enabled (`ARGO_STRICT_HOST_KEY_CHECKING=true`)
- [ ] Environment variables configured
- [ ] File permissions on sensitive files (private keys, logs) set to 600
- [ ] Application tested with production credentials
- [ ] Kubernetes RBAC configured with read-only permissions
- [ ] Reviewed `SECURITY.md` documentation

## Quick Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARGO_JUMP_HOST` | usejump | Jump host hostname |
| `ARGO_INTERNAL_HOST` | 10.0.34.231 | Internal K8s server |
| `ARGO_SERVICE_ACCOUNT` | solutions01-prod-us-east-1-eks | Service account |
| `ARGO_NAMESPACE` | argo | Kubernetes namespace |
| `ARGO_STRICT_HOST_KEY_CHECKING` | false | Enable strict SSH verification (ENABLE FOR PRODUCTION) |
| `ARGO_LOG_SANITIZATION` | true | Enable log sanitization |
| `SSH_CONFIG_PATH` | ~/.ssh/config | Path to SSH config |

### Security Features Enabled

✅ SSH host key verification  
✅ Command injection prevention  
✅ Log injection prevention  
✅ Secure file permissions (0600 for saved logs)  
✅ Read-only Kubernetes operations  
✅ Input sanitization and validation  

## Troubleshooting

### "Host key verification failed"
- Your SSH host keys are not configured
- Solution: Connect manually first: `ssh usejump` and verify the fingerprint

### "Connection refused"
- Check firewall rules
- Verify SSH server is running
- Check your SSH config

### "Permission denied (publickey)"
- Your SSH key is not authorized on the server
- Solution: Add your public key to the server's `~/.ssh/authorized_keys`

### "Unknown configuration 'ARGO_XXX'"
- Environment variables not loaded
- Solution: `source .env` before running the application

## Additional Resources

- **Full Security Documentation**: See `SECURITY.md`
- **Security Fixes Summary**: See `SECURITY_FIXES.md`
- **Configuration Examples**: See `env.example`

## Support

For security-related questions or to report vulnerabilities:
- Email: harshmeet.singh@netcoreunbxd.com
- Please DO NOT open public issues for security vulnerabilities

---

**Last Updated**: January 12, 2026  
**Version**: 1.0.0
