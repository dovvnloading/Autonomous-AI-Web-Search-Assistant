# --- chorus.py ---
import sys
from PySide6.QtWidgets import QApplication

from uimain_window import MainWindow

def main():
    """
    Initializes and runs the Chorus.Ai application.
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()