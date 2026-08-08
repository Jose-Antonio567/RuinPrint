from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ImageView(QFrame):
    """A responsive, aspect-ratio-preserving display for Pillow images or pixmaps."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("imageView")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        layout.addWidget(title_label)

        self.image_label = QLabel("Nenhuma imagem carregada")
        self.image_label.setObjectName("imagePlaceholder")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(1, 1)
        layout.addWidget(self.image_label, 1)

        self._source_pixmap: QPixmap | None = None

    def set_image(self, image: Image.Image | QPixmap) -> None:
        """Set an image without changing the source image's dimensions."""
        if isinstance(image, QPixmap):
            self._source_pixmap = image
        else:
            self._source_pixmap = self._pillow_to_pixmap(image)

        self.image_label.setText("")
        self._update_display_pixmap()

    def clear_image(self) -> None:
        """Restore the empty-state message."""
        self._source_pixmap = None
        self.image_label.clear()
        self.image_label.setText("Nenhuma imagem carregada")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_display_pixmap()

    def _update_display_pixmap(self) -> None:
        if self._source_pixmap is None or self.image_label.size().isEmpty():
            return

        scaled_pixmap = self._source_pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled_pixmap)

    @staticmethod
    def _pillow_to_pixmap(image: Image.Image) -> QPixmap:
        rgba_image = image.convert("RGBA")
        qimage = QImage(
            rgba_image.tobytes(),
            rgba_image.width,
            rgba_image.height,
            QImage.Format.Format_RGBA8888,
        )
        return QPixmap.fromImage(qimage)
