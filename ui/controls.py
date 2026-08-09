"""Reusable editor controls."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QWidget,
)

from core.pipeline import DitherParameters, PaletteParameters, ToneParameters


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
        self.palette_combo.addItems(("Neutral", "Aged Ivory", "Warm Sepia", "Cold Ash"))
        self.palette_combo.setCurrentText("Aged Ivory")
        form_layout.addRow("Palette", self.palette_combo)

        self.tones_combo = QComboBox()
        self.tones_combo.addItems(("2", "3", "4", "5", "6"))
        self.tones_combo.setCurrentText("4")
        form_layout.addRow("Tones", self.tones_combo)

        self.palette_combo.currentTextChanged.connect(self.parameters_changed)
        self.tones_combo.currentTextChanged.connect(self.parameters_changed)

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
            ("Off", "Bayer", "Clustered Dot", "Floyd-Steinberg", "Atkinson", "Noise")
        )
        self.mode_combo.setCurrentText("Bayer")
        form_layout.addRow("Mode", self.mode_combo)

        self.strength_slider, self.strength_value = self._add_slider(
            form_layout, "Strength", 0, 100, 70
        )
        self.scale_slider, self.scale_value = self._add_slider(
            form_layout, "Scale", 1, 8, 1
        )

        self.mode_combo.currentTextChanged.connect(self.parameters_changed)

    def parameters(self) -> DitherParameters:
        """Return the current dither values."""
        return DitherParameters(
            mode=self.mode_combo.currentText(),
            strength=self.strength_slider.value(),
            scale=self.scale_slider.value(),
        )

    def reset(self) -> None:
        """Restore default dither values and emit one update."""
        self.mode_combo.blockSignals(True)
        self.strength_slider.blockSignals(True)
        self.scale_slider.blockSignals(True)
        self.mode_combo.setCurrentText("Bayer")
        self.strength_slider.setValue(70)
        self.scale_slider.setValue(1)
        self.mode_combo.blockSignals(False)
        self.strength_slider.blockSignals(False)
        self.scale_slider.blockSignals(False)
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
