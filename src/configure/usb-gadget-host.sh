#!/bin/bash
# Script for permanent USB Gadget connection settings on deepgadget (Host).
# This version does NOT rely on a fixed MAC address for the Host side.

# --- 1. Variable Configuration ---
# NM connection profile name
NM_CON_NAME="usb-gadget-host"
# Host static IP address (Changed to 10.12.194.2/28)
STATIC_IP="10.12.194.2/28"
# Static route for the gadget network (Changed to 10.12.194.0/28)
STATIC_ROUTE="10.12.194.0/28"
# The interface name is typically 'enx' followed by MAC address. We will not use MAC binding.
INTERFACE_PATTERN="usb"

# --- 2. NetworkManager Connection Profile Creation/Reset ---
# Delete existing profile for Idempotence (ensures script works whether this is first run or a reset)
sudo nmcli connection delete "${NM_CON_NAME}" 2>/dev/null

# Create new profile: Use 'match' to apply this profile to any interface that looks like a USB Ethernet device (e.g., 'enx').
sudo nmcli connection add type ethernet con-name "${NM_CON_NAME}" \
    ifname 'en*' # Apply to any ethernet-like interface, NM will prioritize based on connection context
    ipv4.method manual ipv4.addresses "${STATIC_IP}" connection.autoconnect yes

# Apply specific 'match' criteria to ensure it only applies to the RPi gadget interface if possible
# Note: 'match' is tricky without a fixed MAC. Relying on autoconnect and manual IP is often sufficient.
sudo nmcli connection modify "${NM_CON_NAME}" connection.match "type=ethernet"

echo "NM Profile '${NM_CON_NAME}' created successfully."


# --- 3. Persistent Static Route Addition ---
# Add the required static route (automatically applied on boot/connect)
sudo nmcli connection modify "${NM_CON_NAME}" ipv4.routes "${STATIC_ROUTE}"
echo "Route ${STATIC_ROUTE} added successfully."

# --- 4. Activate Connection (for testing) ---
# Attempt to activate the connection. This requires the gadget to be plugged in and ready.
sudo nmcli connection up "${NM_CON_NAME}"

