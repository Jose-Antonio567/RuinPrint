from dataclasses import asdict
import json
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSignalBlocker, QThread, QTimer, QUrl, Qt
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
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
    QListWidget,
    QLabel,
)

from core.image_loader import (
    SUPPORTED_IMAGE_EXTENSIONS,
    create_preview,
    load_image_with_metadata,
)
from core.pipeline import ImagePipeline
from core.pipeline import PipelineSettings
from core.preset_manager import PresetManager
from core.edit_history import EditHistory
from core.preview_render_controller import PreviewRenderController
from core.image_document import ImageDocument
from core.processing_settings import (
    is_valid_processing_settings,
    migrate_processing_settings,
    settings_to_dict,
)
from core.app_paths import get_settings, resource_path
from core.app_info import APP_NAME
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
from ui.theme import APP_STYLESHEET


class MainWindow(QMainWindow):
    """Main application shell for the initial RuinPrint interface."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(resource_path("assets/ruinprint.ico"))))
        self.resize(1200, 750)
        self.setMinimumSize(800, 500)
        self.setAcceptDrops(True)

        self.current_image_path: str | None = None
        self.documents: list[ImageDocument] = []
        self.active_document_index: int = -1
        self.active_document: ImageDocument | None = None
        self.original_image: Image.Image | None = None
        self.preview_image: Image.Image | None = None
        self.current_result_preview: Image.Image | None = None
        self.pipeline = ImagePipeline()
        self.preset_manager = PresetManager()
        self.settings = get_settings()
        self._applying_preset = False
        self._syncing_views = False
        self.history = EditHistory()
        self._history_suspended = False
        self._before_active = False
        self.preview_controller = PreviewRenderController(self)
        self.preview_controller.result_ready.connect(self._preview_ready)
        self.preview_controller.status_changed.connect(self._set_preview_status)
        self.statusBar().showMessage("Preview: pronto")
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
        top_bar_layout.setSpacing(8)

        self._add_toolbar_group_label(top_bar_layout, "ARQUIVO")
        self.import_button = QPushButton("Importar imagem")
        self.import_button.clicked.connect(self.import_image)
        top_bar_layout.addWidget(self.import_button)
        self._add_toolbar_separator(top_bar_layout)
        self._add_toolbar_group_label(top_bar_layout, "EDIÇÃO")
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
        self._add_toolbar_separator(top_bar_layout)
        self._add_toolbar_group_label(top_bar_layout, "VISUALIZAR")
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
        self.original_image_view.filesDropped.connect(self.add_images_from_paths)
        self.result_image_view.filesDropped.connect(self.add_images_from_paths)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.fit_views)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=self.actual_views)
        QShortcut(QKeySequence("+"), self, activated=lambda: self.original_image_view.zoom_by(1.15))
        QShortcut(QKeySequence("-"), self, activated=lambda: self.original_image_view.zoom_by(1 / 1.15))
        self.image_list_title = QLabel()
        self.image_list_title.setObjectName("imageListTitle")
        self._update_image_list_title()
        self.image_list = QListWidget()
        self.image_list.currentRowChanged.connect(self.set_active_document)
        self.image_list.setMaximumHeight(92)
        self.remove_image_button = QPushButton("Remover")
        self.remove_image_button.clicked.connect(self.remove_active_document)
        image_list_bar = QWidget()
        image_list_layout = QHBoxLayout(image_list_bar)
        image_list_layout.setContentsMargins(0, 0, 0, 0)
        image_list_layout.addWidget(self.image_list_title)
        image_list_layout.addWidget(self.image_list, 1)
        image_list_layout.addWidget(self.remove_image_button)
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
        self.recover_image_settings_button = QPushButton("Carregar config. da imagem")
        self.recover_image_settings_button.setEnabled(False)
        self.recover_image_settings_button.clicked.connect(self.recover_active_image_settings)
        self.recover_image_settings_label = QLabel("Configuração RuinPrint encontrada")
        self.recover_image_settings_label.setObjectName("metadataNotice")
        self.recover_image_settings_label.hide()
        preset_layout.addWidget(self.recover_image_settings_button)
        preset_layout.addWidget(self.recover_image_settings_label)
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
        main_layout.addWidget(image_list_bar)
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
        self.palette_controls.hue_spectrum.interaction_started.connect(
            lambda: setattr(self, "_slider_before", asdict(self.current_pipeline_settings()))
        )
        self.palette_controls.hue_spectrum.interaction_finished.connect(self._commit_slider_edit)
        self._update_history_buttons()
        self._update_document_actions()

    @staticmethod
    def _add_toolbar_group_label(layout: QHBoxLayout, label: str) -> None:
        group_label = QLabel(label)
        group_label.setObjectName("toolGroupLabel")
        layout.addWidget(group_label)

    @staticmethod
    def _add_toolbar_separator(layout: QHBoxLayout) -> None:
        separator = QFrame()
        separator.setObjectName("toolbarSeparator")
        separator.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(separator)

    def _update_image_list_title(self) -> None:
        if hasattr(self, "image_list_title"):
            self.image_list_title.setText(f"IMAGENS ({len(self.documents)})")

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
        normalized_path = str(Path(image_path).resolve())
        for index, document in enumerate(self.documents):
            if document.path == normalized_path:
                self.image_list.setCurrentRow(index)
                return
        try:
            original_image, ruinprint_settings = load_image_with_metadata(image_path)
            preview_image = create_preview(original_image)
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Erro ao carregar imagem",
                f"Não foi possível carregar a imagem selecionada.\n\n{error}",
            )
            return

        self.documents.append(
            ImageDocument(normalized_path, original_image, preview_image, ruinprint_settings)
        )
        self.image_list.addItem(Path(normalized_path).name)
        self._update_image_list_title()
        self.image_list.setCurrentRow(len(self.documents) - 1)

    def add_images_from_paths(self, paths: list[str]) -> None:
        for path in paths:
            self.load_image_from_path(path)

    def set_active_document(self, row: int) -> None:
        """Switch the active source document without changing global settings."""
        if row < 0 or row >= len(self.documents):
            return
        document = self.documents[row]
        self.active_document_index = row
        self.active_document = document
        self.current_image_path = document.path
        self.original_image = document.original_full
        self.preview_image = document.preview_original
        self.current_result_preview = document.preview_original.copy()
        self._update_recover_image_settings_state(document.ruinprint_settings)
        self._update_document_actions()
        self.preview_controller.invalidate()
        self.original_image_view.set_image(self.preview_image, reset_view=True)
        self.result_image_view.set_image(self.current_result_preview, reset_view=True)
        self.update_result_preview()

    def remove_active_document(self) -> None:
        row = self.image_list.currentRow()
        self.remove_document(row)

    def remove_document(self, row: int) -> None:
        """Remove one document while preserving the identity of the active document."""
        if row < 0 or row >= len(self.documents):
            return
        active_before = self.active_document
        removed_document = self.documents[row]

        with QSignalBlocker(self.image_list):
            self.documents.pop(row)
            self.image_list.takeItem(row)
            self._update_image_list_title()

            if not self.documents:
                self.image_list.setCurrentRow(-1)
                self._clear_active_document()
                return

            if active_before is not removed_document:
                for index, document in enumerate(self.documents):
                    if document is active_before:
                        self.active_document_index = index
                        self.image_list.setCurrentRow(index)
                        self._update_document_actions()
                        return

            next_row = min(row, len(self.documents) - 1)
            self.image_list.setCurrentRow(next_row)

        self.set_active_document(next_row)

    def _clear_active_document(self) -> None:
        """Enter the empty editor state after the final document is removed."""
        self._update_image_list_title()
        self.active_document_index = -1
        self.active_document = None
        self.current_image_path = None
        self.original_image = self.preview_image = self.current_result_preview = None
        self._before_active = False
        self._update_recover_image_settings_state(None)
        self._update_document_actions()
        self.preview_controller.invalidate()
        self.original_image_view.clear_image()
        self.result_image_view.clear_image()

    def _update_document_actions(self) -> None:
        has_documents = bool(self.documents)
        self.export_button.setEnabled(has_documents and self._export_thread is None)
        self.remove_image_button.setEnabled(has_documents)

    def update_result_preview(self) -> None:
        """Rebuild the result from the untouched original preview and current controls."""
        if self.preview_image is None:
            return

        self.preview_controller.request(self.preview_image, self.current_pipeline_settings())

    def _preview_ready(self, generation: int, image: Image.Image) -> None:
        self.current_result_preview = image
        if not self._before_active:
            self.result_image_view.set_image(image)

    def _set_preview_status(self, status: str) -> None:
        self.statusBar().showMessage(status)

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

    def _update_recover_image_settings_state(self, settings: dict | None) -> None:
        """Reflect metadata availability for the currently selected document only."""
        available = is_valid_processing_settings(settings)
        self.recover_image_settings_button.setEnabled(available)
        self.recover_image_settings_label.setVisible(available)

    def recover_active_image_settings(self) -> None:
        """Apply the active PNG's embedded snapshot as one undoable editor action."""
        if not (0 <= self.active_document_index < len(self.documents)):
            return
        settings = migrate_processing_settings(
            self.documents[self.active_document_index].ruinprint_settings
        )
        if settings is None:
            self._update_recover_image_settings_state(None)
            return

        before = settings_to_dict(self.current_pipeline_settings())
        self._applying_preset = True
        self._history_suspended = True
        controls = self.findChildren(QSlider) + self.findChildren(QComboBox)
        for control in controls:
            control.blockSignals(True)
        try:
            self._apply_preset_values(settings)
            self.preset_combo.setCurrentText("Personalizado")
        finally:
            for control in controls:
                control.blockSignals(False)
            self._history_suspended = False
            self._applying_preset = False

        self._update_timer.stop()
        self.update_result_preview()
        self._record_history(before)
        self.statusBar().showMessage("Configuração da imagem carregada", 5000)

    def _refresh_preset_combo(self, selected: str = "Personalizado") -> None:
        if not hasattr(self, "preset_combo"):
            return
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("Personalizado")
        self._add_preset_header("FACTORY")
        self.preset_combo.addItems([f"Factory: {name}" for name in self.preset_manager.factory_presets])
        self._add_preset_header("MY PRESETS")
        self.preset_combo.addItems(self.preset_manager.names())
        label = (
            f"Factory: {selected}" if selected in self.preset_manager.factory_presets
            else selected if selected in self.preset_manager.presets
            else "Personalizado"
        )
        self.preset_combo.setCurrentText(label)
        self.preset_combo.blockSignals(False)

    def _add_preset_header(self, title: str) -> None:
        self.preset_combo.addItem(title)
        item = self.preset_combo.model().item(self.preset_combo.count() - 1)
        if item is not None:
            item.setEnabled(False)

    def _preset_name(self) -> str | None:
        name = self.preset_combo.currentText()
        if name == "Personalizado" or name in {"FACTORY", "MY PRESETS"}:
            return None
        return name.removeprefix("Factory: ")

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
        preset_name = self._preset_name()
        readonly = preset_name is not None and self.preset_manager.is_factory(preset_name)
        editable = preset_name is not None and not readonly
        self.update_preset_button.setEnabled(editable)
        self.rename_preset_button.setEnabled(editable)
        self.delete_preset_button.setEnabled(editable)
        if preset_name is None:
            return
        values = self.preset_manager.get(preset_name)
        if values is None:
            return
        before = settings_to_dict(self.current_pipeline_settings())
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
        self._update_timer.stop()
        self.update_result_preview()
        self._record_history(before)

    def _apply_preset_values(self, values: dict) -> None:
        groups = {
            "tone": (self.tone_controls, {"contrast": "contrast_slider", "black_crush": "black_crush_slider", "highlight_burn": "highlight_burn_slider", "gamma": "gamma_slider"}),
            "palette": (self.palette_controls, {"name": "palette_combo", "tones": "tones_combo", "aged_ivory_hue": "hue_spectrum", "aged_ivory_influence": "influence_slider"}),
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
                if isinstance(control, QComboBox):
                    control.setCurrentText(str(value))
                elif attribute == "hue_spectrum":
                    control.set_hue(int(value))
                else:
                    control.setValue(int(round(value * 100)) if group_name == "tone" and key == "gamma" else int(value))
        for widget in (
            self.tone_controls, self.dither_controls, self.engraving_controls,
            self.black_consumption_controls, self.ink_controls, self.focus_controls,
            self.lens_controls, self.degradation_controls,
        ):
            widget._refresh_value_labels()
        self.palette_controls._update_aged_ivory_visibility()
        self.palette_controls._update_swatches()

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
        self._export_worker = ExportWorker(self.original_image, settings, output_path, scale)
        worker = self._export_worker
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
        self.statusBar().showMessage(f"Exportado: {Path(output_path).name}", 5000)

    def _export_failed(self, message: str) -> None:
        self._finish_export()
        QMessageBox.critical(self, "Erro ao exportar", f"Não foi possível exportar a imagem.\n\n{message}")

    def _finish_export(self) -> None:
        self.import_button.setEnabled(True)
        self.export_progress.hide()
        self._export_thread = None
        self._export_worker = None
        self._update_document_actions()

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
        self._applying_preset = True
        controls = self.findChildren(QSlider) + self.findChildren(QComboBox)
        for control in controls:
            control.blockSignals(True)
        try:
            self._apply_preset_values(settings)
        finally:
            for control in controls:
                control.blockSignals(False)
            self._applying_preset = False
            self._history_suspended = False
        self.preset_combo.setCurrentText("Personalizado")
        self._update_timer.stop()
        self.update_result_preview(); self._update_history_buttons()

    def show_before(self) -> None:
        if self.preview_image is not None:
            self._before_active = True; self.result_image_view.set_image(self.preview_image)

    def show_after(self) -> None:
        self._before_active = False
        if self.current_result_preview is not None: self.result_image_view.set_image(self.current_result_preview)

    def copy_settings(self) -> None:
        QApplication.clipboard().setText(json.dumps({"app":"RuinPrint","type":"processing-settings","version":1,"settings":settings_to_dict(self.current_pipeline_settings())}, indent=2))

    def paste_settings(self) -> None:
        try:
            data = json.loads(QApplication.clipboard().text())
            if data.get("app") != "RuinPrint" or data.get("type") != "processing-settings" or data.get("version") != 1 or not is_valid_processing_settings(data.get("settings")): raise ValueError
        except (ValueError, json.JSONDecodeError):
            QMessageBox.warning(self, "Colar config.", "As configurações copiadas não são válidas para o RuinPrint."); return
        settings = migrate_processing_settings(data["settings"])
        if settings is None:
            QMessageBox.warning(self, "Colar config.", "As configurações copiadas não são válidas para o RuinPrint.")
            return
        before = asdict(self.current_pipeline_settings()); self._apply_settings_once(settings); self._record_history(before)

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
        image_paths = self._supported_drop_paths(event.mimeData().urls())
        self._set_drop_feedback(False)
        if not image_paths:
            event.ignore()
            return

        self.add_images_from_paths(image_paths)
        event.acceptProposedAction()

    @staticmethod
    def _first_supported_drop_path(urls: list[QUrl]) -> str | None:
        paths = MainWindow._supported_drop_paths(urls)
        return paths[0] if paths else None

    @staticmethod
    def _supported_drop_paths(urls: list[QUrl]) -> list[str]:
        paths = []
        for url in urls:
            if not url.isLocalFile():
                continue
            image_path = url.toLocalFile()
            if image_path and image_path.lower().endswith(tuple(SUPPORTED_IMAGE_EXTENSIONS)):
                paths.append(image_path)
        return paths

    def _set_drop_feedback(self, is_active: bool) -> None:
        self.workspace.setProperty("dropActive", is_active)
        self.workspace.style().unpolish(self.workspace)
        self.workspace.style().polish(self.workspace)

    def _apply_theme(self) -> None:
        self.setStyleSheet(APP_STYLESHEET)
