"""
Custom PyQt6 widgets, touchpad-safe controls, optical 2D camera viewport zoom,
and application-wide gesture event filters.
"""

import hashlib
import hmac

from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
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
    QDialog,
    QLabel,
    QLineEdit,
    QCheckBox,
)
from PyQt6.QtCore import (
    Qt,
    QRectF,
    pyqtSignal,
    pyqtProperty,
    QPropertyAnimation,
    QEasingCurve,
    QEvent,
    QObject,
)
from PyQt6.QtGui import QPainter, QCursor, QColor, QPen, QBrush, QFont
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

    def __init__(self, min_val: int = 1, max_val: int = 100000, default_val: int = 1, parent=None):
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
        self.spin.setFixedSize(58, 26)
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.valueChanged.connect(self.valueChanged.emit)

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(26, 26)
        self.btn_plus.setStyleSheet("font-weight: bold; font-size: 13px; padding: 0;")
        self.btn_plus.clicked.connect(self._increment)

        self.layout.addWidget(self.btn_minus)
        self.layout.addWidget(self.spin)
        self.layout.addWidget(self.btn_plus)
        self.setFixedSize(116, 26)

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

    def setRange(self, min_val: int, max_val: int):
        self.min_val = min_val
        self.max_val = max_val
        self.spin.setRange(min_val, max_val)

    def setMaximum(self, max_val: int):
        self.max_val = max_val
        self.spin.setMaximum(max_val)

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
                global_pos = QCursor.pos()

                # If Theory PDF tab is active in main window AND cursor is over the PDF canvas:
                if hasattr(self.main_window, 'is_theory_tab_active') and self.main_window.is_theory_tab_active():
                    pdf_v = getattr(self.main_window.theory_tab, 'pdf_view', None)
                    if pdf_v is not None and pdf_v.isVisible():
                        vp = pdf_v.viewport()
                        local_pos = vp.mapFromGlobal(global_pos)
                        if vp.rect().contains(local_pos):
                            self.main_window.theory_tab.apply_pinch_zoom(delta, anchor_pos=local_pos)
                            return True

                # If legacy TheoryDialog is open and cursor is within its bounds:
                if TheoryDialog.current_instance is not None:
                    dlg = TheoryDialog.current_instance
                    if dlg.isVisible() and dlg.rect().contains(dlg.mapFromGlobal(global_pos)):
                        dlg.apply_dialog_zoom(delta)
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

                # Outside the theory canvas (e.g. left parameters bar, header, or tabs): zoom the entire window
                self.main_window.adjust_page_zoom(delta * 5.0)
                return True

        # 2. Touchpad Scrolling and Mouse Wheel Events
        elif event.type() == QEvent.Type.Wheel:
            # Ctrl + Wheel: Zoom application viewport or active dialog/tab
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = 0.12 if event.angleDelta().y() > 0 else -0.12
                global_pos = QCursor.pos()

                # If Theory PDF tab is active in main window AND cursor is over the PDF canvas:
                if hasattr(self.main_window, 'is_theory_tab_active') and self.main_window.is_theory_tab_active():
                    pdf_v = getattr(self.main_window.theory_tab, 'pdf_view', None)
                    if pdf_v is not None and pdf_v.isVisible():
                        vp = pdf_v.viewport()
                        local_pos = vp.mapFromGlobal(global_pos)
                        if vp.rect().contains(local_pos):
                            self.main_window.theory_tab.apply_wheel_zoom(delta, anchor_pos=local_pos)
                            return True

                # If legacy TheoryDialog is open and cursor is within its bounds:
                if TheoryDialog.current_instance is not None:
                    dlg = TheoryDialog.current_instance
                    if dlg.isVisible() and dlg.rect().contains(dlg.mapFromGlobal(global_pos)):
                        if delta > 0:
                            dlg.zoom_in(1)
                        else:
                            dlg.zoom_out(1)
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

                # Outside the theory canvas (e.g. left parameters bar, header, or tabs): zoom the entire window
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


PRACTICE_MODE_HASH = "5eb393af7364234c00d45b9e93b52c6d602c14a8ade3e203636f14785714a15b"


