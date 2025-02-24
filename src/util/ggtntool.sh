#!/bin/bash

DIR=/home/gadgetini/gadgetini/src
#echo "$DIR/util"
#print help option
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

#get current server ip
network_interface=$(ip link show | awk '$9 == "UP" {print $2}' | sed 's/://g' | head -n 1)
server_ip_address=$(ip -4 addr show $network_interface | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

set_network() {
    if [[ $1 == "dhcp" ]]; then
        echo "Setting DHCP configuration..."
        #/home/gadgetini/gadgetini/src/util/GGTN_set_ip.sh $1 $server_ip_address
        $DIR/util/GGTN_set_ip.sh $1 $server_ip_address  
        return
    else
        if [[ $# -eq 4 ]] || [[ $# -eq 5 ]]; then
            local ip_address=$1
            local subnet_mask=$2
            local gateway=$3
            local dns_primary=$4
            local dns_secondary=${5:-""}  # Optional secondary DNS

            echo "Setting static IP configuration..."
            if ! validate_ip "$ip_address" || ! validate_ip "$gateway" || ! validate_ip "$dns_primary" || ( [[ -n $dns_secondary ]] && ! validate_ip "$dns_secondary" ); then
                echo "Validation failed for one or more IP addresses."
                return 1
            fi

            local cidr=$(subnet_to_cidr $subnet_mask)
            echo "IP address set to $ip_address/$cidr"
            echo "Gateway set to $gateway"
            echo "Primary DNS set to $dns_primary"
            [[ -n $dns_secondary ]] && echo "Secondary DNS set to $dns_secondary"
            echo "current server IP address : $server_ip_address"
            #/home/gadgetini/gadgetini/src/util/GGTN_set_ip.sh "$server_ip_address" "$ip_address/$cidr" "$gateway" "$dns_primary" "$dns_secondary"
	    $DIR/util/GGTN_set_ip.sh "$server_ip_address" "$ip_address/$cidr" "$gateway" "$dns_primary" "$dns_secondary"
            return
        else
            echo "Invalid arguments for setting network."
            return 1
        fi
    fi
}

#change display mode
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
