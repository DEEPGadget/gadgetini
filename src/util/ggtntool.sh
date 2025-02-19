#!/bin/bash

#print help option
print_help() {
    echo "Usage: ggtntool command [options]"
    echo "Commands:"
    echo "  --help            Display ggtn command help message"
    echo "  set               Set system configurations"
    echo "    ip              Set IP address (Server IP, main DNS, serve DNS, ggtn IP, main DNS, serve DNS"
    echo "    displaymode     Set ggtn display mode, v : vertical, h : horizontal"
    echo "    time            Set system time"
    echo "  get               Get system information"
    echo "    monitoring      Get grafana monitoring link"
    echo "    time            Get system time"
    echo "    ip              Get ggtn ip"
    echo "  import            Import configuration"
    echo "    gpu             Import gpu dashboard json"
    echo "    tt              Import tt dashboard json"
}

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

#set static server ip, gadgetini ip
set_ip() {
    echo "Setting static IP for Server..."
    echo "Set server IP"
    read server_ip
    if ! validate_ip "$server_ip"; then
        exit 1
    fi
    #echo "$server_ip"

    echo "Set server gateway"
    read server_gateway
    if ! validate_ip "$server_gateway"; then
        exit 1
    fi
    #echo "$server_gateway"

    echo "set server main dns"
    read server_primary_dns
    if ! validate_ip "$server_primary_dns"; then
        exit 1
    fi
    #echo "$server_primary_dns"

    echo "set server serve dns"
    read server_secondary_dns
    if ! validate_ip "$server_secondary_dns"; then
        exit 1
    fi
    #echo "$server_secondary_dns"

    #check network interface
    #echo "Available network interfaces:"
    #ip link show | grep "BROADCAST,MULTICAST" | cut -d: -f2 | awk '{$1=$1};1'
    #read INTERFACE
    #network_interface=$INTERFACE
    #echo "network interface is : $network_interface"

    # Send server IP information to set_ip.sh
    #./set_ip.sh $server_ip $server_gateway $server_primary_dns $server_secondary_dns

    echo "Setting static IP for Gadgetini..."
    echo "Set ggtn IP"
    read ggtn_ip
    if ! validate_ip "$ggtn_ip"; then
        exit 1
    fi

    echo "Set ggtn gateway"
    read ggtn_gateway
    if ! validate_ip "$ggtn_ip"; then
        exit 1
    fi

    echo "Set ggtn main dns"
    read ggtn_primary_dns
    if ! validate_ip "$ggtn_primary_dns"; then
        exit 1
    fi

    echo "Set ggtn serve dns"
    read ggtn_secondary_dns
    if ! validate_ip "$ggtn_secondary_dns"; then
        exit 1
    fi

    # Output the settings
    echo "Server static IP: $server_ip"
    echo "Server Gateway: $server_gateway"
    echo "Server primary DNS: $server_primary_dns"
    echo "Server secondary DNS: $server_secondary_dns"
    echo "--------------------------------"
    echo "Gadgetini static IP: $ggtn_ip"
    echo "Gadgetini Gateway: $ggtn_gateway"
    echo "Gadgetini primary DNS: $ggtn_primary_dns"
    echo "Gadgetini secondary DNS: $ggtn_secondary_dns"
    echo "--------------------------------" 
    echo "IP setting complete...."
    echo "Please rejoin new IP address please...."

    #ggtntool ip change 
    #Send ggtn IP information to ggtn set_ip.sh
    #./set_ip.sh
    ./GGtn_set_ip.sh $server_ip $ggtn_ip $ggtn_gateway $ggtn_primary_dns $ggtn_secondary_dns
 
    #Send server IP information to server set_ip.sh
    #server ip change
    #./set_ip.sh $server_ip $server_gateway $server_primary_dns $server_secondary_dns $network_interface 

}

#get Grafana ip
get_ip() {
    echo "Getting current IP address..."
}

#change display mode
set_displaymode() {
    #/home/gadgetini/gadgetini_monitoring_tool/service_scripts/config.ini
    #config_file="/home/deepgadget/config.ini"

    if [[ "$1" == "v" ]]; then
        echo "Setting display mode to vertical..."
        #sed -i 's/orientation=horizontal/orientation=vertical/' $config_file
        #./GGTN_set_displaymode.sh $1
        /home/deepgadget/gadgetini/src/util/GGTN_set_displaymode.sh $1
        #echo "Display mode set to vertical."
    elif [[ "$1" == "h" ]]; then
        echo "Setting display mode to horizontal..."
        #sed -i 's/orientation=vertical/orientation=horizontal/' $config_file
        #./GGTN_set_displaymode.sh $1
        /home/deepgadget/gadgetini/src/util/GGTN_set_displaymode.sh $1
        #echo "Display mode set to horizontal."
    else
        echo "Invalid option: $1"
        print_help
    fi
}

#set server time, gadgetini time
set_time() {
    echo "Setting system time..."
}

#send json, yaml file to gadgetini
import_config() {
    echo "Importing configuration..."
}

case "$1" in
    --help)
        print_help
        ;;
    set)
        case "$2" in
            ip)
                set_ip
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
                get_ip
                ;;
            *) 
                echo "Invalid get option: $2"
                print_help
                ;;
        esac
        ;;
    *)
        echo "Unknown command: $1"
        print_help
        ;;
    import)
        case "$2" in
            gpu)
                get_gpu
                ;;
            tt)
                get_tt
                ;;
            *)
                echo "Invalid get option: $2"
                print_help
                ;;
        esac
        ;;
esac
