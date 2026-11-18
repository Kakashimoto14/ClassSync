"""Verify denied Postman guards send zero HTTP requests. No institutional APIs/data."""

import json
import os
import subprocess
import tempfile
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def qualify():
    hits = []

    class Receiver(BaseHTTPRequestHandler):
        def handle_request(self):
            hits.append(self.command)
            self.send_response(418)
            self.end_headers()

        do_GET = do_POST = do_PATCH = do_DELETE = do_PUT = handle_request

        def log_message(self, *_args):
            pass

    binary = Path("var/m5-postman-portable/extracted/postman-cli.exe").resolve()
    collection = json.loads(Path("docs/api/ClassSync.postman_collection.json").read_text())
    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix="classsync-postman-guard-") as directory:
            root = Path(directory)
            base = f"http://127.0.0.1:{server.server_port}"
            values = {
                "base_url": base,
                "auth_emulator_url": base,
                "id_token": "",
                "approved_cloud_qualification": "false",
                "approved_disposable_qualification": "false",
                "approved_synthetic_journey": "false",
            }
            denied = deepcopy(collection)
            denied["item"] = denied["item"][1:]
            override = deepcopy(collection["item"][2])
            override["name"] = "Effective data destination override must be skipped"
            override["event"][0]["script"]["exec"].insert(
                0, "pm.environment.set('approved_disposable_qualification', 'true');"
            )
            denied["item"].append(override)
            (root / "collection.json").write_text(json.dumps(denied), encoding="utf-8")
            (root / "environment.json").write_text(
                json.dumps(
                    {"values": [{"key": k, "value": v, "enabled": True} for k, v in values.items()]}
                )
            )
            # Iteration scope outranks environment, but must not redirect a guarded request.
            (root / "data.json").write_text(
                json.dumps([{"base_url": base.replace("127.0.0.1", "localhost")}])
            )
            child = {
                k: v
                for k, v in os.environ.items()
                if not k.startswith(("POSTMAN_", "GOOGLE_", "FIREBASE_", "GCLOUD_"))
            }
            child.update(
                USERPROFILE=str(root),
                APPDATA=str(root),
                LOCALAPPDATA=str(root),
                HTTP_PROXY="http://127.0.0.1:9",
                HTTPS_PROXY="http://127.0.0.1:9",
                NO_PROXY="127.0.0.1,localhost",
                CI="true",
            )
            result = subprocess.run(
                [
                    str(binary),
                    "collection",
                    "run",
                    str(root / "collection.json"),
                    "-e",
                    str(root / "environment.json"),
                    "-d",
                    str(root / "data.json"),
                    "--no-report-events",
                    "--timeout",
                    "20000",
                    "--timeout-request",
                    "2000",
                ],
                cwd=root,
                env=child,
                capture_output=True,
                timeout=30,
            )
            if hits:
                raise RuntimeError("Denied guard sent an HTTP request")
            if result.returncode:
                raise RuntimeError("Guard runtime did not finish successfully")
            return {
                "runner": "Postman CLI1.86.0",
                "denied_folders": len(denied["item"]),
                "receiver_hits": len(hits),
                "effective_variable_override_denied": True,
            }
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


if __name__ == "__main__":
    print(json.dumps(qualify()))
