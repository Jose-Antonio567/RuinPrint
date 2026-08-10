from PIL import Image
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.image_loader import (
    SUPPORTED_IMAGE_EXTENSIONS,
    create_preview,
    load_image,
)
from core.pipeline import ImagePipeline
from ui.controls import DitherControls, InkControls, PaletteControls, ToneControls
from ui.image_view import ImageView


class MainWindow(QMainWindow):
    """Main application shell for the initial RuinPrint interface."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RuinPrint")
        self.resize(1200, 750)
        self.setMinimumSize(800, 500)
        self.setAcceptDrops(True)

        self.current_image_path: str | None = None
        self.original_image: Image.Image | None = None
        self.preview_image: Image.Image | None = None
        self.current_result_preview: Image.Image | None = None
        self.pipeline = ImagePipeline()
        self._is_resetting_controls = False
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(80)
        self._update_timer.timeout.connect(self.update_result_preview)

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
        self.reset_button = QPushButton("Redefinir")
        self.reset_button.clicked.connect(self.reset_tone_controls)
        top_bar_layout.addWidget(self.reset_button)
        top_bar_layout.addStretch()

        image_area = QWidget()
        image_layout = QHBoxLayout(image_area)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(18)
        self.original_image_view = ImageView("Imagem original")
        self.result_image_view = ImageView("Resultado")
        image_layout.addWidget(self.original_image_view, 1)
        image_layout.addWidget(self.result_image_view, 1)

        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        self.tone_controls = ToneControls()
        self.tone_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.tone_controls)
        self.palette_controls = PaletteControls()
        self.palette_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.palette_controls)
        self.dither_controls = DitherControls()
        self.dither_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.dither_controls)
        self.ink_controls = InkControls()
        self.ink_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.ink_controls)
        settings_layout.addStretch()

        settings_scroll_area = QScrollArea()
        settings_scroll_area.setObjectName("settingsPanel")
        settings_scroll_area.setWidgetResizable(True)
        settings_scroll_area.setFixedWidth(280)
        settings_scroll_area.setWidget(settings_content)

        self.workspace = QWidget()
        self.workspace.setObjectName("workspace")
        self.workspace.setProperty("dropActive", False)
        workspace_layout = QHBoxLayout(self.workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(18)
        workspace_layout.addWidget(image_area, 1)
        workspace_layout.addWidget(settings_scroll_area)

        main_layout.addWidget(top_bar)
        main_layout.addWidget(self.workspace, 1)
        self.setCentralWidget(central_widget)

    def import_image(self) -> None:
        """Choose an image and send it through the shared loading flow."""
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not image_path:
            return

        self.load_image_from_path(image_path)

    def load_image_from_path(self, image_path: str) -> None:
        """Load an image and create all display state used by the application."""

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
        self.update_result_preview()

    def update_result_preview(self) -> None:
        """Rebuild the result from the untouched original preview and current controls."""
        if self.preview_image is None:
            return

        self.current_result_preview = self.pipeline.process_preview(
            self.preview_image,
            self.tone_controls.parameters(),
            self.palette_controls.parameters(),
            self.dither_controls.parameters(),
            self.dither_controls.destruction_parameters(),
            self.ink_controls.parameters(),
        )
        self.result_image_view.set_image(self.current_result_preview)

    def schedule_result_update(self) -> None:
        """Debounce preview recalculation while controls are being adjusted."""
        if not self._is_resetting_controls:
            self._update_timer.start()

    def reset_tone_controls(self) -> None:
        """Restore default controls while keeping the image and update once."""
        self._is_resetting_controls = True
        self.tone_controls.reset()
        self.palette_controls.reset()
        self.dither_controls.reset()
        self.ink_controls.reset()
        self._is_resetting_controls = False
        self._update_timer.stop()
        self.update_result_preview()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drags that contain at least one supported local image file."""
        if self._first_supported_drop_path(event.mimeData().urls()) is None:
            event.ignore()
            return

        self._set_drop_feedback(True)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Remove the drop-target feedback when the drag leaves the window."""
        self._set_drop_feedback(False)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        """Load the first valid local image from a drop operation."""
        image_path = self._first_supported_drop_path(event.mimeData().urls())
        self._set_drop_feedback(False)
        if image_path is None:
            event.ignore()
            return

        self.load_image_from_path(image_path)
        event.acceptProposedAction()

    @staticmethod
    def _first_supported_drop_path(urls: list[QUrl]) -> str | None:
        for url in urls:
            if not url.isLocalFile():
                continue
            image_path = url.toLocalFile()
            if image_path and image_path.lower().endswith(tuple(SUPPORTED_IMAGE_EXTENSIONS)):
                return image_path
        return None

    def _set_drop_feedback(self, is_active: bool) -> None:
        self.workspace.setProperty("dropActive", is_active)
        self.workspace.style().unpolish(self.workspace)
        self.workspace.style().polish(self.workspace)

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
            #settingsPanel, #settingsPanel > QWidget {
                background: #202020;
                border: 1px solid #363636;
                border-radius: 6px;
            }
            #toneControls, #paletteControls, #ditherControls, #inkControls {
                border: 1px solid #424242;
                border-radius: 5px;
                margin-top: 8px;
                padding: 8px;
            }
            #toneControls::title, #paletteControls::title, #ditherControls::title, #inkControls::title {
                subcontrol-origin: margin;
                left: 9px;
                padding: 0 4px;
                color: #cfcfcf;
                font-weight: 600;
            }
            #controlValue {
                color: #bcbcbc;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #3a3a3a;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 12px;
                margin: -4px 0;
                background: #bbbbbb;
                border-radius: 6px;
            }
            QComboBox {
                background: #303030;
                border: 1px solid #484848;
                border-radius: 4px;
                padding: 5px 8px;
            }
            #workspace[dropActive="true"] {
                border: 2px dashed #9d8a63;
                border-radius: 6px;
            }
            """
        )
