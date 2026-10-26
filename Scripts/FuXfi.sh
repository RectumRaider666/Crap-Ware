#!/usr/bin/env bash

get_ssid () {
    local ssid
    ssid=$(iwgetid -r 2>/dev/null)
    if [ -z "$ssid" ]; then
        ssid=$(nmcli -t -f IN-USE,SSID dev wifi | grep '^\*:' | cut -d: -f2-)
    fi
    if [ -z "$ssid" ]; then
        printf "None"
    else
        printf '%s' "$ssid"
    fi
}

gen_mac() {
    local fb
    fb=$(printf '%02X' "$(( (RANDOM % 256 & 0xFC) | 0x02 ))") || return 1
    local mac="$fb"
    for _ in {1..5}; do
        local byte
        byte=$(printf '%02X' "$((RANDOM % 256))") || return 1
        mac+=":$byte"
    done

    printf '%s' "$mac"
}

valid_mac () {
	[[ "$1" =~ ^([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}$ ]]
}

valid_hostname() {
    [[ "$1" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$ ]] &&
    (( ${#1} <= 253 ))
}

transform () {
    local mac
    while true; do
        mac="$(gen_mac)" || continue
        valid_mac "$mac" && break
    done
    local newnames="$PWD/names.txt"
    local hostname
    local line_count
    local line
    [[ -r "$newnames" && -w "$newnames" ]] || { printf 'Error: Cannot read or modify %s\n' "$newnames" >&2; return 1; }
    line_count=$(awk 'END {print NR}' "$newnames") || return 1
    (( line_count > 0 )) || { printf 'Error: No hostnames left in %s\n' "$newnames" >&2; return 1; }
    line=$(shuf -i "1-$line_count" -n 1) || return 1
    hostname=$(sed -n "${line}p" "$newnames") || return 1
    valid_hostname "$hostname" || { printf 'Error: Invalid hostname on line %s of %s\n' "$line" "$newnames" >&2; return 1; }
    sed -i "${line}d" "$newnames" || { printf 'Error: Failed to remove hostname from %s\n' "$newnames" >&2; return 1; }
    printf '%s\n' "$hostname" | sudo tee /etc/hostname > /dev/null || return 1
    sudo hostname "$hostname" || return 1
    sudo nmcli radio wifi off || return 1
    sudo ip link set dev "$INTF" down || return 1
    sudo ip link set dev "$INTF" address "$mac" || return 1
    sudo nmcli radio wifi on || return 1
    sudo ip link set dev "$INTF" up || return 1
    local stamp
    stamp=$(date '+%Y-%m-%d %H:%M:%S')
    sleep 5
    local netid
    netid="$(get_ssid)"
    printf 'Mac and Hostname Reset %s SSID=%s MAC=%s Hostname=%s\n' "$stamp" "$netid" "$mac" "$hostname" | tee -a FuXfi.log
}

check () {
    local host="google.com"
    local count=10
    local loss_thresh=40
    while true; do
		if (( FAILS < FAIL_THRESHOLD )); then
			loss=$(ping -c "$count" -q "$host" 2>/dev/null | grep -oP '\d+(?=% packet loss)')
			loss=${loss:-100}
			if (( loss >= loss_thresh )); then
				((FAILS += 1))
				local stamp
				stamp=$(date '+%Y-%m-%d %H:%M:%S')
				local netid
				netid=$(get_ssid)
				printf 'Drop Detected %s SSID=%s\n' "$stamp" "$netid" | tee -a FuXfi.log
				transform || { printf 'Error: Network transformation failed.\n' >&2; exit 1; }
			else
				FAILS=0
				printf 'Ping passed\n'
				sleep 1
			fi
		else
			printf 'Error: Threshold reached (%d).\n' "$FAILS" >&2
			exit 1
		fi
    done
}

printf 'Starting Spoofer Fuck Xfinity!'
FAILS=0
FAIL_THRESHOLD=10
INTF=$(iw dev | awk '$1 == "Interface" {print $2; exit}')
[[ -n "$INTF" ]] || { printf 'Error: Unable to find a Wi-Fi interface.\n' >&2; exit 1; }
check
