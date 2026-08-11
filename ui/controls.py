"""Reusable editor controls."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class CollapsibleSection(QWidget):
    """Reusable header/content wrapper that hides controls without recreating them."""

    toggled = Signal(bool)

    def __init__(self, title: str, content: QWidget, expanded: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.header = QPushButton(title)
        self.header.setObjectName("sectionHeader")
        self.header.clicked.connect(self.toggle)
        layout.addWidget(self.header)
        layout.addWidget(content)
        self.set_expanded(expanded, emit=False)

    def set_expanded(self, expanded: bool, emit: bool = True) -> None:
        self._expanded = expanded
        self._content.setVisible(expanded)
        self.header.setText(("▼ " if expanded else "▶ ") + self.header.text().lstrip("▼ ▶"))
        if emit: self.toggled.emit(expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

from core.pipeline import (
    BlackConsumptionParameters,
    DegradationParameters,
    DitherDestructionParameters,
    DitherParameters,
    EngravingParameters,
    FocusParameters,
    InkParameters,
    LensParameters,
    PaletteParameters,
    ToneParameters,
)
from effects.palette import PALETTES, get_palette


class ToneControls(QGroupBox):
    """Controls for the first tonal stage of the processing pipeline."""

    parameters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("TONE", parent)
        self.setObjectName("toneControls")

        form_layout = QFormLayout(self)
        form_layout.setSpacing(12)

        self.contrast_slider, self.contrast_value = self._add_slider(
            form_layout, "Contrast", -100, 100, 0
        )
        self.black_crush_slider, self.black_crush_value = self._add_slider(
            form_layout, "Black Crush", 0, 100, 0
        )
        self.highlight_burn_slider, self.highlight_burn_value = self._add_slider(
            form_layout, "Highlight Burn", 0, 100, 0
        )
        self.gamma_slider, self.gamma_value = self._add_slider(
            form_layout, "Gamma", 30, 300, 100, is_gamma=True
        )

    def parameters(self) -> ToneParameters:
        """Return the current user-selected tone values."""
        return ToneParameters(
            contrast=self.contrast_slider.value(),
            black_crush=self.black_crush_slider.value(),
            highlight_burn=self.highlight_burn_slider.value(),
            gamma=self.gamma_slider.value() / 100,
        )

    def reset(self) -> None:
        """Restore all sliders to their neutral values and emit one update."""
        sliders_and_values = (
            (self.contrast_slider, 0),
            (self.black_crush_slider, 0),
            (self.highlight_burn_slider, 0),
            (self.gamma_slider, 100),
        )
        for slider, value in sliders_and_values:
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self._refresh_value_labels()
        self.parameters_changed.emit()

    def _add_slider(
        self,
        form_layout: QFormLayout,
        label: str,
        minimum: int,
        maximum: int,
        default: int,
        *,
        is_gamma: bool = False,
    ) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)

        value_label = QLabel()
        value_label.setObjectName("controlValue")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_label)
        form_layout.addRow(label, row)

        def update_value(value: int) -> None:
            value_label.setText(f"{value / 100:.2f}" if is_gamma else str(value))
            self.parameters_changed.emit()

        slider.valueChanged.connect(update_value)
        update_value(default)
        return slider, value_label

    def _refresh_value_labels(self) -> None:
        self.contrast_value.setText(str(self.contrast_slider.value()))
        self.black_crush_value.setText(str(self.black_crush_slider.value()))
        self.highlight_burn_value.setText(str(self.highlight_burn_slider.value()))
        self.gamma_value.setText(f"{self.gamma_slider.value() / 100:.2f}")


class PaletteControls(QGroupBox):
    """Controls for the palette stage of the processing pipeline."""

    parameters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("PALETTE", parent)
        self.setObjectName("paletteControls")

        form_layout = QFormLayout(self)
        form_layout.setSpacing(12)

        self.palette_combo = QComboBox()
        self.palette_combo.addItems(tuple(PALETTES))
        self.palette_combo.setCurrentText("Aged Ivory")
        form_layout.addRow("Palette", self.palette_combo)

        self.tones_combo = QComboBox()
        self.tones_combo.addItems(("2", "3", "4", "5", "6"))
        self.tones_combo.setCurrentText("4")
        form_layout.addRow("Tones", self.tones_combo)
        self.swatches = QLabel()
        self.swatches.setFixedHeight(22)
        form_layout.addRow("", self.swatches)

        self.palette_combo.currentTextChanged.connect(self.parameters_changed)
        self.tones_combo.currentTextChanged.connect(self.parameters_changed)
        self.palette_combo.currentTextChanged.connect(self._update_swatches)
        self.tones_combo.currentTextChanged.connect(self._update_swatches)
        self._update_swatches()

    def _update_swatches(self) -> None:
        colors = get_palette(self.palette_combo.currentText(), int(self.tones_combo.currentText()))
        stops = ", ".join(f"rgb({r},{g},{b}) {index * 100 / len(colors):.1f}%, rgb({r},{g},{b}) {(index + 1) * 100 / len(colors):.1f}%" for index, (r,g,b) in enumerate(colors))
        self.swatches.setStyleSheet(f"border: 1px solid #444; border-radius: 3px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, {stops});")

    def parameters(self) -> PaletteParameters:
        """Return the current palette selection."""
        return PaletteParameters(
            name=self.palette_combo.currentText(),
            tones=int(self.tones_combo.currentText()),
        )

    def reset(self) -> None:
        """Restore the default palette selection and emit one update."""
        self.palette_combo.blockSignals(True)
        self.tones_combo.blockSignals(True)
        self.palette_combo.setCurrentText("Aged Ivory")
        self.tones_combo.setCurrentText("4")
        self.palette_combo.blockSignals(False)
        self.tones_combo.blockSignals(False)
        self._update_swatches()
        self.parameters_changed.emit()


class DitherControls(QGroupBox):
    """Controls for the Dither/Palette stage of the processing pipeline."""

    parameters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("DITHER", parent)
        self.setObjectName("ditherControls")

        form_layout = QFormLayout(self)
        form_layout.setSpacing(12)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(
            (
                "Off",
                "Bayer",
                "Clustered Dot",
                "Cross Dither",
                "Broken Dither",
                "Floyd-Steinberg",
                "Atkinson",
                "Noise",
            )
        )
        self.mode_combo.setCurrentText("Bayer")
        form_layout.addRow("Mode", self.mode_combo)

        self.strength_slider, self.strength_value = self._add_slider(
            form_layout, "Strength", 0, 100, 70
        )
        self.scale_slider, self.scale_value = self._add_slider(
            form_layout, "Scale", 1, 8, 1
        )
        self.pattern_distortion_slider, self.pattern_distortion_value = self._add_slider(
            form_layout, "Pattern Distortion", 0, 100, 0
        )
        self.dither_loss_slider, self.dither_loss_value = self._add_slider(
            form_layout, "Dither Loss", 0, 100, 0
        )
        self.dither_spread_slider, self.dither_spread_value = self._add_slider(
            form_layout, "Dither Spread", 0, 100, 0
        )

        self.mode_combo.currentTextChanged.connect(self.parameters_changed)

    def parameters(self) -> DitherParameters:
        """Return the current dither values."""
        return DitherParameters(
            mode=self.mode_combo.currentText(),
            strength=self.strength_slider.value(),
            scale=self.scale_slider.value(),
        )

    def destruction_parameters(self) -> DitherDestructionParameters:
        """Return the current structural dither modifier values."""
        return DitherDestructionParameters(
            pattern_distortion=self.pattern_distortion_slider.value(),
            dither_loss=self.dither_loss_slider.value(),
            dither_spread=self.dither_spread_slider.value(),
        )

    def reset(self) -> None:
        """Restore default dither values and emit one update."""
        self.mode_combo.blockSignals(True)
        self.strength_slider.blockSignals(True)
        self.scale_slider.blockSignals(True)
        self.pattern_distortion_slider.blockSignals(True)
        self.dither_loss_slider.blockSignals(True)
        self.dither_spread_slider.blockSignals(True)
        self.mode_combo.setCurrentText("Bayer")
        self.strength_slider.setValue(70)
        self.scale_slider.setValue(1)
        self.pattern_distortion_slider.setValue(0)
        self.dither_loss_slider.setValue(0)
        self.dither_spread_slider.setValue(0)
        self.mode_combo.blockSignals(False)
        self.strength_slider.blockSignals(False)
        self.scale_slider.blockSignals(False)
        self.pattern_distortion_slider.blockSignals(False)
        self.dither_loss_slider.blockSignals(False)
        self.dither_spread_slider.blockSignals(False)
        self._refresh_value_labels()
        self.parameters_changed.emit()

    def _add_slider(
        self, form_layout: QFormLayout, label: str, minimum: int, maximum: int, default: int
    ) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)

        value_label = QLabel(str(default))
        value_label.setObjectName("controlValue")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_label)
        form_layout.addRow(label, row)

        def update_value(value: int) -> None:
            value_label.setText(str(value))
            self.parameters_changed.emit()

        slider.valueChanged.connect(update_value)
        return slider, value_label

    def _refresh_value_labels(self) -> None:
        self.strength_value.setText(str(self.strength_slider.value()))
        self.scale_value.setText(str(self.scale_slider.value()))
        self.pattern_distortion_value.setText(str(self.pattern_distortion_slider.value()))
        self.dither_loss_value.setText(str(self.dither_loss_slider.value()))
        self.dither_spread_value.setText(str(self.dither_spread_slider.value()))


class EngravingControls(QGroupBox):
    """Controls for structural edge engraving."""

    parameters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("ENGRAVING", parent)
        self.setObjectName("engravingControls")

        form_layout = QFormLayout(self)
        form_layout.setSpacing(12)
        self.strength_slider, self.strength_value = self._add_slider(
            form_layout, "Strength", 0, 100, 0
        )
        self.detail_slider, self.detail_value = self._add_slider(
            form_layout, "Detail", 0, 100, 35
        )
        self.thickness_slider, self.thickness_value = self._add_slider(
            form_layout, "Thickness", 1, 6, 1
        )
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(
            ("Natural", "Horizontal", "Vertical", "Diagonal /", "Diagonal \\")
        )
        form_layout.addRow("Direction", self.direction_combo)
        self.direction_combo.currentTextChanged.connect(self.parameters_changed)

    def parameters(self) -> EngravingParameters:
        """Return the current engraving values."""
        return EngravingParameters(
            strength=self.strength_slider.value(),
            detail=self.detail_slider.value(),
            thickness=self.thickness_slider.value(),
            direction=self.direction_combo.currentText(),
        )

    def reset(self) -> None:
        """Restore default engraving values and emit one update."""
        for slider, value in (
            (self.strength_slider, 0),
            (self.detail_slider, 35),
            (self.thickness_slider, 1),
        ):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.direction_combo.blockSignals(True)
        self.direction_combo.setCurrentText("Natural")
        self.direction_combo.blockSignals(False)
        self._refresh_value_labels()
        self.parameters_changed.emit()

    def _add_slider(
        self, form_layout: QFormLayout, label: str, minimum: int, maximum: int, default: int
    ) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)

        value_label = QLabel(str(default))
        value_label.setObjectName("controlValue")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_label)
        form_layout.addRow(label, row)

        def update_value(value: int) -> None:
            value_label.setText(str(value))
            self.parameters_changed.emit()

        slider.valueChanged.connect(update_value)
        return slider, value_label

    def _refresh_value_labels(self) -> None:
        self.strength_value.setText(str(self.strength_slider.value()))
        self.detail_value.setText(str(self.detail_slider.value()))
        self.thickness_value.setText(str(self.thickness_slider.value()))


class BlackConsumptionControls(QGroupBox):
    """Controls for localized spatial growth of dark palette masses."""

    parameters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("BLACK CONSUMPTION", parent)
        self.setObjectName("blackConsumptionControls")

        form_layout = QFormLayout(self)
        form_layout.setSpacing(12)
        self.amount_slider, self.amount_value = self._add_slider(
            form_layout, "Amount", 0, 100, 0
        )
        self.reach_slider, self.reach_value = self._add_slider(
            form_layout, "Reach", 1, 8, 2
        )
        self.detail_swallow_slider, self.detail_swallow_value = self._add_slider(
            form_layout, "Detail Swallow", 0, 100, 0
        )

    def parameters(self) -> BlackConsumptionParameters:
        """Return the current black consumption values."""
        return BlackConsumptionParameters(
            amount=self.amount_slider.value(),
            reach=self.reach_slider.value(),
            detail_swallow=self.detail_swallow_slider.value(),
        )

    def reset(self) -> None:
        """Restore default black consumption values and emit one update."""
        for slider, value in (
            (self.amount_slider, 0),
            (self.reach_slider, 2),
            (self.detail_swallow_slider, 0),
        ):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self._refresh_value_labels()
        self.parameters_changed.emit()

    def _add_slider(
        self, form_layout: QFormLayout, label: str, minimum: int, maximum: int, default: int
    ) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)

        value_label = QLabel(str(default))
        value_label.setObjectName("controlValue")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_label)
        form_layout.addRow(label, row)

        def update_value(value: int) -> None:
            value_label.setText(str(value))
            self.parameters_changed.emit()

        slider.valueChanged.connect(update_value)
        return slider, value_label

    def _refresh_value_labels(self) -> None:
        self.amount_value.setText(str(self.amount_slider.value()))
        self.reach_value.setText(str(self.reach_slider.value()))
        self.detail_swallow_value.setText(str(self.detail_swallow_slider.value()))


class FocusControls(QGroupBox):
    """Controls that define the Focus Map without altering image geometry."""

    parameters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("FOCUS MAP", parent)
        self.setObjectName("focusControls")

        form_layout = QFormLayout(self)
        form_layout.setSpacing(12)
        self.shape_combo = QComboBox()
        self.shape_combo.addItems(("Horizontal", "Vertical", "Radial", "Elliptical"))
        form_layout.addRow("Shape", self.shape_combo)
        self.position_x_slider, self.position_x_value = self._add_slider(form_layout, "Position X", 0, 100, 50)
        self.position_y_slider, self.position_y_value = self._add_slider(form_layout, "Position Y", 0, 100, 50)
        self.width_slider, self.width_value = self._add_slider(form_layout, "Width", 5, 100, 40)
        self.softness_slider, self.softness_value = self._add_slider(form_layout, "Softness", 0, 100, 40)
        self.angle_slider, self.angle_value = self._add_slider(form_layout, "Angle", -90, 90, 0)
        self.blur_slider, self.blur_value = self._add_slider(form_layout, "Out-of-Focus Blur", 0, 100, 0)
        self.shape_combo.currentTextChanged.connect(self.parameters_changed)

    def parameters(self) -> FocusParameters:
        """Return the current Focus Map values."""
        return FocusParameters(
            shape=self.shape_combo.currentText(),
            position_x=self.position_x_slider.value(),
            position_y=self.position_y_slider.value(),
            width=self.width_slider.value(),
            softness=self.softness_slider.value(),
            angle=self.angle_slider.value(),
            blur=self.blur_slider.value(),
        )

    def reset(self) -> None:
        """Restore default Focus Map values and emit one update."""
        for slider, value in (
            (self.position_x_slider, 50), (self.position_y_slider, 50),
            (self.width_slider, 40), (self.softness_slider, 40),
            (self.angle_slider, 0), (self.blur_slider, 0),
        ):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.shape_combo.blockSignals(True)
        self.shape_combo.setCurrentText("Horizontal")
        self.shape_combo.blockSignals(False)
        self._refresh_value_labels()
        self.parameters_changed.emit()

    def _add_slider(self, layout: QFormLayout, label: str, minimum: int, maximum: int, default: int) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)
        value_label = QLabel(str(default))
        value_label.setObjectName("controlValue")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_label)
        layout.addRow(label, row)
        slider.valueChanged.connect(lambda value: (value_label.setText(str(value)), self.parameters_changed.emit()))
        return slider, value_label

    def _refresh_value_labels(self) -> None:
        for slider, label in (
            (self.position_x_slider, self.position_x_value), (self.position_y_slider, self.position_y_value),
            (self.width_slider, self.width_value), (self.softness_slider, self.softness_value),
            (self.angle_slider, self.angle_value), (self.blur_slider, self.blur_value),
        ):
            label.setText(str(slider.value()))


class LensControls(QGroupBox):
    """Controls for optical imperfections that use the Focus Map."""

    parameters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("OLD LENS", parent)
        self.setObjectName("lensControls")

        form_layout = QFormLayout(self)
        form_layout.setSpacing(12)
        self.uneven_focus_slider, self.uneven_focus_value = self._add_slider(form_layout, "Uneven Focus", 0, 100, 0)
        self.lens_smear_slider, self.lens_smear_value = self._add_slider(form_layout, "Lens Smear", 0, 100, 0)
        self.smear_angle_slider, self.smear_angle_value = self._add_slider(form_layout, "Smear Angle", -90, 90, 0)
        self.soft_bleed_slider, self.soft_bleed_value = self._add_slider(form_layout, "Soft Bleed", 0, 100, 0)

    def parameters(self) -> LensParameters:
        """Return the current Old Lens values."""
        return LensParameters(
            uneven_focus=self.uneven_focus_slider.value(),
            lens_smear=self.lens_smear_slider.value(),
            smear_angle=self.smear_angle_slider.value(),
            soft_bleed=self.soft_bleed_slider.value(),
        )

    def reset(self) -> None:
        """Restore default Old Lens values and emit one update."""
        for slider in (self.uneven_focus_slider, self.lens_smear_slider, self.smear_angle_slider, self.soft_bleed_slider):
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        self._refresh_value_labels()
        self.parameters_changed.emit()

    def _add_slider(self, layout: QFormLayout, label: str, minimum: int, maximum: int, default: int) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(default)
        value_label = QLabel(str(default))
        value_label.setObjectName("controlValue")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_label)
        layout.addRow(label, row)
        slider.valueChanged.connect(lambda value: (value_label.setText(str(value)), self.parameters_changed.emit()))
        return slider, value_label

    def _refresh_value_labels(self) -> None:
        for slider, label in (
            (self.uneven_focus_slider, self.uneven_focus_value),
            (self.lens_smear_slider, self.lens_smear_value),
            (self.smear_angle_slider, self.smear_angle_value),
            (self.soft_bleed_slider, self.soft_bleed_value),
        ):
            label.setText(str(slider.value()))


class DegradationControls(QGroupBox):
    """Controls for the final Film / Degradation stage."""

    parameters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("FILM / DEGRADATION", parent)
        self.setObjectName("degradationControls")

        form_layout = QFormLayout(self)
        form_layout.setSpacing(12)
        self.film_grain_slider, self.film_grain_value = self._add_slider(form_layout, "Film Grain")
        self.dust_slider, self.dust_value = self._add_slider(form_layout, "Dust")
        self.scratches_slider, self.scratches_value = self._add_slider(form_layout, "Scratches")
        self.edge_decay_slider, self.edge_decay_value = self._add_slider(form_layout, "Edge Decay")
        self.exposure_drift_slider, self.exposure_drift_value = self._add_slider(form_layout, "Exposure Drift")
        self.vignette_slider, self.vignette_value = self._add_slider(form_layout, "Vignette")
        self.image_fade_slider, self.image_fade_value = self._add_slider(form_layout, "Image Fade")

    def parameters(self) -> DegradationParameters:
        """Return the current degradation values."""
        return DegradationParameters(
            film_grain=self.film_grain_slider.value(),
            dust=self.dust_slider.value(),
            scratches=self.scratches_slider.value(),
            edge_decay=self.edge_decay_slider.value(),
            exposure_drift=self.exposure_drift_slider.value(),
            vignette=self.vignette_slider.value(),
            image_fade=self.image_fade_slider.value(),
        )

    def reset(self) -> None:
        """Restore all degradation controls to zero and emit one update."""
        sliders = (
            self.film_grain_slider, self.dust_slider, self.scratches_slider,
            self.edge_decay_slider, self.exposure_drift_slider, self.vignette_slider,
            self.image_fade_slider,
        )
        for slider in sliders:
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        self._refresh_value_labels()
        self.parameters_changed.emit()

    def _add_slider(self, layout: QFormLayout, label: str) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        value_label = QLabel("0")
        value_label.setObjectName("controlValue")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_label)
        layout.addRow(label, row)
        slider.valueChanged.connect(lambda value: (value_label.setText(str(value)), self.parameters_changed.emit()))
        return slider, value_label

    def _refresh_value_labels(self) -> None:
        for slider, label in (
            (self.film_grain_slider, self.film_grain_value), (self.dust_slider, self.dust_value),
            (self.scratches_slider, self.scratches_value), (self.edge_decay_slider, self.edge_decay_value),
            (self.exposure_drift_slider, self.exposure_drift_value), (self.vignette_slider, self.vignette_value),
            (self.image_fade_slider, self.image_fade_value),
        ):
            label.setText(str(slider.value()))


class InkControls(QGroupBox):
    """Controls for the Print/Ink stage of the processing pipeline."""

    parameters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("PRINT / INK", parent)
        self.setObjectName("inkControls")

        form_layout = QFormLayout(self)
        form_layout.setSpacing(12)
        self.ink_bleed_slider, self.ink_bleed_value = self._add_slider(form_layout, "Ink Bleed")
        self.ink_loss_slider, self.ink_loss_value = self._add_slider(form_layout, "Ink Loss")
        self.paper_grain_slider, self.paper_grain_value = self._add_slider(form_layout, "Paper Grain")
        self.speckles_slider, self.speckles_value = self._add_slider(form_layout, "Speckles")
        self.print_misalignment_slider, self.print_misalignment_value = self._add_slider(
            form_layout, "Print Misalignment"
        )

    def parameters(self) -> InkParameters:
        """Return the current print/ink values."""
        return InkParameters(
            ink_bleed=self.ink_bleed_slider.value(),
            ink_loss=self.ink_loss_slider.value(),
            paper_grain=self.paper_grain_slider.value(),
            speckles=self.speckles_slider.value(),
            print_misalignment=self.print_misalignment_slider.value(),
        )

    def reset(self) -> None:
        """Restore the print/ink sliders to zero and emit one update."""
        sliders = (
            self.ink_bleed_slider,
            self.ink_loss_slider,
            self.paper_grain_slider,
            self.speckles_slider,
            self.print_misalignment_slider,
        )
        for slider in sliders:
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        self._refresh_value_labels()
        self.parameters_changed.emit()

    def _add_slider(self, form_layout: QFormLayout, label: str) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)

        value_label = QLabel("0")
        value_label.setObjectName("controlValue")
        value_label.setMinimumWidth(40)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(slider, 1)
        row_layout.addWidget(value_label)
        form_layout.addRow(label, row)

        def update_value(value: int) -> None:
            value_label.setText(str(value))
            self.parameters_changed.emit()

        slider.valueChanged.connect(update_value)
        return slider, value_label

    def _refresh_value_labels(self) -> None:
        self.ink_bleed_value.setText(str(self.ink_bleed_slider.value()))
        self.ink_loss_value.setText(str(self.ink_loss_slider.value()))
        self.paper_grain_value.setText(str(self.paper_grain_slider.value()))
        self.speckles_value.setText(str(self.speckles_slider.value()))
        self.print_misalignment_value.setText(str(self.print_misalignment_slider.value()))
