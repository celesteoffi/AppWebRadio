import sys
import os
import json
import time
import threading
import requests
import vlc
from pypresence import Presence
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QSlider, QMessageBox
from PySide6.QtCore import Qt

# ---------------------------
# CONFIG
# ---------------------------
DISCORD_CLIENT_ID = "1419735937545404456"  # 🔴 à remplacer
STREAM_URL = "https://radio.inspora.fr/listen/wazouinfraweb/radio.mp3"
API_URL = "https://radio.inspora.fr/api/nowplaying/1"
GITHUB_REPO = "celesteoffi/AppWebRadio"
CURRENT_VERSION = "1.0.0"
MAP_URL = "https://raw.githubusercontent.com/celesteoffi/AppWebRadio/main/images_map.json"

# ---------------------------
# Charger libVLC embarqué
# ---------------------------
if sys.platform.startswith("win"):
    vlc_path = os.path.join(os.path.dirname(__file__), "vlc")
    if os.path.exists(vlc_path):
        os.add_dll_directory(vlc_path)

# ---------------------------
# Charger mapping images
# ---------------------------
def load_images_map():
    try:
        r = requests.get(MAP_URL, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("[!] Erreur chargement map GitHub :", e)

    # fallback
    return {"default": "logo_default", "live": "logo_live", "titles": {}}

config = load_images_map()

def choose_image(title, live):
    if live:
        return config.get("live", "logo_live")
    for song_title, img in config.get("titles", {}).items():
        if song_title.lower() in title.lower():
            return img
    return config.get("default", "logo_default")

# ---------------------------
# Vérifier update GitHub
# ---------------------------
def check_update():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        r = requests.get(url, timeout=5).json()
        latest_version = r.get("tag_name", "").replace("v", "")
        download_url = None
        if r.get("assets"):
            download_url = r["assets"][0]["browser_download_url"]

        if latest_version and latest_version != CURRENT_VERSION:
            return (latest_version, download_url)
    except Exception as e:
        print("[!] Erreur vérification maj :", e)
    return None

# ---------------------------
# Classe Application
# ---------------------------
class RadioApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"🎶 InsporaRadio Player v{CURRENT_VERSION}")

        # VLC
        instance = vlc.Instance("--no-video")
        self.player = instance.media_player_new()
        media = instance.media_new(STREAM_URL)
        self.player.set_media(media)

        # Discord RPC
        self.rpc = Presence(DISCORD_CLIENT_ID)
        try:
            self.rpc.connect()
        except Exception as e:
            print("[!] Discord RPC non dispo :", e)
            self.rpc = None
        self.start_ts = int(time.time())

        # UI
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

        # Vérifier update
        update = check_update()
        if update:
            latest, url = update
            QMessageBox.information(
                self, "Mise à jour dispo",
                f"🚀 Version {latest} disponible !\nTélécharge ici :\n{url}"
            )

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
                    self.rpc.update(
                        details=f"{title} — {artist}",
                        state=f"👥 {listeners} auditeurs",
                        start=self.start_ts,
                        large_image=large_image,
                        large_text="InsporaRadio"
                    )
                    print(f"[RPC] {title} [{large_image}]")
            except Exception as e:
                print("[!] Erreur update infos :", e)

            time.sleep(15)

# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = RadioApp()
    win.show()
    sys.exit(app.exec())
