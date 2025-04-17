import sys
import subprocess
import psutil

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

def get_all_valid_ipv4():
    ip_list = []
    try:
        net_if_stats = psutil.net_if_addrs()
        for interface, addrs in net_if_stats.items():
            for addr in addrs:
                if addr.family == 2 and not addr.address.startswith("127."):
                    ip_list.append(addr.address)
        return ip_list
    except Exception as e:
        print(f"Error getting IP addresses: {e}")
        return []

def select_ip_interactively(ip_list):
    if not ip_list:
        print("No valid IP addresses found.")
        return None

    print("Valid IPv4 addresses found:")
    for idx, server_ip in enumerate(ip_list, 1):
        print(f"{idx}. {server_ip}")

    try:
        choice = int(input("Select the IP to use by number: "))
        if 1 <= choice <= len(ip_list):
            return ip_list[choice - 1]
        else:
            print("Invalid selection.")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

#-------------------------------------------------------------------------------
# To return selected IP (for use in other Python files)
#-------------------------------------------------------------------------------
def get_selected_server_ip():
    ip_list = get_all_valid_ipv4()
    selected_ip = select_ip_interactively(ip_list)

    if selected_ip:
        return selected_ip
    else:
        print("No IP selected. Exiting.")
        sys.exit(1)

def main():
    selected_ip = get_selected_server_ip()
    print(f"Selected Server IP: {selected_ip}")

if __name__ == "__main__":
    main()
