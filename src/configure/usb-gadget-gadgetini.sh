#!/bin/bash

# --- Variable Configuration ---
GADGET_MAC="fe:f1:1a:d3:6e:b6"
NM_CON_NAME="usb-gadget-gadgetini"
STATIC_IP="10.12.194.1/28"
CMDLINE_FILE="/boot/firmware/cmdline.txt"
CONFIG_FILE="/boot/firmware/config.txt"
SERVICE_FILE="/etc/systemd/system/usb-gadget-up.service"

CMDLINE_CONTENT="overlayroot=tmpfs console=serial0,9600 root=PARTUUID=1e7ee8d2-02 rootfstype=ext4 fsck.repair=yes rootwait quiet splash plymouth.ignore-serial-consoles cfg80211.ieee80211_regdom=GB modules-load=dwc2,g_ether g_ether.dev_addr=${GADGET_MAC}"

# --- Overwrite cmdline.txt ---
sudo tee "${CMDLINE_FILE}" > /dev/null <<EOF
${CMDLINE_CONTENT}
EOF
echo "1. cmdline overwritten"

# --- Overwrite config.txt ---
sudo tee "${CONFIG_FILE}" > /dev/null <<EOF
# For more options and information see
# http://rptl.io/configtxt

dtparam=i2c_arm=on
dtparam=spi=on
dtparam=audio=on

camera_auto_detect=1
display_auto_detect=1
auto_initramfs=1

dtoverlay=vc4-kms-v3d
max_framebuffers=2
disable_fw_kms_setup=1

arm_64bit=1
disable_overscan=1
arm_boost=1

[cm4]
# otg_mode=1

[cm5]
# dtoverlay=dwc2,dr_mode=host

[all]
dtoverlay=spi1-1cs
enable_uart=1
dtoverlay=disable-bt
dtoverlay=dwc2
EOF
echo "2. config overwritten"

# --- NetworkManager connection profile ---
sudo nmcli connection delete "${NM_CON_NAME}" 2>/dev/null || true
sudo nmcli connection add type ethernet ifname usb0 con-name "${NM_CON_NAME}" \
    ipv4.method manual ipv4.addresses "${STATIC_IP}" connection.autoconnect yes
sudo nmcli connection modify "${NM_CON_NAME}" ipv4.route-metric 700
echo "3. NM profile created (${NM_CON_NAME})"

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
echo "4. systemd service enabled (usb-gadget-up.service)"

echo "5. Gadget configuration complete (reboot required)"

