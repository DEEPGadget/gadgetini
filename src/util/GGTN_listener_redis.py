import redis
import os
import time

#-------------------------------------------------------------------------------
# get_and_apply_network_config()
# - Retrieves IP configuration from Redis keys
# - Builds and executes the corresponding command for GGTN_set_ip.py
# - Handles both DHCP and Static modes
#-------------------------------------------------------------------------------

def get_and_apply_network_config():
    rd = redis.Redis(host='localhost', port=6379, decode_responses=True)

    ip_mode   = rd.get("ggtn_ip_mode")
    ip        = rd.get("ggtn_ip_address")
    netmask   = rd.get("ggtn_netmask")
    gateway   = rd.get("ggtn_gateway")
    dns1      = rd.get("ggtn_dns1")
    dns2      = rd.get("ggtn_dns2")

    print("Redis Data : mode=", ip_mode, ", ip=", ip, ", netmask=", netmask, ", gateway=", gateway, ", dns1=", dns1, ", dns2=", dns2)

    if ip_mode == "dhcp":
        cmd = "sudo python3 /home/deepgadget/gadgetini/src/util/GGTN_set_ip.py dhcp"
    elif ip_mode == "static":
        if not all([ip, netmask, gateway, dns1]):
            print("Error Missing one or more static IP configuration values.")
            return

        cmd = f"sudo python3 /home/deepgadget/gadgetini/src/util/GGTN_set_ip.py static {ip} {netmask} {gateway} {dns1}"
        if dns2:
            cmd += f" {dns2}"
    else:
        print(f"Error Invalid or missing ip_mode: {ip_mode}")
        return

    print(f"Command : {cmd}")
    os.system(cmd)

#-------------------------------------------------------------------------------
# handle_message()
# - Handles incoming Pub/Sub messages from Redis
# - Executes configuration only when "apply_ip_config" is received
#-------------------------------------------------------------------------------

def handle_message(message):
    data = message['data']

    if isinstance(data, int):  
        return

    print("===================================")
    print(f"[Received Message Trigger] {data}")

    if data.strip() == "apply_ip_config":
        get_and_apply_network_config()
    else:
        print(f"Warning Unknown message trigger: {data}")

#-------------------------------------------------------------------------------
# main()
# - Subscribes to Redis channel "ggtn_cmd"
# - Continuously listens for new messages and handles them
#-------------------------------------------------------------------------------

def main():
    try:
        rd = redis.Redis(host='localhost', port=6379, decode_responses=True)
        p = rd.pubsub()
        p.subscribe("ggtn_cmd")
        print("GGTN Listener Listening on Redis channel 'ggtn_cmd'...")

        for message in p.listen():
            handle_message(message)

    except Exception as e:
        print(f"Error Redis listener failed: {e}")

if __name__ == "__main__":
    main()
