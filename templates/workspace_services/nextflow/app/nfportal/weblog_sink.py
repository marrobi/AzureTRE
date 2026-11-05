"""Local nf-weblog receiver that runs beside the Nextflow head process.

Nextflow posts workflow events to 127.0.0.1, and this process appends each
event to runs/<run_id>/events.jsonl with the head pool's managed identity. The
portal therefore needs no endpoint reachable from the Batch subnet.
"""

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from .store import RUNS, AzureBlobStore

MAX_EVENT_BYTES = 1024 * 1024
log = logging.getLogger("weblog-sink")


def make_handler(store, run_id: str):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (http.server API)
            length = min(int(self.headers.get("Content-Length") or 0), MAX_EVENT_BYTES)
            body = self.rfile.read(length)
            try:
                event = json.loads(body)
                store.append_line(RUNS, f"{run_id}/events.jsonl", json.dumps(event, separators=(",", ":")))
            except Exception:  # never fail the pipeline because progress reporting failed
                log.exception("Could not record weblog event")
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args) -> None:
            pass

    return Handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    from azure.identity import ManagedIdentityCredential

    run_id = os.environ["NF_RUN_ID"]
    account = os.environ["NF_STORAGE_ACCOUNT"]
    credential = ManagedIdentityCredential(client_id=os.environ["NF_IDENTITY_CLIENT_ID"])
    store = AzureBlobStore(f"https://{account}.blob.core.windows.net", credential)
    port = int(os.environ.get("NF_WEBLOG_PORT", "8099"))
    HTTPServer(("127.0.0.1", port), make_handler(store, run_id)).serve_forever()


if __name__ == "__main__":
    main()
