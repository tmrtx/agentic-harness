"""Capture proxy: relay Claude API traffic upstream byte-for-byte
untouched, and write each JSON POST body to the capture dir as
req-NNNN.json with a req-NNNN.headers.json sibling. It is a
verification transport — proof of what the model saw — so it must not
mutate the wire, and it carries nothing beyond the relay and the
capture (no export, no timing marks, no rewriting).

Mechanics:
- Capture BEFORE forward: a call that dies upstream still leaves
  evidence of what was sent.
- Relay the response line by line and flush each line: the CLI
  streams SSE; a buffering relay stalls it.
- Accept-Encoding forced to identity so the response can be re-chunked
  without decoding.
- The capture counter seeds from the highest existing req-*.json
  instead of restarting at zero, so a proxy restart (or a capture dir
  shared with cc-sniff, whose layout this matches) never overwrites
  earlier captures. Select captures by mtime window, never by
  filename order.
- A gzipped request body is stored decompressed so every capture stays
  json.load-able; the original bytes go upstream untouched.

The headers file includes Authorization. Treat the capture dir as
secret material and clear it when done.

Run:
    python3 wire_capture.py [port]        # default 8899
    ANTHROPIC_BASE_URL=http://127.0.0.1:8899 <rollouts>

Env:
    WIRE_CAPTURE_DIR       capture dir    (default /tmp/cc-sniff/capture)
    WIRE_CAPTURE_UPSTREAM  upstream host  (default api.anthropic.com)
    WIRE_CAPTURE_SCHEME    https | http   (default https)
"""
import glob
import gzip
import http.client
import http.server
import json
import os
import re
import sys
import threading

CAPTURE_DIR = os.environ.get("WIRE_CAPTURE_DIR", "/tmp/cc-sniff/capture")
UPSTREAM = os.environ.get("WIRE_CAPTURE_UPSTREAM", "api.anthropic.com")
SCHEME = os.environ.get("WIRE_CAPTURE_SCHEME", "https")

os.makedirs(CAPTURE_DIR, exist_ok=True)

_lock = threading.Lock()


def _seed():
    hi = 0
    for p in glob.glob(os.path.join(CAPTURE_DIR, "req-*.json")):
        m = re.match(r"req-(\d+)\.json$", os.path.basename(p))
        if m:
            hi = max(hi, int(m.group(1)))
    return hi


_n = {"i": _seed()}


def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def json_body(raw):
    """(storable_bytes, parsed_dict) for a JSON request body, gunzipping
    if the client compressed it; (None, None) when not JSON."""
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except OSError:
            return None, None
    try:
        data = json.loads(raw)
    except ValueError:
        return None, None
    return raw, (data if isinstance(data, dict) else {})


class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _fwd_headers(self):
        h = {k: v for k, v in self.headers.items()
             if k.lower() not in ("host", "accept-encoding")}
        h["Host"] = UPSTREAM.split(":")[0]
        h["Accept-Encoding"] = "identity"
        return h

    def do_GET(self):
        self._relay("GET", None)

    def do_DELETE(self):
        self._relay("DELETE", None)

    def do_PUT(self):
        self._relay("PUT", self._body())

    def do_POST(self):
        raw = self._body()
        cap, data = json_body(raw)
        if cap is not None:
            with _lock:
                _n["i"] += 1
                idx = _n["i"]
            try:
                with open(os.path.join(CAPTURE_DIR,
                                       "req-%04d.json" % idx), "wb") as f:
                    f.write(cap)
                with open(os.path.join(CAPTURE_DIR,
                                       "req-%04d.headers.json" % idx),
                          "w") as f:
                    json.dump(dict(self.headers.items()), f, indent=1)
                log("[%04d] POST %s model=%s (%d bytes)"
                    % (idx, self.path, data.get("model"), len(cap)))
            except OSError as e:
                log("  capture error: %s" % e)
        self._relay("POST", raw)

    def _relay(self, method, body):
        try:
            cls = (http.client.HTTPSConnection if SCHEME == "https"
                   else http.client.HTTPConnection)
            c = cls(UPSTREAM, timeout=900)
            c.request(method, self.path, body=body,
                      headers=self._fwd_headers())
            r = c.getresponse()
        except Exception as e:
            log("  forward error: %s" % e)
            try:
                self.send_response(502)
                self.send_header("Content-Length", "0")
                self.end_headers()
            except Exception:
                pass
            return
        try:
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in ("transfer-encoding", "content-length",
                                     "connection", "content-encoding"):
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            while True:
                line = r.readline()
                if not line:
                    break
                self.wfile.write(b"%x\r\n" % len(line))
                self.wfile.write(line)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            log("  relay error: %s" % e)
        finally:
            try:
                c.close()
            except Exception:
                pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Proxy)
    log("wire_capture on http://127.0.0.1:%d  ->  %s://%s"
        % (port, SCHEME, UPSTREAM))
    log("  captures  %s  (next index %d)" % (CAPTURE_DIR, _n["i"] + 1))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("bye")
