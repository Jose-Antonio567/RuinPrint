"""Reusable editor controls."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QWidget,
)

from core.pipeline import ToneParameters


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
