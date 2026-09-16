"""Local OpenCode launcher. Python standard library only."""

from __future__ import annotations

import atexit
import base64
import hashlib
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
STATIC = Path(getattr(sys, "_MEIPASS", APP_ROOT)) / "static"
STATE_DIR = Path(os.getenv("APPDATA") or (Path.home() / ".config")) / "opencode-portale"
STATE_FILE = STATE_DIR / "projects.json"
INSTALL_DIR = STATE_DIR / "bin"
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
PROCESSES: dict[str, tuple[subprocess.Popen, int]] = {}
INSTALL = {"busy": False, "error": "", "message": ""}


def load_projects() -> list[str]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return [x for x in data if isinstance(x, str) and Path(x).is_dir()][:30]
    except (OSError, ValueError, TypeError):
        return []


PROJECTS = load_projects()


def save_projects() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(PROJECTS, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATE_FILE)


def opencode_path() -> str | None:
    override = os.getenv("OPENCODE_BIN")
    if override and Path(override).is_file():
        return override
    name = "opencode.exe" if os.name == "nt" else "opencode"
    local = INSTALL_DIR / name
    if local.is_file():
        return str(local)
    for root in (APP_ROOT, APP_ROOT.parent):
        portable = root / "OpenCode-portatile-Windows" / name
        if portable.is_file():
            return str(portable)
    return shutil.which("opencode")


def platform_asset() -> str:
    machine = platform.machine().lower()
    arm = machine in {"arm64", "aarch64"}
    if sys.platform == "win32":
        return "opencode-windows-arm64.zip" if arm else "opencode-windows-x64-baseline.zip"
    if sys.platform == "darwin":
        return "opencode-darwin-arm64.zip" if arm else "opencode-darwin-x64-baseline.zip"
    if sys.platform.startswith("linux"):
        return "opencode-linux-arm64.tar.gz" if arm else "opencode-linux-x64-baseline.tar.gz"
    raise RuntimeError("Sistema operativo non supportato")


def _request_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "OpenCode-Portale/1.0", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def install_opencode() -> None:
    with LOCK:
        if INSTALL["busy"]:
            return
        INSTALL.update(busy=True, error="", message="Controllo la release ufficiale…")
    try:
        release = _request_json("https://api.github.com/repos/anomalyco/opencode/releases/latest")
        name = platform_asset()
        asset = next((item for item in release.get("assets", []) if item["name"] == name), None)
        if not asset:
            raise RuntimeError(f"Pacchetto {name} non trovato nella release")
        digest = asset.get("digest", "")
        if not digest.startswith("sha256:"):
            raise RuntimeError("La release non fornisce un digest SHA-256 verificabile")
        with LOCK:
            INSTALL["message"] = f"Scarico {name}…"
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=STATE_DIR) as temp:
            archive = Path(temp) / name
            request = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "OpenCode-Portale/1.0"})
            hash_value = hashlib.sha256()
            with urllib.request.urlopen(request, timeout=90) as response, archive.open("wb") as target:
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
                    hash_value.update(chunk)
            if hash_value.hexdigest().lower() != digest[7:].lower():
                raise RuntimeError("Hash SHA-256 non corrispondente alla release")
            with LOCK:
                INSTALL["message"] = "Estraggo OpenCode…"
            name_exe = "opencode.exe" if os.name == "nt" else "opencode"
            extracted = Path(temp) / name_exe
            if name.endswith(".zip"):
                with zipfile.ZipFile(archive) as bundle:
                    member = next((m for m in bundle.infolist() if Path(m.filename).name == name_exe and not m.is_dir()), None)
                    if not member:
                        raise RuntimeError("Eseguibile non trovato nell'archivio")
                    with bundle.open(member) as source, extracted.open("wb") as target:
                        shutil.copyfileobj(source, target)
            else:
                with tarfile.open(archive, "r:gz") as bundle:
                    member = next((m for m in bundle.getmembers() if Path(m.name).name == name_exe and m.isfile()), None)
                    if not member:
                        raise RuntimeError("Eseguibile non trovato nell'archivio")
                    source = bundle.extractfile(member)
                    if source is None:
                        raise RuntimeError("Impossibile leggere l'eseguibile")
                    with source, extracted.open("wb") as target:
                        shutil.copyfileobj(source, target)
            extracted.chmod(0o755)
            INSTALL_DIR.mkdir(parents=True, exist_ok=True)
            extracted.replace(INSTALL_DIR / name_exe)
        with LOCK:
            INSTALL["message"] = f"OpenCode {release.get('tag_name', '')} installato"
    except (OSError, RuntimeError, KeyError, ValueError, urllib.error.URLError) as error:
        with LOCK:
            INSTALL["error"] = str(error)
            INSTALL["message"] = ""
    finally:
        with LOCK:
            INSTALL["busy"] = False


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_server(process: subprocess.Popen, port: int, timeout: float = 12) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("OpenCode si è chiuso durante l'avvio. Controlla il file opencode.log.")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return
        except OSError:
            time.sleep(0.15)
    process.terminate()
    raise RuntimeError("OpenCode non ha risposto entro 12 secondi. Controlla il file opencode.log.")


