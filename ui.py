# ui.py — thèmes clair/sombre + pochette + prochain titre + badge auditeurs + multi-stations + RPC

import requests
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QSlider, QComboBox,
    QVBoxLayout, QHBoxLayout, QFrame, QMessageBox
)

import config, utils
from player import RadioPlayer
from rpc import DiscordRPCManager
from updater import UpdateChecker, UpdateDownloader


# -------------------- THEMES --------------------
APP_QSS_DARK = """
* { font-family: Segoe UI, Roboto, Arial; }
QMainWindow { background: #0f1216; }
QFrame#card { background: #171b22; border: 1px solid #222832; border-radius: 14px; }
QLabel#title { color: #e5f0ff; font-size: 18px; font-weight: 600; }
QLabel#now { color: #d6e2f2; font-size: 14px; }
QLabel#next { color: #8ea3bd; font-size: 12px; }
QLabel.small { color:#8e9aab; font-size:12px; }
QPushButton { background: #1f2530; color: #eaf2ff; border: 1px solid #2b3340; border-radius: 10px; padding: 8px 12px; }
QPushButton:hover { background: #2a3140; } QPushButton:pressed { background: #323a49; }
QPushButton#play { font-weight: 600; font-size: 14px; }
QSlider::groove:horizontal { height: 6px; background: #2a3140; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height:16px; margin: -6px 0; background: #6ca0ff; border-radius: 8px; border: 2px solid #cfe0ff; }
QLabel#badge { background:#243043; color:#eaf2ff; border-radius:10px; padding:3px 8px; border:1px solid #32405a; }
QLabel#cover { background:#0b0e13; border-radius:10px; }
"""

