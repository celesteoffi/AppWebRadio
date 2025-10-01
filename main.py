import sys
import os
import json
import time
import threading
import subprocess
import requests
import vlc
from pypresence import Presence
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QVBoxLayout,
    QSlider, QMessageBox
)
from PySide6.QtCore import Qt

# ========= CONFIG =========
DISCORD_CLIENT_ID = "1419735937545404456"  # ⚠️ remplace par ton vrai Client ID
STREAM_URL = "https://radio.inspora.fr/listen/wazouinfraweb/radio.mp3"
API_URL    = "https://radio.inspora.fr/api/nowplaying/1"

GITHUB_REPO = "celesteoffi/AppWebRadio"
CURRENT_VERSION = "1.0.1"  # ⚠️ incrémente à chaque build publié
MAP_URL = "https://raw.githubusercontent.com/celesteoffi/AppWebRadio/main/images_map.json"
APP_NAME = "InsporaRadio"

# ========= VLC PORTABLE (embarqué) =========
if sys.platform.startswith("win"):
    vlc_path = os.path.join(os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__), "vlc")
    if os.path.exists(vlc_path):
        os.add_dll_directory(vlc_path)

# ========= UTILS =========
def is_frozen_exe() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

def this_exe_path() -> str:
    if is_frozen_exe():
        return sys.executable
    # mode dev: pas un exe, on retourne le chemin du script
    return os.path.abspath(__file__)

def temp_path(name: str) -> str:
    return os.path.join(os.environ.get("TEMP", os.getcwd()), name)

# ========= IMAGES MAP (GitHub) =========
def load_images_map():
    try:
        r = requests.get(MAP_URL, timeout=6)
        if r.status_code == 200:
            return r.json()
        print("[!] MAP GitHub statut:", r.status_code)
    except Exception as e:
        print("[!] Erreur MAP GitHub:", e)
    # fallback minimal
    return {"default": "logo_default", "live": "logo_live", "titles": {}}

config = load_images_map()

def choose_image(title: str, live: bool) -> str:
    if live:
        return config.get("live", "logo_live")
    for song_title, img in config.get("titles", {}).items():
        if song_title.lower() in title.lower():
            return img
    return config.get("default", "logo_default")

# ========= UPDATE (GitHub Releases) =========
def get_latest_release():
    """Retourne (version, asset_url) ou None si rien."""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        data = requests.get(url, timeout=8).json()
        tag = (data.get("tag_name") or "").lstrip("v")
        asset_url = None
        for asset in data.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".exe"):
                asset_url = asset.get("browser_download_url")
                break
        if tag and asset_url and tag != CURRENT_VERSION:
            return tag, asset_url
    except Exception as e:
        print("[!] get_latest_release:", e)
    return None

def download_file(url: str, dest: str):
    """Téléchargement streaming → dest"""
    with requests.get(url, stream=True, timeout=20) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", "0") or 0)
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
    return dest

