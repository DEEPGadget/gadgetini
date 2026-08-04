#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

SERVICES=(
    "data_crawler.service"
    "gadgetini_net_up.service"
    "nvidia-pm.service"
)

echo "=== Configuring USB Gadget Network ==="
if command -v nmcli >/dev/null 2>&1 && systemctl is-active --quiet NetworkManager; then
    sudo bash "${SCRIPT_DIR}/../../../configure/usb_net/usb-gadget-host.sh"
else
    echo "  Skipping usb-gadget-host.sh (no NetworkManager); gadgetini_net_up.service will handle the link"
fi
echo ""

echo "=== Installing Python venv and dependencies ==="
sudo mkdir -p /opt/gadgetini
sudo apt install -y python3-venv python3-pip
sudo python3 -m venv /opt/gadgetini/venv
sudo /opt/gadgetini/venv/bin/python -m pip install --upgrade pip
sudo /opt/gadgetini/venv/bin/python -m pip install redis jsons rich
sudo cp -f "${SCRIPT_DIR}/../../../exporter/data_crawler_host.py" /opt/gadgetini/
echo "  venv ready at /opt/gadgetini/venv"

echo ""
echo "=== Copying service files ==="
for svc in "${SERVICES[@]}"; do
    sudo cp -f "${SCRIPT_DIR}/${svc}" "${SYSTEMD_DIR}/"
    echo "  Copied: ${svc}"
done

# mlnx template: copy only (no [Install] section, managed by OFED)
sudo cp -f "${SCRIPT_DIR}/mlnx_interface_mgr@.service" "${SYSTEMD_DIR}/"
echo "  Copied: mlnx_interface_mgr@.service (template only)"

echo ""
echo "=== Reloading systemd ==="
sudo systemctl daemon-reload

echo ""
echo "=== Enabling and starting services ==="
for svc in "${SERVICES[@]}"; do
    sudo systemctl enable "${svc}"
    sudo systemctl restart "${svc}"
    echo "  Enabled & started: ${svc}"
done

echo ""
echo "=== Service status ==="
for svc in "${SERVICES[@]}"; do
    echo "--- ${svc} ---"
    sudo systemctl status "${svc}" --no-pager -l
    echo ""
done
