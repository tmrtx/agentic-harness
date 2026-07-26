#!/usr/bin/env bash
# Tests for the commit-protocol token-diff script. Each case runs the script
# against a fixture repo and a stubbed count_tokens endpoint (one word = one
# token) and asserts the emitted line and exit code. Measured lines are
# compared for exact stdout equality: rc 0 or 2 promises stdout is only the
# line, paste-able into a commit body. Exit code is the number of failing
# cases.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REPO/plugins/harness/skills/commit-protocol/scripts/token_diff.py"
TMP="$(mktemp -d)"
trap '[ -n "${STUB_PID:-}" ] && kill "$STUB_PID" 2>/dev/null; rm -rf "$TMP"' EXIT
fails=0

check_line() { # name expected_stdout actual_stdout (exact - stdout is the line)
  if [ "$3" = "$2" ]; then echo "PASS: $1"; else
    echo "FAIL: $1"; echo "  want: <$2>"; echo "  got:  <$3>"; fails=$((fails+1)); fi
}
check_prefix() { # name expected_prefix actual
  case "$3" in
    "$2"*) echo "PASS: $1" ;;
    *) echo "FAIL: $1"; echo "  want prefix: <$2>"; echo "  got:         <$3>"; fails=$((fails+1)) ;;
  esac
}
check_rc() { # name expected actual
  if [ "$2" -eq "$3" ]; then echo "PASS: $1"; else
    echo "FAIL: $1"; echo "  want rc $2, got rc $3"; fails=$((fails+1)); fi
}

# Stub endpoint: input_tokens = whitespace-separated word count of the message
# content (string or content-block form); content containing BOOM simulates a
# server-side failure. Each request's auth headers append to a log so cases
# can assert which credential reached the wire.
cat > "$TMP/stub.py" <<'PY'
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        with open(sys.argv[2], "a") as log:
            log.write("AUTH=%s BETA=%s KEY=%s PATH=%s VER=%s MODEL=%s\n" % (
                self.headers.get("authorization", ""),
                self.headers.get("anthropic-beta", ""),
                self.headers.get("x-api-key", ""),
                self.path,
                self.headers.get("anthropic-version", ""),
                body.get("model", "")))
        content = body["messages"][0]["content"]
        if isinstance(content, list):
            content = "".join(block.get("text", "") for block in content)
        if "BOOM" in content:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"type":"error"}')
            return
        out = json.dumps({"input_tokens": len(content.split())}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass

srv = HTTPServer(("127.0.0.1", 0), H)
with open(sys.argv[1], "w") as f:
    f.write(str(srv.server_address[1]))
srv.serve_forever()
PY
python3 "$TMP/stub.py" "$TMP/port" "$TMP/hdr.log" & STUB_PID=$!
for _ in $(seq 50); do [ -s "$TMP/port" ] && break; sleep 0.1; done
export ANTHROPIC_BASE_URL="http://127.0.0.1:$(cat "$TMP/port")"
export ANTHROPIC_API_KEY="test-key"

# Fixture repo. Committed state -> staged state, word counts in parentheses:
#   skills/a/f1.md modified  (4 -> 6): delta +2
#   skills/a/f2.md modified  (3 -> 1): delta -2
#   skills/a/f3.md added     (0 -> 2): delta +1 against the one-word sentinel
#   skills/a/f4.md deleted   (3 -> 0): delta -2 against the same sentinel
#   src/app.py    modified   - not steering text, excluded from derivation
# Aggregate over the steering files: added 3, removed 4, net -1.
R="$TMP/repo"
git init -q "$R"
g() { git -C "$R" -c user.email=t@t -c user.name=t "$@"; }
mkdir -p "$R/skills/a" "$R/src"
printf 'a b c d' > "$R/skills/a/f1.md"
printf 'one two three' > "$R/skills/a/f2.md"
printf 'z z z' > "$R/skills/a/f4.md"
printf 'code v1' > "$R/src/app.py"
g add .
g commit -qm base
printf 'a b c d e f' > "$R/skills/a/f1.md"
printf 'one' > "$R/skills/a/f2.md"
printf 'p q' > "$R/skills/a/f3.md"
printf 'code v2' > "$R/src/app.py"
g add .
g rm -q skills/a/f4.md

# 1. explicit paths: aggregates per-file deltas across modified/added/deleted;
#    stderr carries the per-file breakdown
out="$(cd "$R" && python3 "$SCRIPT" skills/a/f1.md skills/a/f2.md skills/a/f3.md skills/a/f4.md 2>"$TMP/err1")"; rc=$?
check_line "explicit paths measure the staged diff" "Token diff: +3/-4 (net -1, claude-opus-5)" "$out"
check_rc "explicit paths exit 0" 0 "$rc"
grep -q 'skills/a/f1.md +2' "$TMP/err1" && echo "PASS: stderr breaks down per-file deltas" || { echo "FAIL: stderr breakdown missing: $(cat "$TMP/err1")"; fails=$((fails+1)); }

# 2. no paths: the set derives from the staged diff, non-steering files excluded
out="$(cd "$R" && python3 "$SCRIPT" 2>/dev/null)"
check_line "derived paths match and filter steering text" "Token diff: +3/-4 (net -1, claude-opus-5)" "$out"

# 2b. an empty steering file is a real zero-cost side, not an absent path:
#     it must not abort the figure for the rest of the commit
printf '' > "$R/skills/a/empty.md"
g add skills/a/empty.md
out="$(cd "$R" && python3 "$SCRIPT" 2>/dev/null)"; rc=$?
check_line "empty file measures as zero" "Token diff: +3/-4 (net -1, claude-opus-5)" "$out"
check_rc "empty file exits 0" 0 "$rc"
g rm -q --cached skills/a/empty.md
rm -f "$R/skills/a/empty.md"

g commit -qm change

# 3. an unchanged file contributes zero; --model is named in the line AND
#    reaches the endpoint, on the documented path with the pinned API version
out="$(cd "$R" && python3 "$SCRIPT" --model test-model skills/a/f1.md 2>/dev/null)"
check_line "unchanged file is zero, model override named" "Token diff: +0/-0 (net +0, test-model)" "$out"
hdr="$(tail -1 "$TMP/hdr.log")"
case "$hdr" in *"PATH=/v1/messages/count_tokens "*) echo "PASS: request hits the count_tokens path" ;; *) echo "FAIL: request path: <$hdr>"; fails=$((fails+1)) ;; esac
case "$hdr" in *"VER=2023-06-01 "*) echo "PASS: anthropic-version pinned" ;; *) echo "FAIL: anthropic-version: <$hdr>"; fails=$((fails+1)) ;; esac
case "$hdr" in *"MODEL=test-model"*) echo "PASS: the named model is the counting model" ;; *) echo "FAIL: model in body: <$hdr>"; fails=$((fails+1)) ;; esac
case "$hdr" in *"KEY=test-key"*) echo "PASS: the api key rides x-api-key" ;; *) echo "FAIL: x-api-key header: <$hdr>"; fails=$((fails+1)) ;; esac

