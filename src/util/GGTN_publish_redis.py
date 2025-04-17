import redis
import ipaddress
import sys
from Server_ip import get_selected_server_ip

#-------------------------------------------------------------------------------
# publish_dhcp_config(rd, server_ip)
# - Sets Redis keys related to DHCP mode for ggtn device
# - Clears IP, netmask, gateway, DNS1/2 values (empty)
# - Sets 'server_ip' key for reference
# - Publishes 'apply_ip_config' trigger to 'ggtn_cmd' Redis channel
#-------------------------------------------------------------------------------

def publish_dhcp_config(rd, server_ip):
    rd.set("ggtn_ip_mode", "dhcp")
    rd.set("ggtn_ip_address", "")
    rd.set("ggtn_netmask", "")
    rd.set("ggtn_gateway", "")
    rd.set("ggtn_dns1", "")
    rd.set("ggtn_dns2", "")
    rd.set("server_ip", server_ip)
    print(f"DHCP mode with server_ip={server_ip}")
    rd.publish("ggtn_cmd", "apply_ip_config")


#-------------------------------------------------------------------------------
#invalid IP foramt
#-------------------------------------------------------------------------------

def is_valid_ip(ip):
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        return False

#-------------------------------------------------------------------------------
# publish_static_config(rd, args, server_ip)
# - Sets Redis keys related to static IP mode for ggtn device
# - Parses static IP values from command-line arguments
#   - ip, netmask, gateway, dns1, [dns2]
# - Sets these values in Redis under expected keys
# - Also sets 'server_ip' for reference
# - Publishes 'apply_ip_config' to notify listener
#-------------------------------------------------------------------------------

def publish_static_config(rd, args, server_ip):
    if len(args) < 6:
        print("Usage: static <ip> <netmask> <gateway> <dns1> [dns2]")
        sys.exit(1)

    ip      = args[2]
    netmask = args[3]
    gateway = args[4]
    dns1    = args[5]
    if len(args) > 6:
        dns2 = args[6]
    else:
        dns2 = ""

    ip_fields = [ip, netmask, gateway, dns1]
    if dns2:
        ip_fields.append(dns2)

    for field in ip_fields:
        if not is_valid_ip(field):
            print(f"Error Invalid IP address format: {field}")
            sys.exit(1)

    rd.set("ggtn_ip_mode", "static")
    rd.set("ggtn_ip_address", ip)
    rd.set("ggtn_netmask", netmask)
    rd.set("ggtn_gateway", gateway)
    rd.set("ggtn_dns1", dns1)
    rd.set("ggtn_dns2", dns2)
    rd.set("server_ip", server_ip)

    print(f"static mode: IP={ip}, netmask={netmask}, gateway={gateway}, dns={dns1},{dns2}, ServerIP={server_ip}")
    rd.publish("ggtn_cmd", "apply_ip_config")


#-------------------------------------------------------------------------------
# main()
# - Entry point for the script
# - Parses mode from CLI args: either 'dhcp' or 'static'
# - Gets selected server IP via interactive prompt
# - Dispatches to appropriate publish function based on mode
#-------------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Invalid args")
        sys.exit(1)

    rd = redis.Redis(host='localhost', port=6379, decode_responses=True)
    mode = sys.argv[1]
    server_ip = get_selected_server_ip()

    if mode == "dhcp":
        publish_dhcp_config(rd, server_ip)
    elif mode == "static":
        publish_static_config(rd, sys.argv, server_ip)
    else:
        print("Invalid mode. Use 'dhcp' or 'static'.")
        sys.exit(1)

if __name__ == "__main__":
    main()
