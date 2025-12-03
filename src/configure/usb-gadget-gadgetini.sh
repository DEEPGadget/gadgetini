#!/bin/bash
# Script for enabling USB Gadget Mode and permanent network settings on gadgetini (Gadget).
# This version overwrites cmdline.txt and config.txt with predefined content.

# --- 1. Variable Configuration ---
HOST_MAC="9a:1d:1d:0b:35:6b"  # MAC address passed to the host
GADGET_MAC="fe:f1:1a:d3:6e:b6"  # MAC address for gadgetini's usb0 interface
NM_CON_NAME="gadgetini"
STATIC_IP="192.168.4.1/24"
SERVICE_FILE="/etc/systemd/system/usb-gadget-${NM_CON_NAME}.service"

echo "### 1. Starting Script: USB Gadget Configuration (${NM_CON_NAME}) ###"

# --- 2. Overwrite /boot/firmware/cmdline.txt ---
# WARNING: This overwrites the entire file content with the provided configuration.
CMDLINE_FILE="/boot/firmware/cmdline.txt"
CMDLINE_CONTENT="overlayroot=tmpfs console=serial0,9600 root=PARTUUID=1e7ee8d2-02 rootfstype=ext4 fsck.repair=yes rootwait quiet splash plymouth.ignore-serial-consoles cfg80211.ieee80211_regdom=GB modules-load=dwc2,g_ether g_ether.host_addr=${HOST_MAC} g_ether.dev_addr=${GADGET_MAC}"

echo "### 2. Overwriting ${CMDLINE_FILE} with fixed MAC addresses ###"
# Using tee with sudo to overwrite the file content
sudo tee "${CMDLINE_FILE}" > /dev/null <<EOF
${CMDLINE_CONTENT}
EOF
echo "=> ${CMDLINE_FILE} overwritten successfully."


# --- 3. Overwrite /boot/firmware/config.txt ---
# WARNING: This overwrites the entire file content with the provided configuration.
CONFIG_FILE="/boot/firmware/config.txt"

echo "### 3. Overwriting ${CONFIG_FILE} for Gadget/System settings ###"
# Using tee with sudo to overwrite the file content
sudo tee "${CONFIG_FILE}" > /dev/null <<EOF
# For more options and information see
# http://rptl.io/configtxt
# Some settings may impact device functionality. See link above for details

# Uncomment some or all of these to enable the optional hardware interfaces
dtparam=i2c_arm=on
#dtparam=i2s=on
dtparam=spi=on

# Enable audio (loads snd_bcm2835)
dtparam=audio=on

# Additional overlays and parameters are documented
# /boot/firmware/overlays/README

# Automatically load overlays for detected cameras
camera_auto_detect=1

# Automatically load overlays for detected DSI displays
display_auto_detect=1

# Automatically load initramfs files, if found
auto_initramfs=1

# Enable DRM VC4 V3D driver
dtoverlay=vc4-kms-v3d
max_framebuffers=2

# Don't have the firmware create an initial video= setting in cmdline.txt.
# Use the kernel's default instead.
disable_fw_kms_setup=1

# Run in 64-bit mode
arm_64bit=1

# Disable compensation for displays with overscan
disable_overscan=1

# Run as fast as firmware / board allows
arm_boost=1

[cm4]
# Enable host mode on the 2711 built-in XHCI USB controller.
# This line should be removed if the legacy DWC2 controller is required
# (e.g. for USB device mode) or if USB support is not required.
# otg_mode=1

[cm5]
# dtoverlay=dwc2,dr_mode=host

[all]
dtoverlay=spi1-1cs
enable_uart=1
dtoverlay=disable-bt
dtoverlay=dwc2
EOF
echo "=> ${CONFIG_FILE} overwritten successfully."


# --- 4. NetworkManager Connection Profile Creation/Reset ---
echo "### 4. Creating/Resetting NetworkManager Connection Profile ###"

# Delete existing profile (for idempotent execution)
sudo nmcli connection delete "${NM_CON_NAME}" 2>/dev/null

# Create new profile: static IP assignment for usb0 interface, set to autoconnect
sudo nmcli connection add type ethernet ifname usb0 con-name "${NM_CON_NAME}" \
    ipv4.method manual ipv4.addresses "${STATIC_IP}" connection.autoconnect yes

echo "=> NM Profile '${NM_CON_NAME}' created successfully."


# --- 5. systemd Service File Creation (To ensure UP state on boot) ---
echo "### 5. Creating and Registering systemd Service File ###"

# Create the service file content
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

echo "=> Service file '${SERVICE_FILE}' created successfully."

# --- 6. systemd Service Registration and Activation ---
sudo systemctl daemon-reload
sudo systemctl enable "usb-gadget-${NM_CON_NAME}.service"
echo "=> Service registration and enabling complete. Will run automatically on next reboot."

echo "### Script Complete. Requires reboot of gadgetini. ###"
