#!/bin/bash

IP_ADDR=$1
GATEWAY=$2
DNS1=$3
DNS2=$4
echo "set_ip.sh's data information"
echo "$1"
echo "$2"
echo "$3"
echo "$4"


echo "Available network interfaces:"
network_interface=$(ip link show | grep "BROADCAST,MULTICAST" | cut -d: -f2 | awk '{$1=$1};1')
echo "configure your network interface"

CONFIG_FILE="/etc/netplan/01-netcfg.yaml"
sudo bash -c "cat > $CONFIG_FILE <<EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    \"$network_interface\":
      dhcp4: no
      addresses:
        - \"$IP_ADDR/24\"
      gateway4: \"$GATEWAY\"
      nameservers:
        addresses:
          - \"$DNS1\"
          - \"$DNS2\"
EOF"

sudo netplan apply

