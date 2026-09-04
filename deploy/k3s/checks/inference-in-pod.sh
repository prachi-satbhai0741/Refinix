#!/bin/sh
# Run the bounded inference check inside the worker Pod.
#
# The script is piped in over `kubectl exec -i` with no TTY, so nothing has to
# exist in the image. The outer call is bounded as well: a stuck kubectl
# connection must not leave the operator waiting.
#
# KUBECTL is overridable so this wrapper itself can be exercised offline.
set -u

NS=${AEGIS_NAMESPACE:-aegisforge}
KUBECTL=${KUBECTL:-sudo k3s kubectl}
EXPECTED=${AEGIS_EXPECTED_ANSWER:-POD}
DEADLINE=${AEGIS_CHECK_DEADLINE:-90}
OUTER=${AEGIS_OUTER_TIMEOUT:-$((DEADLINE + 30))}
SCRIPT=$(dirname "$0")/pod_inference_check.py

[ -r "$SCRIPT" ] || { echo "FAIL: cannot read $SCRIPT"; exit 4; }

# Prefer coreutils timeout; fall back to a shell watchdog so the wrapper is
# bounded everywhere rather than silently running unbounded.
if command -v timeout >/dev/null 2>&1; then TIMEOUT_CMD=timeout
elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT_CMD=gtimeout
else TIMEOUT_CMD=""; fi

POD=$($KUBECTL -n "$NS" get pod -l app=aegisforge-worker \
        -o jsonpath='{.items[0].metadata.name}') || POD=""
[ -n "$POD" ] || { echo "FAIL: no worker Pod found in namespace $NS"; exit 4; }
echo "pod: $POD  container: worker  expected: $EXPECTED  deadline: ${DEADLINE}s"

# -i forwards stdin; no -t, because a TTY mangles the piped script and the exit
# status. --container is explicit so a future sidecar cannot shift it.
if [ -n "$TIMEOUT_CMD" ]; then
  "$TIMEOUT_CMD" "$OUTER" $KUBECTL -n "$NS" exec -i "$POD" --container worker -- \
    env AEGIS_EXPECTED_ANSWER="$EXPECTED" AEGIS_CHECK_DEADLINE="$DEADLINE" \
        PYTHONDONTWRITEBYTECODE=1 \
    python - < "$SCRIPT"
  status=$?
else
  # Job control puts the child in its own process group, so the watchdog can
  # signal the whole group. Killing only the direct child leaves grandchildren
  # holding the pipe open, and the wrapper would hang despite its deadline.
  set -m
  $KUBECTL -n "$NS" exec -i "$POD" --container worker -- \
    env AEGIS_EXPECTED_ANSWER="$EXPECTED" AEGIS_CHECK_DEADLINE="$DEADLINE" \
        PYTHONDONTWRITEBYTECODE=1 \
    python - < "$SCRIPT" &
  child=$!
  ( sleep "$OUTER"
    kill -TERM -"$child" 2>/dev/null || kill -TERM "$child" 2>/dev/null
    sleep 2
    kill -KILL -"$child" 2>/dev/null || true ) &
  guard=$!
  wait "$child"
  status=$?
  set +m
  kill -TERM -"$guard" 2>/dev/null || kill -TERM "$guard" 2>/dev/null
  wait "$guard" 2>/dev/null
  # A terminated child reports 128+SIGTERM. Normalise so both paths agree.
  [ "$status" -eq 143 ] && status=124
fi

if [ "$status" -eq 124 ]; then
  echo "FAIL: the kubectl exec itself exceeded ${OUTER}s"
fi
exit "$status"
