"""Development helper: restart the desktop app whenever its .py files change.

Not for the packaged .exe — this is a dev-only convenience so you don't have
to manually close and reopen the app after every code edit. Unsaved state
(loaded orders, unsaved edits) is lost on each restart, same as closing the
window yourself.

Run with:  python dev_watch.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
WATCHED_DIRS = [PROJECT_ROOT / "rm_planner"]
WATCHED_FILES = [PROJECT_ROOT / "app.py"]
POLL_SECONDS = 1.0


def snapshot_mtimes() -> dict[Path, float]:
    mtimes: dict[Path, float] = {}
    for path in WATCHED_FILES:
        if path.exists():
            mtimes[path] = path.stat().st_mtime
    for directory in WATCHED_DIRS:
        for path in directory.rglob("*.py"):
            mtimes[path] = path.stat().st_mtime
    return mtimes


def launch_app() -> subprocess.Popen:
    print("[dev_watch] starting app.py")
    return subprocess.Popen([sys.executable, str(PROJECT_ROOT / "app.py")], cwd=PROJECT_ROOT)


def main() -> None:
    process = launch_app()
    last_mtimes = snapshot_mtimes()
    try:
        while True:
            time.sleep(POLL_SECONDS)
            current_mtimes = snapshot_mtimes()
            if current_mtimes != last_mtimes:
                print("[dev_watch] change detected, restarting app")
                last_mtimes = current_mtimes
                if process.poll() is None:
                    process.terminate()
                    process.wait()
                process = launch_app()
            elif process.poll() is not None:
                # App was closed by hand; wait for the next edit before relaunching.
                print("[dev_watch] app closed, waiting for changes…")
                while current_mtimes == last_mtimes:
                    time.sleep(POLL_SECONDS)
                    current_mtimes = snapshot_mtimes()
                last_mtimes = current_mtimes
                process = launch_app()
    except KeyboardInterrupt:
        print("[dev_watch] stopping")
        if process.poll() is None:
            process.terminate()
            process.wait()


if __name__ == "__main__":
    main()
