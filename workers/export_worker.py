"""Thread-safe full-resolution PNG export worker."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from core.pipeline import ImagePipeline, PipelineSettings


class ExportWorker(QObject):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, image, settings: PipelineSettings, output_path: str, spatial_scale: float) -> None:
        super().__init__()
        self.image = image.copy()
        self.settings = settings
        self.output_path = output_path
        self.spatial_scale = spatial_scale

    @Slot()
    def run(self) -> None:
        try:
            result = ImagePipeline().process(self.image, self.settings, spatial_scale=self.spatial_scale, progress_callback=self.progress.emit)
            result.save(self.output_path, "PNG")
            self.progress.emit(100)
            self.finished.emit(self.output_path)
        except Exception as error:
            self.error.emit(str(error))