APP_QSS_LIGHT = """
* { font-family: Segoe UI, Roboto, Arial; }
QMainWindow { background: #f6f8fb; }
QFrame#card { background: #ffffff; border: 1px solid #e5e9f0; border-radius: 14px; }
QLabel#title { color: #111827; font-size: 18px; font-weight: 600; }
QLabel#now { color: #1f2937; font-size: 14px; }
QLabel#next { color: #6b7280; font-size: 12px; }
QLabel.small { color:#6b7280; font-size:12px; }
QPushButton { background: #f3f4f6; color: #111827; border: 1px solid #e5e7eb; border-radius: 10px; padding: 8px 12px; }
QPushButton:hover { background: #e5e7eb; } QPushButton:pressed { background: #d1d5db; }
QPushButton#play { font-weight: 600; font-size: 14px; }
QSlider::groove:horizontal { height: 6px; background: #e5e7eb; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height:16px; margin: -6px 0; background: #3b82f6; border-radius: 8px; border: 2px solid #bfdbfe; }
QLabel#badge { background:#eef2ff; color:#1f2937; border-radius:10px; padding:3px 8px; border:1px solid #dbeafe; }
QLabel#cover { background:#eef2ff; border-radius:10px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"🎵 {config.APP_NAME} v{config.CURRENT_VERSION}")
        # Icône de fenêtre si présent
        try:
            self.setWindowIcon(QIcon(str((utils.app_dir() / "assets" / "app.ico").resolve())))
        except Exception:
            pass

        self.setMinimumSize(520, 320)

        # Settings
        self.settings_path = utils.app_dir() / config.SETTINGS_FILE
        self.settings = utils.load_json(self.settings_path, {
            "volume": 80, "autoplay": True, "station": None, "theme": "dark"
        })

        # Stations (depuis GitHub) + sélection courante
        self.stations = utils.load_stations()
        names = utils.get_station_names(self.stations)
        default_name = self.settings.get("station") or self.stations.get("default") or (names[0] if names else "InsporaRadio")
        self.current_station_name = default_name
        self.current_station = utils.get_station(self.stations, self.current_station_name)

        # Player
        self.player = RadioPlayer()
        self.player.set_volume(self.settings["volume"])

        # RPC auto
        self.rpc = DiscordRPCManager(config.DISCORD_CLIENT_ID, config.APP_NAME)
        rpc_ok = self.rpc.connect()

        # Images map — spécifique à la station courante
        self.images_map = utils.load_images_map_for_station(self.current_station)

        # UI
        self.build_ui(names, default_name)
        self.apply_theme(self.settings.get("theme", "dark"))
        self.lbl_rpc.setText("RPC : connecté ✅" if rpc_ok else "RPC : inactif ❌")

        # Sync état VLC
        self.playing = False
        self.state_timer = QTimer(self)
        self.state_timer.setInterval(400)
        self.state_timer.timeout.connect(self.sync_player_state)
        self.state_timer.start()

        # NowPlaying + RPC refresh
        self.timer = QTimer(self); self.timer.setInterval(12_000)
        self.timer.timeout.connect(self.refresh_nowplaying)
        self.timer.start()
        self.refresh_nowplaying()

        # Autoplay
        if self.settings.get("autoplay", True):
            self.handle_play()

        # Update banner
        if utils.is_frozen_exe():
            QTimer.singleShot(1500, self.start_silent_update_check)

        # cache art
        self._last_art_url = None

    # ---------------- UI ----------------
    def build_ui(self, station_names, default_name):
        root = QWidget(); self.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(14,14,14,14); v.setSpacing(12)

        # Header
        header = QHBoxLayout(); header.setSpacing(10)
        t = QLabel("🎶 InsporaRadio"); t.setObjectName("title")
        header.addWidget(t)

        # Badge auditeurs
        self.lbl_badge = QLabel("👥 0"); self.lbl_badge.setObjectName("badge")
        header.addWidget(self.lbl_badge)

        header.addStretch(1)

        # Choix station
        header.addWidget(QLabel("Station :"))
        self.cb_station = QComboBox()
        self.cb_station.addItems(station_names)
        self.cb_station.setEnabled(len(station_names) > 1)
        if default_name in station_names:
            self.cb_station.setCurrentText(default_name)
        self.cb_station.currentTextChanged.connect(self.on_station_changed)
        header.addWidget(self.cb_station)

        # Toggle thème
        self.btn_theme = QPushButton("🌙")
        self.btn_theme.setToolTip("Basculer thème clair/sombre")
        self.btn_theme.clicked.connect(self.toggle_theme)
        header.addWidget(self.btn_theme)

        # Version
        self.lbl_ver = QLabel(f"v{config.CURRENT_VERSION}"); self.lbl_ver.setProperty("class","small")
        header.addWidget(self.lbl_ver)

        # Card principale
        card = QFrame(); card.setObjectName("card")
        cv = QVBoxLayout(card); cv.setContentsMargins(14,12,14,12); cv.setSpacing(8)

        # Ligne titre + pochette
        top = QHBoxLayout(); top.setSpacing(12)

        self.lbl_cover = QLabel(); self.lbl_cover.setObjectName("cover")
        self.lbl_cover.setFixedSize(112, 112); self.lbl_cover.setScaledContents(True)
        top.addWidget(self.lbl_cover)

        textcol = QVBoxLayout(); textcol.setSpacing(6)
        self.lbl_now = QLabel("⏸️ Radio arrêtée"); self.lbl_now.setObjectName("now")
        textcol.addWidget(self.lbl_now)
        self.lbl_next = QLabel("")  # prochain titre
        self.lbl_next.setObjectName("next")
        textcol.addWidget(self.lbl_next)
        top.addLayout(textcol)

        cv.addLayout(top)

        # Contrôles
        ctrl = QHBoxLayout(); ctrl.setSpacing(10)
        self.btn_play = QPushButton("▶️  Lecture"); self.btn_play.setObjectName("play")
        self.btn_play.clicked.connect(self.handle_play)
        ctrl.addWidget(self.btn_play)
        cv.addLayout(ctrl)

        # Statut RPC
        self.lbl_rpc = QLabel("RPC : …"); self.lbl_rpc.setProperty("class","small")
        cv.addWidget(self.lbl_rpc)

        # Volume
        vol = QHBoxLayout()
        vol.addWidget(QLabel("🔊"))
        self.slider = QSlider(Qt.Horizontal); self.slider.setRange(0,100); self.slider.setValue(self.settings["volume"])
        self.slider.valueChanged.connect(self.on_volume)
        vol.addWidget(self.slider)
        self.lbl_vol = QLabel(f"{self.settings['volume']}%"); self.lbl_vol.setProperty("class","small")
        vol.addWidget(self.lbl_vol)
        cv.addLayout(vol)

        # Actions
        actions = QHBoxLayout()
        self.btn_reload = QPushButton("🖼️  Recharger images"); self.btn_reload.clicked.connect(self.reload_images_map)
        self.btn_update = QPushButton("🔄  Vérifier les mises à jour"); self.btn_update.clicked.connect(self.on_check_update_clicked)
        actions.addWidget(self.btn_reload); actions.addWidget(self.btn_update)

        v.addLayout(header); v.addWidget(card); v.addLayout(actions)

    # ---------------- Thème ----------------
    def apply_theme(self, theme: str):
        theme = (theme or "dark").lower()
        self.current_theme = theme
        self.setStyleSheet(APP_QSS_LIGHT if theme == "light" else APP_QSS_DARK)
        self.btn_theme.setText("☀️" if theme == "light" else "🌙")
        # Sauver
        self.settings["theme"] = theme
        utils.save_json(self.settings_path, self.settings)

    def toggle_theme(self):
        self.apply_theme("light" if self.current_theme == "dark" else "dark")

    # ---------------- Player ----------------
    def handle_play(self):
        s = str(self.player.state())
        if self.playing or s in ("State.Playing", "State.Opening", "State.Buffering"):
            self.player.stop_stream()
        else:
            self.player.start_stream(self.current_station["stream_url"])

    def sync_player_state(self):
        s = str(self.player.state())
        if s == "State.Playing":
            if not self.playing:
                self.playing = True
                self.btn_play.setText("⏹️  Stop")
        elif s in ("State.Stopped", "State.Ended", "State.NothingSpecial"):
            if self.playing:
                self.playing = False
                self.btn_play.setText("▶️  Lecture")
                self.lbl_now.setText("⏸️ Radio arrêtée")
        elif s in ("State.Opening", "State.Buffering"):
            self.btn_play.setText("⏳  Chargement…")
        elif s == "State.Error":
            # petit retry doux si erreur
            QTimer.singleShot(1200, lambda: self.player.start_stream(self.current_station["stream_url"]))

    def on_volume(self, v: int):
        self.player.set_volume(v); self.lbl_vol.setText(f"{v}%")
        self.settings["volume"] = int(v); utils.save_json(self.settings_path, self.settings)

    # ---------------- Stations ----------------
    def on_station_changed(self, name: str):
        self.current_station_name = name
        self.current_station = utils.get_station(self.stations, name)
        self.images_map = utils.load_images_map_for_station(self.current_station)
        self.settings["station"] = name
        utils.save_json(self.settings_path, self.settings)

        state = str(self.player.state())
        if self.playing or state in ("State.Playing", "State.Opening", "State.Buffering"):
            self.player.start_stream(self.current_station["stream_url"])
            self.lbl_now.setText("⏳ Changement de station…")
        else:
            self.lbl_now.setText("✅ Station prête. Appuie sur Lecture.")
        QTimer.singleShot(300, self.refresh_nowplaying)

    # ---------------- NowPlaying & RPC ----------------
    def _set_cover(self, url: str | None):
        if not url or url == self._last_art_url:
            return
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                pix = QPixmap()
                pix.loadFromData(r.content)
                self.lbl_cover.setPixmap(pix)
                self._last_art_url = url
        except Exception:
            pass

    def refresh_nowplaying(self):
        try:
            api_url = self.current_station.get("nowplaying_url", config.API_URL)
            data = requests.get(api_url, timeout=5).json()

            np = data.get("now_playing", {}) or {}
            song = np.get("song", {}) or {}
            title = song.get("title", "Inconnu")
            artist = song.get("artist", "")
            art_url = song.get("art")

            # prochain titre si dispo
            pn = data.get("playing_next", {}) or {}
            pn_song = pn.get("song", {}) or {}
            next_title = pn_song.get("title")
            next_artist = pn_song.get("artist")

            listeners = (data.get("listeners") or {}).get("total", 0)
            live = (data.get("live") or {}).get("is_live", False)

            # UI
            self.lbl_now.setText(f"🎼 {title} — {artist}")
            self.lbl_badge.setText(f"👥 {listeners}")
            if next_title:
                na = f" — {next_artist}" if next_artist else ""
                self.lbl_next.setText(f"🔜 À suivre : {next_title}{na}")
            else:
                self.lbl_next.setText("")

            self._set_cover(art_url)

            # RPC
            if not self.rpc.enabled():
                if self.rpc.connect():
                    self.lbl_rpc.setText("RPC : connecté ✅")
                else:
                    self.lbl_rpc.setText("RPC : inactif ❌")
            else:
                img = utils.choose_image(self.images_map, title, live)
                small = self.current_station.get("rpc_small_image")
                self.rpc.update(title, artist, listeners, img, small_image=small, small_text=self.current_station_name)

        except Exception as e:
            print("[NowPlaying]", e)

    def reload_images_map(self):
        self.images_map = utils.load_images_map_for_station(self.current_station)
        QMessageBox.information(self, "Images", f"Mappings rechargés pour « {self.current_station_name} » ✅")

    # ---------------- Updates ----------------
    def start_silent_update_check(self):
        self.chk = UpdateChecker()
        self.chk.found.connect(self.on_update_found_banner)
        self.chk.none.connect(lambda: self.lbl_ver.setText(f"v{config.CURRENT_VERSION}"))
        self.chk.fail.connect(lambda msg: print("[update fail]", msg))
        self.chk.start()

    @Slot(str, str)
    def on_update_found_banner(self, latest, url):
        self.lbl_ver.setText(f"v{config.CURRENT_VERSION} → dispo v{latest}")

    def on_check_update_clicked(self):
        self.btn_update.setEnabled(False); self.btn_update.setText("Recherche…")
        self.chk = UpdateChecker()
        self.chk.found.connect(self.ask_install_update)
        self.chk.none.connect(lambda: QMessageBox.information(self, "Mises à jour", "✅ Aucune mise à jour disponible."))
        self.chk.fail.connect(lambda msg: QMessageBox.warning(self, "Erreur", f"Vérification échouée : {msg}"))
        self.chk.finished.connect(lambda: (self.btn_update.setEnabled(True), self.btn_update.setText("🔄  Vérifier les mises à jour")))
        self.chk.start()

    @Slot(str, str)
    def ask_install_update(self, latest, url):
        if not utils.is_frozen_exe():
            QMessageBox.information(self, "Mise à jour", f"Nouvelle version {latest} dispo.\nCompile l’exe pour l’auto-update.")
            return
        res = QMessageBox.question(self, "Mise à jour",
                                   f"🚀 Version {latest} disponible.\nInstaller maintenant ?",
                                   QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            self.download_update(url)

    def download_update(self, url: str):
        dest = utils.temp_path(f"{config.APP_NAME}_new.exe")
        self.btn_update.setEnabled(False); self.btn_update.setText("Téléchargement… 0%")
        self.dl = UpdateDownloader(url, dest)
        self.dl.progress.connect(lambda p: self.btn_update.setText(f"Téléchargement… {p}%"))
        self.dl.done.connect(self.install_update)
        self.dl.fail.connect(lambda msg: (QMessageBox.critical(self, "Erreur", f"Téléchargement échoué : {msg}"),
                                          self.btn_update.setEnabled(True), self.btn_update.setText("🔄  Vérifier les mises à jour")))
        self.dl.start()

    @Slot(str)
    def install_update(self, new_exe_path: str):
        self.btn_update.setText("Installation…")
        try:
            import os
            utils.write_updater_and_run(new_exe_path, utils.this_exe_path(), os.getpid())
            self.safe_quit()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Installation échouée : {e}")
            self.btn_update.setEnabled(True); self.btn_update.setText("🔄  Vérifier les mises à jour")

    # ---------------- Quit ----------------
    def safe_quit(self):
        try:
            self.rpc.clear_close()
        except Exception:
            pass
        self.player.stop_stream()
        self.close()