def write_updater_and_run(new_exe_path: str, target_path: str):
    """
    Crée un .bat dans %TEMP% qui attend la fermeture de l'app,
    remplace le .exe, relance, puis s'auto-supprime.
    """
    bat_path = temp_path("updater_inspora.bat")
    # Important : guillemets pour gérer les espaces
    bat = f"""@echo off
setlocal
echo Mise a jour en cours...
ping 127.0.0.1 -n 2 > nul
:repeat
move /Y "{new_exe_path}" "{target_path}" > nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 1 /nobreak > nul
    goto repeat
)
start "" "{target_path}"
del "%~f0"
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat)
    # Lancer le .bat et quitter l'app (le .bat relancera l'exe)
    subprocess.Popen(['cmd', '/c', bat_path], creationflags=subprocess.CREATE_NO_WINDOW)

# ========= APP =========
class RadioApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"🎶 {APP_NAME} v{CURRENT_VERSION}")

        # VLC
        instance = vlc.Instance("--no-video")
        self.player = instance.media_player_new()
        media = instance.media_new(STREAM_URL)
        self.player.set_media(media)

        # Discord RPC
        self.rpc = None
        try:
            self.rpc = Presence(DISCORD_CLIENT_ID)
            self.rpc.connect()
        except Exception as e:
            print("[!] Discord RPC indisponible:", e)
        self.start_ts = int(time.time())

        # UI
        self.label = QLabel("⏸️ Radio arrêtée")
        self.btn   = QPushButton("▶️ Lecture")
        self.btn.clicked.connect(self.toggle_play)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.player.audio_set_volume(80)

        self.update_btn = QPushButton("🔄 Vérifier les mises à jour")
        self.update_btn.clicked.connect(self.on_check_update_clicked)

        lay = QVBoxLayout()
        lay.addWidget(self.label)
        lay.addWidget(self.btn)
        lay.addWidget(QLabel("🔊 Volume"))
        lay.addWidget(self.volume_slider)
        lay.addWidget(self.update_btn)
        self.setLayout(lay)

        # Vérif maj silencieuse au démarrage (si exe)
        if is_frozen_exe():
            threading.Thread(target=self.silent_update_check, daemon=True).start()

        # Infos Now Playing
        threading.Thread(target=self.update_info_loop, daemon=True).start()

    # ----- lecture -----
    def toggle_play(self):
        if self.player.is_playing():
            self.player.stop()
            self.label.setText("⏸️ Radio arrêtée")
            self.btn.setText("▶️ Lecture")
        else:
            self.player.play()
            self.label.setText("🎵 Lecture en cours…")
            self.btn.setText("⏹️ Stop")

    def set_volume(self, v):
        self.player.audio_set_volume(int(v))

    # ----- updates -----
    def silent_update_check(self):
        info = get_latest_release()
        if info:
            latest, url = info
            # On propose tout de même (silencieux = sans bouton dédié)
            self.ask_and_update(latest, url)

    def on_check_update_clicked(self):
        info = get_latest_release()
        if not info:
            QMessageBox.information(self, "Mises à jour", "✅ Aucune mise à jour disponible.")
            return
        latest, url = info
        self.ask_and_update(latest, url)

    def ask_and_update(self, latest, url):
        if not is_frozen_exe():
            QMessageBox.information(
                self, "Mise à jour disponible",
                f"Version {latest} disponible.\n\n"
                f"Tu es en mode développement (script). Compile l'exe pour profiter de la mise à jour auto."
            )
            return
        res = QMessageBox.question(
            self,
            "Mise à jour disponible",
            f"🚀 Nouvelle version {latest} disponible.\n\nSouhaites-tu l’installer maintenant ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.perform_update(url)

    def perform_update(self, url):
        try:
            tmp_new = temp_path(f"{APP_NAME}_new.exe")
            self.update_btn.setEnabled(False)
            self.update_btn.setText("Téléchargement…")
            QApplication.processEvents()

            download_file(url, tmp_new)

            target = this_exe_path()
            self.update_btn.setText("Installation…")
            QApplication.processEvents()

            # Prépare le batch qui remplacera l'exe (après fermeture)
            write_updater_and_run(tmp_new, target)

            # Fermer proprement l'app pour libérer l'exe
            try:
                if self.rpc:
                    self.rpc.clear(); self.rpc.close()
            except Exception:
                pass
            try:
                if self.player: self.player.stop()
            except Exception:
                pass

            QApplication.quit()  # le .bat prendra le relais
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de la mise à jour : {e}")
        finally:
            self.update_btn.setEnabled(True)
            self.update_btn.setText("🔄 Vérifier les mises à jour")

    # ----- now playing / RPC -----
    def update_info_loop(self):
        while True:
            try:
                data = requests.get(API_URL, timeout=6).json()
                np = data.get("now_playing", {})
                song = np.get("song", {})
                title = song.get("title", "Inconnu")
                artist = song.get("artist", "")
                listeners = (data.get("listeners") or {}).get("total", 0)
                live = (data.get("live") or {}).get("is_live", False)

                self.label.setText(f"🎶 {title} — {artist} | 👥 {listeners} auditeurs")

                if self.rpc:
                    large_image = choose_image(title, live)
                    try:
                        self.rpc.update(
                            details=f"{title} — {artist}",
                            state=f"👥 {listeners} auditeurs",
                            start=int(time.time()),
                            large_image=large_image,
                            large_text=APP_NAME
                        )
                    except Exception as e:
                        print("[RPC] erreur:", e)
            except Exception as e:
                print("[NowPlaying] erreur:", e)

            time.sleep(12)

# ========= MAIN =========
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = RadioApp()
    w.show()
    sys.exit(app.exec())
