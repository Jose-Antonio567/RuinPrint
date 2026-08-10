from dataclasses import asdict
import json
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSettings, QThread, QTimer, QUrl, Qt
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QGroupBox,
    QComboBox,
    QCheckBox,
)

from core.image_loader import (
    SUPPORTED_IMAGE_EXTENSIONS,
    create_preview,
    load_image,
)
from core.pipeline import ImagePipeline
from core.pipeline import PipelineSettings
from core.preset_manager import PresetManager
from core.edit_history import EditHistory
from workers.export_worker import ExportWorker
from ui.controls import (
    BlackConsumptionControls,
    DegradationControls,
    DitherControls,
    EngravingControls,
    FocusControls,
    InkControls,
    LensControls,
    PaletteControls,
    ToneControls,
)
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
        self.preset_manager = PresetManager()
        self.settings = QSettings("RuinPrint", "RuinPrint")
        self._applying_preset = False
        self._syncing_views = False
        self.history = EditHistory()
        self._history_suspended = False
        self._before_active = False
        self._export_thread: QThread | None = None
        self._is_resetting_controls = False
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(80)
        self._update_timer.timeout.connect(self.update_result_preview)

        self._build_interface()
        self._apply_theme()
        self._restore_window_state()

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
        self.undo_button = QPushButton("Desfazer")
        self.redo_button = QPushButton("Refazer")
        self.undo_button.clicked.connect(self.undo); self.redo_button.clicked.connect(self.redo)
        top_bar_layout.addWidget(self.undo_button); top_bar_layout.addWidget(self.redo_button)
        self.export_button = QPushButton("Exportar PNG")
        self.export_button.clicked.connect(self.export_png)
        top_bar_layout.addWidget(self.export_button)
        self.reset_button = QPushButton("Redefinir")
        self.reset_button.clicked.connect(self.reset_tone_controls)
        top_bar_layout.addWidget(self.reset_button)
        self.before_button = QPushButton("Antes (B)")
        self.before_button.pressed.connect(self.show_before); self.before_button.released.connect(self.show_after)
        top_bar_layout.addWidget(self.before_button)
        self.sync_views_checkbox = QCheckBox("Sincronizar visualização")
        self.sync_views_checkbox.setChecked(True)
        top_bar_layout.addWidget(self.sync_views_checkbox)
        top_bar_layout.addStretch()

        self.original_image_view = ImageView("Imagem original")
        self.result_image_view = ImageView("Resultado")
        self.original_image_view.setMinimumWidth(200)
        self.result_image_view.setMinimumWidth(200)
        self.original_image_view.view_changed.connect(lambda: self._sync_view(self.original_image_view, self.result_image_view))
        self.result_image_view.view_changed.connect(lambda: self._sync_view(self.result_image_view, self.original_image_view))
        self.original_image_view.fileDropped.connect(self.load_image_from_path)
        self.result_image_view.fileDropped.connect(self.load_image_from_path)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.fit_views)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=self.actual_views)
        QShortcut(QKeySequence("+"), self, activated=lambda: self.original_image_view.zoom_by(1.15))
        QShortcut(QKeySequence("-"), self, activated=lambda: self.original_image_view.zoom_by(1 / 1.15))
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.redo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.redo)
        QShortcut(QKeySequence("B"), self, activated=self.show_before)

        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        preset_box = QGroupBox("PRESET")
        preset_box.setObjectName("presetControls")
        preset_layout = QVBoxLayout(preset_box)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Personalizado")
        self._refresh_preset_combo()
        self.preset_combo.currentTextChanged.connect(self.load_selected_preset)
        preset_layout.addWidget(self.preset_combo)
        preset_buttons = QHBoxLayout()
        self.save_preset_button = QPushButton("Salvar como...")
        self.update_preset_button = QPushButton("Atualizar")
        self.rename_preset_button = QPushButton("Renomear")
        self.delete_preset_button = QPushButton("Excluir")
        for button in (self.save_preset_button, self.update_preset_button, self.rename_preset_button, self.delete_preset_button):
            preset_buttons.addWidget(button)
        preset_layout.addLayout(preset_buttons)
        self.save_preset_button.clicked.connect(self.save_preset_as)
        self.update_preset_button.clicked.connect(self.update_preset)
        self.rename_preset_button.clicked.connect(self.rename_preset)
        self.delete_preset_button.clicked.connect(self.delete_preset)
        settings_layout.addWidget(preset_box)
        copy_button = QPushButton("Copiar config."); paste_button = QPushButton("Colar config.")
        copy_button.clicked.connect(self.copy_settings); paste_button.clicked.connect(self.paste_settings)
        preset_layout.addWidget(copy_button); preset_layout.addWidget(paste_button)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_settings)
        QShortcut(QKeySequence("Ctrl+Shift+V"), self, activated=self.paste_settings)
        self.tone_controls = ToneControls()
        self.tone_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.tone_controls)
        self.palette_controls = PaletteControls()
        self.palette_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.palette_controls)
        self.dither_controls = DitherControls()
        self.dither_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.dither_controls)
        self.engraving_controls = EngravingControls()
        self.engraving_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.engraving_controls)
        self.black_consumption_controls = BlackConsumptionControls()
        self.black_consumption_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.black_consumption_controls)
        self.ink_controls = InkControls()
        self.ink_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.ink_controls)
        self.focus_controls = FocusControls()
        self.focus_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.focus_controls)
        self.lens_controls = LensControls()
        self.lens_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.lens_controls)
        self.degradation_controls = DegradationControls()
        self.degradation_controls.parameters_changed.connect(self.schedule_result_update)
        settings_layout.addWidget(self.degradation_controls)
        settings_layout.addStretch()

        settings_scroll_area = QScrollArea()
        settings_scroll_area.setObjectName("settingsPanel")
        settings_scroll_area.setWidgetResizable(True)
        settings_scroll_area.setMinimumWidth(280)
        settings_scroll_area.setWidget(settings_content)

        self.workspace = QSplitter()
        self.workspace.setObjectName("workspace")
        self.workspace.setOrientation(Qt.Orientation.Horizontal)
        self.workspace.setProperty("dropActive", False)
        self.workspace.addWidget(self.original_image_view)
        self.workspace.addWidget(self.result_image_view)
        self.workspace.addWidget(settings_scroll_area)
        self.workspace.setStretchFactor(0, 35)
        self.workspace.setStretchFactor(1, 35)
        self.workspace.setStretchFactor(2, 30)
        self.workspace.setSizes((350, 350, 300))

        main_layout.addWidget(top_bar)
        main_layout.addWidget(self.workspace, 1)
        self.export_progress = QProgressBar()
        self.export_progress.setRange(0, 100)
        self.export_progress.setTextVisible(True)
        self.export_progress.setFormat("Exportando... %p%")
        self.export_progress.hide()
        main_layout.addWidget(self.export_progress)
        self.setCentralWidget(central_widget)
        self._last_settings = asdict(self.current_pipeline_settings())
        for slider in self.findChildren(QSlider):
            slider.sliderPressed.connect(lambda: setattr(self, "_slider_before", asdict(self.current_pipeline_settings())))
            slider.sliderReleased.connect(self._commit_slider_edit)
        self._update_history_buttons()

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
        self.history.clear()
        self._last_settings = asdict(self.current_pipeline_settings())
        self._update_history_buttons()

        self.original_image_view.set_image(self.preview_image, reset_view=True)
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
            self.engraving_controls.parameters(),
            self.black_consumption_controls.parameters(),
            self.ink_controls.parameters(),
            self.focus_controls.parameters(),
            self.lens_controls.parameters(),
            self.degradation_controls.parameters(),
        )
        if not self._before_active:
            self.result_image_view.set_image(self.current_result_preview)

    def _sync_view(self, source: ImageView, target: ImageView) -> None:
        if not self.sync_views_checkbox.isChecked() or self._syncing_views:
            return
        self._syncing_views = True
        try:
            target.set_view_state(source.view_state())
        finally:
            self._syncing_views = False

    def fit_views(self) -> None:
        self.original_image_view.fit_to_view()
        if self.sync_views_checkbox.isChecked():
            self.result_image_view.fit_to_view()

    def actual_views(self) -> None:
        self.original_image_view.actual_size()
        if self.sync_views_checkbox.isChecked():
            self.result_image_view.actual_size()

    def current_pipeline_settings(self) -> PipelineSettings:
        """Capture all visible controls as one immutable processing snapshot."""
        return PipelineSettings(
            self.tone_controls.parameters(), self.palette_controls.parameters(),
            self.dither_controls.parameters(), self.dither_controls.destruction_parameters(),
            self.engraving_controls.parameters(), self.black_consumption_controls.parameters(),
            self.ink_controls.parameters(), self.focus_controls.parameters(),
            self.lens_controls.parameters(), self.degradation_controls.parameters(),
        )

    def _refresh_preset_combo(self, selected: str = "Personalizado") -> None:
        if not hasattr(self, "preset_combo"):
            return
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("Personalizado")
        self.preset_combo.addItems([f"Factory: {name}" for name in self.preset_manager.factory_presets])
        self.preset_combo.addItems(self.preset_manager.names())
        factory_label = f"Factory: {selected}"
        self.preset_combo.setCurrentText(factory_label if selected in self.preset_manager.factory_presets else (selected if selected in self.preset_manager.presets else "Personalizado"))
        self.preset_combo.blockSignals(False)

    def _preset_name(self) -> str | None:
        name = self.preset_combo.currentText()
        return None if name == "Personalizado" or name.startswith("Factory: ") else name

    def save_preset_as(self) -> None:
        name, accepted = QInputDialog.getText(self, "Salvar preset", "Nome do preset:")
        if not accepted:
            return
        try:
            name = name.strip()
            if name in self.preset_manager.presets and QMessageBox.question(self, "Sobrescrever preset", "Já existe um preset com esse nome. Sobrescrever?") != QMessageBox.StandardButton.Yes:
                return
            self.preset_manager.save(name, asdict(self.current_pipeline_settings()))
            self._refresh_preset_combo(name)
        except ValueError as error:
            QMessageBox.warning(self, "Preset inválido", str(error))

    def update_preset(self) -> None:
        name = self._preset_name()
        if name is None:
            return
        if QMessageBox.question(self, "Atualizar preset", f"Atualizar '{name}' com os valores atuais?") == QMessageBox.StandardButton.Yes:
            self.preset_manager.save(name, asdict(self.current_pipeline_settings()))

    def rename_preset(self) -> None:
        name = self._preset_name()
        if name is None:
            return
        new_name, accepted = QInputDialog.getText(self, "Renomear preset", "Novo nome:", text=name)
        if accepted:
            try:
                self.preset_manager.rename(name, new_name)
                self._refresh_preset_combo(new_name.strip())
            except ValueError as error:
                QMessageBox.warning(self, "Preset inválido", str(error))

    def delete_preset(self) -> None:
        name = self._preset_name()
        if name and QMessageBox.question(self, "Excluir preset", f"Excluir '{name}'?") == QMessageBox.StandardButton.Yes:
            self.preset_manager.delete(name)
            self._refresh_preset_combo()

    def load_selected_preset(self, name: str) -> None:
        preset_name = name.removeprefix("Factory: ")
        factory = self.preset_manager.is_factory(preset_name)
        self.update_preset_button.setEnabled(not factory and name != "Personalizado")
        self.rename_preset_button.setEnabled(not factory and name != "Personalizado")
        self.delete_preset_button.setEnabled(not factory and name != "Personalizado")
        values = self.preset_manager.get(preset_name)
        if values is None:
            return
        self._applying_preset = True
        controls = self.findChildren(QSlider) + self.findChildren(QComboBox)
        for control in controls:
            control.blockSignals(True)
        try:
            self._apply_preset_values(values)
        finally:
            for control in controls:
                control.blockSignals(False)
            self._applying_preset = False
        self.update_result_preview()

    def _apply_preset_values(self, values: dict) -> None:
        groups = {
            "tone": (self.tone_controls, {"contrast": "contrast_slider", "black_crush": "black_crush_slider", "highlight_burn": "highlight_burn_slider", "gamma": "gamma_slider"}),
            "palette": (self.palette_controls, {"name": "palette_combo", "tones": "tones_combo"}),
            "dither": (self.dither_controls, {"mode": "mode_combo", "strength": "strength_slider", "scale": "scale_slider"}),
            "dither_destruction": (self.dither_controls, {"pattern_distortion": "pattern_distortion_slider", "dither_loss": "dither_loss_slider", "dither_spread": "dither_spread_slider"}),
            "engraving": (self.engraving_controls, {"strength": "strength_slider", "detail": "detail_slider", "thickness": "thickness_slider", "direction": "direction_combo"}),
            "black_consumption": (self.black_consumption_controls, {"amount": "amount_slider", "reach": "reach_slider", "detail_swallow": "detail_swallow_slider"}),
            "ink": (self.ink_controls, {"ink_bleed": "ink_bleed_slider", "ink_loss": "ink_loss_slider", "paper_grain": "paper_grain_slider", "speckles": "speckles_slider", "print_misalignment": "print_misalignment_slider"}),
            "focus": (self.focus_controls, {"shape": "shape_combo", "position_x": "position_x_slider", "position_y": "position_y_slider", "width": "width_slider", "softness": "softness_slider", "angle": "angle_slider", "blur": "blur_slider"}),
            "lens": (self.lens_controls, {"uneven_focus": "uneven_focus_slider", "lens_smear": "lens_smear_slider", "smear_angle": "smear_angle_slider", "soft_bleed": "soft_bleed_slider"}),
            "degradation": (self.degradation_controls, {"film_grain": "film_grain_slider", "dust": "dust_slider", "scratches": "scratches_slider", "edge_decay": "edge_decay_slider", "exposure_drift": "exposure_drift_slider", "vignette": "vignette_slider", "image_fade": "image_fade_slider"}),
        }
        for group_name, (widget, fields) in groups.items():
            for key, attribute in fields.items():
                if key not in values.get(group_name, {}):
                    continue
                control, value = getattr(widget, attribute), values[group_name][key]
                control.setCurrentText(str(value)) if isinstance(control, QComboBox) else control.setValue(int(round(value * 100)) if group_name == "tone" and key == "gamma" else int(value))
        for widget in (
            self.tone_controls, self.dither_controls, self.engraving_controls,
            self.black_consumption_controls, self.ink_controls, self.focus_controls,
            self.lens_controls, self.degradation_controls,
        ):
            widget._refresh_value_labels()

    def export_png(self) -> None:
        if self.original_image is None:
            QMessageBox.information(self, "Exportar PNG", "Importe uma imagem antes de exportar.")
            return
        suggested = f"{Path(self.current_image_path or 'imagem').stem}_ruinprint.png"
        output_path, _ = QFileDialog.getSaveFileName(self, "Exportar PNG", suggested, "PNG (*.png)")
        if not output_path:
            return
        if not output_path.lower().endswith(".png"):
            output_path += ".png"
        scale = max(self.original_image.width / self.preview_image.width, self.original_image.height / self.preview_image.height)
        self._start_export(output_path, self.current_pipeline_settings(), scale)

    def _start_export(self, output_path: str, settings: PipelineSettings, scale: float) -> None:
        self.import_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.export_progress.setValue(0)
        self.export_progress.show()
        self._export_thread = QThread(self)
        worker = ExportWorker(self.original_image, settings, output_path, scale)
        worker.moveToThread(self._export_thread)
        self._export_thread.started.connect(worker.run)
        worker.progress.connect(self.export_progress.setValue)
        worker.finished.connect(self._export_finished)
        worker.error.connect(self._export_failed)
        worker.finished.connect(self._export_thread.quit)
        worker.error.connect(self._export_thread.quit)
        self._export_thread.finished.connect(worker.deleteLater)
        self._export_thread.finished.connect(self._export_thread.deleteLater)
        self._export_thread.start()

    def _export_finished(self, output_path: str) -> None:
        self._finish_export()
        QMessageBox.information(self, "Exportar PNG", f"Imagem exportada com sucesso.\n\n{output_path}")

    def _export_failed(self, message: str) -> None:
        self._finish_export()
        QMessageBox.critical(self, "Erro ao exportar", f"Não foi possível exportar a imagem.\n\n{message}")

    def _finish_export(self) -> None:
        self.import_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.export_progress.hide()
        self._export_thread = None

    def schedule_result_update(self) -> None:
        """Debounce preview recalculation while controls are being adjusted."""
        if not self._is_resetting_controls and not self._applying_preset:
            if self.preset_combo.currentText() != "Personalizado":
                self.preset_combo.blockSignals(True)
                self.preset_combo.setCurrentText("Personalizado")
                self.preset_combo.blockSignals(False)
                self.update_preset_button.setEnabled(False)
                self.rename_preset_button.setEnabled(False)
                self.delete_preset_button.setEnabled(False)
            self._update_timer.start()

    def _commit_slider_edit(self) -> None:
        before = getattr(self, "_slider_before", None)
        if before is not None and not self._history_suspended:
            self._record_history(before)

    def _record_history(self, before: dict) -> None:
        after = asdict(self.current_pipeline_settings())
        self.history.record(before, after)
        self._last_settings = after
        self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        self.undo_button.setEnabled(bool(self.history.undo_stack))
        self.redo_button.setEnabled(bool(self.history.redo_stack))

    def undo(self) -> None:
        settings = self.history.undo(asdict(self.current_pipeline_settings()))
        if settings: self._apply_settings_once(settings)

    def redo(self) -> None:
        settings = self.history.redo(asdict(self.current_pipeline_settings()))
        if settings: self._apply_settings_once(settings)

    def _apply_settings_once(self, settings: dict) -> None:
        self._history_suspended = True
        self._apply_preset_values(settings)
        self._history_suspended = False
        self.preset_combo.setCurrentText("Personalizado")
        self.update_result_preview(); self._update_history_buttons()

    def show_before(self) -> None:
        if self.preview_image is not None:
            self._before_active = True; self.result_image_view.set_image(self.preview_image)

    def show_after(self) -> None:
        self._before_active = False
        if self.current_result_preview is not None: self.result_image_view.set_image(self.current_result_preview)

    def copy_settings(self) -> None:
        QApplication.clipboard().setText(json.dumps({"app":"RuinPrint","type":"processing-settings","version":1,"settings":asdict(self.current_pipeline_settings())}, indent=2))

    def paste_settings(self) -> None:
        try:
            data = json.loads(QApplication.clipboard().text())
            if data.get("app") != "RuinPrint" or data.get("type") != "processing-settings" or data.get("version") != 1 or not isinstance(data.get("settings"), dict): raise ValueError
        except (ValueError, json.JSONDecodeError):
            QMessageBox.warning(self, "Colar config.", "As configurações copiadas não são válidas para o RuinPrint."); return
        before = asdict(self.current_pipeline_settings()); self._apply_settings_once(data["settings"]); self._record_history(before)

    def reset_tone_controls(self) -> None:
        """Restore default controls while keeping the image and update once."""
        before = asdict(self.current_pipeline_settings())
        self._is_resetting_controls = True
        self.tone_controls.reset()
        self.palette_controls.reset()
        self.dither_controls.reset()
        self.engraving_controls.reset()
        self.black_consumption_controls.reset()
        self.ink_controls.reset()
        self.focus_controls.reset()
        self.lens_controls.reset()
        self.degradation_controls.reset()
        self._is_resetting_controls = False
        self.preset_combo.setCurrentText("Personalizado")
        self._update_timer.stop()
        self.update_result_preview()
        self._record_history(before)

    def _restore_window_state(self) -> None:
        try:
            geometry = self.settings.value("window_geometry")
            splitter_state = self.settings.value("splitter_state")
            if geometry:
                self.restoreGeometry(geometry)
            if splitter_state:
                self.workspace.restoreState(splitter_state)
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        if self._export_thread is not None and self._export_thread.isRunning():
            QMessageBox.information(self, "Exportação em andamento", "Aguarde a exportação terminar antes de fechar.")
            event.ignore()
            return
        self.settings.setValue("window_geometry", self.saveGeometry())
        self.settings.setValue("splitter_state", self.workspace.saveState())
        super().closeEvent(event)

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
            #toneControls, #paletteControls, #ditherControls, #engravingControls, #blackConsumptionControls, #inkControls, #focusControls, #lensControls, #degradationControls {
                border: 1px solid #424242;
                border-radius: 5px;
                margin-top: 8px;
                padding: 8px;
            }
            #toneControls::title, #paletteControls::title, #ditherControls::title, #engravingControls::title, #blackConsumptionControls::title, #inkControls::title, #focusControls::title, #lensControls::title, #degradationControls::title {
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
            #imageView[dropActive="true"] {
                border: 2px dashed #9d8a63;
            }
            """
        )
