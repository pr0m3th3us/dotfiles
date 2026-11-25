#!/usr/bin/env bash
# Regression tests for common/.local/bin/chrome-debug (Linux and WSL; not macOS).
#
# Runs the real launcher against stand-in processes rather than mocked command output:
# a fake browser (python3 copied to a file named `chrome`, running fake_browser.py) that
# really owns its DevTools socket, and unrelated processes whose command lines look like
# a browser's. Windows tools are kept off PATH and CHROME_DEBUG_CHROME selects the fake
# browser, so on WSL this exercises the Linux code path only.
#
# Usage: tests/chrome-debug/run.sh        (about a minute; needs python3, curl, jq)
# Nothing outside a temporary directory is touched. Every stand-in process is stopped
# on exit.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd -P)"
REPO="$(cd "$HERE/../.." && pwd -P)"
CD="$REPO/common/.local/bin/chrome-debug"
FAKE_PY="$HERE/fake_browser.py"

for tool in python3 curl jq; do
  command -v "$tool" >/dev/null 2>&1 || { echo "skip: $tool is required" >&2; exit 0; }
done
[ -r /proc/net/tcp ] || { echo "skip: needs Linux /proc (run on Linux or WSL)" >&2; exit 0; }

T="$(mktemp -d "${TMPDIR:-/tmp}/chrome-debug-test.XXXXXX")"
T="$(cd "$T" && pwd -P)"
H="$T/home"
mkdir -p "$H" "$T/tmp" "$T/bin" "$T/work"

stop_stand_ins() {
  local pids
  pids="$(ps -axo pid=,command= | NEEDLE="$T/" awk 'index($0, ENVIRON["NEEDLE"]) { print $1 }')"
  [ -n "$pids" ] && kill $pids 2>/dev/null
  return 0
}
cleanup() {
  stop_stand_ins
  sleep 0.3
  rm -rf "$T"
}
trap cleanup EXIT

# --- Stand-in executables ------------------------------------------------------
PY_BIN="$(python3 -c 'import sys; print(sys.executable)')"
PY_BIN="$(readlink -f "$PY_BIN")"
PY_HOME="$(python3 -c 'import sys; print(sys.base_prefix)')"
cp "$PY_BIN" "$T/bin/chrome"          # a browser-named executable
cp "$PY_BIN" "$T/bin/decoy"           # answers DevTools, but is not a browser
cp "$(readlink -f "$(command -v bash)")" "$T/bin/export-chrome"   # unrelated helpers
cp "$(readlink -f "$(command -v bash)")" "$T/bin/logger"
cat > "$T/fake-chrome" <<EOF
#!/usr/bin/env bash
exec "$T/bin/chrome" "$FAKE_PY" "\$@"
EOF
chmod +x "$T/fake-chrome"

# PATH without Windows interop (/mnt/c/...), so WSL behaves like plain Linux.
TPATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/' | paste -sd: -)"

# run_cd [VAR=value ...] -- <chrome-debug args...>; output in $OUT, status in $RC.
run_cd() {
  local -a extra=()
  while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do extra+=("$1"); shift; done
  shift
  OUT="$(cd "$T/work" && env -i HOME="$H" PATH="$TPATH" TMPDIR="$T/tmp" LANG=C.UTF-8 \
    PYTHONHOME="$PY_HOME" FAKE_DECOY_BIN="$T/bin/decoy" CHROME_DEBUG_CHROME="$T/fake-chrome" \
    ${extra[@]+"${extra[@]}"} bash "$CD" "$@" 2>&1)"
  RC=$?
}

# Start a stand-in browser directly (not through chrome-debug), in the background.
start_fake() {   # start_fake <mode> <port> <dir>
  mkdir -p "$3"
  env PYTHONHOME="$PY_HOME" FAKE_MODE="$1" FAKE_DECOY_BIN="$T/bin/decoy" \
    "$T/fake-chrome" "--remote-debugging-port=$2" "--user-data-dir=$3" >/dev/null 2>&1 &
  sleep 0.5
}

