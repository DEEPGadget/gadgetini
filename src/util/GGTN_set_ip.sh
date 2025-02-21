#!/bin/bash

SERVER_IP_ADDR=$1
GGTN_IP_ADDR=$2
GATEWAY=$3
DNS1=$4
DNS2=$5
echo "set_ip.sh's data information"
echo "$1"
echo "$2"
echo "$3"
echo "$4"
echo "$5"

FILES=(
    #"/etc/prometheus/prometheus.yml"
    #"/etc/chrony/chrony.conf"
    "/home/deepgadget/prometheus.yml"
    "/home/deepgadget/display_plot.py"
)

for FILE_PATH in "${FILES[@]}"; do
    # ▒▒▒▒ ▒▒▒ ▒▒▒▒ Ȯ▒▒
    if [ ! -f "$FILE_PATH" ]; then
        echo "Error: File '$FILE_PATH' does not exist. Skipping..."
        continue
    fi

    BACKUP_PATH="${FILE_PATH}.backup.$(date +%Y%m%d%H%M%S)"
    cp "$FILE_PATH" "$BACKUP_PATH"
    echo "Backup created for $FILE_PATH at: $BACKUP_PATH"

    IP_REGEX='([0-9]{1,3}\.){3}[0-9]{1,3}'
    if grep -E -q "$IP_REGEX" "$FILE_PATH"; then
        sed -i -E "s/$IP_REGEX/$1/g" "$FILE_PATH"
        echo "Successfully replaced all IP addresses in $FILE_PATH"
    else
        echo "No IP address found in $FILE_PATH. Skipping..."
    fi
done



CONFIG_FILE="/etc/systemd/network/static-ip.network"
sudo bash -c "cat > $CONFIG_FILE <<EOF
[Match]
Name=wlan0

[Network]
Address=$2/24
Gateway=$3
DNS=$4
DNS=$5
EOF"



#sudo systemctl restart systemd-networkd
#sudo systemctl daemon-reload
#sudo systemctl restart prometheus
#sudo systemctl restart display_pannel.service