class ModeToggleSlider(QWidget):
    """
    Top-right sliding toggle switch to distinguish between Exam Mode and Practice Mode.
    Hovering in Exam Mode displays "Unlock practice mode".
    Clicking in Exam Mode triggers a modal password prompt to activate Practice Mode.
    Clicking in Practice Mode relocks the system back to Exam Mode.
    """
    modeToggleRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._is_practice = False
        self._knob_pos = 0.0  # 0.0 = Exam (left), 1.0 = Practice (right)

        self.anim = QPropertyAnimation(self, b"knob_position", self)
        self.anim.setDuration(160)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._update_tooltip()

    @pyqtProperty(float)
    def knob_position(self) -> float:
        return self._knob_pos

    @knob_position.setter
    def knob_position(self, val: float):
        self._knob_pos = max(0.0, min(1.0, val))
        self.update()

    def is_practice(self) -> bool:
        return self._is_practice

    def set_practice_mode(self, practice: bool, animate: bool = True):
        self._is_practice = practice
        target = 1.0 if practice else 0.0
        if animate:
            self.anim.stop()
            self.anim.setStartValue(self._knob_pos)
            self.anim.setEndValue(target)
            self.anim.start()
        else:
            self._knob_pos = target
            self.update()
        self._update_tooltip()

    def _update_tooltip(self):
        if not self._is_practice:
            self.setToolTip("Unlock practice mode")
        else:
            self.setToolTip("Lock exam mode (Practice mode active)")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.modeToggleRequested.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Outer background pill container
        bg_col = QColor("#181825")
        border_col = QColor("#a6e3a1" if self._is_practice else "#45475a")
        painter.setPen(QPen(border_col, 1))
        painter.setBrush(QBrush(bg_col))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 12, 12)

        # Mode Text on the Left
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        if self._is_practice:
            painter.setPen(QColor("#a6e3a1"))
            painter.drawText(
                QRectF(10, 1, 80, h - 2),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                "PRACTICE",
            )
        else:
            painter.setPen(QColor("#f38ba8"))
            painter.drawText(
                QRectF(10, 1, 80, h - 2),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                "EXAM MODE",
            )

        # Sliding Track on the Right
        sw_w = 42
        sw_h = 18
        sw_x = w - sw_w - 6
        sw_y = (h - sw_h) / 2

        track_col = QColor("#313244") if not self._is_practice else QColor("#a6e3a1")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_col))
        painter.drawRoundedRect(QRectF(sw_x, sw_y, sw_w, sw_h), sw_h / 2, sw_h / 2)

        # Sliding Knob
        knob_dia = 14
        min_kx = sw_x + 2
        max_kx = sw_x + sw_w - knob_dia - 2
        kx = min_kx + self._knob_pos * (max_kx - min_kx)
        ky = sw_y + 2

        knob_col = QColor("#ffffff") if not self._is_practice else QColor("#11111b")
        painter.setBrush(QBrush(knob_col))
        painter.drawEllipse(QRectF(kx, ky, knob_dia, knob_dia))
        painter.end()


class UnlockPracticeDialog(QDialog):
    """
    Modal authentication dialog prompting for password to unlock Practice Mode.
    Password hash is cryptographically validated without plain text in source code.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unlock Practice Mode")
        self.setFixedSize(390, 210)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")

        vl = QVBoxLayout(self)
        vl.setContentsMargins(20, 18, 20, 18)
        vl.setSpacing(10)

        lbl_title = QLabel("Unlock Practice Mode")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #89b4fa;")
        vl.addWidget(lbl_title)

        lbl_desc = QLabel("Enter instructor password to enable Practice Mode and unlock theory tabs:")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("font-size: 10px; color: #a6adc8;")
        vl.addWidget(lbl_desc)

        self.input_pwd = QLineEdit()
        self.input_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pwd.setPlaceholderText("Enter password...")
        self.input_pwd.setStyleSheet(
            "background-color: #181825; border: 1px solid #45475a; border-radius: 4px; "
            "padding: 6px; color: #cdd6f4; font-size: 11px;"
        )
        self.input_pwd.returnPressed.connect(self._verify_and_accept)
        vl.addWidget(self.input_pwd)

        self.chk_show = QCheckBox("Show password")
        self.chk_show.setStyleSheet("font-size: 10px; color: #a6adc8;")
        self.chk_show.toggled.connect(
            lambda s: self.input_pwd.setEchoMode(
                QLineEdit.EchoMode.Normal if s else QLineEdit.EchoMode.Password
            )
        )
        vl.addWidget(self.chk_show)

        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet("color: #f38ba8; font-size: 10px; font-weight: bold;")
        self.lbl_err.hide()
        vl.addWidget(self.lbl_err)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background-color: #313244; color: #cdd6f4; font-size: 11px; padding: 5px 12px;")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_unlock = QPushButton("Unlock")
        btn_unlock.setStyleSheet(
            "background-color: #a6e3a1; color: #11111b; font-size: 11px; font-weight: bold; padding: 5px 16px; border-radius: 4px;"
        )
        btn_unlock.clicked.connect(self._verify_and_accept)
        btn_row.addWidget(btn_unlock)

        vl.addLayout(btn_row)

    def _verify_and_accept(self):
        cand = self.input_pwd.text().strip()
        cand_hash = hashlib.sha256(cand.encode("utf-8")).hexdigest()
        if hmac.compare_digest(cand_hash, PRACTICE_MODE_HASH):
            self.accept()
        else:
            self.lbl_err.setText("Incorrect password. Practice mode remains locked.")
            self.lbl_err.show()
            self.input_pwd.selectAll()
            self.input_pwd.setFocus()