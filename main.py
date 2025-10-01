import sys
import utils

def main():
    # IMPORTANT : charger libVLC AVANT d'importer quelque module qui importe vlc
    utils.load_vlc_portable()

    from PySide6.QtWidgets import QApplication
    from ui import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
