import os, sys, json, requests, subprocess
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import config

# ---------- chemins ----------
def app_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys.executable).parent
    return Path(__file__).parent

def is_frozen_exe() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

def this_exe_path() -> str:
    return sys.executable if is_frozen_exe() else os.path.abspath(__file__)

def temp_path(name: str) -> str:
    return os.path.join(os.environ.get("TEMP", str(app_dir())), name)

# ---------- JSON helpers ----------
def load_json(path: Path, default: dict) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def save_json(path: Path, data: dict):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

# ---------- fetch helper ----------
def fetch_json(url: str, timeout: int = 6):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        print(f"[!] fetch_json status {r.status_code} for {url}")
    except Exception as e:
        print(f"[!] fetch_json error for {url}:", e)
    return None

# ---------- VLC portable ----------
def load_vlc_portable():
    if sys.platform.startswith("win"):
        vlc_path = app_dir() / "vlc"
        if vlc_path.exists():
            os.add_dll_directory(str(vlc_path))

# ---------- images map (globale) ----------
def normalize_image_map(m: dict) -> dict:
    if not isinstance(m, dict):
        m = {}
    return {
        "default": m.get("default", "logo_default"),
        "live": m.get("live", "logo_live"),
        "titles": m.get("titles", {}) if isinstance(m.get("titles", {}), dict) else {}
    }

def merge_image_maps(base: dict, override: dict) -> dict:
    base = normalize_image_map(base)
    override = normalize_image_map(override)
    return {
        "default": override.get("default", base["default"]),
        "live": override.get("live", base["live"]),
        "titles": {**base["titles"], **override["titles"]},
    }

def load_images_map() -> dict:
    data = fetch_json(config.MAP_URL) or {}
    return normalize_image_map(data)

def choose_image(images_map: dict, title: str, live: bool) -> str:
    if live:
        return images_map.get("live", "logo_live")
    for song_title, img in images_map.get("titles", {}).items():
        if song_title.lower() in title.lower():
            return img
    return images_map.get("default", "logo_default")

# ---------- stations (multi-radios) ----------
def load_stations() -> Dict[str, Any]:
    data = fetch_json(config.STATIONS_URL)
    if data and isinstance(data.get("stations"), dict):
        return data
    # Fallback local minimal
    return {
        "default": "InsporaRadio",
        "stations": {
            "InsporaRadio": {
                "stream_url": config.STREAM_URL,
                "nowplaying_url": config.API_URL
            }
        }
    }

def get_station_names(stations: Dict[str, Any]):
    return list(stations.get("stations", {}).keys())

def get_station(stations: Dict[str, Any], name: str) -> Dict[str, str]:
    return stations["stations"].get(name, next(iter(stations["stations"].values())))

def load_images_map_for_station(station: Dict[str, Any]) -> dict:
    """Retourne la map d'images propre à la station, fusionnée avec la map globale."""
    global_map = load_images_map()
    # inline ?
    inline = station.get("images_map")
    if isinstance(inline, dict):
        return merge_image_maps(global_map, inline)
    # url dédiée ?
    url = station.get("images_map_url")
    if isinstance(url, str) and url.startswith("http"):
        remote = fetch_json(url) or {}
        return merge_image_maps(global_map, remote)
    # fallback global
    return global_map

# ---------- GitHub Releases ----------
def get_latest_release(repo: str, current_version: str) -> Optional[Tuple[str, str]]:
    data = fetch_json(f"https://api.github.com/repos/{repo}/releases/latest", timeout=8) or {}
    try:
        tag = (data.get("tag_name") or "").lstrip("v")
        asset_url = None
        for asset in data.get("assets", []):
            if asset.get("name", "").lower().endswith(".exe"):
                asset_url = asset.get("browser_download_url")
                break
        if tag and asset_url and tag != current_version:
            return tag, asset_url
    except Exception as e:
        print("[get_latest_release]", e)
    return None

def download_file(url: str, dest: str):
    with requests.get(url, stream=True, timeout=20) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024 * 64):
                if chunk:
                    f.write(chunk)
    return dest

def write_updater_and_run(new_exe_path: str, target_path: str):
    bat_path = temp_path("updater_inspora.bat")
    bat = f"""@echo off
setlocal
ping 127.0.0.1 -n 2 > nul
:loop
move /Y "{new_exe_path}" "{target_path}" > nul 2>&1
if %errorlevel% neq 0 (
  timeout /t 1 /nobreak > nul
  goto loop
)
start "" "{target_path}"
del "%~f0"
"""
    Path(bat_path).write_text(bat, encoding="utf-8")
    subprocess.Popen(['cmd', '/c', bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
