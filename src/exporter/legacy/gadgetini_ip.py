# Filename: change_ip_module.py
import redis
import subprocess
import re


class ChangeIPDaemon:
    def __init__(self, redis_host="localhost", redis_port=6379, redis_db=0,
                 redis_key="gadgetini_ip", nic_name="eth0", netmask="24",
                 prometheus_service="prometheus"):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_key = redis_key
        self.nic_name = nic_name
        self.netmask = netmask
        self.prometheus_service = prometheus_service
        self.channel = f"__keyspace@{redis_db}__:{redis_key}"
        self.redis_client = redis.StrictRedis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            decode_responses=True
        )

    @staticmethod
    def is_valid_ipv4(ip):
        """Check if the given string is a valid IPv4 address."""
        pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
        return re.match(pattern, ip) and all(0 <= int(o) <= 255 for o in ip.split("."))

    def get_current_ip(self):
        """Get the current IPv4 address of the NIC."""
        try:
            result = subprocess.run(
                ["ip", "-4", "addr", "show", self.nic_name],
                capture_output=True, text=True, check=True
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    return line.split()[1].split("/")[0]
        except subprocess.CalledProcessError:
            return None
        return None

    def change_ip(self, new_ip):
        """Change NIC IP and restart Prometheus service."""
        try:
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.nic_name], check=True)
            subprocess.run(
                ["sudo", "ip", "addr", "add", f"{new_ip}/{self.netmask}", "dev", self.nic_name],
                check=True
            )
            subprocess.run(["sudo", "ip", "link", "set", self.nic_name, "up"], check=True)
            print(f"[INFO] {self.nic_name} IP changed to {new_ip}")

            self.restart_prometheus()

        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to change IP: {e}")

    def restart_prometheus(self):
        """Restart Prometheus service."""
        try:
            subprocess.run(["sudo", "systemctl", "restart", self.prometheus_service], check=True)
            print(f"[INFO] Prometheus service '{self.prometheus_service}' restarted successfully.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to restart Prometheus: {e}")

    def run(self):
        """Listen for Redis key changes and update NIC IP only if it is different."""
        print("[INFO] Starting ChangeIPDaemon...")
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(self.channel)

        for message in pubsub.listen():
            if message["type"] == "message":
                event_type = message["data"]
                if event_type in ("set", "hset", "del"):
                    current_ip_val = self.redis_client.get(self.redis_key)
                    if current_ip_val and self.is_valid_ipv4(current_ip_val):
                        nic_ip = self.get_current_ip()
                        if nic_ip != current_ip_val:
                            print(f"[INFO] Detected Redis IP change -> {current_ip_val}")
                            self.change_ip(current_ip_val)
                        else:
                            print(f"[INFO] NIC already has IP {current_ip_val}, skipping changes.")
                    else:
                        print(f"[WARN] Invalid IP value: {current_ip_val}")


def main():
    """
    Standalone execution entry point.
    Requires Redis keyspace notifications enabled:
        redis-cli config set notify-keyspace-events K$
        redis-cli config rewrite
    """
    daemon = ChangeIPDaemon(
        redis_host="localhost",
        redis_port=6379,
        redis_db=0,
        redis_key="gadgetini_ip",
        nic_name="wlan0",
        netmask="24",
        prometheus_service="prometheus"
    )
    daemon.run()


if __name__ == "__main__":
    main()
