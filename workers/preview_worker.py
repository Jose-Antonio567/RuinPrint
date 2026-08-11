"""Background preview renderer that never touches Qt widgets."""

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from core.pipeline import ImagePipeline, PipelineSettings


class PreviewSignals(QObject):
    finished = Signal(int, object)
    error = Signal(int, str)


class PreviewWorker(QRunnable):
    def __init__(self, generation: int, image, settings: PipelineSettings) -> None:
        super().__init__()
        self.generation, self.image, self.settings = generation, image.copy(), settings
        self.signals = PreviewSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.generation, ImagePipeline().process(self.image, self.settings))
        except Exception as error:
            self.signals.error.emit(self.generation, str(error))
