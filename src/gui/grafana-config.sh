#!/bin/bash

cd /usr/share/grafana/public/build
sudo sed -i 's|B\.M\.AppTitle|"gadgetini"|g' 3729.*.js
sudo sed -i 's|To\.M\.AppTitle|"gadgetini"|g' 3729.*.js
sudo sed -i 's/" - "/" | "/g' 3729.*.js

sudo cp fav32.png /usr/share/grafana/public/img/fav32.png
sudo cp grafana_icon.svg /usr/share/grafana/public/img/grafana_icon.svg

sudo sed -i 's/;theme = dark/theme = light/g' /etc/grafana/grafana.ini
sudo sed -i 's/theme = dark/theme = light/g' /etc/grafana/grafana.ini

sudo systemctl restart grafana-server
