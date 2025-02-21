#!/bin/bash

#mode=$1

# Get the first available network interface for configuration
network_interface=$(ip -br link show | awk '$2 == "UP" {print $1}' | head -n 1)
dhcp_ip_address=$(ifconfig $network_interface | grep 'inet ' | awk '{print $2}')

if [ "$1" == "dhcp" ]; then
    echo "Configuring DHCP..."
    SERVER_IP_ADDR=$2
    CONFIG_FILE="/etc/systemd/network/static-ip.network"
    sudo bash -c "cat > $CONFIG_FILE <<EOF
[Match]
Name=$network_interface

[Network]
DHCP=yes
EOF"
    #sudo systemctl restart systemd-networkd
    echo "DHCP configured on $network_interface"
    echo "Current IP Address: $dhcp_ip_address"
else
    SERVER_IP_ADDR=$1
    IP_ADDR=$2
    GATEWAY=$3
    DNS1=$4
    DNS2=$5
    echo "Setting static IP with systemd-networkd..."
    echo "SERVER IP Address: $SERVER_IP_ADDR"
    echo "IP Address: $IP_ADDR"
    echo "Gateway: $GATEWAY"
    echo "Primary DNS: $DNS1"
    echo "Secondary DNS: $DNS2"

    CONFIG_FILE="/etc/systemd/network/static-ip.network"
    sudo bash -c "cat > $CONFIG_FILE <<EOF
[Match]
Name=$network_interface

[Network]
Address=$IP_ADDR
Gateway=$GATEWAY
DNS=$DNS1
DNS=$DNS2
EOF"
    #sudo systemctl restart systemd-networkd
fi

#SERVER_IP_ADDR=$1
#GGTN_IP_ADDR=$2
#GATEWAY=$3
#DNS1=$4
#DNS2=$5

FILES=(
    #"/etc/prometheus/prometheus.yml"
    #"/etc/chrony/chrony.conf"
    "/home/deepgadget/prometheus.yml"
    "/home/deepgadget/display_plot.py"
)

for FILE_PATH in "${FILES[@]}"; do
    if [ ! -f "$FILE_PATH" ]; then
        echo "Error: File '$FILE_PATH' does not exist. Skipping..."
        continue
    fi

    BACKUP_PATH="${FILE_PATH}.backup.$(date +%Y%m%d%H%M%S)"
    cp "$FILE_PATH" "$BACKUP_PATH"
    echo "Backup created for $FILE_PATH at: $BACKUP_PATH"

    IP_REGEX='([0-9]{1,3}\.){3}[0-9]{1,3}'
    if grep -E -q "$IP_REGEX" "$FILE_PATH"; then
        sed -i -E "s/$IP_REGEX/$SERVER_IP_ADDR/g" "$FILE_PATH"
        echo "Successfully replaced all IP addresses in $FILE_PATH"
    else
        echo "No IP address found in $FILE_PATH. Skipping..."
    fi
done

#sudo systemctl restart systemd-networkd
#sudo systemctl daemon-reload
#sudo systemctl restart prometheus
#sudo systemctl restart display_pannel.service