def normalize_project(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Inserisci il percorso della cartella")
    project = Path(os.path.expandvars(raw.strip())).expanduser().resolve()
    if not project.is_dir():
        raise ValueError("La cartella non esiste su questo computer")
    return str(project)


def project_url(path: str, port: int) -> str:
    directory = base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")
    return f"http://127.0.0.1:{port}/{directory}/session"


def process_status() -> list[dict]:
    result = []
    for path in PROJECTS:
        current = PROCESSES.get(path)
        running = bool(current and current[0].poll() is None)
        if current and not running:
            PROCESSES.pop(path, None)
        result.append({"path": path, "name": Path(path).name, "running": running,
                       "url": project_url(path, current[1]) if running else None})
    return result


def stop_all() -> None:
    with LOCK:
        for process, _ in PROCESSES.values():
            if process.poll() is None:
                process.terminate()
        PROCESSES.clear()


atexit.register(stop_all)


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenCodePortale/1.0"

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _valid_host(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0]
        return host in {"127.0.0.1", "localhost", "[::1]"}

    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._valid_host():
            return self._json(403, {"error": "Host non valido"})
        path = urlparse(self.path).path
        if path == "/api/status":
            with LOCK:
                binary = opencode_path()
                return self._json(200, {"projects": process_status(), "installed": bool(binary),
                                        "binary": binary, "install": INSTALL.copy()})
        files = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"),
                 "/app.js": ("app.js", "application/javascript")}
        if path not in files:
            return self._json(404, {"error": "Pagina non trovata"})
        filename, mime = files[path]
        body = (STATIC / filename).read_bytes()
        if filename == "index.html":
            body = body.replace(b"__TOKEN__", TOKEN.encode("ascii"))
        self.send_response(200)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if not self._valid_host() or self.headers.get("X-Portale-Token") != TOKEN:
            return self._json(403, {"error": "Richiesta non autorizzata"})
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            return self._json(415, {"error": "Formato non valido"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 0 or size > 16_384:
                raise ValueError("Richiesta troppo grande")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Richiesta non valida")
            path = urlparse(self.path).path
            if path == "/api/install":
                if not INSTALL["busy"]:
                    threading.Thread(target=install_opencode, daemon=True).start()
                return self._json(202, {"ok": True})
            project = normalize_project(data.get("path", ""))
            with LOCK:
                if path == "/api/add":
                    if project in PROJECTS:
                        PROJECTS.remove(project)
                    PROJECTS.insert(0, project)
                    del PROJECTS[30:]
                    save_projects()
                    return self._json(200, {"ok": True})
                if path == "/api/remove":
                    if project in PROCESSES and PROCESSES[project][0].poll() is None:
                        raise ValueError("Arresta OpenCode prima di rimuovere il progetto")
                    if project in PROJECTS:
                        PROJECTS.remove(project)
                        save_projects()
                    return self._json(200, {"ok": True})
                if path == "/api/stop":
                    current = PROCESSES.pop(project, None)
                    if current and current[0].poll() is None:
                        current[0].terminate()
                    return self._json(200, {"ok": True})
                if path == "/api/start":
                    if project not in PROJECTS:
                        raise ValueError("Aggiungi prima il progetto")
                    binary = opencode_path()
                    if not binary:
                        raise ValueError("Installa OpenCode prima di avviarlo")
                    current = PROCESSES.get(project)
                    if current and current[0].poll() is None:
                        return self._json(200, {"url": project_url(project, current[1])})
                    port = free_port()
                    log = STATE_DIR / "opencode.log"
                    with log.open("ab") as output:
                        process = subprocess.Popen([binary, "web", "--hostname", "127.0.0.1", "--port", str(port)],
                                                   cwd=project, stdout=output, stderr=subprocess.STDOUT)
                    wait_for_server(process, port)
                    PROCESSES[project] = (process, port)
                    return self._json(200, {"url": project_url(project, port)})
            return self._json(404, {"error": "Azione non trovata"})
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            return self._json(400, {"error": str(error)})
        except (OSError, RuntimeError) as error:
            return self._json(500, {"error": str(error)})


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"OpenCode Portale: {url}", flush=True)
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        stop_all()


if __name__ == "__main__":
    main()
