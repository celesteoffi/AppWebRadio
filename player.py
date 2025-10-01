import vlc
import config

class RadioPlayer:
    def __init__(self):
        self.instance = vlc.Instance("--no-video")
        self.player = self.instance.media_player_new()

    def start_stream(self, url: str = None):
        """(Re)crée le média avant lecture pour éviter les états bloqués."""
        self.player.stop()
        media = self.instance.media_new(url or config.STREAM_URL)
        self.player.set_media(media)
        self.player.play()

    def stop_stream(self):
        self.player.stop()

    def is_playing(self) -> bool:
        try:
            return bool(self.player.is_playing())
        except Exception:
            return False

    def set_volume(self, v: int):
        self.player.audio_set_volume(int(v))

    def state(self):
        try:
            return self.player.get_state()
        except Exception:
            return None
