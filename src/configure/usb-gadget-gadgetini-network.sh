#!/bin/bash

# --- Variable Configuration ---
NM_CON_NAME="usb-gadget-gadgetini"
STATIC_IP="10.12.194.1/28"
SERVICE_FILE="/etc/systemd/system/usb-gadget-up.service"

# --- NetworkManager connection profile ---
sudo nmcli connection delete "${NM_CON_NAME}" 2>/dev/null || true
sudo nmcli connection add type ethernet ifname usb0 con-name "${NM_CON_NAME}" \
    ipv4.method manual ipv4.addresses "${STATIC_IP}" connection.autoconnect yes
sudo nmcli connection modify "${NM_CON_NAME}" ipv4.route-metric 700
echo "1. NM profile created (${NM_CON_NAME})"

# --- Systemd service creation ---
sudo tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=Activate Gadget USB Network Connection
After=network-online.target

[Service]
ExecStart=/usr/bin/nmcli connection up ${NM_CON_NAME} ifname usb0
Type=oneshot
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "usb-gadget-up.service"
echo "2. systemd service enabled (usb-gadget-up.service)"

