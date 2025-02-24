About gadgetini display module

*** service script

```
sudo vim /etc/systemd/system/display_pannel.service
```
```
[Unit]
Description=dg5w external LCD display pannel control daemon.
After=display_logo.service
Requires=networking.service
[Service]
Type=simple
ExecStart=python3 /home/gadgetini/gadgetini/src/display/display_main.py
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
```
