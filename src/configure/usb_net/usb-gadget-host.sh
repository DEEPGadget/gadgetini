#!/bin/bash

# --- Variable Configuration ---
NM_CON_NAME="usb-gadget-host"
STATIC_IP="fd12:3456:789a:1::1/64"

echo "Searching for USB Gadget interface..."

# --- Interface Detection ---
if ip link show enxfef11ad36eb7 > /dev/null 2>&1; then
    IFNAME="enxfef11ad36eb7"
    echo "Found primary interface: $IFNAME"
elif ip link show usb0 > /dev/null 2>&1; then
    IFNAME="usb0"
    echo "Found fallback interface: $IFNAME"
else
    echo "Error: No suitable USB Gadget interface found (checked enxfef11ad36eb7 and usb0)."
    echo "Please check 'ip a' and your physical connection."
    exit 1
fi

# --- NetworkManager connection (reset & create) ---
echo "Deleting existing connection profile..."
sudo nmcli connection delete "${NM_CON_NAME}" 2>/dev/null || true

echo "Creating new connection profile for $IFNAME..."
sudo nmcli connection add type ethernet \
  con-name "${NM_CON_NAME}" \
  ifname "${IFNAME}" \
  ipv6.method manual \
  ipv6.addresses "${STATIC_IP}" \
  connection.autoconnect yes

echo "Modifying routing and metrics..."
sudo nmcli connection modify "${NM_CON_NAME}" ipv4.routes "${STATIC_ROUTE}"
sudo nmcli connection modify "${NM_CON_NAME}" ipv4.route-metric 700

echo "Activating connection..."
sudo nmcli connection up "${NM_CON_NAME}"

echo "--------------------------------------------------"
echo "1. NM profile created (${NM_CON_NAME}) & activated"
echo "2. Interface used: ${IFNAME}"
echo "3. Assigned IP: ${STATIC_IP}"
echo "--------------------------------------------------"

ip addr show "$IFNAME"
