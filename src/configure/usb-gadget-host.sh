#!/bin/bash
# Script for permanent USB Gadget connection settings on deepgadget (Host)

# --- 1. Variable Configuration ---
# The fixed MAC address of the gadget recognized by the host (g_ether.host_addr from gadgetini's cmdline.txt)
GADGET_HOST_MAC="9a:1d:1d:0b:35:6b"
# NM connection profile name
NM_CON_NAME="gadgetini"
# Host static IP address
STATIC_IP="192.168.4.2/24"
# Static route for the gadget network
STATIC_ROUTE="192.168.4.0/24"

echo "### 1. Starting Script: USB Host Configuration ###"

# --- 2. NetworkManager Connection Profile Creation/Reset ---
echo "### 2. Creating/Resetting NetworkManager Connection Profile ###"

# Delete existing profile (for idempotent execution)
sudo nmcli connection delete "${NM_CON_NAME}" 2>/dev/null

# Create new profile: bind to the fixed MAC address for persistence across interface name changes (enx...)
sudo nmcli connection add type ethernet con-name "${NM_CON_NAME}" mac "${GADGET_HOST_MAC}" \
    ipv4.method manual ipv4.addresses "${STATIC_IP}" connection.autoconnect yes

echo "=> NM Profile '${NM_CON_NAME}' created successfully."


# --- 3. Persistent Static Route Addition ---
echo "### 3. Adding Persistent Static Route ###"

# Add the required static route to the NM profile (automatically applied on boot/connect)
sudo nmcli connection modify "${NM_CON_NAME}" ipv4.routes "${STATIC_ROUTE}"

echo "=> Route ${STATIC_ROUTE} added successfully."

# --- 4. Activate Connection (for testing before reboot) ---
echo "### 4. Activating Connection Immediately ###"
# Attempt to activate the newly created connection
sudo nmcli connection up "${NM_CON_NAME}" || echo "Warning: Connection might already be active or needs gadget connection."

echo "### Script Complete. Requires gadgetini to be connected and rebooted for full effect. ###"
