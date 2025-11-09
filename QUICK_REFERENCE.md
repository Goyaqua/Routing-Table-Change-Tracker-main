# Quick Reference Card

## Installation

```bash
# Using requirements.txt
pip install -r requirements.txt

# OR install manually
pip install netmiko paramiko pyyaml psutil

# If pip not available
python3 -m pip install --user --break-system-packages netmiko paramiko pyyaml psutil
```

## Basic Commands

```bash
# Single check (manual mode)
python3 tracker.py check

# Continuous monitoring (daemon mode)
python3 tracker.py daemon

# Custom interval (120 seconds)
python3 tracker.py daemon --interval 120

# Custom config file
python3 tracker.py check --config my_config.yaml
```

## Configuration Quick Edit

Edit `config.yaml`:

```yaml
# Local mode (monitor local routing table)
mode: 'local'

# SSH mode (monitor remote router)
mode: 'ssh'
ssh_config:
  enabled: true
  host: 'localhost'      # or router IP
  port: 2222             # default: 22
  username: 'admin'
  password: 'admin123'
  device_type: 'generic' # Generic/virtual router
  commands:
    default: 'vtysh -c "show ip route"'  # Router command
```

## Quick Testing

### Docker FRRouting (5 min setup)
```bash
# 1. Start router
docker run -d --name frr-router --privileged -p 2222:22 frrouting/frr:latest

# 2. Configure SSH
docker exec frr-router apk add openssh openssh-server
docker exec frr-router ssh-keygen -A
docker exec frr-router adduser -D admin
docker exec frr-router sh -c 'echo "admin:admin123" | chpasswd'
docker exec frr-router sh -c 'echo "PermitRootLogin yes" >> /etc/ssh/sshd_config'
docker exec frr-router sh -c 'echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config'
docker exec frr-router /usr/sbin/sshd

# 3. Add test routes
docker exec frr-router vtysh -c "configure terminal" \
  -c "ip route 10.1.1.0/24 172.17.0.1" \
  -c "ip route 10.2.2.0/24 172.17.0.1" \
  -c "end" -c "write memory"

# 4. Fix permissions
docker exec frr-router sh -c 'addgroup admin frrvty 2>/dev/null || true'
docker exec frr-router sh -c 'mkdir -p /etc/frr && touch /etc/frr/vtysh.conf'

# 5. Update config.yaml to SSH mode (see Configuration section above)

# 6. Test
python3 tracker.py check
```

### Local Mode Testing
```bash
# Initial check
python3 tracker.py check

# Add test route
sudo ip route add 10.99.99.0/24 via 192.168.1.1

# Check again (will show change)
python3 tracker.py check

# Remove test route
sudo ip route del 10.99.99.0/24
```

## Log Files

Logs are saved in `logs/` directory:
- Format: `route_tracker_YYYYMMDD_HHMMSS.svc`
- View latest: `ls -lt logs/*.svc | head -1`
- Tail logs: `tail -f logs/route_tracker_*.svc`

## Background Execution

```bash
# Run in background
nohup python3 tracker.py daemon > /dev/null 2>&1 &

# Check if running
ps aux | grep tracker.py

# Kill process
pkill -f tracker.py
```

## Supported Router Types

- `generic` - FRRouting and generic routers (default)
- Any router accessible via SSH with routing table commands

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Config file not found` | Create `config.yaml` or specify with `--config` |
| `Netmiko not installed` | Run `pip install netmiko` |
| `SSH connection failed` | Check router IP, credentials, SSH enabled |
| `Permission denied` | Check file permissions, SSH keys |
| No changes detected | Verify snapshot file is writable |

## File Structure

```
.
├── tracker.py              # Main monitoring script
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
├── README.md              # Project overview
├── QUICK_REFERENCE.md     # This file
└── logs/                  # Log output directory
    ├── *.svc              # Service logs
    └── last_snapshot.txt  # Previous route snapshot
```

## Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `mode` | 'local' or 'ssh' | 'local' |
| `monitoring.interval_seconds` | Check interval | 60 |
| `logging.output_dir` | Log directory | './logs' |
| `logging.log_extension` | Log file extension | '.svc' |
| `statistics.enabled` | Collect network stats | true |

## Network Statistics Collected

- Bytes sent/received
- Packets sent/received
- Active connections by state
- Top 10 local ports
- Top 10 remote ports
- Network interface status
- Error and drop counts

## Advanced Usage

### Multiple Routers

```bash
# Router 1
python tracker.py daemon --config router1.yaml &

# Router 2
python tracker.py daemon --config router2.yaml &
```

### Systemd Service

Create `/etc/systemd/system/route-tracker.service`:

```ini
[Unit]
Description=Routing Table Change Tracker
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 tracker.py daemon
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable route-tracker
sudo systemctl start route-tracker
```

## Example Output

```
[2025-11-08 00:45:33] Route change detected!
[2025-11-08 00:45:33] Added routes:
[2025-11-08 00:45:33]   + 10.99.99.0/24 via 192.168.1.1 dev eth0
[2025-11-08 00:45:33] Network Traffic:
[2025-11-08 00:45:33]   Bytes sent: 45.23 MB
[2025-11-08 00:45:33]   Bytes received: 128.67 MB
```

## Help & Documentation

- Help: `python3 tracker.py --help`
- README.md: General overview and features
- QUICK_REFERENCE.md: This quick reference guide
- config.yaml: Configuration file

## Security Best Practices

1. Use SSH keys instead of passwords
2. Don't commit `config.yaml` with real credentials
3. Restrict file permissions: `chmod 600 config.yaml`
4. Use least-privilege router accounts
5. Monitor router SSH logs

## Common Use Cases

### Home Network Monitoring
```yaml
mode: 'local'
monitoring:
  interval_seconds: 300  # Check every 5 minutes
```

### Remote Router Monitoring
```yaml
mode: 'ssh'
ssh_config:
  enabled: true
  host: 'router.example.com'
  key_file: '/home/user/.ssh/router_key'
  device_type: 'generic'
  commands:
    default: 'show ip route'  # Or your router's command
```

### Lab/Testing Environment (FRRouting)
```yaml
mode: 'ssh'
ssh_config:
  host: 'localhost'
  port: 2222
  username: 'admin'
  password: 'admin123'
  device_type: 'generic'
  commands:
    default: 'vtysh -c "show ip route"'
monitoring:
  interval_seconds: 30  # Frequent checks for testing
```
