#!/bin/sh
# Host exposure controls for AegisForge C05.
#
# Two guards, each applied by a systemd unit that the thing it protects depends
# on, so protection is established BEFORE the listener exists and removed only
# after it stops.
#
#   cluster   the Kubernetes administration ports, 6443 (API) and 10250
#             (kubelet). Both are host processes, so INPUT is the correct
#             chain. Loopback and in-cluster traffic stay allowed; the LAN
#             interface is dropped. NodePort traffic is NOT handled here — it
#             is DNATed and forwarded, never traversing INPUT, and is
#             restricted by kube-proxy's nodeport-addresses instead.
#
#   ollama    the bridge-side forwarder on 11434. Also a host process.
#
#   worker    the LAN-side forwarder on 30443 that C06 adds. Also a host
#             process, which is the whole reason it exists: the worker's
#             NodePort is DNATed and forwarded, so INPUT rules do NOT restrict
#             it and `nodeport-addresses` stays 127.0.0.1/32. A
#             systemd-socket-proxyd listener on the LAN address forwards to
#             that loopback NodePort, and because the listener is an ordinary
#             host socket, INPUT is once again the correct chain. The proxy
#             passes bytes through, so the pinned TLS session is end-to-end
#             between the Mac and the worker Pod and this host never terminates
#             it. Only the confirmed Mac address is permitted.
#
# Both address families are covered. The cluster is IPv4 single-stack, but the
# listeners bind dual-stack and the LAN interface carries a link-local IPv6
# address, so an IPv4-only guard leaves a reachable path.
#
# ORDERING MATTERS. `iptables -I INPUT n` places a rule at position n, so a
# rule set whose DROP overlaps its own ACCEPTs is only correct if the ACCEPTs
# sit above it. Rules are therefore declared in the order they must appear and
# inserted at increasing positions, rather than each being pushed to the top.
#
# Rules carry a comment tag and are removed by reconstructing the same specs,
# never by parsing `iptables -S`: that output quotes a comment only when it
# contains characters needing escaping, so a parser keyed to quoting silently
# matches nothing.
#
#   aegisforge-guard.sh apply|remove|status cluster|ollama|worker
set -eu

TAG_CLUSTER="aegisforge-c05-api"
TAG_OLLAMA="aegisforge-c05-ollama"
TAG_WORKER="aegisforge-c06-worker"
API_PORT=${AEGIS_API_PORT:-6443}
KUBELET_PORT=${AEGIS_KUBELET_PORT:-10250}
OLLAMA_PORT=${AEGIS_OLLAMA_PORT:-11434}
WORKER_PORT=${AEGIS_WORKER_NODE_PORT:-30443}
# The one address permitted to reach the worker forwarder. Required: there is
# no default, because a default here is either useless or far wider than
# intended, and an unset value must fail loudly rather than open the port.
MAC_ADDRESS=${AEGIS_MAC_ADDRESS:-}
POD_CIDR=${AEGIS_POD_CIDR:-10.42.0.0/16}
SERVICE_CIDR=${AEGIS_SERVICE_CIDR:-10.43.0.0/16}
IPT4=${AEGIS_IPTABLES:-iptables}
IPT6=${AEGIS_IP6TABLES:-ip6tables}

die() { echo "aegisforge-guard: $*" >&2; exit 1; }

command -v "$IPT4" >/dev/null 2>&1 || die "$IPT4 not found"
command -v "$IPT6" >/dev/null 2>&1 || die "$IPT6 not found (IPv6 must be covered too)"

lan_interface() {
    ip route show default 2>/dev/null | awk '/^default/ {print $5; exit}'
}

bridge_address() {
    ip -4 -o addr show "${AEGIS_BRIDGE_IF:-cni0}" 2>/dev/null \
        | awk '{split($4,a,"/"); print a[1]; exit}'
}

lan_address() {
    ip -4 -o addr show "$(lan_interface)" 2>/dev/null \
        | awk '{split($4,a,"/"); print a[1]; exit}'
}

# A single IPv4 host address, nothing else. A CIDR, a range or a hostname here
# would silently widen the one rule that limits who may reach the worker.
valid_host_address() {
    echo "$1" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$' || return 1
    for octet in $(echo "$1" | tr '.' ' '); do
        [ "$octet" -le 255 ] 2>/dev/null || return 1
    done
    return 0
}

# ---------------------------------------------------------------- rule sets --
# Each emits one rule per line, in the order they must appear in INPUT.
# The ACCEPTs are interface- or source-scoped and the DROP is LAN-only, so the
# sets are disjoint; the ordering discipline is kept regardless, because a
# future rule that overlaps must not silently become unreachable.

