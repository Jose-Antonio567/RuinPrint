"""Centralized visual theme for the RuinPrint interface."""

APP_STYLESHEET = """
QMainWindow, QWidget { background: #181818; color: #e7e7e7; font-family: "Segoe UI", sans-serif; font-size: 13px; }
#topBar { background: #222222; border: 1px solid #333333; border-radius: 6px; }
#toolGroupLabel, #imageListTitle { color: #a8a8a8; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; }
#toolbarSeparator { background: #404040; max-width: 1px; margin: 3px 2px; }
QPushButton { background: #303030; border: 1px solid #484848; border-radius: 4px; padding: 8px 12px; }
QPushButton:hover { background: #3a3a3a; border-color: #696153; }
QPushButton:pressed { background: #252525; }
QPushButton:disabled { color: #777777; background: #242424; border-color: #303030; }
#imageView { background: #202020; border: 1px solid #363636; border-radius: 6px; }
#panelTitle { font-size: 15px; font-weight: 600; }
#imagePlaceholder { background: #191919; border: 1px dashed #454545; border-radius: 4px; color: #8d8d8d; }
#settingsPanel, #settingsPanel > QWidget { background: #202020; border: 1px solid #363636; border-radius: 6px; }
#toneControls, #paletteControls, #ditherControls, #engravingControls, #blackConsumptionControls, #inkControls, #focusControls, #lensControls, #degradationControls { border: 1px solid #424242; border-radius: 5px; margin-top: 8px; padding: 8px; }
#toneControls::title, #paletteControls::title, #ditherControls::title, #engravingControls::title, #blackConsumptionControls::title, #inkControls::title, #focusControls::title, #lensControls::title, #degradationControls::title { subcontrol-origin: margin; left: 9px; padding: 0 4px; color: #cfcfcf; font-weight: 600; }
#controlValue { color: #bcbcbc; }
QComboBox { background: #303030; border: 1px solid #484848; border-radius: 4px; padding: 5px 8px; }
QComboBox:hover { border-color: #696153; }
QComboBox QAbstractItemView { background: #292929; selection-background-color: #4a453a; }
QSlider::groove:horizontal { height: 4px; background: #3a3a3a; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; margin: -4px 0; background: #bbbbbb; border-radius: 6px; }
QSlider::handle:horizontal:hover { background: #ded8c8; }
QListWidget { background: #202020; border: 1px solid #363636; border-radius: 4px; }
QListWidget::item { padding: 4px 6px; border-radius: 3px; }
QListWidget::item:hover { background: #303030; }
QListWidget::item:selected { background: #4a453a; color: #f0eadb; }
QScrollBar:vertical { background: #1b1b1b; width: 10px; }
QScrollBar::handle:vertical { background: #4a4a4a; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #606060; }
QStatusBar { background: #202020; color: #bcbcbc; border-top: 1px solid #303030; }
#workspace[dropActive="true"] { border: 2px dashed #9d8a63; border-radius: 6px; }
#imageView[dropActive="true"] { border: 2px dashed #9d8a63; }
"""