# 4. a recorded figure re-derives from history with no path list (ORC-5)
out="$(cd "$R" && python3 "$SCRIPT" --base HEAD^ --target HEAD 2>/dev/null)"
check_line "historical derivation matches the staged figure" "Token diff: +3/-4 (net -1, claude-opus-5)" "$out"

# 4b. a staged rename counts both sides: the moved content leaves one path
#     and arrives at another, so the recurring cost nets to zero
g mv skills/a/f1.md skills/a/f1moved.md
out="$(cd "$R" && python3 "$SCRIPT" 2>/dev/null)"
check_line "rename counts source and destination" "Token diff: +5/-5 (net +0, claude-opus-5)" "$out"
g reset -q --hard HEAD

# 4c. after the commit, a bare run must not print a paste-able falsehood:
#     the staged diff is empty, so it exits 1 and points at --base/--target
out="$(cd "$R" && python3 "$SCRIPT" 2>"$TMP/err4c")"; rc=$?
check_rc "post-commit bare run exits 1" 1 "$rc"
[ -z "$out" ] && echo "PASS: post-commit bare run prints no line" || { echo "FAIL: post-commit bare run printed: $out"; fails=$((fails+1)); }
grep -q -- '--base <sha>^ --target <sha>' "$TMP/err4c" && echo "PASS: post-commit bare run names the recovery" || { echo "FAIL: recovery hint missing: $(cat "$TMP/err4c")"; fails=$((fails+1)); }

# 5. a named path absent on both sides aborts: a wrong list must not read
#    as a measured zero
out="$(cd "$R" && python3 "$SCRIPT" skills/a/nope.md 2>/dev/null)"; rc=$?
check_prefix "absent path degrades to unavailable" "Token diff: unavailable (" "$out"
check_rc "absent path exits 2" 2 "$rc"

# 6. nothing steering in the staged diff: no paste-able line at all - exit 1
#    with the recovery hint, never a figure and never `unavailable`
printf 'code v3' > "$R/src/app.py"
g add src/app.py
out="$(cd "$R" && python3 "$SCRIPT" 2>"$TMP/err6")"; rc=$?
check_rc "steering-free diff exits 1" 1 "$rc"
[ -z "$out" ] && echo "PASS: steering-free diff prints no line" || { echo "FAIL: steering-free diff printed: $out"; fails=$((fails+1)); }
grep -q -- '--base' "$TMP/err6" && echo "PASS: steering-free diff names the recovery" || { echo "FAIL: recovery hint missing: $(cat "$TMP/err6")"; fails=$((fails+1)); }
g reset -q -- src/app.py
g checkout -q -- src/app.py