cluster_rules_v4() {
    lan=$1
    for port in "$API_PORT" "$KUBELET_PORT"; do
        echo "-i lo -p tcp --dport $port -j ACCEPT"
        echo "-s $POD_CIDR -p tcp --dport $port -j ACCEPT"
        echo "-s $SERVICE_CIDR -p tcp --dport $port -j ACCEPT"
        echo "-i $lan -p tcp --dport $port -j DROP"
    done
}

# The cluster runs IPv4 single-stack: there is no IPv6 Pod or Service CIDR, so
# loopback is the only legitimate IPv6 path to these ports.
cluster_rules_v6() {
    lan=$1
    for port in "$API_PORT" "$KUBELET_PORT"; do
        echo "-i lo -p tcp --dport $port -j ACCEPT"
        echo "-i $lan -p tcp --dport $port -j DROP"
    done
}

# ACCEPT first: this DROP is a superset of the ACCEPT, so the reverse order
# would block the very Pods the forwarder exists to serve.
ollama_rules_v4() {
    bridge=$1
    echo "-d $bridge -p tcp --dport $OLLAMA_PORT -s $POD_CIDR -j ACCEPT"
    echo "-d $bridge -p tcp --dport $OLLAMA_PORT -j DROP"
}

# ACCEPT first, then DROP: the DROP is a superset, so the reverse order would
# block the paired Mac along with everyone else.
worker_rules_v4() {
    lan_addr=$1 mac=$2
    echo "-d $lan_addr -p tcp --dport $WORKER_PORT -s $mac/32 -j ACCEPT"
    echo "-d $lan_addr -p tcp --dport $WORKER_PORT -j DROP"
}

# The forwarder binds one IPv4 address, so there is no IPv6 listener to reach.
# The DROP is kept anyway: IPv6 stays closed unless it is explicitly
# configured, and a future dual-stack socket must not open silently.
worker_rules_v6() {
    lan=$1
    echo "-i $lan -p tcp --dport $WORKER_PORT -j DROP"
}

# ------------------------------------------------------------------ plumbing --

# Delete by reconstructing the spec, so only this guard's rules go and the
# other guard's and the host's own rules are never touched. Bounded: a delete
# that silently fails must not spin forever.
remove_rules() {
    ipt=$1 tag=$2
    removed=0
    while IFS= read -r rule; do
        [ -n "$rule" ] || continue
        attempt=0
        while [ "$attempt" -lt 8 ]; do
            # shellcheck disable=SC2086
            "$ipt" -C INPUT $rule -m comment --comment "$tag" 2>/dev/null || break
            # shellcheck disable=SC2086
            "$ipt" -D INPUT $rule -m comment --comment "$tag" \
                || die "could not delete: $rule"
            removed=$((removed + 1))
            attempt=$((attempt + 1))
        done
        [ "$attempt" -lt 8 ] || die "$ipt: $rule kept matching after 8 deletions"
    done
    echo "$removed"
}

# Remove first, then insert at increasing positions, so re-applying always
# yields the declared order instead of whatever a partial earlier run left.
apply_rules() {
    ipt=$1 tag=$2 rules=$3
    printf '%s\n' "$rules" | remove_rules "$ipt" "$tag" >/dev/null
    position=1
    printf '%s\n' "$rules" | while IFS= read -r rule; do
        [ -n "$rule" ] || continue
        # shellcheck disable=SC2086
        "$ipt" -I INPUT "$position" $rule -m comment --comment "$tag" \
            || die "could not insert: $rule"
        position=$((position + 1))
    done
}

apply_cluster() {
    lan=$(lan_interface)
    [ -n "$lan" ] || die "cannot determine the LAN interface from the default route"
    apply_rules "$IPT4" "$TAG_CLUSTER" "$(cluster_rules_v4 "$lan")"
    apply_rules "$IPT6" "$TAG_CLUSTER" "$(cluster_rules_v6 "$lan")"
    echo "aegisforge-guard: ports $API_PORT and $KUBELET_PORT protected on" \
         "IPv4 and IPv6 (LAN interface $lan dropped)"
}

remove_cluster() {
    lan=$(lan_interface)
    [ -n "$lan" ] || die "cannot determine the LAN interface from the default route"
    v4=$(cluster_rules_v4 "$lan" | remove_rules "$IPT4" "$TAG_CLUSTER")
    v6=$(cluster_rules_v6 "$lan" | remove_rules "$IPT6" "$TAG_CLUSTER")
    echo "aegisforge-guard: removed $v4 IPv4 and $v6 IPv6 rule(s) tagged $TAG_CLUSTER"
}

