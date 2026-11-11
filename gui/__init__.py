"""
Graphical User Interface (GUI) package for the Queueing System Simulator.
"""

from .canvas import AnimatedCanvas
from .main_window import QueueSimulatorApp
from .styles import MAIN_STYLESHEET, ZOOM_VIEW_STYLESHEET, THEORY_HTML_CSS
from .theory_dialog import TheoryDialog, generate_theory_html
from .theory_tab import TheoryPdfTab
from .widgets import (
    NoWheelSlider,
    NoWheelSpinBox,
    NoWheelDoubleSpinBox,
    NoWheelComboBox,
    DynamicStackedWidget,
    NumberStepper,
    OpticalZoomView,
    GlobalZoomFilter,
)

__all__ = [
    "AnimatedCanvas",
    "QueueSimulatorApp",
    "MAIN_STYLESHEET",
    "ZOOM_VIEW_STYLESHEET",
    "THEORY_HTML_CSS",
    "TheoryDialog",
    "generate_theory_html",
    "TheoryPdfTab",
    "NoWheelSlider",
    "NoWheelSpinBox",
    "NoWheelDoubleSpinBox",
    "NoWheelComboBox",
    "DynamicStackedWidget",
    "NumberStepper",
    "OpticalZoomView",
    "GlobalZoomFilter",
]