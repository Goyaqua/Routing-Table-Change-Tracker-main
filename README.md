# Routing Table Change Tracker

A Python-based CLI tool for **monitoring routing table changes** with support for both SSH router monitoring and local network tracking.

Monitor routing changes in real-time, log differences with timestamps, and collect comprehensive network statistics.

## Features

- **Dual Mode Operation**: SSH router monitoring or local Linux routing table tracking
- **Manual & Daemon Modes**: Single check or continuous periodic monitoring
- **Change Detection**: Unified diff format showing exactly what changed
- **Network Statistics**: Connection counts, top ports, traffic metrics, interface status
- **Service Logs**: Timestamped `.svc` log files with complete audit trail
- **Snapshot Comparison**: Persistent storage of previous states for accurate change detection
- **Router Support**: FRRouting, generic routers via SSH
- **Configurable**: YAML-based configuration for easy customization

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# OR install manually:
pip install netmiko paramiko pyyaml psutil

# If pip is not available:
python3 -m pip install --user --break-system-packages netmiko paramiko pyyaml psutil
```

### Basic Usage

**Manual check (single run):**
```bash
python3 tracker.py check
```

**Daemon mode (continuous monitoring):**
```bash
python3 tracker.py daemon
```

**Custom interval:**
```bash
python3 tracker.py daemon --interval 120
```

## Configuration

Edit [config.yaml](config.yaml) to configure monitoring mode and settings.

### Local Mode (Default)

Monitor your local Ubuntu/Linux routing table:

```yaml
mode: 'local'

local_config:
  command: 'ip route'
```

### SSH Mode

Monitor remote routers via SSH:

```yaml
mode: 'ssh'

ssh_config:
  enabled: true
  host: 'localhost'      # Router IP or hostname
  port: 2222             # SSH port (default: 22)
  username: 'admin'
  password: 'admin123'
  device_type: 'generic' # Generic/virtual router

  commands:
    default: 'vtysh -c "show ip route"'  # Router command
```

## Usage Examples

### Manual Mode

Execute a single route check:

```bash
python3 tracker.py check
```

Output:
```
[2025-11-08 17:00:17] ============================================================
[2025-11-08 17:00:17] Routing Table Change Tracker Started
[2025-11-08 17:00:17] Mode: ssh
[2025-11-08 17:00:17] ============================================================
[2025-11-08 17:00:17] Connecting to router localhost...
[2025-11-08 17:00:17] Authentication (password) successful!
[2025-11-08 17:00:17] Successfully retrieved routing table from router
[2025-11-08 17:00:17] Route change detected!
[2025-11-08 17:00:17] Added routes:
[2025-11-08 17:00:17]   + S>* 10.3.3.0/24 [1/0] via 172.17.0.1, eth0, weight 1, 00:00:09
```

### Daemon Mode

Run continuous monitoring every 60 seconds:

```bash
python3 tracker.py daemon
```

Run in background:
```bash
nohup python3 tracker.py daemon > /dev/null 2>&1 &
```

### Custom Configuration

```bash
python3 tracker.py check --config router1_config.yaml
```

## Log Files

Logs are saved as `.svc` files with timestamps:

```
logs/route_tracker_20251108_004533.svc
```

Example log content:
```
[2025-11-08 00:45:33] ============================================================
[2025-11-08 00:45:33] Routing Table Change Tracker Started
[2025-11-08 00:45:33] Mode: local
[2025-11-08 00:45:33] ============================================================
[2025-11-08 00:45:33] Route change detected!
[2025-11-08 00:45:33] ------------------------------------------------------------
[2025-11-08 00:45:33] Added routes:
[2025-11-08 00:45:33]   + 10.99.99.0/24 via 192.168.1.1 dev eth0
[2025-11-08 00:45:33] Network Statistics:
[2025-11-08 00:45:33] ------------------------------------------------------------
[2025-11-08 00:45:33] Network Traffic:
[2025-11-08 00:45:33]   Bytes sent: 45.23 MB
[2025-11-08 00:45:33]   Bytes received: 128.67 MB
[2025-11-08 00:45:33] Active Connections: 42
[2025-11-08 00:45:33]   ESTABLISHED: 15
[2025-11-08 00:45:33]   LISTEN: 12
```

## Testing

### Option 1: Docker FRRouting Router (Recommended)

The fastest way to test with a virtual router:

```bash
# Start FRR container
docker run -d --name frr-router --privileged -p 2222:22 frrouting/frr:latest

# Configure SSH and add routes
# Full setup instructions in QUICK_REFERENCE.md - takes only 5 minutes!

# Test
python3 tracker.py check
```

### Option 2: Local Testing

Test on your local Ubuntu/Linux machine:

```bash
# Run initial check
python3 tracker.py check

# Add a test route
sudo ip route add 10.99.99.0/24 via 192.168.1.1

# Run check again to see changes
python3 tracker.py check

# Remove test route
sudo ip route del 10.99.99.0/24
```

## Network Statistics

The tracker collects comprehensive network statistics using `psutil`:

- **Traffic Metrics**: Bytes/packets sent and received
- **Active Connections**: Connection counts by state (ESTABLISHED, LISTEN, etc.)
- **Port Statistics**: Most frequently used local and remote ports
- **Interface Status**: Network interface states and speeds
- **Error/Drop Counts**: Network errors and dropped packets

Enable/disable in [config.yaml](config.yaml):

```yaml
statistics:
  enabled: true
  collect_connections: true
  collect_ports: true
  collect_traffic: true
```

## Documentation

- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick command reference
- **[config.yaml](config.yaml)** - Configuration file reference

## Current Setup

This project is currently configured with:
- **Mode**: SSH (FRRouting Docker container)
- **Router**: localhost:2222 (frr-router container)
- **Test Routes**: 10.1.1.0/24, 10.2.2.0/24, 10.3.3.0/24, 192.168.100.0/24

**Container Management:**
```bash
docker ps | grep frr-router          # Check status
docker exec frr-router vtysh         # Access router CLI
docker stop frr-router               # Stop router
docker start frr-router              # Start router
docker rm frr-router                 # Remove container
```

---
