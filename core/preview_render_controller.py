"""Latest-render-wins preview coordinator."""

from PySide6.QtCore import QObject, QThreadPool, Signal

from workers.preview_worker import PreviewWorker


class PreviewRenderController(QObject):
    result_ready = Signal(int, object)
    status_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.pool = QThreadPool(self); self.pool.setMaxThreadCount(1)
        self.generation = 0; self.busy = False; self.pending = None

    def request(self, image, settings) -> None:
        self.generation += 1
        request = (self.generation, image.copy(), settings)
        if self.busy:
            self.pending = request; self.status_changed.emit("Preview: atualização pendente...")
        else:
            self._start(request)

    def invalidate(self) -> None:
        self.generation += 1; self.pending = None

    def _start(self, request) -> None:
        generation, image, settings = request; self.busy = True; self.status_changed.emit("Preview: processando...")
        worker = PreviewWorker(generation, image, settings)
        worker.signals.finished.connect(self._finished); worker.signals.error.connect(self._error)
        self.pool.start(worker)

    def _finished(self, generation: int, result) -> None:
        self.busy = False
        if generation == self.generation: self.result_ready.emit(generation, result)
        self._next()

    def _error(self, generation: int, message: str) -> None:
        self.busy = False; self._next()

    def _next(self) -> None:
        if self.pending:
            request, self.pending = self.pending, None; self._start(request)
        else: self.status_changed.emit("Preview: pronto")
