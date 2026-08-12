"""Zoomable, pannable image viewer used by the editor."""

from PIL import Image
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGraphicsPixmapItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout,
)


class ImageView(QFrame):
    """Non-destructive QGraphicsView image presentation with zoom and pan."""

    view_changed = Signal()
    fileDropped = Signal(str)
    filesDropped = Signal(object)

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("imageView")
        self.setAcceptDrops(True)
        self._zoom = 1.0
        self._panning = False
        self._pan_button = Qt.MouseButton.NoButton
        self._pan_position = None
        self._space_pressed = False
        self._source_pixmap: QPixmap | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        layout.addWidget(title_label)
        self.scene = QGraphicsScene(self)
        self.item = QGraphicsPixmapItem()
        self.scene.addItem(self.item)
        self.empty_item = QGraphicsTextItem("Nenhuma imagem carregada")
        self.empty_item.setDefaultTextColor(Qt.GlobalColor.gray)
        self.scene.addItem(self.empty_item)
        self.view = QGraphicsView(self.scene)
        self.view.setObjectName("graphicsImageView")
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setBackgroundBrush(Qt.GlobalColor.black)
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.view.setAcceptDrops(True)
        self.view.installEventFilter(self)
        self.view.viewport().setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.view.viewport().setAcceptDrops(True)
        self.view.viewport().installEventFilter(self)
        layout.addWidget(self.view, 1)
        bar = QHBoxLayout()
        fit = QPushButton("Fit")
        actual = QPushButton("100%")
        fit.clicked.connect(self.fit_to_view)
        actual.clicked.connect(self.actual_size)
        self.zoom_label = QLabel("Fit")
        bar.addWidget(fit); bar.addWidget(actual); bar.addStretch(); bar.addWidget(self.zoom_label)
        layout.addLayout(bar)

    def set_image(self, image: Image.Image | QPixmap, *, reset_view: bool = False) -> None:
        pixmap = image if isinstance(image, QPixmap) else self._pillow_to_pixmap(image)
        had_image = self._source_pixmap is not None
        self._source_pixmap = pixmap
        self.item.setPixmap(pixmap)
        self.scene.setSceneRect(self.item.boundingRect())
        self.empty_item.hide()
        if reset_view or not had_image:
            self.fit_to_view()

    def clear_image(self) -> None:
        self._source_pixmap = None
        self.item.setPixmap(QPixmap())
        self.empty_item.show()
        self._position_empty_message()

    def fit_to_view(self) -> None:
        if self._source_pixmap is None:
            return
        self.view.resetTransform()
        self.view.fitInView(self.item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.view.transform().m11()
        self._update_label(); self.view_changed.emit()

    def actual_size(self) -> None:
        if self._source_pixmap is None:
            return
        self.view.resetTransform(); self._zoom = 1.0
        self._update_label(); self.view_changed.emit()

    def zoom_by(self, factor: float) -> None:
        if self._source_pixmap is None:
            return
        target = max(0.10, min(16.0, self._zoom * factor))
        self.view.scale(target / self._zoom, target / self._zoom)
        self._zoom = target; self._update_label(); self.view_changed.emit()

    def view_state(self) -> tuple[float, float, float]:
        rect = self.scene.sceneRect()
        center = self.view.mapToScene(self.view.viewport().rect().center())
        return self._zoom, (center.x() - rect.left()) / max(rect.width(), 1), (center.y() - rect.top()) / max(rect.height(), 1)

    def set_view_state(self, state: tuple[float, float, float]) -> None:
        if self._source_pixmap is None:
            return
        zoom, x, y = state
        self.view.resetTransform(); self.view.scale(zoom, zoom); self._zoom = zoom
        rect = self.scene.sceneRect()
        self.view.centerOn(rect.left() + rect.width() * x, rect.top() + rect.height() * y)
        self._update_label()

    def eventFilter(self, watched, event):
        if watched is self.view:
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Space:
                if not event.isAutoRepeat():
                    self._space_pressed = True
                    if not self._panning:
                        self.view.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
                event.accept()
                return True
            if event.type() == QEvent.Type.KeyRelease and event.key() == Qt.Key.Key_Space:
                if not event.isAutoRepeat():
                    self._space_pressed = False
                    if not self._panning:
                        self.view.viewport().unsetCursor()
                event.accept()
                return True
            if event.type() == QEvent.Type.FocusOut:
                self._space_pressed = False
                if not self._panning:
                    self.view.viewport().unsetCursor()

        if watched is self.view.viewport():
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                if self._drop_path(event.mimeData().urls()):
                    self.setProperty("dropActive", True); self.style().unpolish(self); self.style().polish(self)
                    event.acceptProposedAction(); return True
            if event.type() == QEvent.Type.DragLeave:
                self.setProperty("dropActive", False); self.style().unpolish(self); self.style().polish(self)
                return False
            if event.type() == QEvent.Type.Drop:
                paths = self._drop_paths(event.mimeData().urls())
                self.setProperty("dropActive", False); self.style().unpolish(self); self.style().polish(self)
                if paths:
                    self.filesDropped.emit(paths); event.acceptProposedAction(); return True
            if event.type() == QEvent.Type.Wheel and self._source_pixmap is not None:
                self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1 / 1.15); return True
            if event.type() == QEvent.Type.MouseButtonPress:
                self.view.setFocus(Qt.FocusReason.MouseFocusReason)
                should_pan = (
                    event.button() == Qt.MouseButton.MiddleButton
                    or (
                        event.button() == Qt.MouseButton.LeftButton
                        and self._space_pressed
                    )
                )
                if should_pan:
                    self._panning = True
                    self._pan_button = event.button()
                    self._pan_position = event.position().toPoint()
                    self.view.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                    event.accept()
                    return True
            if event.type() == QEvent.Type.MouseMove and self._panning:
                position = event.position().toPoint()
                delta = position - self._pan_position
                self.view.horizontalScrollBar().setValue(
                    self.view.horizontalScrollBar().value() - delta.x()
                )
                self.view.verticalScrollBar().setValue(
                    self.view.verticalScrollBar().value() - delta.y()
                )
                self._pan_position = position
                event.accept()
                return True
            if (
                event.type() == QEvent.Type.MouseButtonRelease
                and self._panning
                and event.button() == self._pan_button
            ):
                self._panning = False
                self._pan_button = Qt.MouseButton.NoButton
                self._pan_position = None
                if self._space_pressed:
                    self.view.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
                else:
                    self.view.viewport().unsetCursor()
                self.view_changed.emit()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_empty_message()

    def _position_empty_message(self) -> None:
        point = self.view.mapToScene(self.view.viewport().rect().center())
        bounds = self.empty_item.boundingRect()
        self.empty_item.setPos(point.x() - bounds.width() / 2, point.y() - bounds.height() / 2)

    @staticmethod
    def _drop_path(urls) -> str | None:
        paths = ImageView._drop_paths(urls)
        return paths[0] if paths else None

    @staticmethod
    def _drop_paths(urls) -> list[str]:
        paths = []
        for url in urls:
            path = url.toLocalFile() if url.isLocalFile() else ""
            if path and path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                paths.append(path)
        return paths

    def _update_label(self) -> None:
        self.zoom_label.setText(f"{round(self._zoom * 100)}%")

    @staticmethod
    def _pillow_to_pixmap(image: Image.Image) -> QPixmap:
        rgba = image.convert("RGBA")
        return QPixmap.fromImage(QImage(rgba.tobytes(), rgba.width, rgba.height, QImage.Format.Format_RGBA8888))
