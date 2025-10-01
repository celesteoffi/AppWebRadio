from PySide6.QtCore import QThread, Signal
import utils, config

class UpdateChecker(QThread):
    found = Signal(str, str)   # version, url
    none  = Signal()
    fail  = Signal(str)

    def run(self):
        try:
            res = utils.get_latest_release(config.GITHUB_REPO, config.CURRENT_VERSION)
            if res:
                self.found.emit(res[0], res[1])
            else:
                self.none.emit()
        except Exception as e:
            self.fail.emit(str(e))

class UpdateDownloader(QThread):
    progress = Signal(int)     # %
    done     = Signal(str)     # path
    fail     = Signal(str)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self.url = url
        self.dest = dest

    def run(self):
        try:
            import requests
            with requests.get(self.url, stream=True, timeout=20) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length") or 0)
                done = 0
                with open(self.dest, "wb") as f:
                    for chunk in r.iter_content(1024 * 64):
                        if chunk:
                            f.write(chunk)
                            if total:
                                done += len(chunk)
                                self.progress.emit(int(done * 100 / total))
            self.done.emit(self.dest)
        except Exception as e:
            self.fail.emit(str(e))