apply_ollama() {
    bridge=$(bridge_address)
    [ -n "$bridge" ] || die "bridge ${AEGIS_BRIDGE_IF:-cni0} has no IPv4 address yet"
    # No IPv6 set: the forwarder binds an IPv4 bridge address only, so there
    # is no IPv6 listener to protect. Stated rather than silently skipped.
    apply_rules "$IPT4" "$TAG_OLLAMA" "$(ollama_rules_v4 "$bridge")"
    echo "aegisforge-guard: forwarder $bridge:$OLLAMA_PORT limited to $POD_CIDR"
}

remove_ollama() {
    bridge=$(bridge_address)
    [ -n "$bridge" ] || die "bridge ${AEGIS_BRIDGE_IF:-cni0} has no IPv4 address yet"
    v4=$(ollama_rules_v4 "$bridge" | remove_rules "$IPT4" "$TAG_OLLAMA")
    echo "aegisforge-guard: removed $v4 rule(s) tagged $TAG_OLLAMA"
}

apply_worker() {
    [ -n "$MAC_ADDRESS" ] || die "AEGIS_MAC_ADDRESS must name the paired Mac's IPv4 address"
    valid_host_address "$MAC_ADDRESS" \
        || die "AEGIS_MAC_ADDRESS must be a single IPv4 address, not $MAC_ADDRESS"
    lan=$(lan_interface)
    [ -n "$lan" ] || die "cannot determine the LAN interface from the default route"
    lan_addr=$(lan_address)
    [ -n "$lan_addr" ] || die "the LAN interface $lan has no IPv4 address"
    apply_rules "$IPT4" "$TAG_WORKER" "$(worker_rules_v4 "$lan_addr" "$MAC_ADDRESS")"
    apply_rules "$IPT6" "$TAG_WORKER" "$(worker_rules_v6 "$lan")"
    echo "aegisforge-guard: forwarder $lan_addr:$WORKER_PORT limited to" \
         "$MAC_ADDRESS; IPv6 closed"
}

remove_worker() {
    lan=$(lan_interface)
    [ -n "$lan" ] || die "cannot determine the LAN interface from the default route"
    lan_addr=$(lan_address)
    [ -n "$lan_addr" ] || die "the LAN interface $lan has no IPv4 address"
    # Removal must not require AEGIS_MAC_ADDRESS to still be set, or a rollback
    # after the variable is gone would leave the ACCEPT rule behind. The stored
    # address is read back from the rule itself.
    mac=${MAC_ADDRESS:-$("$IPT4" -S INPUT 2>/dev/null \
        | awk -v t="$TAG_WORKER" '$0 ~ t && /-s / {for(i=1;i<NF;i++) if($i=="-s"){split($(i+1),a,"/"); print a[1]; exit}}')}
    v4=0
    if [ -n "$mac" ]; then
        v4=$(worker_rules_v4 "$lan_addr" "$mac" | remove_rules "$IPT4" "$TAG_WORKER")
    fi
    v6=$(worker_rules_v6 "$lan" | remove_rules "$IPT6" "$TAG_WORKER")
    echo "aegisforge-guard: removed $v4 IPv4 and $v6 IPv6 rule(s) tagged $TAG_WORKER"
}

show_status() {
    found=0
    for pair in "IPv4:$IPT4" "IPv6:$IPT6"; do
        family=${pair%%:*}; ipt=${pair#*:}
        rules=$("$ipt" -S INPUT 2>/dev/null \
            | grep -e "$TAG_CLUSTER" -e "$TAG_OLLAMA" -e "$TAG_WORKER" || true)
        if [ -n "$rules" ]; then
            found=1
            echo "$rules" | sed "s/^/$family /"
        fi
    done
    [ "$found" -eq 1 ] || echo "no AegisForge rules present"
}

case "${1:-}" in
  apply)
    case "${2:-}" in
      cluster) apply_cluster ;;
      ollama)  apply_ollama ;;
      worker)  apply_worker ;;
      *) die "apply needs cluster|ollama|worker" ;;
    esac ;;
  remove)
    case "${2:-}" in
      cluster) remove_cluster ;;
      ollama)  remove_ollama ;;
      worker)  remove_worker ;;
      *) die "remove needs cluster|ollama|worker" ;;
    esac ;;
  status) show_status ;;
  *) die "usage: $0 apply|remove|status cluster|ollama|worker" ;;
esac
