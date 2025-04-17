#!/bin/bash

#-------------------------------------------------------------------------------
# All relate path base working directory 'DIR'
#-------------------------------------------------------------------------------

DIR="/home/deepgadget/gadgetini/src"

#echo "$DIR/util"

#-------------------------------------------------------------------------------
# Print print_help()
# Display ggtntool command-line tool
# Show usage guide for ggtntool
# Use '--help' option 
# If input invalid or unknown argument, print print_help() 
#-------------------------------------------------------------------------------

print_help() {
    echo "Usage: ggtntool command [options]"
    echo "Commands:"
    echo "  --help            Display ggtn command help message"
    echo "  set               Set system configurations"
    echo "    network         Set IP address (dhcp, static)"
    echo "    displaymode     Set ggtn display mode, v : vertical, h : horizontal"
    echo "    time            Set ggtn time"
    echo "  get               Get system information"
    echo "    monitoring      Get grafana monitoring link"
    echo "    time            Get ggtn time"
    echo "    network         Get ggtn ip"
    echo "  import            Import configuration"
    echo "    gpu             Import gpu dashboard json"
    echo "    tt              Import tt dashboard json"
}

#-------------------------------------------------------------------------------
# Set ggtn ip dhcp or static
# Supports two modes:
#   - dhcp : enables DHCP on eth0
#   - static : sets a static IP with netmask, gateway, and DNS
# *secondary_dns is optional
# Usage:
#   ggtntool set network dhcp
#   ggtntool set network static <ip_address> <netmask> <gateway> <primary_dns> [secondary_dns]
#-------------------------------------------------------------------------------

set_network() {
    if [[ $1 == "dhcp" ]]; then
        echo "Setting DHCP configuration..."
        #python3 $DIR/util/Server_ip.py
        #python3 $DIR/util/GGTN_set_ip.py $1
        python3 $DIR/util/GGTN_publish_redis.py $1
        return
    elif [[ $1 == "static" ]]; then
        IP_ADDR=$2
        NETMASK=$3
        GATEWAY=$4
        DNS1=$5
        DNS2=$6

        if [[ -z "$IP_ADDR" || -z "$NETMASK" || -z "$GATEWAY" || -z "$DNS1" ]]; then
            echo "Error: Missing arguments for static IP configuration."
            echo "Usage: ggtntool set network static <ip_address> <netmask> <gateway> <primary_dns> [secondary_dns]"
            return 1
        fi

        echo "Setting Static IP configuration..."
        if [[ -n "$DNS2" ]]; then
            echo "With Secondary DNS: $DNS2"
            #python3 $DIR/util/Server_ip.py
            #python3 $DIR/util/GGTN_set_ip.py $1 "$IP_ADDR" "$NETMASK" "$GATEWAY" "$DNS1" "$DNS2"
            python3 $DIR/util/GGTN_publish_redis.py $1 "$IP_ADDR" "$NETMASK" "$GATEWAY" "$DNS1" "$DNS2"
        else
            #python3 $DIR/util/Server_ip.py
            #python3 $DIR/util/GGTN_set_ip.py $1 "$IP_ADDR" "$NETMASK" "$GATEWAY" "$DNS1"
            python3 $DIR/util/GGTN_publish_redis.py $1 "$IP_ADDR" "$NETMASK" "$GATEWAY" "$DNS1"
        fi
        return
    else
        echo "Invalid network mode. Use 'dhcp' or 'static'."
        return 1
    fi
}

#-------------------------------------------------------------------------------
# Set display mode (orientation) for ggtn screen
# - Input argument 'v' (vertical) or 'h' (horizontal)
# - Passes the argument to GGTN_set_displaymode.py script for actual update
# Example usage:
# - ggtntool set displaymode v  → set to vertical mode
# - ggtntool set displaymode h  → set to horizontal mode
# If input invalid or unknown argument, print print_help()
#-------------------------------------------------------------------------------
set_displaymode() {
    #/home/gadgetini/gadgetini_monitoring_tool/service_scripts/config.ini
    #config_file="/home/deepgadget/config.ini"

    if [[ "$1" == "v" ]]; then
        echo "Setting display mode to vertical..."
        #sed -i 's/orientation=horizontal/orientation=vertical/' $config_file
        #./GGTN_set_displaymode.sh $1
        #/home/gadgetini/gadgetini/src/util/GGTN_set_displaymode.sh $1
        $DIR/util/GGTN_set_displaymode.sh $1
        #echo "Display mode set to vertical."
    elif [[ "$1" == "h" ]]; then
        echo "Setting display mode to horizontal..."
        #sed -i 's/orientation=vertical/orientation=horizontal/' $config_file
        #./GGTN_set_displaymode.sh $1
        #/home/gadgetini/gadgetini/src/util/GGTN_set_displaymode.sh $1
        $DIR/util/GGTN_set_displaymode.sh $1	
        #echo "Display mode set to horizontal."
    else
        echo "Invalid option: $1"
        print_help
    fi
}

set_time() {
    current_server_time=$(date '+%Y-%m-%d %H:%M:%S')
    $DIR/util/set_time.sh $current_server_time
}
 
get_monitoring() {
    $DIR/util/send_monitoring.sh
}

get_time() {
    $DIR/util/send_time.sh 
}

get_network() {
    $DIR/util/send_ip.sh
}

import() {
    if [[ "$1" == "tt" ]]; then
        echo "Set dashboard.json..."
	cp "$DIR/configure/tt-dashboard.json" /etc/grafana/provisioning/dashboards/
	cp "$DIR/configure/change_json.yaml" /etc/grafana/provisioning/dashboards/
    elif [[ "$1" == "gpu" ]]; then
        cp "$DIR/configure/gpu-dashboard.json" /etc/grafana/provisioning/dashboards/
	cp "$DIR/configure/change_json.yaml" /etc/grafana/provisioning/dashboards/
    else
        echo "Invalid option: $1"
	print_help
    fi
}


case "$1" in
    --help)
        print_help
        ;;
    set)
        case "$2" in
            network)
                shift 2
                set_network "$@"
                ;;
            displaymode)
                set_displaymode "$3"
                ;;
            time)
                set_time
                ;;
            *)
                echo "Invalid set option: $2"
                print_help
                ;;
        esac
        ;;
    get)
        case "$2" in
            monitoring)
                get_monitoring
                ;;
            time)
                get_time
                ;;
            ip)
                get_network
                ;;
            *)
                echo "Invalid get option: $2"
                print_help
                ;;
        esac
        ;;
    import)
        case "$2" in
            gpu)
                import_gpu
                ;;
            tt)
                import_tt
                ;;
            *)
                echo "Invalid import option: $2"
                print_help
                ;;
        esac
        ;;
    *)
        echo "Unknown command: $1"
        print_help
        ;;
esac
