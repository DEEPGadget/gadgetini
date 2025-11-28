#!/bin/bash

# Grafana customzing
cd /usr/share/grafana/public/build
sudo sed -i 's|B\.M\.AppTitle|"gadgetini"|g' 3729.*.js
sudo sed -i 's|To\.M\.AppTitle|"gadgetini"|g' 3729.*.js
sudo sed -i 's/" - "/" | "/g' 3729.*.js
sudo sed -i 's/Welcome to Grafana/Gadgetini Dashboard/g' ./3729.be5ac8a04a9e69d79ca7.js
cd /home/gadgetini/gadgetini/src/gui/grafana
sudo cp ./fav32.png /usr/share/grafana/public/img/fav32.png
sudo cp ./grafana_icon.svg /usr/share/grafana/public/img/grafana_icon.svg

# Grafana alarm setting
sudo cp alert.yaml /etc/grafana/provisioning/alerting/

# Grafana theme setting
sudo sed -i 's/;defalut_theme = dark/default_theme = light/g' /etc/grafana/grafana.ini
sudo sed -i 's/default_theme = dark/default_theme = light/g' /etc/grafana/grafana.ini
sudo sed -i 's/;default_theme = light/default_theme = light/g' /etc/grafana/grafana.ini

sudo systemctl restart grafana-server
