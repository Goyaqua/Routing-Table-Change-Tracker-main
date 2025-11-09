#!/usr/bin/env python3
"""
Routing Table Change Tracker
Monitors routing tables via SSH (routers) or locally (Linux systems)
Supports both manual execution and daemon mode with periodic checks
"""

import subprocess
import time
import logging
import os
import sys
import argparse
import yaml
import difflib
import psutil
from datetime import datetime
from collections import Counter
from typing import Dict, List, Tuple, Optional

# Netmiko import with error handling
try:
    from netmiko import ConnectHandler
    NETMIKO_AVAILABLE = True
except ImportError:
    NETMIKO_AVAILABLE = False


class RouteTracker:
    """Main route tracking class supporting SSH and local modes"""

    def __init__(self, config_file='config.yaml'):
        """Initialize the route tracker with configuration"""
        self.config = self.load_config(config_file)
        self.previous_routes = None
        self.setup_directories()
        self.setup_logging()

    def load_config(self, config_file: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            print(f"Error: Config file '{config_file}' not found")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            sys.exit(1)

    def setup_directories(self):
        """Create necessary directories"""
        output_dir = self.config['logging']['output_dir']
        os.makedirs(output_dir, exist_ok=True)

    def setup_logging(self):
        """Configure logging to .svc file with timestamps"""
        output_dir = self.config['logging']['output_dir']
        log_ext = self.config['logging']['log_extension']
        prefix = self.config['logging']['file_prefix']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        self.log_file = os.path.join(output_dir, f'{prefix}_{timestamp}{log_ext}')

        # Configure file logging
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(self.log_file),
            ]
        )

        # Add console handler if enabled
        if self.config['logging']['enable_console']:
            console = logging.StreamHandler()
            console.setLevel(logging.INFO)
            formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            console.setFormatter(formatter)
            logging.getLogger().addHandler(console)

        logging.info("=" * 60)
        logging.info("Routing Table Change Tracker Started")
        logging.info(f"Mode: {self.config['mode']}")
        logging.info(f"Log file: {self.log_file}")
        logging.info("=" * 60)

    def get_routes_ssh(self) -> Optional[str]:
        """Get routing table from router via SSH using Netmiko"""
        if not NETMIKO_AVAILABLE:
            logging.error("Netmiko not installed. Install with: pip install netmiko")
            return None

        ssh_config = self.config['ssh_config']

        if not ssh_config.get('enabled', False):
            logging.error("SSH mode selected but not enabled in config")
            return None

        device = {
            'device_type': ssh_config['device_type'],
            'host': ssh_config['host'],
            'port': ssh_config.get('port', 22),
            'username': ssh_config['username'],
            'timeout': self.config['monitoring']['check_timeout'],
        }

        # Add password or key file
        if 'password' in ssh_config:
            device['password'] = ssh_config['password']
        if 'key_file' in ssh_config:
            device['key_file'] = ssh_config['key_file']

        try:
            logging.info(f"Connecting to router {ssh_config['host']}...")
            connection = ConnectHandler(**device)

            # Get command from config
            commands = ssh_config.get('commands', {})
            command = commands.get('default', 'show ip route')

            logging.info(f"Executing command: {command}")
            output = connection.send_command(command)
            connection.disconnect()

            logging.info("Successfully retrieved routing table from router")
            return output

        except Exception as e:
            logging.error(f"SSH connection failed: {e}")
            return None

    def get_routes_local(self) -> Optional[str]:
        """Get local routing table using ip route command"""
        command = self.config['local_config']['command']

        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=self.config['monitoring']['check_timeout']
            )

            if result.returncode == 0:
                logging.info("Successfully retrieved local routing table")
                return result.stdout
            else:
                logging.error(f"Command failed with return code {result.returncode}")
                logging.error(f"Error: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logging.error(f"Command timed out after {self.config['monitoring']['check_timeout']} seconds")
            return None
        except Exception as e:
            logging.error(f"Error executing local command: {e}")
            return None

    def check_routes(self) -> Optional[str]:
        """Get routing table based on configured mode"""
        mode = self.config['mode']

        if mode == 'ssh':
            return self.get_routes_ssh()
        elif mode == 'local':
            return self.get_routes_local()
        else:
            logging.error(f"Invalid mode: {mode}. Must be 'ssh' or 'local'")
            return None

    def load_previous_snapshot(self) -> Optional[str]:
        """Load previous routing table snapshot from file"""
        if not self.config['snapshot']['store_previous']:
            return None

        snapshot_file = self.config['snapshot']['snapshot_file']

        if os.path.exists(snapshot_file):
            try:
                with open(snapshot_file, 'r') as f:
                    return f.read()
            except Exception as e:
                logging.warning(f"Could not load previous snapshot: {e}")
                return None
        return None

    def save_snapshot(self, routes: str):
        """Save current routing table snapshot to file"""
        if not self.config['snapshot']['store_previous']:
            return

        snapshot_file = self.config['snapshot']['snapshot_file']

        try:
            os.makedirs(os.path.dirname(snapshot_file), exist_ok=True)
            with open(snapshot_file, 'w') as f:
                f.write(routes)
        except Exception as e:
            logging.warning(f"Could not save snapshot: {e}")

    def compare_and_log_changes(self, previous: str, current: str):
        """Compare two routing tables and log differences"""
        if previous == current:
            logging.info("No routing table changes detected")
            return

        logging.info("Route change detected!")
        logging.info("-" * 60)

        # Generate unified diff
        previous_lines = previous.splitlines(keepends=True)
        current_lines = current.splitlines(keepends=True)

        diff = difflib.unified_diff(
            previous_lines,
            current_lines,
            fromfile='Previous Routes',
            tofile='Current Routes',
            lineterm=''
        )

        diff_output = list(diff)

        if diff_output:
            logging.info("Routing table diff:")
            for line in diff_output:
                logging.info(line.rstrip())

        logging.info("-" * 60)

        # Log added and removed routes
        previous_set = set(previous.splitlines())
        current_set = set(current.splitlines())

        added = current_set - previous_set
        removed = previous_set - current_set

        if added:
            logging.info("Added routes:")
            for route in sorted(added):
                if route.strip():
                    logging.info(f"  + {route}")

        if removed:
            logging.info("Removed routes:")
            for route in sorted(removed):
                if route.strip():
                    logging.info(f"  - {route}")

        logging.info("=" * 60)

    def collect_network_stats(self):
        """Collect and log network statistics using psutil"""
        if not self.config['statistics']['enabled']:
            return

        logging.info("Network Statistics:")
        logging.info("-" * 60)

        try:
            # Network I/O counters
            if self.config['statistics']['collect_traffic']:
                net_io = psutil.net_io_counters()
                logging.info(f"Network Traffic:")
                logging.info(f"  Bytes sent: {self.format_bytes(net_io.bytes_sent)}")
                logging.info(f"  Bytes received: {self.format_bytes(net_io.bytes_recv)}")
                logging.info(f"  Packets sent: {net_io.packets_sent:,}")
                logging.info(f"  Packets received: {net_io.packets_recv:,}")
                logging.info(f"  Errors in: {net_io.errin}, Errors out: {net_io.errout}")
                logging.info(f"  Drops in: {net_io.dropin}, Drops out: {net_io.dropout}")

            # Active connections
            if self.config['statistics']['collect_connections']:
                connections = psutil.net_connections(kind='inet')
                logging.info(f"\nActive Connections: {len(connections)}")

                # Count by status
                status_count = Counter(conn.status for conn in connections)
                for status, count in status_count.most_common():
                    logging.info(f"  {status}: {count}")

            # Top ports
            if self.config['statistics']['collect_ports']:
                local_ports = [conn.laddr.port for conn in connections if conn.laddr]
                remote_ports = [conn.raddr.port for conn in connections if conn.raddr]

                top_count = self.config['statistics']['top_ports_count']

                if local_ports:
                    logging.info(f"\nTop {top_count} Local Ports:")
                    for port, count in Counter(local_ports).most_common(top_count):
                        logging.info(f"  Port {port}: {count} connections")

                if remote_ports:
                    logging.info(f"\nTop {top_count} Remote Ports:")
                    for port, count in Counter(remote_ports).most_common(top_count):
                        logging.info(f"  Port {port}: {count} connections")

            # Network interfaces
            if_addrs = psutil.net_if_addrs()
            if_stats = psutil.net_if_stats()

            logging.info(f"\nNetwork Interfaces:")
            for interface, stats in if_stats.items():
                status = "UP" if stats.isup else "DOWN"
                speed = f"{stats.speed} Mbps" if stats.speed > 0 else "Unknown"
                logging.info(f"  {interface}: {status}, Speed: {speed}")

        except Exception as e:
            logging.error(f"Error collecting network statistics: {e}")

        logging.info("=" * 60)

    @staticmethod
    def format_bytes(bytes_value: int) -> str:
        """Format bytes into human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"

    def log_changes(self, message: str):
        """Log a message with timestamp"""
        logging.info(message)

    def run_once(self):
        """Execute a single route check"""
        logging.info("Starting single route check...")

        # Get current routes
        current_routes = self.check_routes()

        if current_routes is None:
            logging.error("Failed to retrieve routing table")
            return False

        # Load previous snapshot
        previous_routes = self.load_previous_snapshot()

        if previous_routes is None:
            logging.info("No previous snapshot found - this is the first run")
            logging.info(f"Current routing table has {len(current_routes.splitlines())} entries")
        else:
            # Compare and log changes
            self.compare_and_log_changes(previous_routes, current_routes)

        # Collect network statistics
        self.collect_network_stats()

        # Save current snapshot
        self.save_snapshot(current_routes)

        logging.info("Route check completed")
        return True

    def run_periodically(self, interval: Optional[int] = None):
        """Run route checks periodically (daemon mode)"""
        if interval is None:
            interval = self.config['monitoring']['interval_seconds']

        logging.info(f"Starting periodic monitoring (interval: {interval} seconds)")
        logging.info("Press Ctrl+C to stop monitoring")

        try:
            # Run first check immediately
            self.run_once()

            # Continue periodic checks
            while True:
                time.sleep(interval)
                self.run_once()

        except KeyboardInterrupt:
            logging.info("Monitoring stopped by user")
            logging.info("Tracker shutdown complete")
        except Exception as e:
            logging.error(f"Unexpected error in daemon mode: {e}")
            raise


def main():
    """Main entry point with CLI argument parsing"""
    parser = argparse.ArgumentParser(
        description='Routing Table Change Tracker - Monitor routing changes via SSH or locally',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Manual check:
    python tracker.py check

  Daemon mode (periodic monitoring):
    python tracker.py daemon

  Daemon with custom interval:
    python tracker.py daemon --interval 120

  Use custom config file:
    python tracker.py check --config my_config.yaml
        """
    )

    parser.add_argument(
        'mode',
        choices=['check', 'daemon'],
        help='Execution mode: "check" for single run, "daemon" for continuous monitoring'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )

    parser.add_argument(
        '--interval',
        type=int,
        help='Monitoring interval in seconds (daemon mode only, overrides config)'
    )

    args = parser.parse_args()

    # Validate config file exists
    if not os.path.exists(args.config):
        print(f"Error: Config file '{args.config}' not found")
        sys.exit(1)

    # Initialize tracker
    try:
        tracker = RouteTracker(config_file=args.config)
    except Exception as e:
        print(f"Error initializing tracker: {e}")
        sys.exit(1)

    # Execute based on mode
    if args.mode == 'check':
        # Manual mode - single execution
        if args.interval:
            print("Warning: --interval is ignored in 'check' mode")

        success = tracker.run_once()
        sys.exit(0 if success else 1)

    elif args.mode == 'daemon':
        # Daemon mode - periodic execution
        tracker.run_periodically(interval=args.interval)


if __name__ == "__main__":
    main()
