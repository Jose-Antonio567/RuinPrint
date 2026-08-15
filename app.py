import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from core.app_paths import AppDataError
from ui.main_window import MainWindow


def main() -> int:
    """Create and run the RuinPrint application."""
    application = QApplication(sys.argv)
    try:
        window = MainWindow()
    except AppDataError as error:
        QMessageBox.critical(None, "Pasta de dados indisponível", str(error))
        return 1
    window.show()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
