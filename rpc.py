from pypresence import Presence
import time

class DiscordRPCManager:
    def __init__(self, client_id: str, app_name: str):
        self.client_id = client_id
        self.app_name = app_name
        self.rpc = None
        self.start_ts = int(time.time())
        self.last_error = None

    def connect(self) -> bool:
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.last_error = None
            return True
        except Exception as e:
            self.rpc = None
            self.last_error = str(e)
            return False

    def enabled(self) -> bool:
        return self.rpc is not None

    def update(self, title: str, artist: str, listeners: int, large_image: str):
        if not self.rpc:
            return
        try:
            self.rpc.update(
                details=f"{title} — {artist}",
                state=f"👥 {listeners} auditeurs",
                start=self.start_ts,
                large_image=large_image,
                large_text=self.app_name
            )
        except Exception as e:
            self.last_error = str(e)
            try:
                self.connect()
            except Exception:
                pass

    def clear_close(self):
        try:
            if self.rpc:
                self.rpc.clear()
                self.rpc.close()
        except Exception:
            pass
        self.rpc = None