pids_for() {   # PIDs whose command line contains a string (passed via the environment,
               # so this awk's own command line never matches)
  ps -axo pid=,command= | NEEDLE="$1" awk 'index($0, ENVIRON["NEEDLE"]) { print $1 }'
}

port_free() {
  local hex
  hex="$(printf '%04X' "$1")"
  ! awk -v hp=":$hex" 'FNR > 1 && toupper($2) ~ hp"$" { found = 1 } END { exit !found }' /proc/net/tcp /proc/net/tcp6 2>/dev/null \
    && ! curl -s -m 1 "http://127.0.0.1:$1/" >/dev/null 2>&1
}

BASE=$((39000 + RANDOM % 800))
NEXT_PORT=$BASE
new_port() {
  while ! port_free "$NEXT_PORT"; do NEXT_PORT=$((NEXT_PORT + 1)); done
  PORT_OUT=$NEXT_PORT
  NEXT_PORT=$((NEXT_PORT + 1))
}

PASS=0 FAIL=0
ok()   { PASS=$((PASS + 1)); printf '  ok    %s\n' "$1"; }
bad()  { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$1"; printf '%s\n' "$OUT" | sed 's/^/        | /'; }
check() { local name="$1"; shift; if "$@"; then ok "$name"; else bad "$name"; fi; }
has()   { printf '%s\n' "$OUT" | grep -qF -- "$1"; }
lacks() { ! has "$1"; }
alive() { [ -n "$(pids_for "$1")" ]; }
gone()  { [ -z "$(pids_for "$1")" ]; }
log_has() { grep -qF -- "$2" "$1" 2>/dev/null; }

echo "chrome-debug regression tests (temp dir $T)"

# --- Launch, ownership and attach ---------------------------------------------
echo "launch and ownership"
new_port; PA=$PORT_OUT
run_cd -- -d "$T/profA" -p "$PA"
check "launch confirms its own listener" [ "$RC" -eq 0 ]
check "launch reports the session active" has "✔ Chrome debug session active on port $PA"

# Finding: a symlink followed by '..' resolved lexically to the caller's directory.
mkdir -p "$T/physical/nested"
ln -s "$T/physical/nested" "$T/work/parentlink"
echo phys > "$T/physical/page.html"
echo wrong > "$T/work/page.html"
run_cd -- -d "$T/profA" parentlink/../page.html
check "attach opens a tab for a symlink/.. path" [ "$RC" -eq 0 ]
check "symlink/.. resolves in filesystem order" log_has "$T/profA/fake-requests.log" "NEW file://$T/physical/page.html"
check "symlink/.. does not open the caller's file" bash -c "! grep -qF 'NEW file://$T/work/page.html' '$T/profA/fake-requests.log'"

# Blocker: two browsers claim one port; only the listener's own PID proves ownership.
start_fake nobind "$PA" "$T/profB"
run_cd -- --status -d "$T/profB"
check "status for the non-owner fails" [ "$RC" -ne 0 ]
check "status for the non-owner hides the other profile's tabs" lacks "fake tab"
check "status for the non-owner names the mismatch" has "from another process"
run_cd -- -d "$T/profB" https://example.com/b
check "attach for the non-owner fails" [ "$RC" -ne 0 ]
check "attach for the non-owner opens no tab anywhere" bash -c "! grep -qF 'example.com/b' '$T/profA/fake-requests.log'"
run_cd -- --status -d "$T/profA"
check "status for the owner succeeds" [ "$RC" -eq 0 ]
check "status for the owner lists its tabs" has "fake tab $T/profA"
run_cd -- --status -p "$PA"
check "bare-port status with two claimants is refused" [ "$RC" -ne 0 ]
run_cd -- --stop -d "$T/profB"
check "profile stop of the non-owner succeeds" has "✔ Stopped"
check "profile stop removed the non-owner" gone "--user-data-dir=$T/profB"
check "profile stop left the owner running" alive "--user-data-dir=$T/profA"

# Blocker: an answering endpoint with a live child and no owner was reported ready.
new_port; PC=$PORT_OUT
run_cd FAKE_MODE=decoy -- -d "$T/profC" -p "$PC"
check "launch fails when another process answers its port" [ "$RC" -ne 0 ]
check "launch never reports a decoy endpoint as active" lacks "✔"
check "launch names the foreign listener" has "from another process"
check "failed launch cleans up its own browser" gone "--user-data-dir=$T/profC"
kill $(pids_for "$T/bin/decoy") 2>/dev/null

# --- Stop selection -------------------------------------------------------------
echo "stop selection"
new_port; PS=$PORT_OUT
# Short sleeps in a loop, so no long-lived orphan outlives its killed parent.
"$T/bin/export-chrome" -c 'while :; do sleep 1; done' "--remote-debugging-port=$PS" "--user-data-dir=$T/profX" &
"$T/bin/logger" -c 'while :; do sleep 1; done' chrome "--remote-debugging-port=$PS" &
bash -c "exec -a /opt/google/chrome/chrome bash -c 'while :; do sleep 1; done' --remote-debugging-port=$PS --tag=$T/spoof" &
sleep 0.3
run_cd -- --stop -p "$PS"
check "stop with only look-alike processes stops nothing" has "○ No Chrome debug session was running on port $PS"
check "stop spared the *-chrome helper" alive "$T/bin/export-chrome"
check "stop spared the logger" alive "$T/bin/logger"
check "stop spared a process faking argv[0]" alive "--tag=$T/spoof"
run_cd -- -d "$T/profD" -p "$PS"
check "launch beside look-alikes succeeds" [ "$RC" -eq 0 ]
run_cd -- --stop -p "$PS"
check "bare-port stop stops the real browser" has "✔ Stopped Chrome debug session on port $PS"
check "bare-port stop removed the browser" gone "--user-data-dir=$T/profD"
check "bare-port stop still spared the look-alikes" alive "$T/bin/export-chrome"
kill $(pids_for "$T/bin/export-chrome") $(pids_for "$T/bin/logger") $(pids_for "--tag=$T/spoof") 2>/dev/null

# --- Listing ----------------------------------------------------------------------
echo "listing"
new_port; PG=$PORT_OUT
start_fake nobind "$PG" "$H/.chrome-debug-gamma"
new_port; PL=$PORT_OUT
run_cd -- alpha -p "$PL"
mkdir -p "$H/.chrome-debug-acct/Default"
printf '%s\n' '{"profile":{"info_cache":{"Default":{"user_name":"","gaia_name":"Display Name"}}}}' > "$H/.chrome-debug-acct/Local State"
printf '%s\n' '{"account_info":[{"email":"real@example.com"}]}' > "$H/.chrome-debug-acct/Default/Preferences"
run_cd -- --list
check "list shows a closed endpoint as not answering" bash -c "printf '%s\n' \"\$1\" | grep '^gamma ' | grep -q 'not answering'" _ "$OUT"
check "list never shows a closed endpoint as running" bash -c "! printf '%s\n' \"\$1\" | grep '^gamma ' | grep -q '● port'" _ "$OUT"
check "list shows a confirmed endpoint as running" bash -c "printf '%s\n' \"\$1\" | grep '^alpha ' | grep -q '● port $PL'" _ "$OUT"
check "list keeps an empty email out of the name column" bash -c "printf '%s\n' \"\$1\" | grep '^acct ' | grep -q 'real@example.com *Display Name'" _ "$OUT"
run_cd -- --status gamma
check "status for a closed endpoint fails" [ "$RC" -eq 1 ]
check "status for a closed endpoint says so" has "not answering"
run_cd -- --stop gamma
run_cd -- --stop alpha

# --- Launch lock ------------------------------------------------------------------
echo "launch lock"
LOCK="$T/tmp/chrome-debug.lock.$(id -u)"
sleep 300 &
HOLDER=$!
mkdir -p "$LOCK" && echo "$HOLDER" > "$LOCK/pid"
new_port; PE=$PORT_OUT
start=$SECONDS
run_cd CHROME_DEBUG_LOCK_WAIT=2 -- -d "$T/profE" -p "$PE"
check "lock timeout fails the launch" [ "$RC" -ne 0 ]
check "lock timeout exits before launching" lacks "Starting Chrome"
check "lock timeout explains the wait" has "still in progress"
check "lock timeout starts no browser" gone "--user-data-dir=$T/profE"
check "lock timeout leaves the live holder's lock" [ -f "$LOCK/pid" ]

# TERM while waiting for someone else's lock: exit, and do not remove their lock.
( cd "$T/work" && exec env -i HOME="$H" PATH="$TPATH" TMPDIR="$T/tmp" PYTHONHOME="$PY_HOME" \
    CHROME_DEBUG_CHROME="$T/fake-chrome" CHROME_DEBUG_LOCK_WAIT=30 bash "$CD" -d "$T/profE" -p "$PE" >"$T/term1.out" 2>&1 ) &
W=$!
sleep 1
kill -TERM "$W"
wait "$W"; RC=$?; OUT="$(cat "$T/term1.out")"
check "TERM while waiting for the lock exits 143" [ "$RC" -eq 143 ]
check "TERM while waiting never launches" lacks "Starting Chrome"
check "TERM while waiting keeps the other holder's lock" [ -f "$LOCK/pid" ]
kill "$HOLDER" 2>/dev/null; wait "$HOLDER" 2>/dev/null

# A lock whose holder died is taken over.
echo 999999 > "$LOCK/pid"
run_cd -- -d "$T/profF" -p "$PE"
check "stale lock is taken over" [ "$RC" -eq 0 ]
check "lock is released after a successful launch" [ ! -e "$LOCK" ]
run_cd -- --stop -d "$T/profF"

# TERM after acquiring the lock (browser still starting): exit, release, no success.
new_port; PT=$PORT_OUT
( cd "$T/work" && exec env -i HOME="$H" PATH="$TPATH" TMPDIR="$T/tmp" PYTHONHOME="$PY_HOME" FAKE_DELAY=8 \
    CHROME_DEBUG_CHROME="$T/fake-chrome" bash "$CD" -d "$T/profT" -p "$PT" >"$T/term2.out" 2>&1 ) &
W=$!
for _ in $(seq 1 40); do grep -q 'Starting Chrome' "$T/term2.out" 2>/dev/null && break; sleep 0.2; done
sleep 0.5
start=$SECONDS
kill -TERM "$W"
wait "$W"; RC=$?; OUT="$(cat "$T/term2.out")"
check "TERM during startup exits 143" [ "$RC" -eq 143 ]
check "TERM during startup exits promptly" [ $((SECONDS - start)) -le 3 ]
check "TERM during startup never reports success" lacks "✔"
check "TERM during startup releases the lock" [ ! -e "$LOCK" ]
kill $(pids_for "--user-data-dir=$T/profT") 2>/dev/null

# Ordinary contention: simultaneous launches of fresh profiles get distinct ports.
( cd "$T/work" && exec env -i HOME="$H" PATH="$TPATH" TMPDIR="$T/tmp" PYTHONHOME="$PY_HOME" \
    CHROME_DEBUG_CHROME="$T/fake-chrome" bash "$CD" -d "$T/profH1" >"$T/h1.out" 2>&1 ) &
W1=$!
( cd "$T/work" && exec env -i HOME="$H" PATH="$TPATH" TMPDIR="$T/tmp" PYTHONHOME="$PY_HOME" \
    CHROME_DEBUG_CHROME="$T/fake-chrome" bash "$CD" -d "$T/profH2" >"$T/h2.out" 2>&1 ) &
W2=$!
wait "$W1"; R1=$?
wait "$W2"; R2=$?
P1="$(grep -o 'active on port [0-9]*' "$T/h1.out" | grep -o '[0-9]*$')"
P2="$(grep -o 'active on port [0-9]*' "$T/h2.out" | grep -o '[0-9]*$')"
OUT="$(cat "$T/h1.out" "$T/h2.out")"
check "concurrent launches both succeed" [ "$R1" -eq 0 -a "$R2" -eq 0 ]
check "concurrent launches pick distinct ports" [ -n "$P1" -a -n "$P2" -a "$P1" != "$P2" ]
run_cd -- --stop -d "$T/profH1"
run_cd -- --stop -d "$T/profH2"

echo
echo "passed: $PASS  failed: $FAIL"
[ "$FAIL" -eq 0 ]
