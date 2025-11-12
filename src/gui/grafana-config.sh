#!/bin/bash

cd /usr/share/grafana/public/build
sudo sed -i 's|B\.M\.AppTitle|"gadgetini"|g' 3729.*.js
sudo sed -i 's|To\.M\.AppTitle|"gadgetini"|g' 3729.*.js
sudo sed -i 's/" - "/" | "/g' 3729.*.js
sudo systemctl restart grafana-server
sudo sed -i 's/;theme = dark/theme = light/g' /etc/grafana/grafana.ini
sudo sed -i 's/theme = dark/theme = light/g' /etc/grafana/grafana.ini

