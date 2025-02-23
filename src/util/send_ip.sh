#!/bin/bash

#get current server ip
network_interface=$(ip link show | awk '$9 == "UP" {print $2}' | sed 's/://g' | head -n 1)
server_ip_address=$(ip -4 addr show $network_interface | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

echo "GGTN current IP : $server_ip_address"

