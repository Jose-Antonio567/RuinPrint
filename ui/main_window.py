from PIL import Image
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.image_loader import create_preview, load_image
from ui.image_view import ImageView


class MainWindow(QMainWindow):
    """Main application shell for the initial RuinPrint interface."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RuinPrint")
        self.resize(1200, 750)
        self.setMinimumSize(800, 500)

        self.current_image_path: str | None = None
        self.original_image: Image.Image | None = None
        self.preview_image: Image.Image | None = None
        self.current_result_preview: Image.Image | None = None

        self._build_interface()
        self._apply_theme()

    def _build_interface(self) -> None:
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(22, 22, 22, 22)
        main_layout.setSpacing(18)

        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(14, 12, 14, 12)
        top_bar_layout.setSpacing(10)

        self.import_button = QPushButton("Importar imagem")
        self.import_button.clicked.connect(self.import_image)
        top_bar_layout.addWidget(self.import_button)
        top_bar_layout.addWidget(QPushButton("Exportar PNG"))
        top_bar_layout.addWidget(QPushButton("Redefinir"))
        top_bar_layout.addStretch()

        image_area = QWidget()
        image_layout = QHBoxLayout(image_area)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(18)
        self.original_image_view = ImageView("Imagem original")
        self.result_image_view = ImageView("Resultado")
        image_layout.addWidget(self.original_image_view, 1)
        image_layout.addWidget(self.result_image_view, 1)

        main_layout.addWidget(top_bar)
        main_layout.addWidget(image_area, 1)
        self.setCentralWidget(central_widget)

    def import_image(self) -> None:
        """Choose an image and display independent previews of original and result."""
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not image_path:
            return

        try:
            original_image = load_image(image_path)
            preview_image = create_preview(original_image)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Erro ao carregar imagem",
                f"Não foi possível carregar a imagem selecionada.\n\n{error}",
            )
            return

        self.current_image_path = image_path
        self.original_image = original_image
        self.preview_image = preview_image
        self.current_result_preview = preview_image.copy()

        self.original_image_view.set_image(self.preview_image)
        self.result_image_view.set_image(self.current_result_preview)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #181818;
                color: #e7e7e7;
                font-family: Segoe UI, sans-serif;
                font-size: 13px;
            }
            #topBar {
                background: #222222;
                border: 1px solid #333333;
                border-radius: 6px;
            }
            QPushButton {
                background: #303030;
                border: 1px solid #484848;
                border-radius: 4px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background: #3a3a3a;
            }
            #imageView {
                background: #202020;
                border: 1px solid #363636;
                border-radius: 6px;
            }
            #panelTitle {
                font-size: 15px;
                font-weight: 600;
            }
            #imagePlaceholder {
                background: #191919;
                border: 1px dashed #454545;
                border-radius: 4px;
                color: #8d8d8d;
            }
            """
        )
