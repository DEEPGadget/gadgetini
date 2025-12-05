#!/bin/bash

# --- Variable Configuration ---
GADGET_MAC="fe:f1:1a:d3:6e:b6"
NM_CON_NAME="usb-gadget-gadgetini"
STATIC_IP="10.12.194.1/28"
CMDLINE_FILE="/boot/firmware/cmdline.txt"
CONFIG_FILE="/boot/firmware/config.txt"
SERVICE_FILE="/etc/systemd/system/usb-gadget-up.service"


# --- Overwrite cmdline.txt ---
sudo sed -i 's/$/ modules-load=dwc2,g_ether g_ether.dev_addr=fe:f1:1a:d3:6e:b6/' /boot/firmware/cmdline.txt
echo "1. ${CMLINE_FILE} modified"

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
echo "2. ${CONFIG_FILE} overwritten"

echo "3. Gadget configuration complete (reboot required)"

