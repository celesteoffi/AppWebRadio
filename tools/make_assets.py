# tools/make_assets.py
from pathlib import Path
import sys
from PIL import Image

# QtSvg (pas besoin de fenêtre)
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QGuiApplication

ROOT = Path(__file__).resolve().parents[1]
SVG  = ROOT / "assets" / "logo.svg"
PNG  = ROOT / "assets" / "logo_512.png"
ICO  = ROOT / "assets" / "app.ico"

def svg_to_png(svg_path: Path, png_path: Path, size: int = 512):
    app = QGuiApplication(sys.argv)  # application “headless”
    renderer = QSvgRenderer(str(svg_path))
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(0)  # transparent
    p = QPainter(img)
    renderer.render(p)
    p.end()
    img.save(str(png_path))
    app.quit()

def png_to_ico(png_path: Path, ico_path: Path):
    im = Image.open(png_path).convert("RGBA")
    im.save(ico_path, sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])

if __name__ == "__main__":
    SVG.parent.mkdir(parents=True, exist_ok=True)
    svg_to_png(SVG, PNG, 512)
    png_to_ico(PNG, ICO)
    print("OK →", PNG, "et", ICO)
