"""
Integrated PDF-based Educational Theory Tab with Computer Modern LaTeX typesetting,
continuous multi-page rendering, silky-smooth flicker-free zoom, and tab close handling.
"""

import os
import math
import tempfile
from typing import Optional, Tuple, List

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QMarginsF, QSize, QPoint, QRectF, QTimer
from PyQt6.QtGui import (
    QPageSize,
    QPageLayout,
    QTextDocument,
    QFont,
    QCursor,
    QPainter,
    QPixmap,
    QColor,
    QPen,
    QBrush,
    QTransform,
)
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtPdf import QPdfDocument

from core.engine import QueueSimEngine
from .theory_dialog import generate_theory_html
from .widgets import NoWheelComboBox
from .styles import ZOOM_VIEW_STYLESHEET

THEORY_TOPIC_NAMES = [
    ("Exponential Distribution (M)", "Exponential (M)"),
    ("Deterministic Distribution (D)", "Deterministic (D)"),
    ("Uniform Distribution (U)", "Uniform (U)"),
    ("Erlang Distribution (E_k)", "Erlang (E_k)"),
    ("Hyperexponential Distribution (H_2)", "Hyperexponential (H_2)"),
    ("Pareto Distribution (Heavy-Tailed)", "Pareto"),
    ("Stochastic Stability Theory & Ergodicity", "Stability Theory"),
    ("Metric Theory: Server Utilization ρ (Offered Traffic A₀)", "Server Utilization ρ"),
    ("Metric Theory: Avg Traffic in System A (k(t))", "Traffic in System A"),
    ("Metric Theory: Avg Queue Backlog A_c", "Queue Backlog A_c"),
    ("Metric Theory: Avg Sojourn Time δ̄", "Sojourn Time δ̄"),
    ("Metric Theory: Avg Waiting Time η̄ (and ε̄)", "Waiting Time η̄"),
    ("Metric Theory: Blocking Probability π_p", "Blocking Probability π_p"),
    ("Metric Theory: Little's Law Invariance (A = λ_s δ̄)", "Little's Law"),
    ("Metric Theory: Traffic Accounting & Throughput (d(t) / a(t))", "Throughput d(t)/a(t)"),
]


