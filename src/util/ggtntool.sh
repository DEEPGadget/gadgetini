#!/bin/bash

#-------------------------------------------------------------------------------
# All relate path base working directory 'DIR'
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Print print_help()
# Display ggtntool command-line tool
# Show usage guide for ggtntool
# Use '--help' option 
# If input invalid or unknown argument, print print_help() 
#-------------------------------------------------------------------------------

print_help() {
    echo "Usage: ggtntool <command> [options]"
    echo ""
    echo "Available Commands:"
    echo "  --help"
    echo "      Display this help message"
    echo ""
    echo "  set                Configure system settings"
    echo "    network"
    echo "        Set IP address mode (dhcp or static)"
    echo "        Usage: ggtntool set network dhcp"
    echo "               ggtntool set network static [ipaddress] [netmask] [gateway] [dns1] [dns2]"
    echo ""
    echo "    displaymode"
    echo "        Set display mode (v: vertical, h: horizontal)"
    echo "        Usage: ggtntool set displaymode v"
    echo "               ggtntool set displaymode h"
    echo ""
    echo "    time"
    echo "        Set current system time"
    echo "        Usage: ggtntool set time"
    echo ""
    echo "  get                Get system information"
    echo "    monitoring"
    echo "        Get Grafana monitoring link"
    echo "        Usage: ggtntool get monitoring"
    echo ""
    echo "    ip"
    echo "        Get Server IP, GGtN IP address"
    echo "        Usage: ggtntool get ip"
    echo ""
    echo "    displaymode"
    echo "        Get current display mode"
    echo "        Usage: ggtntool get displaymode"
    echo ""
    echo "    time"
    echo "        Get current system time"
    echo "        Usage: ggtntool get time"
    echo ""
    echo "  import             Import dashboard configuration"
    echo "    gpu"
    echo "        Import GPU dashboard JSON"
    echo "        Usage: ggtntool import gpu"
    echo ""
    echo "    tt"
    echo "        Import Tenstorrent dashboard JSON"
    echo "        Usage: ggtntool import tt"
}

# select server IP
select_server_ip() {
    local ips=()
    local i=1

    echo "Available IPv4 addresses:"

    for ip in $(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v "^127"); do
        echo "$i) $ip"
        ips+=("$ip")
        ((i++))
    done

    if [[ ${#ips[@]} -eq 0 ]]; then
        echo "No valid IPv4 addresses found."
        exit 1
    fi

    read -p "Select the IP to use by number: " choice
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || (( choice < 1 || choice > ${#ips[@]} )); then
        echo "Invalid selection."
        exit 1
    fi

    selected_ip="${ips[$((choice-1))]}"
    echo "Selected Server IP: $selected_ip"
    redis-cli set server_ip "$selected_ip"
    
}



# Subnet Mask to CIDR Conversion
subnet_to_cidr() {
    local subnet_mask=$1
    local -i cidr=0
    IFS='.' read -ra ADDR <<< "$subnet_mask"
    for octet in "${ADDR[@]}"; do
        while [ $octet -gt 0 ]; do
            cidr=$((cidr + (octet & 1)))
            octet=$((octet >> 1))
        done
    done
    echo $cidr
}

# Validate IP Address
validate_ip() {
    local ip=$1
    if [[ $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        IFS='.' read -ra ADDR <<< "$ip"
        for octet in "${ADDR[@]}"; do
            if ((octet < 0 || octet > 255)); then
                echo "Error: '$ip' is not a valid IP address."
                return 1
            fi
        done
        return 0
    else
        echo "Error: '$ip' is not a valid IP address."
        return 1
    fi
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

select_server_ip

    if [[ $1 == "dhcp" ]]; then
        echo "Setting DHCP configuration..."
        #python3 $DIR/util/Server_ip.py
        #python3 $DIR/util/GGTN_set_ip.py $1
        #python3 $DIR/util/GGTN_publish_redis.py $1
        redis-cli set ggtn_ip_mode "$1"
        redis-cli set ggtn_netmask ""
        redis-cli set ggtn_gateway ""
        redis-cli set ggtn_dns1 ""
        redis-cli set ggtn_dns2 ""
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

        for ip in "$IP_ADDR" "$NETMASK" "$GATEWAY" "$DNS1" "$DNS2"; do
            if [[ -n "$ip" ]]; then
                validate_ip "$ip" || return 1
            fi
        done

        CIDR=$(subnet_to_cidr "$NETMASK")
        echo "Converted $NETMASK to CIDR: /$CIDR"

        echo "Setting Static IP configuration..."
        redis-cli set ggtn_ip_mode "static"
        redis-cli set ggtn_ip_address "$IP_ADDR/$CIDR"
        redis-cli set ggtn_netmask "$NETMASK"
        redis-cli set ggtn_gateway "$GATEWAY"
        redis-cli set ggtn_dns1 "$DNS1"
        [[ -n "$DNS2" ]] && redis-cli set ggtn_dns2 "$DNS2"

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
    if [[ "$1" == "v" ]]; then
        echo "Setting display mode to vertical..."
        redis-cli set ggtn_displaymode "vertical"
    elif [[ "$1" == "h" ]]; then
        echo "Setting display mode to horizontal..."
        redis-cli set ggtn_displaymode "horizontal"
    else
        echo "Invalid option: $1"
        print_help
    fi
}

set_time() {
    server_time=$(date -Iseconds)
    redis-cli set ggtntime "$server_time"
    echo "ggtn time : $server_time"
    easy_read_time=$(date -d "$server_time" +"%Y-%m-%d %H:%M:%S") 
    echo "ggtn time : $easy_read_time"
}
 
get_monitoring() {
    monitoring_ip=$(redis-cli get ggtn_ip_address)
    get_monitoring_ip=$(echo "$monitoring_ip" | cut -d'/' -f1)
    echo "monitoring dashboard url : http://$get_monitoring_ip"
}

get_time() {
    get_ggtn_time=$(redis-cli get ggtntime)
    echo "ggtn time : $get_ggtn_time"
}

get_network() {
    get_server_ip=$(redis-cli get server_ip)
    raw_ggtn_ip=$(redis-cli get ggtn_ip_address)
    get_ggtn_ip=$(echo "$raw_ggtn_ip" | cut -d'/' -f1)
    
    echo "Server IP : $get_server_ip"
    echo "ggtn IP : $get_ggtn_ip"
}

get_displaymode() {
    get_display_arg=$(redis-cli get ggtn_displaymode)
    echo "ggtn displaymode : $get_display_arg"
}

import() {
    if [[ "$1" == "tt" ]]; then
        echo "Set dashboard.json..."
        import_tt_dashboard=$(redis-cli set import "$1")
        get_tt_dashboard=$(redis-cli get import)
        echo "wait...import_tt_dashboard.."
        echo "state dashboard : $get_tt_dashboard" 
    elif [[ "$1" == "gpu" ]]; then
        echo "Set dashboard.json..."
        import_gpu_dashboard=$(redis-cli set import "$1")
        get_gpu_dashboard=$(redis-cli get import)
        echo "wait...import_gpu_dashboard.."
        echo "state dashboard : $get_gpu_dashboard"
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
            displaymode)
                get_displaymode
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
                import "$2"
                ;;
            tt)
                import "$2"
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
