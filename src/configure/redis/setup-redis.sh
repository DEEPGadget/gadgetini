#!/bin/bash
# Redis setup for Gadgetini (Raspberry Pi side)
# Configures Redis to listen on the USB gadget IPv6 address so the host
# can write sensor metrics over the USB network.
set -e

REDIS_CONF="/etc/redis/redis.conf"
GADGET_IPV6="fd12:3456:789a:1::2"
SYSCTL_DROPIN="/etc/sysctl.d/99-gadgetini.conf"

if [ ! -f "$REDIS_CONF" ]; then
    echo "Error: $REDIS_CONF not found. Install redis first." >&2
    exit 1
fi

echo "=== Configuring Redis bind for USB gadget network ==="
if grep -qE "^bind .*${GADGET_IPV6}" "$REDIS_CONF"; then
    echo "  bind: already contains ${GADGET_IPV6}"
else
    sudo sed -i -E "s|^(bind[[:space:]]+.*)$|\1 ${GADGET_IPV6}|" "$REDIS_CONF"
    echo "  bind: appended ${GADGET_IPV6}"
fi

echo "=== Disabling protected-mode ==="
sudo sed -i 's/^protected-mode yes/protected-mode no/' "$REDIS_CONF"

echo "=== Installing sysctl drop-in ==="
sudo tee "$SYSCTL_DROPIN" > /dev/null <<EOF
net.ipv4.ip_nonlocal_bind=1
net.ipv6.ip_nonlocal_bind=1
EOF
sudo sysctl --system

echo "=== Restarting redis ==="
sudo systemctl restart redis
sudo systemctl status redis --no-pager -l
