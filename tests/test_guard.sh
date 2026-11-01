#!/bin/sh
# Run on OpenWrt ash/jshn/jsonfilter. All addresses use documentation ranges.
set -e
ROOT=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
sed '/^# CLI entry point/,$d' "$ROOT/package/lan-arp-guard/files/usr/sbin/lan-arp-guard" > "$TMP/functions"
. "$TMP/functions"
RUNDIR="$TMP/run"; mkdir -p "$RUNDIR"
PASS=0
assert_eq() {
	[ "$2" = "$3" ] || { echo "FAIL $1: expected <$3>, got <$2>"; exit 1; }
	PASS=$((PASS + 1)); echo "ok $1"
}
for ip in 192.0.2.1 10.0.0.1 203.0.113.254; do
	if valid_ipv4 "$ip"; then code=0; else code=$?; fi
	assert_eq "valid $ip" "$code" 0
done
for ip in '' 1.2.3 1.2.3.4. .1.2.3.4 1..2.3 256.1.2.3 01.2.3.4 127.0.0.1 0.0.0.0 224.0.0.1 '1.2.3.4;reboot' '1.2.3.4/24'; do
	if valid_ipv4 "$ip"; then code=0; else code=$?; fi
	assert_eq "invalid $ip" "$code" 1
done
for name in 'lan;reboot' 'lan"' '../lan' '' 'lan space'; do
	if valid_name "$name"; then code=0; else code=$?; fi
	assert_eq "invalid name $name" "$code" 1
done
IPS='192.0.2.1 198.51.100.1'; DEVICE=br-test; LOGGING=1
render_rules > "$TMP/rules"
assert_eq kernel_drop "$(grep -c 'counter name blocked drop' "$TMP/rules")" 1
assert_eq limited_log "$(grep -c 'limit rate 2/minute burst 2 packets' "$TMP/rules")" 1
LOGGING=0; render_rules > "$TMP/no-log"
assert_eq no_log "$(grep -c 'log prefix' "$TMP/no-log" || true)" 0
assert_eq still_drop "$(grep -c 'counter name blocked drop' "$TMP/no-log")" 1

# An unavailable interface must never remove existing protection.
load_settings() { ENABLED=1; }
resolve_bridge() { ERROR=interface_unavailable; return 1; }
logger() { :; }
nft() { echo "$*" >> "$TMP/nft-calls"; }
if apply_rules; then code=0; else code=$?; fi
assert_eq unavailable_fails "$code" 1
assert_eq retains_rules "$(test -e "$TMP/nft-calls" && echo bad || echo good)" good
assert_eq records_error "$(cat "$RUNDIR/error")" interface_unavailable

# A syntax failure must only invoke nft --check, never mutate the table.
resolve_bridge() { DEVICE=br-test; IPS=192.0.2.1; LOGGING=1; return 0; }
nft() { echo "$*" >> "$TMP/nft-calls"; return 1; }
if apply_rules; then code=0; else code=$?; fi
assert_eq validation_fails "$code" 1
assert_eq check_only "$(wc -l < "$TMP/nft-calls" | tr -d ' ')" 1
assert_eq validation_error "$(cat "$RUNDIR/error")" validation_failed

# Read-only status parses live counter data and represents >32-bit safely.
load_settings() { ENABLED=1; IFACE=test; }
nft() {
	case "$*" in
		'-j list table bridge lan_arp_guard') echo '{"nftables":[{"rule":{"expr":[{"match":{"right":"br-test"}}]}}]}' ;;
		'-j list counter bridge lan_arp_guard blocked') echo '{"nftables":[{"counter":{"name":"blocked","packets":4294967300,"bytes":180388626600}}]}' ;;
		'-j list set bridge lan_arp_guard gateways') echo '{"nftables":[{"set":{"elem":["192.0.2.1","198.51.100.1"]}}]}' ;;
		*) return 1 ;;
	esac
}
show_status > "$TMP/status"
assert_eq active "$(jsonfilter -i "$TMP/status" -e '@.active')" true
assert_eq large_count "$(jsonfilter -i "$TMP/status" -e '@.packets')" 4294967300
assert_eq live_device "$(jsonfilter -i "$TMP/status" -e '@.device')" br-test
assert_eq second_address "$(jsonfilter -i "$TMP/status" -e '@.addresses[1]')" 198.51.100.1
echo "PASS $PASS assertions"