class SmoothPdfView(QGraphicsView):
    """
    Flicker-free, silky smooth PDF viewport using QGraphicsView and 2D affine scaling.
    Eliminates multi-frame tile-clearing flashing during pinch-to-zoom and wheel events,
    clamps minimum zoom strictly to 100% (1.0x), and keeps the document anchored under the pointer.
    """
    zoomChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setStyleSheet(ZOOM_VIEW_STYLESHEET)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)

        self._doc: Optional[QPdfDocument] = None
        self._page_items: List[Tuple[int, QGraphicsPixmapItem, QSize, QGraphicsRectItem]] = []
        self._max_page_width = 595.0
        self._zoom_factor = 1.0
        self._rendered_scale = 2.0
        self._is_panning = False
        self._pan_start = None

        # Debounced re-renderer: when zoom settles, optionally refresh pixmaps at higher DPI if needed
        self._rerender_timer = QTimer(self)
        self._rerender_timer.setSingleShot(True)
        self._rerender_timer.setInterval(150)
        self._rerender_timer.timeout.connect(self._check_rerender)

    def minimumSizeHint(self) -> QSize:
        return QSize(300, 200)

    def setDocument(self, doc: Optional[QPdfDocument]):
        self._doc = doc
        self._rebuild_scene()

    def document(self) -> Optional[QPdfDocument]:
        return self._doc

    def zoomFactor(self) -> float:
        return self._zoom_factor

    def _rebuild_scene(self):
        self._rerender_timer.stop()
        self.scene_obj.clear()
        self._page_items.clear()
        if not self._doc or self._doc.pageCount() == 0:
            self._max_page_width = 595.0
            return

        dpr = self.viewport().devicePixelRatioF() if self.viewport() else 1.0
        self._rendered_scale = max(1.0, self._zoom_factor * dpr)
        gap = 16
        y = gap
        max_w = 0.0

        for i in range(self._doc.pageCount()):
            pts = self._doc.pagePointSize(i)
            pw, ph = pts.width(), pts.height()
            max_w = max(max_w, pw)

            rw = int(round(pw * self._rendered_scale))
            rh = int(round(ph * self._rendered_scale))
            img = self._doc.render(i, QSize(rw, rh))
            pix = QPixmap.fromImage(img)

            # Solid white paper rectangle with subtle border
            bg = self.scene_obj.addRect(
                QRectF(gap, y, pw, ph),
                QPen(QColor("#313244"), 1),
                QBrush(QColor("#ffffff")),
            )
            bg.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

            item = self.scene_obj.addPixmap(pix)
            item.setScale(pw / rw)
            item.setPos(gap, y)
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

            self._page_items.append((i, item, pts, bg))
            y += ph + gap

        self._max_page_width = max_w
        self.scene_obj.setSceneRect(0, 0, max_w + gap * 2, y)
        self.set_absolute_zoom(1.0)

    def set_absolute_zoom(self, zoom: float, anchor_pos: Optional[QPoint] = None):
        target = max(1.0, min(4.0, round(zoom, 2)))
        self._apply_zoom(target, anchor_pos=anchor_pos)

    def apply_zoom_delta(self, delta: float, anchor_pos: Optional[QPoint] = None):
        target = max(1.0, min(4.0, round(self._zoom_factor * (1.0 + delta), 2)))
        self._apply_zoom(target, anchor_pos=anchor_pos)

    def handle_pinch_gesture(self, delta: float, anchor_pos: Optional[QPoint] = None):
        """Silky-smooth, instant gesture zoom without multi-frame tile flashes."""
        self.apply_zoom_delta(delta * 1.5, anchor_pos=anchor_pos)

    def fit_width(self):
        """Fits page width to tab viewport, strictly bounded >= 100%."""
        if self._max_page_width <= 0:
            return
        vp_width = self.viewport().width()
        padding = 32  # 16px left + 16px right
        avail_w = max(100, vp_width - padding)
        fit_zoom = max(1.0, min(4.0, round(avail_w / self._max_page_width, 2)))
        self.set_absolute_zoom(fit_zoom, anchor_pos=QPoint(vp_width // 2, 0))

    def _apply_zoom(self, target: float, anchor_pos: Optional[QPoint] = None):
        if abs(target - self._zoom_factor) < 0.005:
            return

        vp = self.viewport()
        if anchor_pos is None:
            mouse_global = QCursor.pos()
            local_pos = vp.mapFromGlobal(mouse_global)
            if vp.rect().contains(local_pos):
                anchor_pos = local_pos
            else:
                anchor_pos = QPoint(vp.width() // 2, vp.height() // 2)

        # Precise pointer anchoring
        scene_pt = self.mapToScene(anchor_pos)
        self._zoom_factor = target
        self.setTransform(QTransform().scale(target, target))

        new_vp_pt = self.mapFromScene(scene_pt)
        diff = new_vp_pt - anchor_pos
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + diff.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + diff.y())

        self.zoomChanged.emit(self._zoom_factor)
        self._rerender_timer.start(150)

    def _check_rerender(self):
        if not self._doc or self._doc.pageCount() == 0:
            return
        needed_scale = min(4.0, max(2.0, round(self._zoom_factor * 1.25, 2)))
        if abs(needed_scale - self._rendered_scale) >= 0.4:
            self._rendered_scale = needed_scale
            for page_idx, item, pts, _ in self._page_items:
                pw, ph = pts.width(), pts.height()
                rw = int(round(pw * self._rendered_scale))
                rh = int(round(ph * self._rendered_scale))
                img = self._doc.render(page_idx, QSize(rw, rh))
                pix = QPixmap.fromImage(img)
                item.setPixmap(pix)
                item.setScale(pw / rw)

    # Mouse drag-to-pan implementation
    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
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
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = 0.12 if event.angleDelta().y() > 0 else -0.12
            anchor = event.position().toPoint()
            self.apply_zoom_delta(delta, anchor_pos=anchor)
            event.accept()
            return

        dx = event.angleDelta().x()
        dy = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and dy != 0 and dx == 0:
            dx = dy
            dy = 0

        scrolled = False
        if dy != 0:
            vbar = self.verticalScrollBar()
            vbar.setValue(vbar.value() - dy)
            scrolled = True
        if dx != 0:
            hbar = self.horizontalScrollBar()
            hbar.setValue(hbar.value() - dx)
            scrolled = True
        if scrolled:
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        vbar = self.verticalScrollBar()
        hbar = self.horizontalScrollBar()
        step_v = max(24, vbar.singleStep() * 2)
        step_h = max(24, hbar.singleStep() * 2)
        if key == Qt.Key.Key_Down:
            vbar.setValue(vbar.value() + step_v)
            event.accept()
        elif key == Qt.Key.Key_Up:
            vbar.setValue(vbar.value() - step_v)
            event.accept()
        elif key == Qt.Key.Key_Right:
            hbar.setValue(hbar.value() + step_h)
            event.accept()
        elif key == Qt.Key.Key_Left:
            hbar.setValue(hbar.value() - step_h)
            event.accept()
        elif key == Qt.Key.Key_PageDown:
            vbar.setValue(vbar.value() + vbar.pageStep())
            event.accept()
        elif key == Qt.Key.Key_PageUp:
            vbar.setValue(vbar.value() - vbar.pageStep())
            event.accept()
        elif key == Qt.Key.Key_Home:
            vbar.setValue(0)
            event.accept()
        elif key == Qt.Key.Key_End:
            vbar.setValue(vbar.maximum())
            event.accept()
        else:
            super().keyPressEvent(event)


# Backwards compatibility alias
PinchablePdfView = SmoothPdfView


class TheoryPdfTab(QWidget):
    """
    Embedded Tab displaying textbook-grade compiled PDF theory notes.
    Replaces separate popup dialogs and provides in-place educational reading.
    """
    closeRequested = pyqtSignal()

    def __init__(self, engine: QueueSimEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.current_topic_index = 6
        self.current_role = "Arrival"
        self.current_pdf_path: Optional[str] = None
        self.pdf_doc = QPdfDocument(self)

        self._init_ui()

    def minimumSizeHint(self) -> QSize:
        return QSize(300, 200)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        # Initialize Smooth PDF Document Viewport
        self.pdf_view = SmoothPdfView(self)
        self.pdf_view.zoomChanged.connect(self._on_zoom_changed)

        # ---------------------------------------------------------------
        # Top Navigation & Document Controls Bar (Compact & Overflow-Safe)
        # ---------------------------------------------------------------
        top_bar = QWidget()
        top_bar.setFixedHeight(34)
        top_bar.setStyleSheet(
            "background-color: #1e1e2e; border: 1px solid #313244; border-radius: 4px;"
        )
        bar_layout = QHBoxLayout(top_bar)
        bar_layout.setContentsMargins(6, 2, 6, 2)
        bar_layout.setSpacing(6)

        lbl_topic = QLabel("Topic:")
        lbl_topic.setStyleSheet("font-size: 11px; font-weight: bold; color: #89b4fa;")
        bar_layout.addWidget(lbl_topic)

        self.combo_topic = NoWheelComboBox()
        for full_name, _ in THEORY_TOPIC_NAMES:
            self.combo_topic.addItem(full_name)
        self.combo_topic.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.combo_topic.setMinimumWidth(80)
        self.combo_topic.setMaximumWidth(220)
        self.combo_topic.currentIndexChanged.connect(self._on_topic_combo_changed)
        bar_layout.addWidget(self.combo_topic)

        self.lbl_role = QLabel("Role:")
        self.lbl_role.setStyleSheet("font-size: 11px; font-weight: bold; color: #89b4fa;")
        bar_layout.addWidget(self.lbl_role)

        self.combo_role = NoWheelComboBox()
        self.combo_role.addItems(["Arrival (Input)", "Service (Server)"])
        self.combo_role.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.combo_role.setMinimumWidth(70)
        self.combo_role.setMaximumWidth(125)
        self.combo_role.currentIndexChanged.connect(self._on_role_combo_changed)
        bar_layout.addWidget(self.combo_role)

        bar_layout.addSpacing(4)

        # Zoom Controls with embedded helpful tooltips
        tip_text = "Tip: Pinch trackpad or Ctrl+Wheel to zoom. Drag with mouse to pan."

        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setFixedSize(24, 24)
        btn_zoom_out.setToolTip(f"Zoom Out ({tip_text})")
        btn_zoom_out.setStyleSheet("font-weight: bold; font-size: 12px; padding: 0;")
        btn_zoom_out.clicked.connect(lambda: self.pdf_view.apply_zoom_delta(-0.15))
        bar_layout.addWidget(btn_zoom_out)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(38)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_zoom.setStyleSheet("font-size: 10px; font-weight: bold; color: #cdd6f4;")
        bar_layout.addWidget(self.lbl_zoom)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(24, 24)
        btn_zoom_in.setToolTip(f"Zoom In ({tip_text})")
        btn_zoom_in.setStyleSheet("font-weight: bold; font-size: 12px; padding: 0;")
        btn_zoom_in.clicked.connect(lambda: self.pdf_view.apply_zoom_delta(0.15))
        bar_layout.addWidget(btn_zoom_in)

        btn_fit_width = QPushButton("Fit")
        btn_fit_width.setFixedSize(36, 24)
        btn_fit_width.setToolTip(f"Fit to Page Width ({tip_text})")
        btn_fit_width.setStyleSheet("font-size: 10px; padding: 0;")
        btn_fit_width.clicked.connect(self.pdf_view.fit_width)
        bar_layout.addWidget(btn_fit_width)

        btn_reset_zoom = QPushButton("100%")
        btn_reset_zoom.setFixedSize(40, 24)
        btn_reset_zoom.setToolTip("Reset Zoom to 100%")
        btn_reset_zoom.setStyleSheet("font-size: 10px; padding: 0;")
        btn_reset_zoom.clicked.connect(lambda: self.pdf_view.set_absolute_zoom(1.0))
        bar_layout.addWidget(btn_reset_zoom)

        bar_layout.addStretch()

        # Dedicated Prominent "X" Close Button (Always visible on right)
        self.btn_close = QPushButton("✕ Close")
        self.btn_close.setFixedHeight(24)
        self.btn_close.setObjectName("btnCloseTheory")
        self.btn_close.setStyleSheet(
            "QPushButton { background-color: #313244; color: #f38ba8; font-weight: bold; font-size: 11px; "
            "border: 1px solid #f38ba8; border-radius: 4px; padding: 1px 10px; } "
            "QPushButton:hover { background-color: #f38ba8; color: #11111b; }"
        )
        self.btn_close.clicked.connect(self._on_close_clicked)
        bar_layout.addWidget(self.btn_close)

        layout.addWidget(top_bar)

        # PDF Document Viewport
        layout.addWidget(self.pdf_view, stretch=1)

    def _on_zoom_changed(self, factor: float):
        self.lbl_zoom.setText(f"{int(round(factor * 100))}%")

    def _on_close_clicked(self):
        self.closeRequested.emit()

    def _on_topic_combo_changed(self, idx: int):
        role = "Arrival" if self.combo_role.currentIndex() == 0 else "Service"
        self._reload_current(topic_index=idx, role=role)

    def _on_role_combo_changed(self, idx: int):
        role = "Arrival" if idx == 0 else "Service"
        self._reload_current(topic_index=self.combo_topic.currentIndex(), role=role)

    def _reload_current(self, topic_index: int, role: str):
        lam = sum(1.0 / max(1e-6, d.mean()) for d in self.engine.arrival_dists.values() if d is not None)
        mean_s = self.engine.service_dist.mean()
        mu = (1.0 / mean_s) if (not math.isinf(mean_s) and mean_s > 0) else 0.0
        rho = self.engine.get_metrics()['rho']
        self.load_topic(
            topic_index=topic_index,
            role=role,
            rho=rho,
            lam=lam,
            mu=mu,
            m=self.engine.c
        )

    @staticmethod
    def get_short_title(topic_index: int) -> str:
        if 0 <= topic_index < len(THEORY_TOPIC_NAMES):
            return THEORY_TOPIC_NAMES[topic_index][1]
        return "Theory Notes"

    def apply_pinch_zoom(self, delta: float, anchor_pos: Optional[QPoint] = None):
        """Called by GlobalZoomFilter during trackpad pinch gestures."""
        self.pdf_view.handle_pinch_gesture(delta, anchor_pos=anchor_pos)

    def apply_wheel_zoom(self, delta: float, anchor_pos: Optional[QPoint] = None):
        """Called by GlobalZoomFilter during Ctrl+Wheel scrolling."""
        self.pdf_view.apply_zoom_delta(delta, anchor_pos=anchor_pos)

    def load_topic(
        self,
        topic_index: int,
        role: str = "Arrival",
        rho: Optional[float] = None,
        lam: Optional[float] = None,
        mu: Optional[float] = None,
        m: int = 1,
    ):
        """
        Compiles the requested topic into a genuine A4 vector PDF document
        with Computer Modern LaTeX formulas and loads it into the viewer.
        """
        self.current_topic_index = topic_index
        self.current_role = role

        # Sync topic dropdown
        self.combo_topic.blockSignals(True)
        self.combo_topic.setCurrentIndex(topic_index)
        self.combo_topic.blockSignals(False)

        # Show role selector only for distribution topics (0..5)
        is_dist = (topic_index <= 5)
        self.lbl_role.setVisible(is_dist)
        self.combo_role.setVisible(is_dist)
        if is_dist:
            self.combo_role.blockSignals(True)
            self.combo_role.setCurrentIndex(0 if "arr" in role.lower() else 1)
            self.combo_role.blockSignals(False)

        # Generate HTML with Computer Modern LaTeX formulas
        title, html = generate_theory_html(
            topic_index=topic_index,
            role=role,
            engine=self.engine,
            rho=rho,
            lam=lam,
            mu=mu,
            m=m,
            zoom_factor=1.0,
        )

        # Compile HTML into an authentic A4 PDF file with balanced textbook margins
        cache_dir = os.path.join(tempfile.gettempdir(), "argon_sim_theory_pdf")
        os.makedirs(cache_dir, exist_ok=True)
        pdf_path = os.path.join(cache_dir, f"theory_topic_{topic_index}_{role.lower()}.pdf")

        # Detach previous document before writing
        self.pdf_view.setDocument(None)
        self.pdf_doc.close()

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(pdf_path)
        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(8, 12, 8, 12),
            QPageLayout.Unit.Millimeter,
        )
        printer.setPageLayout(layout)

        doc = QTextDocument()
        doc.setDefaultFont(QFont("Cambria"))
        doc.setDocumentMargin(0)
        doc.setPageSize(printer.pageRect(QPrinter.Unit.Point).size())
        doc.setHtml(html)
        doc.print(printer)

        self.current_pdf_path = pdf_path
        self.pdf_doc.load(pdf_path)
        self.pdf_view.setDocument(self.pdf_doc)
        self.pdf_view.fit_width()
        self._on_zoom_changed(self.pdf_view.zoomFactor())
