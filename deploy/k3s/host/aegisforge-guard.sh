#!/bin/sh
# Host exposure controls for AegisForge C05.
#
# Two guards, each applied by a systemd unit that the thing it protects depends
# on, so protection is established BEFORE the listener exists and removed only
# after it stops.
#
#   cluster   the Kubernetes API on 6443. It is a host process, so INPUT is the
#             correct chain. Loopback and in-cluster traffic stay allowed;
#             the LAN interface is dropped. NodePort traffic is NOT handled
#             here — it is DNATed and forwarded, never traversing INPUT, and is
#             restricted by kube-proxy's nodeport-addresses instead.
#
#   ollama    the bridge-side forwarder on 11434. Also a host process.
#
# Rules are inserted with a comment tag so removal touches only our own rules
# and never flushes a chain.
#
#   aegisforge-guard.sh apply|remove|status cluster|ollama
set -eu

TAG_CLUSTER="aegisforge-c05-api"
TAG_OLLAMA="aegisforge-c05-ollama"
API_PORT=${AEGIS_API_PORT:-6443}
OLLAMA_PORT=${AEGIS_OLLAMA_PORT:-11434}
POD_CIDR=${AEGIS_POD_CIDR:-10.42.0.0/16}
SERVICE_CIDR=${AEGIS_SERVICE_CIDR:-10.43.0.0/16}

die() { echo "aegisforge-guard: $*" >&2; exit 1; }

command -v iptables >/dev/null 2>&1 || die "iptables not found"

lan_interface() {
    ip route show default 2>/dev/null | awk '/^default/ {print $5; exit}'
}

bridge_address() {
    ip -4 -o addr show "${AEGIS_BRIDGE_IF:-cni0}" 2>/dev/null \
        | awk '{split($4,a,"/"); print a[1]; exit}'
}

# Idempotent: applying twice must not stack duplicate rules.
add_rule() {
    tag=$1; shift
    iptables -C "$@" -m comment --comment "$tag" 2>/dev/null && return 0
    iptables -I "$@" -m comment --comment "$tag"
}

drop_tagged() {
    tag=$1
    removed=0
    # Bounded: a delete that silently fails must not spin forever.
    attempt=0
    while [ "$attempt" -lt 32 ]; do
        attempt=$((attempt + 1))
        rule=$(iptables -S INPUT | grep -- "--comment \"$tag\"" | head -1) || rule=""
        [ -n "$rule" ] || break
        # shellcheck disable=SC2086
        if iptables $(echo "$rule" | sed 's/^-A /-D /'); then
            removed=$((removed + 1))
        else
            echo "aegisforge-guard: could not delete: $rule" >&2
            return 1
        fi
    done
    if [ "$attempt" -ge 32 ]; then
        echo "aegisforge-guard: gave up after 32 deletions; inspect INPUT manually" >&2
        return 1
    fi
    echo "aegisforge-guard: removed $removed rule(s) tagged $tag"
}

apply_cluster() {
    lan=$(lan_interface)
    [ -n "$lan" ] || die "cannot determine the LAN interface from the default route"
    add_rule "$TAG_CLUSTER" INPUT -i lo -p tcp --dport "$API_PORT" -j ACCEPT
    add_rule "$TAG_CLUSTER" INPUT -p tcp --dport "$API_PORT" -s "$POD_CIDR" -j ACCEPT
    add_rule "$TAG_CLUSTER" INPUT -p tcp --dport "$API_PORT" -s "$SERVICE_CIDR" -j ACCEPT
    # Only the LAN interface is dropped, so cluster components and any future
    # internal interface keep working.
    add_rule "$TAG_CLUSTER" INPUT -i "$lan" -p tcp --dport "$API_PORT" -j DROP
    echo "aegisforge-guard: API $API_PORT protected (LAN interface $lan dropped)"
}

apply_ollama() {
    bridge=$(bridge_address)
    [ -n "$bridge" ] || die "bridge ${AEGIS_BRIDGE_IF:-cni0} has no IPv4 address yet"
    add_rule "$TAG_OLLAMA" INPUT -p tcp -d "$bridge" --dport "$OLLAMA_PORT" \
        -s "$POD_CIDR" -j ACCEPT
    add_rule "$TAG_OLLAMA" INPUT -p tcp -d "$bridge" --dport "$OLLAMA_PORT" -j DROP
    echo "aegisforge-guard: forwarder $bridge:$OLLAMA_PORT limited to $POD_CIDR"
}

case "${1:-}" in
  apply)
    case "${2:-}" in
      cluster) apply_cluster ;;
      ollama)  apply_ollama ;;
      *) die "apply needs cluster|ollama" ;;
    esac ;;
  remove)
    case "${2:-}" in
      cluster) drop_tagged "$TAG_CLUSTER" ;;
      ollama)  drop_tagged "$TAG_OLLAMA" ;;
      *) die "remove needs cluster|ollama" ;;
    esac ;;
  status)
    iptables -S INPUT | grep -E "aegisforge-c05" || echo "no AegisForge rules present" ;;
  *) die "usage: $0 apply|remove|status cluster|ollama" ;;
esac
