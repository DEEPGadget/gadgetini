import sys
import subprocess
import psutil

NETWORK_FILE = "/etc/systemd/network/eth0.network"

#-------------------------------------------------------------------------------
# Create a systemd-networkd style .network file
# Configures the network interface in DHCP mode
# For Raspberry Pi, the network device is fixed 'eth0'
#-------------------------------------------------------------------------------

def write_dhcp_config():
    content = """[Match]
Name=eth0

[Network]
DHCP=yes
"""
    with open(NETWORK_FILE, "w") as f:
        f.write(content)

#-------------------------------------------------------------------------------
# Converts a subnet mask (ex: '255.255.255.0') to CIDR notation (ex: '24')
# Calculates the number of 1-bits in the binary representation of the netmask
#-------------------------------------------------------------------------------

def mask_to_cidr(netmask):
    try:
        return sum([bin(int(x)).count("1") for x in netmask.split(".")])
    except Exception:
        print(f"Invalid netmask: {netmask}")
        sys.exit(1)

#-------------------------------------------------------------------------------
# Create a static IP configuration file for systemd-networkd
# Parameters:
#   ip      - Static IP address with subnet (ex: 192.168.1.100/24)
#   netmask - Subnet mask (ex: 255.255.255.0)
#   gateway - Default gateway address
#   dns1    - Primary DNS server
#   dns2    - (Optional) Secondary DNS server
# The configuration is applied to the 'eth0' network interface
# Written to /etc/systemd/network/eth0.network
#-------------------------------------------------------------------------------

def write_static_config(ip, netmask, gateway, dns1, dns2=None):
    cidr = mask_to_cidr(netmask)
    ip_with_cidr = f"{ip}/{cidr}"

    content = f"""[Match]
Name=eth0

[Network]
Address={ip_with_cidr}
Gateway={gateway}
DNS={dns1}"""
    if dns2:
        content += f"\nDNS={dns2}"
    content += "\n"

    with open(NETWORK_FILE, "w") as f:
        f.write(content)
    print("GGTN Static configuration written.")

#-------------------------------------------------------------------------------
# Get the current IPv4 address assigned to the 'eth0' network interface.
# - Gadgetini fixed network interface name 'eth0'
# - Uses psutil to check interface addresses
# - Filters for IPv4 and ignores loopback (127.*)
# - Returns the first valid address found, or None if unavailable
#-------------------------------------------------------------------------------

def get_eth0_ip():
    try:
        net_if_addrs = psutil.net_if_addrs()
        for addr in net_if_addrs.get("eth0", []):
            if addr.family == 2 and not addr.address.startswith("127."):
                return addr.address
    except Exception as e:
        print(f"Failed to get eth0 IP: {e}")
    return None

#-------------------------------------------------------------------------------
# Get and select a valid server IP address, then send it to the Redis file
# This block explains the following functions:
# - get_all_valid_ipv4(): Collects all valid non-loopback IPv4 addresses (non-loopback : 127.0.0.1)
# - select_ip_interactively(): Allows the user to choose one from the list
# - Server may have multiple network interfaces (ex: eth0, enp0, br0, eno0, etc.)
# - Each interface may have multiple IP addresses (ex: dual LAN ports, Docker, K8s, etc.)
# - Uses psutil to retrieve addresses for all interfaces
# - Returns a list of valid IPv4 addresses
# - User selects their server IP from the list and sends it to the Redis file
#-------------------------------------------------------------------------------


#-------------------------------------------------------------------------------
# Restart essential services after updating network configuration
# - Restarts systemd-networkd to apply new eth0.network settings
# - Restarts Prometheus for monitoring integration
# - Restarts custom display_pannel.service (for GGTTN display updates)
# - Prints success message if all succeed, or error message on failure
#-------------------------------------------------------------------------------

def restart_services():
    try:
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "restart", "systemd-networkd"], check=True)
        subprocess.run(["sudo", "systemctl", "restart", "prometheus"], check=True)
        subprocess.run(["sudo", "systemctl", "restart", "display_pannel.service"], check=True)
        print("All services restarted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to restart services: {e}")

#-------------------------------------------------------------------------------
# Main function to configure ggtn IP settings based on command-line arguments
# - Supports two modes: 'dhcp' and 'static'
# - Prompts user to select server IP from available non-loopback IPv4 addresses
# - Applies the network configuration to ggtn (eth0) using systemd-networkd format
# - Output inforamtion server IP selection and displays the configured ggtn IP
#-------------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  GGTN_set_ip.py dhcp")
        print("  GGTN_set_ip.py static <ip> <netmask> <gateway> <dns1> [dns2]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "dhcp":
        write_dhcp_config()
        #restart_services()

        ip = get_eth0_ip()
        if ip:
            print(f"ggtn DHCP IP address acquired: {ip}")
        else:
            print("DHCP IP address not yet acquired (check systemd-networkd status)")

    elif mode == "static":
        if len(sys.argv) < 6:
            print("Missing arguments for static mode.")
            print("Usage: static <ip> <netmask> <gateway> <dns1> [dns2]")
            sys.exit(1)
        ip = sys.argv[2]
        netmask = sys.argv[3]
        gateway = sys.argv[4]
        dns1 = sys.argv[5]
        dns2 = None
        if len(sys.argv) > 6:
            dns2 = sys.argv[6]
        write_static_config(ip, netmask, gateway, dns1, dns2)
        #restart_services()
        print(f"ggtn static IP address set to: {ip}/{mask_to_cidr(netmask)}")
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
