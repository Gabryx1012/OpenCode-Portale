import json
import base64
import hashlib
import io
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

import app


class PortaleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = app.PROJECTS[:]
        app.PROJECTS.clear()
        self.state = patch.object(app, "STATE_DIR", Path(self.temp.name))
        self.file = patch.object(app, "STATE_FILE", Path(self.temp.name) / "projects.json")
        self.state.start(); self.file.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        app.stop_all()
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        self.state.stop(); self.file.stop()
        app.PROJECTS[:] = self.original
        self.temp.cleanup()

    def request(self, path, data=None, token=True):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Portale-Token"] = app.TOKEN
        request = urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status, json.load(response)

    def test_project_add_persist_remove(self):
        project = Path(self.temp.name)
        status, _ = self.request("/api/add", {"path": str(project)})
        self.assertEqual(status, 200)
        self.assertEqual(app.load_projects(), [str(project.resolve())])
        _, result = self.request("/api/status")
        self.assertEqual(result["projects"][0]["name"], project.name)
        self.request("/api/remove", {"path": str(project)})
        self.assertEqual(app.load_projects(), [])

    def test_rejects_invalid_path_and_missing_token(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/api/add", {"path": str(Path(self.temp.name) / "missing")})
        self.assertEqual(error.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/api/add", {"path": self.temp.name}, token=False)
        self.assertEqual(error.exception.code, 403)
        self.assertEqual(app.PROJECTS, [])

    def test_asset_selection_and_normalization(self):
        with patch.object(app.sys, "platform", "win32"), patch.object(app.platform, "machine", return_value="AMD64"):
            self.assertEqual(app.platform_asset(), "opencode-windows-x64-baseline.zip")
        with patch.object(app.sys, "platform", "darwin"), patch.object(app.platform, "machine", return_value="arm64"):
            self.assertEqual(app.platform_asset(), "opencode-darwin-arm64.zip")
        self.assertEqual(app.normalize_project(self.temp.name), str(Path(self.temp.name).resolve()))
        encoded = app.project_url(self.temp.name, 4096).split("/")[3]
        self.assertEqual(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode(), self.temp.name)

    def test_verified_installation_from_release_asset(self):
        binary = b"sample-opencode-binary"
        exe_name = "opencode.exe" if app.os.name == "nt" else "opencode"
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w") as bundle:
            bundle.writestr(exe_name, binary)
        archive = memory.getvalue()
        release = {"tag_name": "v-test", "assets": [{"name": "opencode-windows-x64-baseline.zip",
                    "digest": "sha256:" + hashlib.sha256(archive).hexdigest(), "browser_download_url": "https://example.invalid/archive"}]}
        with patch.object(app, "INSTALL_DIR", Path(self.temp.name) / "bin"), \
             patch.object(app, "platform_asset", return_value="opencode-windows-x64-baseline.zip"), \
             patch.object(app, "_request_json", return_value=release), \
             patch.object(app.urllib.request, "urlopen", return_value=io.BytesIO(archive)):
            app.install_opencode()
            self.assertEqual((Path(self.temp.name) / "bin" / exe_name).read_bytes(), binary)
            self.assertFalse(app.INSTALL["busy"])
            self.assertFalse(app.INSTALL["error"])


if __name__ == "__main__":
    unittest.main()
