"""Stand-in for a Chrome browser process, used by tests/chrome-debug/run.sh.

The test copies the python3 binary to a file named `chrome` and runs this script with it,
so the process has a real browser-named executable (/proc/<pid>/exe), the same
command-line flags Chrome gets, and a DevTools-like HTTP endpoint whose listening socket
it really owns.

FAKE_MODE (environment):
  normal  serve /json/version, /json/list and /json/new on the debug port (default)
  nobind  stay alive without listening (a browser that lost its port, or is starting)
  decoy   start a different executable (FAKE_DECOY_BIN) that listens on the port, then
          behave like nobind: an endpoint that answers but is not this browser's
FAKE_DELAY  seconds to wait before listening (normal mode)

Every request is appended to <user-data-dir>/fake-requests.log, with /json/new targets
decoded, so a test can see which endpoint received which tab.
"""

import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

args = sys.argv[1:]
is_decoy = bool(args) and args[0] == "--decoy"
port = None
user_data_dir = ""
if is_decoy:
    port, log_path = int(args[1]), args[2]
else:
    for arg in args:
        if arg.startswith("--remote-debugging-port="):
            port = int(arg.split("=", 1)[1])
        elif arg.startswith("--user-data-dir="):
            user_data_dir = arg.split("=", 1)[1]
    log_path = os.path.join(user_data_dir, "fake-requests.log") if user_data_dir else os.devnull


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _any(self):
        path = self.path
        with open(log_path, "a") as log:
            if path.startswith("/json/new?"):
                log.write("NEW " + unquote(path.split("?", 1)[1]) + "\n")
            else:
                log.write(self.command + " " + path + "\n")
        if path.startswith("/json/version"):
            self._json({
                "Browser": "Decoy/1.0" if is_decoy else "FakeChrome/1.0",
                "webSocketDebuggerUrl": "ws://127.0.0.1:%d/devtools/browser/fake" % port,
            })
        elif path.startswith("/json/list"):
            owner = "decoy" if is_decoy else user_data_dir
            self._json([{"type": "page", "id": "1", "url": "about:blank", "title": "fake tab " + owner}])
        elif path.startswith("/json/new"):
            self._json({"type": "page", "id": "2"})
        else:
            self.send_response(404)
            self.end_headers()

    do_GET = _any
    do_PUT = _any


mode = "normal" if is_decoy else os.environ.get("FAKE_MODE", "normal")
if mode == "decoy":
    subprocess.Popen([os.environ["FAKE_DECOY_BIN"], sys.argv[0], "--decoy", str(port), log_path + ".decoy"])
    mode = "nobind"
if mode == "nobind":
    while True:
        time.sleep(60)

time.sleep(float(os.environ.get("FAKE_DELAY", "0")))
ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
