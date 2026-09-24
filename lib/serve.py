"""Serve the editor on localhost and let it save the proposed layout, the Tray and notes."""

import errno
import json
import os
import subprocess
import sys
import threading
import urllib.request
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from file_tray import file_tray_contents
from layout import APP_LIBRARY_ONLY, BACKUPS, PROPOSED, ROOT, STATE, TRAY

NOTES = STATE / "notes.json"
EDITOR_TITLE = b"<title>Home Screen Organizer</title>"
NOTE_STATUSES = {"open", "done"}

# Overridable so tests can stub out the phone-facing step without touching a real iPhone.
APPLY_COMMAND = os.environ.get("HOMESCREEN_APPLY_COMMAND", str(ROOT / "bin" / "homescreen-apply"))
APPLY_TIMEOUT_SECONDS = 90


def layout_problem(proposal):
    if not isinstance(proposal, list):
        return "a layout is a list of pages"


def tray_problem(tray):
    if not isinstance(tray, list) or not all(isinstance(entry, dict) and isinstance(entry.get("app"), dict) for entry in tray):
        return "the Tray is a list of {app, origin}"


def notes_problem(notes):
    if not isinstance(notes, list):
        return "notes are a list"
    for note in notes:
        if not isinstance(note, dict) or not isinstance(note.get("id"), str) or not isinstance(note.get("text"), str):
            return "every note needs an id and text"
        if not isinstance(note.get("apps"), list) or note.get("status") not in NOTE_STATUSES:
            return "every note needs a list of apps and a status of open or done"


def app_library_only_problem(entries):
    if not isinstance(entries, list) or not all(
        isinstance(entry, dict) and isinstance(entry.get("displayIdentifier"), str) and isinstance(entry.get("displayName"), str)
        for entry in entries
    ):
        return "App Library Only is a list of {displayIdentifier, displayName}"


SAVABLE = {
    "/state/proposed.json": (PROPOSED, layout_problem),
    "/state/tray.json": (TRAY, tray_problem),
    "/state/notes.json": (NOTES, notes_problem),
    "/state/app-library-only.json": (APP_LIBRARY_ONLY, app_library_only_problem),
}


class ApplyRunner:
    """Runs bin/homescreen-apply (or its stand-in) as a subprocess, one at a time."""

    def __init__(self, command):
        self.command = command
        self.lock = threading.Lock()
        self.running = False

    def run(self, *extra_args):
        with self.lock:
            if self.running:
                return {"ok": False, "output": "Already applying to the phone; wait for it to finish."}
            self.running = True
        try:
            result = subprocess.run(
                [self.command, *extra_args],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=APPLY_TIMEOUT_SECONDS,
            )
            return {"ok": result.returncode == 0, "output": result.stdout + result.stderr}
        except subprocess.TimeoutExpired as error:
            timed_out_output = (error.stdout or "") + (error.stderr or "")
            return {"ok": False, "output": f"Timed out after {APPLY_TIMEOUT_SECONDS}s.\n{timed_out_output}"}
        finally:
            with self.lock:
                self.running = False


apply_runner = ApplyRunner(APPLY_COMMAND)


def latest_before_apply_backup():
    if not BACKUPS.exists():
        return None
    candidates = sorted(BACKUPS.glob("*before-apply*.json"))
    if not candidates:
        return None
    newest = candidates[-1]
    return {"path": str(newest.relative_to(ROOT)), "time": _backup_time(newest).isoformat()}


def _backup_time(path):
    prefix = path.name.split("-before-apply")[0]
    try:
        return datetime.strptime(prefix, "%Y-%m-%d-%H%M%S")
    except ValueError:
        return datetime.fromtimestamp(path.stat().st_mtime)


class EditorRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/backups.json":
            self.respond_json({"restore": latest_before_apply_backup()})
            return
        super().do_GET()

    def do_PUT(self):
        self.save_state()

    def do_POST(self):
        path = self.path.split("?")[0]
        if path in SAVABLE:
            self.save_state()
        elif path == "/file-tray":
            self.file_tray()
        elif path == "/apply":
            self.respond_json(apply_runner.run("--yes"))
        elif path == "/restore":
            self.restore()
        else:
            self.send_error(404, f"only {', '.join(SAVABLE)}, /file-tray, /apply and /restore can be posted to")

    def save_state(self):
        path = self.path.split("?")[0]
        if path not in SAVABLE:
            self.send_error(404, f"only {', '.join(SAVABLE)} can be saved")
            return
        destination, problem_with = SAVABLE[path]
        document = self.read_json_body()
        if document is None:
            return
        problem = problem_with(document)
        if problem:
            self.send_error(400, problem)
            return
        save_atomically(document, destination)
        self.send_response(204)
        self.end_headers()

    def file_tray(self):
        body = self.read_json_body()
        if body is None:
            return
        layout, tray, app_library_only = body.get("layout"), body.get("tray"), body.get("appLibraryOnly", [])
        if not isinstance(layout, list) or not isinstance(tray, list) or not isinstance(app_library_only, list):
            self.send_error(400, "file-tray needs {layout, tray, appLibraryOnly}")
            return
        layout, remaining_tray, archived, filed, unfiled = file_tray_contents(layout, tray, app_library_only)
        self.respond_json({"layout": layout, "tray": remaining_tray, "appLibraryOnly": archived, "filed": filed, "unfiled": unfiled})

    def restore(self):
        backup = latest_before_apply_backup()
        if backup is None:
            self.send_error(409, "no before-apply backup to restore")
            return
        self.respond_json(apply_runner.run("--restore", str(ROOT / backup["path"]), "--yes"))

    def read_json_body(self):
        try:
            return json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        except (TypeError, ValueError):
            self.send_error(400, "the body is not JSON")
            return None

    def respond_json(self, document):
        body = json.dumps(document).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def save_atomically(document, destination):
    draft = destination.with_suffix(".json.saving")
    draft.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    os.replace(draft, destination)


def editor_url(port):
    return f"http://localhost:{port}/web/"


def is_editor_at(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return EDITOR_TITLE in response.read()
    except OSError:
        return False


def explain_port_in_use(port):
    url = editor_url(port)
    if is_editor_at(url):
        print(f"The editor is already running: {url}")
        raise SystemExit(0)
    raise SystemExit(f"Port {port} is taken by another program. Start the editor on another port:\n  bin/homescreen-serve {port + 1}")


class EditorHTTPServer(ThreadingHTTPServer):
    # The default backlog of 5 (socketserver.TCPServer.request_queue_size) resets
    # connections under a page load's burst of concurrent icon requests, which the
    # browser shows as placeholder letters instead of artwork.
    request_queue_size = 128


def serve(port):
    handler = partial(EditorRequestHandler, directory=str(ROOT))
    try:
        server = EditorHTTPServer(("127.0.0.1", port), handler)
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        explain_port_in_use(port)
    print(f"Home Screen editor: {editor_url(port)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
