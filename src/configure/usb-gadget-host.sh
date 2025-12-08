#!/bin/bash

# --- Variable Configuration ---
NM_CON_NAME="usb-gadget-host"
STATIC_IP="10.12.194.2/28"
STATIC_ROUTE="10.12.194.0/28"
IFNAME="enxfef11ad36eb7"

# --- NetworkManager connection (reset & create) ---
sudo nmcli connection delete "${NM_CON_NAME}" 2>/dev/null || true
sudo nmcli connection add type ethernet \
  con-name "${NM_CON_NAME}" \
  ifname "${IFNAME}" \
  ipv4.method manual \
  ipv4.addresses "${STATIC_IP}" \
  connection.autoconnect yes
echo "1. NM profile created (${NM_CON_NAME})"

# --- Apply route and metric ---
sudo nmcli connection modify "${NM_CON_NAME}" ipv4.routes "${STATIC_ROUTE}"
sudo nmcli connection modify "${NM_CON_NAME}" ipv4.route-metric 700
echo "2. Route and metric applied"

# --- Activate connection ---
sudo nmcli connection up "${NM_CON_NAME}"
echo "3. Connection activated (${NM_CON_NAME})"

