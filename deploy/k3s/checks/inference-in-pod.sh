#!/bin/sh
# Run the bounded inference check inside the worker Pod.
#
# The script is piped in over `kubectl exec -i` with no TTY, so nothing has to
# exist in the image. EVERY kubectl call is bounded, the Pod lookup included: an
# unbounded lookup against an unreachable API leaves the operator waiting before
# the bounded part is ever reached, which defeats the point of the wrapper.
#
# KUBECTL is overridable so this wrapper itself can be exercised offline.
set -u

NS=${AEGIS_NAMESPACE:-aegisforge}
KUBECTL=${KUBECTL:-sudo k3s kubectl}
EXPECTED=${AEGIS_EXPECTED_ANSWER:-POD}
DEADLINE=${AEGIS_CHECK_DEADLINE:-90}
OUTER=${AEGIS_OUTER_TIMEOUT:-$((DEADLINE + 30))}
LOOKUP=${AEGIS_LOOKUP_TIMEOUT:-20}
GRACE=${AEGIS_KILL_GRACE:-5}
SCRIPT=$(dirname "$0")/pod_inference_check.py

[ -r "$SCRIPT" ] || { echo "FAIL: cannot read $SCRIPT"; exit 4; }

# Prefer coreutils timeout; fall back to a shell watchdog so the wrapper is
# bounded everywhere rather than silently running unbounded.
if command -v timeout >/dev/null 2>&1; then TIMEOUT_CMD=timeout
elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT_CMD=gtimeout
else TIMEOUT_CMD=""; fi

# Run a command under a hard deadline, with forced termination on both paths.
# `timeout -k` escalates to SIGKILL for a process that ignores SIGTERM. The
# fallback enables job control so the watchdog can signal the whole process
# group: killing only the direct child leaves grandchildren holding the pipe
# open, and the wrapper hangs despite its deadline.
bounded() {
    limit=$1; shift
    if [ -n "$TIMEOUT_CMD" ]; then
        "$TIMEOUT_CMD" -k "$GRACE" "$limit" "$@"
        return $?
    fi
    set -m
    "$@" <&0 &                       # <&0 keeps stdin explicit under job control
    child=$!
    ( sleep "$limit"
      kill -TERM -"$child" 2>/dev/null || kill -TERM "$child" 2>/dev/null
      sleep "$GRACE"
      kill -KILL -"$child" 2>/dev/null || kill -KILL "$child" 2>/dev/null ) &
    guard=$!
    wait "$child"
    status=$?
    set +m
    kill -TERM -"$guard" 2>/dev/null || kill -TERM "$guard" 2>/dev/null
    wait "$guard" 2>/dev/null
    # A terminated child reports 128+signal. Normalise so both paths agree.
    case "$status" in 143|137) status=124 ;; esac
    return "$status"
}

# shellcheck disable=SC2086  # KUBECTL is a command line, splitting is intended
POD=$(bounded "$LOOKUP" $KUBECTL -n "$NS" get pod -l app=aegisforge-worker \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) || POD=""
if [ -z "$POD" ]; then
    echo "FAIL: no worker Pod found in namespace $NS within ${LOOKUP}s"
    echo "      (an unreachable API looks identical here — check the cluster first)"
    exit 4
fi
echo "pod: $POD  container: worker  expected: $EXPECTED  deadline: ${DEADLINE}s"

# -i forwards stdin; no -t, because a TTY mangles the piped script and the exit
# status. --container is explicit so a future sidecar cannot shift it.
# shellcheck disable=SC2086
bounded "$OUTER" $KUBECTL -n "$NS" exec -i "$POD" --container worker -- \
  env AEGIS_EXPECTED_ANSWER="$EXPECTED" AEGIS_CHECK_DEADLINE="$DEADLINE" \
      PYTHONDONTWRITEBYTECODE=1 \
  python - < "$SCRIPT"
status=$?

if [ "$status" -eq 124 ]; then
  echo "FAIL: the kubectl exec itself exceeded ${OUTER}s"
fi
exit "$status"
