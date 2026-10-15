"""
Custom PyQt6 widgets, touchpad-safe controls, optical 2D camera viewport zoom,
and application-wide gesture event filters.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QTabBar,
    QAbstractSpinBox,
    QGraphicsView,
    QGraphicsScene,
    QStackedWidget,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QEvent, QObject
from PyQt6.QtGui import QPainter, QCursor
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from .styles import ZOOM_VIEW_STYLESHEET


class NoWheelSlider(QSlider):
    """Slider that strictly ignores wheel and touchpad scrolling to prevent accidental value adjustments."""
    def wheelEvent(self, event):
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    """SpinBox that strictly ignores wheel and touchpad scrolling to prevent accidental value adjustments."""
    def wheelEvent(self, event):
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """DoubleSpinBox that strictly ignores wheel and touchpad scrolling to prevent accidental value adjustments."""
    def wheelEvent(self, event):
        event.ignore()


class NoWheelComboBox(QComboBox):
    """ComboBox that strictly ignores wheel and touchpad scrolling to prevent accidental item changes."""
    def wheelEvent(self, event):
        event.ignore()


class DynamicStackedWidget(QStackedWidget):
    """QStackedWidget that dynamically adapts its sizeHint to the currently active page."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.currentChanged.connect(self._on_page_changed)

    def _on_page_changed(self, idx: int):
        self.updateGeometry()
        p = self.parentWidget()
        if p:
            if p.layout():
                p.layout().invalidate()
            p.updateGeometry()
            grand = p.parentWidget()
            if grand:
                if grand.layout():
                    grand.layout().invalidate()
                    grand.layout().activate()
                grand.updateGeometry()

    def sizeHint(self):
        cur = self.currentWidget()
        if cur:
            return cur.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        cur = self.currentWidget()
        if cur:
            return cur.minimumSizeHint()
        return super().minimumSizeHint()