# 7. endpoint failure: prints the unavailable line, exit 2
printf 'BOOM goes the server' > "$R/skills/a/f5.md"
g add skills/a/f5.md
out="$(cd "$R" && python3 "$SCRIPT" skills/a/f5.md 2>/dev/null)"; rc=$?
check_prefix "endpoint failure degrades to unavailable" "Token diff: unavailable (" "$out"
check_rc "endpoint failure exits 2" 2 "$rc"
g rm -q --cached skills/a/f5.md

# 8. no resolvable credentials: prints the unavailable line, exit 2.
# PATH holds only git and python3, so no `ant` CLI can supply a fallback.
mkdir -p "$TMP/bin"
ln -sf "$(command -v git)" "$TMP/bin/git"
ln -sf "$(command -v python3)" "$TMP/bin/python3"
out="$(cd "$R" && env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN PATH="$TMP/bin" python3 "$SCRIPT" skills/a/f1.md 2>/dev/null)"; rc=$?
check_prefix "missing credentials degrade to unavailable" "Token diff: unavailable (" "$out"
check_rc "missing credentials exit 2" 2 "$rc"

# 9. bad usage: exit 1, no line on stdout
out="$(cd "$R" && python3 "$SCRIPT" --bogus-flag 2>/dev/null)"; rc=$?
check_rc "bad usage exits 1" 1 "$rc"
[ -z "$out" ] && echo "PASS: bad usage prints no line" || { echo "FAIL: bad usage printed: $out"; fails=$((fails+1)); }

# Credential-resolution chain. Each case runs on an unchanged file (one
# memoized request), so the log's last line is that invocation's request.

# 10. ANTHROPIC_AUTH_TOKEN authenticates as a bearer token, no oauth beta
out="$(cd "$R" && env -u ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN=plain-tok python3 "$SCRIPT" skills/a/f1.md 2>/dev/null)"
check_line "auth token still measures" "Token diff: +0/-0 (net +0, claude-opus-5)" "$out"
hdr="$(tail -1 "$TMP/hdr.log")"
case "$hdr" in *"AUTH=Bearer plain-tok "*) echo "PASS: bearer header carries the auth token" ;; *) echo "FAIL: bearer header: <$hdr>"; fails=$((fails+1)) ;; esac
case "$hdr" in *"BETA= KEY="*) echo "PASS: plain token sends no oauth beta" ;; *) echo "FAIL: unexpected beta: <$hdr>"; fails=$((fails+1)) ;; esac

# 11. an sk-ant-oat token adds the oauth beta header
out="$(cd "$R" && env -u ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN=sk-ant-oat01-test python3 "$SCRIPT" skills/a/f1.md 2>/dev/null)"
check_line "oauth token still measures" "Token diff: +0/-0 (net +0, claude-opus-5)" "$out"
hdr="$(tail -1 "$TMP/hdr.log")"
case "$hdr" in *"AUTH=Bearer sk-ant-oat01-test "*) echo "PASS: bearer header carries the oauth token" ;; *) echo "FAIL: oauth bearer header: <$hdr>"; fails=$((fails+1)) ;; esac
case "$hdr" in *"BETA=oauth-2025-04-20 "*) echo "PASS: oauth beta header sent" ;; *) echo "FAIL: oauth beta header: <$hdr>"; fails=$((fails+1)) ;; esac

# 12. with no env credentials, an `ant` login supplies the token
mkdir -p "$TMP/bin-ant"
ln -sf "$(command -v git)" "$TMP/bin-ant/git"
ln -sf "$(command -v python3)" "$TMP/bin-ant/python3"
cat > "$TMP/bin-ant/ant" <<'SH'
#!/bin/sh
if [ "$1 $2 $3" = "auth print-credentials --access-token" ]; then
  echo sk-ant-oat01-fromant
  exit 0
fi
exit 1
SH
chmod +x "$TMP/bin-ant/ant"
out="$(cd "$R" && env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN PATH="$TMP/bin-ant" python3 "$SCRIPT" skills/a/f1.md 2>/dev/null)"
check_line "ant login still measures" "Token diff: +0/-0 (net +0, claude-opus-5)" "$out"
hdr="$(tail -1 "$TMP/hdr.log")"
case "$hdr" in *"AUTH=Bearer sk-ant-oat01-fromant "*) echo "PASS: bearer header carries the ant token" ;; *) echo "FAIL: ant bearer header: <$hdr>"; fails=$((fails+1)) ;; esac

# 13. outside a git work tree: exit 1, no line on stdout
out="$(cd "$TMP" && python3 "$SCRIPT" x.md 2>/dev/null)"; rc=$?
check_rc "non-repo exits 1" 1 "$rc"
[ -z "$out" ] && echo "PASS: non-repo prints no line" || { echo "FAIL: non-repo printed: $out"; fails=$((fails+1)); }

echo "---"
[ "$fails" -eq 0 ] && echo "ALL PASS" || echo "$fails FAILURE(S)"
exit "$fails"
