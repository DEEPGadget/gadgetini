#!/bin/bash

config_file="/home/deepgadget/config.ini"

if [[ "$1" == "v" ]]; then
    #echo "Setting display mode to vertical..."
    sed -i 's/orientation=horizontal/orientation=vertical/' $config_file
    echo "Display mode set to vertical."
elif [[ "$1" == "h" ]]; then
    #echo "Setting display mode to horizontal..."
    sed -i 's/orientation=vertical/orientation=horizontal/' $config_file
    echo "Display mode set to horizontal."
else
    echo "Invalid option: $1"
    print_help
fi

