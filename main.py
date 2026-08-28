import sys
from PyQt6.QtWidgets import QApplication

from main_window import MainWindow
from ui.theme import build_stylesheet

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(build_stylesheet())
    db_save_path = '/home/masoud/Desktop/projects/volleyball_analytics/db/annotations.db'
    window = MainWindow(db_path=db_save_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()