class NumberStepper(QWidget):
    """Stepper Widget with dedicated [-] and [+] buttons and no internal spin arrows."""
    valueChanged = pyqtSignal(int)

    def __init__(self, min_val: int = 1, max_val: int = 500, default_val: int = 1, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(3)

        self.btn_minus = QPushButton("-")
        self.btn_minus.setFixedSize(26, 26)
        self.btn_minus.setStyleSheet("font-weight: bold; font-size: 13px; padding: 0;")
        self.btn_minus.clicked.connect(self._decrement)

        self.spin = NoWheelSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setValue(default_val)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setFixedSize(48, 26)
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.valueChanged.connect(self.valueChanged.emit)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(26, 26)
        self.btn_plus.setStyleSheet("font-weight: bold; font-size: 13px; padding: 0;")
        self.btn_plus.clicked.connect(self._increment)

        self.layout.addWidget(self.btn_minus)
        self.layout.addWidget(self.spin)
        self.layout.addWidget(self.btn_plus)
        self.setFixedSize(106, 26)

    def _decrement(self):
        cur = self.spin.value()
        if cur > self.min_val:
            self.spin.setValue(cur - 1)

    def _increment(self):
        cur = self.spin.value()
        if cur < self.max_val:
            self.spin.setValue(cur + 1)

    def value(self) -> int:
        return self.spin.value()

    def setValue(self, val: int):
        self.spin.setValue(val)

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self.btn_minus.setEnabled(enabled)
        self.btn_plus.setEnabled(enabled)
        self.spin.setEnabled(enabled)


class OpticalZoomView(QGraphicsView):
    """
    Optical Viewport Zoom View (True Camera / Viewport Zoom).
    Does NOT modify fonts or widget layout; performs pure 2D affine scaling.
    """
    def __init__(self, content_widget: QWidget, parent=None):
        super().__init__(parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(ZOOM_VIEW_STYLESHEET)

        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.content_widget = content_widget
        self.proxy = self.scene_obj.addWidget(content_widget)

        self.zoom_level = 1.0
        self.base_size = None
        self._is_panning = False
        self._pan_start = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        vp = self.viewport().size()
        if abs(self.zoom_level - 1.0) < 0.01:
            self.base_size = vp
            self.content_widget.resize(vp)
            self.scene_obj.setSceneRect(QRectF(0, 0, vp.width(), vp.height()))
            self.horizontalScrollBar().setValue(0)
            self.verticalScrollBar().setValue(0)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        elif self.base_size is not None:
            self.scene_obj.setSceneRect(QRectF(0, 0, self.base_size.width(), self.base_size.height()))
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def set_zoom(self, zoom: float, anchor_center: bool = False):
        # Enforce minimum zoom strictly to 1.0 (cannot zoom out below 100% full program size)
        zoom = max(1.0, min(3.0, round(zoom, 2)))
        if abs(zoom - self.zoom_level) < 0.001:
            return

        if abs(zoom - 1.0) < 0.001:
            self.reset_zoom()
            return

        old_anchor = self.transformationAnchor()
        if anchor_center:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        else:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        factor = zoom / self.zoom_level
        self.zoom_level = zoom
        self.scale(factor, factor)

        if anchor_center:
            self.setTransformationAnchor(old_anchor)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        if self.base_size is not None:
            self.scene_obj.setSceneRect(QRectF(0, 0, self.base_size.width(), self.base_size.height()))
        else:
            vp = self.viewport().size()
            self.scene_obj.setSceneRect(QRectF(0, 0, vp.width(), vp.height()))

    def reset_zoom(self):
        self.zoom_level = 1.0
        self.resetTransform()
        vp = self.viewport().size()
        self.base_size = vp
        self.content_widget.resize(vp)
        self.scene_obj.setSceneRect(QRectF(0, 0, vp.width(), vp.height()))
        self.horizontalScrollBar().setValue(0)
        self.verticalScrollBar().setValue(0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning and self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def scroll_by_wheel(self, event, sensitivity: float = 0.55) -> bool:
        """Smooth horizontal and vertical scrolling with slightly reduced sensitivity."""
        dx = event.angleDelta().x()
        dy = event.angleDelta().y()
        scrolled = False
        if dx != 0:
            hbar = self.horizontalScrollBar()
            delta_x = int(dx * sensitivity)
            if delta_x == 0 and dx != 0:
                delta_x = 1 if dx > 0 else -1
            hbar.setValue(hbar.value() - delta_x)
            scrolled = True
        if dy != 0:
            vbar = self.verticalScrollBar()
            delta_y = int(dy * sensitivity)
            if delta_y == 0 and dy != 0:
                delta_y = 1 if dy > 0 else -1
            vbar.setValue(vbar.value() - delta_y)
            scrolled = True
        return scrolled

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            super().wheelEvent(event)
            return
        # Only pan the outer viewport if the application itself is zoomed in
        if self.zoom_level > 1.01:
            if self.scroll_by_wheel(event):
                event.accept()
                return
        super().wheelEvent(event)


class GlobalZoomFilter(QObject):
    """Captures trackpad pinch gestures and Ctrl+Wheel events across the application."""
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    def eventFilter(self, obj, event):
        from .theory_dialog import TheoryDialog

        # 1. Native Touchpad Pinch-to-Zoom Gesture
        if event.type() == QEvent.Type.NativeGesture:
            if hasattr(event, 'gestureType') and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                delta = event.value()
                # If Theory PDF tab is active in main window, pinch-zoom the PDF anchored at pointer
                if hasattr(self.main_window, 'is_theory_tab_active') and self.main_window.is_theory_tab_active():
                    pdf_v = getattr(self.main_window.theory_tab, 'pdf_view', None)
                    anchor = pdf_v.viewport().mapFromGlobal(QCursor.pos()) if pdf_v else None
                    self.main_window.theory_tab.apply_pinch_zoom(delta, anchor_pos=anchor)
                    return True

                # If legacy TheoryDialog is open, zoom dialog text
                if TheoryDialog.current_instance is not None:
                    TheoryDialog.current_instance.apply_dialog_zoom(delta)
                    return True

                curr = obj
                while curr is not None:
                    if isinstance(curr, TheoryDialog):
                        curr.apply_dialog_zoom(delta)
                        return True
                    if hasattr(curr, 'parent'):
                        curr = curr.parent()
                    else:
                        break
                # Responsive sensitivity multiplier (5.0x) for fluid, responsive zoom
                self.main_window.adjust_page_zoom(delta * 5.0)
                return True

        # 2. Touchpad Scrolling and Mouse Wheel Events
        elif event.type() == QEvent.Type.Wheel:
            # Ctrl + Wheel: Zoom application viewport or active dialog/tab
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = 0.12 if event.angleDelta().y() > 0 else -0.12
                if hasattr(self.main_window, 'is_theory_tab_active') and self.main_window.is_theory_tab_active():
                    pdf_v = getattr(self.main_window.theory_tab, 'pdf_view', None)
                    anchor = pdf_v.viewport().mapFromGlobal(QCursor.pos()) if pdf_v else None
                    self.main_window.theory_tab.apply_wheel_zoom(delta, anchor_pos=anchor)
                    return True

                if TheoryDialog.current_instance is not None:
                    if delta > 0:
                        TheoryDialog.current_instance.zoom_in(1)
                    else:
                        TheoryDialog.current_instance.zoom_out(1)
                    return True

                curr = obj
                while curr is not None:
                    if isinstance(curr, TheoryDialog):
                        if delta > 0:
                            curr.zoom_in(1)
                        else:
                            curr.zoom_out(1)
                        return True
                    if hasattr(curr, 'parent'):
                        curr = curr.parent()
                    else:
                        break
                self.main_window.adjust_page_zoom(delta)
                return True
            else:
                # Wheel without Ctrl:
                # 1. If scrolling over QPdfView (Theory PDF tab), route 2D scrolling directly to PDF viewer
                curr = obj
                pdf_widget = None
                while curr is not None:
                    if curr.__class__.__name__ in ("QPdfView", "PinchablePdfView", "SmoothPdfView"):
                        pdf_widget = curr
                        break
                    if hasattr(self.main_window, 'is_theory_tab_active') and self.main_window.is_theory_tab_active():
                        if curr == self.main_window.theory_tab:
                            pdf_widget = getattr(self.main_window.theory_tab, 'pdf_view', None)
                            if pdf_widget is not None:
                                break
                    if hasattr(curr, 'parent'):
                        curr = curr.parent()
                    else:
                        break

                if pdf_widget is not None:
                    dx = event.angleDelta().x()
                    dy = event.angleDelta().y()
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and dy != 0 and dx == 0:
                        dx = dy
                        dy = 0
                    if dy != 0:
                        vbar = pdf_widget.verticalScrollBar()
                        vbar.setValue(vbar.value() - dy)
                    if dx != 0:
                        hbar = pdf_widget.horizontalScrollBar()
                        hbar.setValue(hbar.value() - dx)
                    event.accept()
                    return True

                # 2. Completely block accidental changes on sliders, spinboxes, comboboxes, and tab bars
                curr = obj
                while curr is not None:
                    if isinstance(curr, (QSlider, QAbstractSpinBox, QComboBox, QTabBar)):
                        event.ignore()
                        return True
                    if hasattr(curr, 'parent'):
                        curr = curr.parent()
                    else:
                        break

                # 3. If scrolling over FigureCanvas (Analytics & Histograms tab), route scrolling
                # directly to OpticalZoomView so user can move freely vertically and horizontally
                curr = obj
                is_canvas = False
                while curr is not None:
                    if isinstance(curr, FigureCanvas):
                        is_canvas = True
                        break
                    if hasattr(curr, 'parent'):
                        curr = curr.parent()
                    else:
                        break

                if is_canvas:
                    self.main_window.zoom_view.scroll_by_wheel(event)
                    event.accept()
                    return True

        return super().eventFilter(obj, event)