import sys
import os
import json
import time
import threading
import requests
import vlc
from pypresence import Presence
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QSlider
from PySide6.QtCore import Qt

# ---------------------------
# CONFIG
# ---------------------------
DISCORD_CLIENT_ID = "1419735937545404456"  # remplace par ton vrai Client ID
STREAM_URL = "https://radio.inspora.fr/listen/wazouinfraweb/radio.mp3"
API_URL = "https://radio.inspora.fr/api/nowplaying/1"
MAP_FILE = "images_map.json"

# ---------------------------
# Charger mapping images
# ---------------------------
with open(MAP_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

def choose_image(title, live):
    if live:
        return config["live"]

    for song_title, img in config["titles"].items():
        if song_title.lower() in title.lower():  # match partiel insensible à la casse
            return img

    return config["default"]

# ---------------------------
# Classe Application
# ---------------------------
class RadioApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎶 InsporaRadio Player")

        # VLC player
        instance = vlc.Instance("--no-video")
        self.player = instance.media_player_new()
        media = instance.media_new(STREAM_URL)
        self.player.set_media(media)

        # Discord RPC
        self.rpc = Presence(DISCORD_CLIENT_ID)
        try:
            self.rpc.connect()
        except Exception as e:
            print("[!] Impossible de se connecter à Discord :", e)
            self.rpc = None
        self.start_ts = int(time.time())

        # UI elements
        self.label = QLabel("⏸️ Radio arrêtée")
        self.btn = QPushButton("▶️ Lecture")
        self.btn.clicked.connect(self.toggle_play)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.player.audio_set_volume(80)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.btn)
        layout.addWidget(QLabel("🔊 Volume"))
        layout.addWidget(self.volume_slider)
        self.setLayout(layout)

        # Threads
        threading.Thread(target=self.update_info_loop, daemon=True).start()

    def toggle_play(self):
        if self.player.is_playing():
            self.player.stop()
            self.label.setText("⏸️ Radio arrêtée")
            self.btn.setText("▶️ Lecture")
        else:
            self.player.play()
            self.label.setText("🎵 Lecture en cours...")
            self.btn.setText("⏹️ Stop")

    def set_volume(self, value):
        self.player.audio_set_volume(value)

    def update_info_loop(self):
        """Boucle pour récupérer les infos NowPlaying + update Discord"""
        while True:
            try:
                r = requests.get(API_URL, timeout=5).json()
                song = r.get("now_playing", {}).get("song", {})
                title = song.get("title", "Inconnu")
                artist = song.get("artist", "")
                listeners = r.get("listeners", {}).get("total", 0)
                live = r.get("live", {}).get("is_live", False)

                text = f"🎶 {title} — {artist} | 👥 {listeners} auditeurs"
                self.label.setText(text)

                if self.rpc:
                    large_image = choose_image(title, live)
                    try:
                        self.rpc.update(
                            details=f"{title} — {artist}",
                            state=f"👥 {listeners} auditeurs",
                            start=self.start_ts,
                            large_image=large_image,
                            large_text="InsporaRadio"
                        )
                        print(f"[RPC] {title} [{large_image}]")
                    except Exception as e:
                        print("[!] Erreur RPC :", e)
            except Exception as e:
                print("[!] Erreur récupération infos :", e)

            time.sleep(15)

# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = RadioApp()
    win.show()
    sys.exit(app.exec())
