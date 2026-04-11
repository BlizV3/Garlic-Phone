"""
Version checking against GitHub releases API.
Called once on startup before connecting to the server.
"""
import urllib.request
import json
import threading
from PyQt6.QtCore import QObject, pyqtSignal


class VersionChecker(QObject):
    """Checks GitHub releases API on a background thread."""
    up_to_date    = pyqtSignal()
    update_needed = pyqtSignal(str, str)   # latest_version, download_url
    check_failed  = pyqtSignal()           # network error — assume up to date

    def __init__(self, parent=None):
        super().__init__(parent)

    def check(self):
        """Start the background check. Emits one of the three signals when done."""
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        from app.version import VERSION, GITHUB_REPO
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "GarlicPhone"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())

            latest_tag = data.get("tag_name", "")
            if not latest_tag:
                self.check_failed.emit()
                return

            # Find the .exe asset
            download_url = ""
            for asset in data.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    download_url = asset.get("browser_download_url", "")
                    break

            if latest_tag == VERSION:
                self.up_to_date.emit()
            else:
                self.update_needed.emit(latest_tag, download_url)

        except Exception as e:
            print(f"[Version check] Could not check for updates: {e}")
            self.check_failed.emit()   # fail silently — let them play