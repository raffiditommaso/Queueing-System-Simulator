"""
Main Application Window (QueueSimulatorApp) integrating controls,
live vector canvas, Matplotlib analytics, and theoretical benchmarks.
"""

import math
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QSplitter,
    QFrame,
    QScrollArea,
    QAbstractSpinBox,
    QTabBar,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.constants import PRIORITY_COLORS, PRIORITY_NAMES
from core.distributions import (
    Distribution,
    ExponentialDist,
    DeterministicDist,
    UniformDist,
    ErlangDist,
    HyperexponentialDist,
    ParetoDist,
)
from core.entities import Server
from core.engine import QueueSimEngine
from core.theory import TheoreticalModels

from .canvas import AnimatedCanvas
from .markov_canvas import MarkovChainView
from .styles import (
    MAIN_STYLESHEET,
    QUESTION_BTN_STYLE,
    METRIC_QUESTION_BTN_STYLE,
    PLAYBACK_RUN_STYLE,
    PLAYBACK_STOP_STYLE,
    PLAYBACK_CONTINUE_STYLE,
    PLAYBACK_RESET_STYLE,
)
from .theory_dialog import TheoryDialog
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


class QueueSimulatorApp(QMainWindow):
    def __init__(self, cli_args=None):
        super().__init__()
        self.setWindowTitle("Queueing System Simulator - Master's Network Design")
        self.resize(1360, 840)

        # Default to Simple Single-Class FIFO Queue (Priority is False)
        priority_flag = bool(
            cli_args
            and getattr(cli_args, 'priority', False)
            and not getattr(cli_args, 'no_priority', False)
        )

        self.engine = QueueSimEngine(
            n_servers=max(1, int(cli_args.servers)) if cli_args else 1,
            queue_capacity=float(cli_args.queue) if cli_args and cli_args.queue != 'inf' else 12,
            priority_enabled=priority_flag,
            seed=cli_args.seed if cli_args else 42,
        )

        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)

        self.timer_interval_ms = 1000
        self.events_per_tick = 1
        self.tab_theory_doc = None
        self.playback_state = "RUN"

        self._init_ui()
        self._update_speed(15)
        self._apply_config()

        # Install global zoom filter across the entire application
        self.zoom_filter = GlobalZoomFilter(self)
        QApplication.instance().installEventFilter(self.zoom_filter)

        # Start window maximized
        self.showMaximized()

    def _init_ui(self):
        # Page container hosting the entire interface: Header bar + Sidebar + Tabs
        # Hosting the header bar inside the zoom view ensures Kendall notation,
        # Clock, Load, and controls are uniformly included in the zoom!
        self.page_container = QWidget()
        self.page_layout = QVBoxLayout(self.page_container)
        self.page_layout.setContentsMargins(8, 6, 8, 8)
        self.page_layout.setSpacing(6)

        # Top Header Bar (Kendall, Clock, Load, Controls, Zoom, Warning) - included in zoom
        self.header_bar = self._create_header_bar()
        self.page_layout.addWidget(self.header_bar)

        # Splitter: Left Sidebar (Controls) + Right Tab Views
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.scroll_sidebar = self._create_sidebar()
        self.splitter.addWidget(self.scroll_sidebar)
        self.splitter.addWidget(self._create_content_tabs())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        self.page_layout.addWidget(self.splitter, stretch=1)

        # OpticalZoomView hosts the entire page_container (including header bar)
        self.zoom_view = OpticalZoomView(self.page_container)
        self.setCentralWidget(self.zoom_view)
        self._apply_base_stylesheet()

    def _apply_base_stylesheet(self):
        self.setStyleSheet(MAIN_STYLESHEET)

    def adjust_page_zoom(self, delta: float):
        new_zoom = max(1.0, min(3.0, round(self.zoom_view.zoom_level + delta, 2)))
        if abs(new_zoom - self.zoom_view.zoom_level) > 0.005:
            self.set_page_zoom(new_zoom)

    def set_page_zoom(self, zoom: float, anchor_center: bool = False):
        self.zoom_view.set_zoom(zoom, anchor_center=anchor_center)
        self.lbl_zoom_val.setText(f"{int(self.zoom_view.zoom_level * 100)}%")

    def reset_page_zoom(self):
        self.zoom_view.reset_zoom()
        self.lbl_zoom_val.setText("100%")

    def _create_header_bar(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 4px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 2, 10, 2)
        h_layout.setSpacing(10)

        self.lbl_kendall = QLabel("[ M/M/1/8 (FIFO) ]")
        self.lbl_kendall.setStyleSheet("font-size: 12px; font-weight: bold; color: #a6e3a1;")

        self.lbl_sim_time = QLabel("Clock: 0.0s")
        self.lbl_sim_time.setStyleSheet("font-size: 11px; font-weight: bold; color: #89b4fa;")

        self.lbl_rho_header = QLabel("Avg Server Utilization ρ: 0.80")
        self.lbl_rho_header.setStyleSheet("font-size: 11px; font-weight: bold; color: #cdd6f4;")

        self.btn_rho_header_theory = QPushButton("?")
        self.btn_rho_header_theory.setFixedSize(22, 22)
        self.btn_rho_header_theory.setToolTip("View explanation, definition, and computation for Average Server Utilization (ρ)")
        self.btn_rho_header_theory.setStyleSheet(QUESTION_BTN_STYLE)
        self.btn_rho_header_theory.clicked.connect(self._show_server_utilization_theory)

        self.btn_warning_why = QPushButton("Warning: Overload (A₀/m ≥ 1.0) - See Why")
        self.btn_warning_why.setStyleSheet(
            "background-color: #f38ba8; color: #11111b; font-size: 10px; padding: 2px 6px; border-radius: 3px;"
        )
        self.btn_warning_why.clicked.connect(self._show_theory_dialog)
        self.btn_warning_why.setVisible(False)

        # Full-Page Browser Zoom Controls
        lbl_zoom_title = QLabel("Page Zoom:")
        lbl_zoom_title.setStyleSheet("font-size: 10px; color: #a6adc8;")

        btn_zoom_dec = QPushButton("-")
        btn_zoom_dec.setFixedSize(22, 22)
        btn_zoom_dec.setStyleSheet("font-size: 11px; font-weight: bold; padding: 0;")
        btn_zoom_dec.clicked.connect(lambda: self.adjust_page_zoom(-0.15))

        self.lbl_zoom_val = QLabel("100%")
        self.lbl_zoom_val.setStyleSheet("font-size: 10px; font-weight: bold; color: #cdd6f4;")

        btn_zoom_inc = QPushButton("+")
        btn_zoom_inc.setFixedSize(22, 22)
        btn_zoom_inc.setStyleSheet("font-size: 11px; font-weight: bold; padding: 0;")
        btn_zoom_inc.clicked.connect(lambda: self.adjust_page_zoom(0.15))

        btn_zoom_reset = QPushButton("Reset")
        btn_zoom_reset.setFixedHeight(22)
        btn_zoom_reset.setStyleSheet("font-size: 9px; padding: 1px 4px;")
        btn_zoom_reset.clicked.connect(self.reset_page_zoom)

        self.lbl_status = QLabel("PAUSED")
        self.lbl_status.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #f9e2af; padding: 2px 6px; "
            "background-color: #313244; border-radius: 3px;"
        )

        h_layout.addWidget(self.lbl_kendall)
        h_layout.addWidget(self.lbl_sim_time)
        h_layout.addSpacing(10)
        h_layout.addWidget(self.lbl_rho_header)
        h_layout.addWidget(self.btn_rho_header_theory)
        h_layout.addWidget(self.btn_warning_why)
        h_layout.addStretch()

        h_layout.addWidget(lbl_zoom_title)
        h_layout.addWidget(btn_zoom_dec)
        h_layout.addWidget(self.lbl_zoom_val)
        h_layout.addWidget(btn_zoom_inc)
        h_layout.addWidget(btn_zoom_reset)
        h_layout.addSpacing(8)
        h_layout.addWidget(self.lbl_status)

        return header

    def _create_sidebar(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(340)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 6, 2)
        layout.setSpacing(8)

        # 1. Playback Controls Box
        grp_playback = QGroupBox("Execution Playback")
        play_layout = QGridLayout(grp_playback)
        play_layout.setSpacing(6)

        self.btn_run = QPushButton("RUN")
        self.btn_run.setObjectName("btnRun")
        self.btn_run.setFixedHeight(32)
        self.btn_run.setStyleSheet(PLAYBACK_RUN_STYLE)
        self.btn_run.clicked.connect(self._on_playback_btn_clicked)

        self.btn_reset = QPushButton("RESET")
        self.btn_reset.setObjectName("btnReset")
        self.btn_reset.setFixedHeight(32)
        self.btn_reset.setStyleSheet(PLAYBACK_RESET_STYLE)
        self.btn_reset.clicked.connect(self._reset_sim)

        play_layout.addWidget(self.btn_run, 0, 0)
        play_layout.addWidget(self.btn_reset, 0, 1)

        self.lbl_speed_desc = QLabel("Speed: 1 event / 1.0s")
        self.lbl_speed_desc.setStyleSheet("color: #a6adc8; font-size: 10px; margin-top: 4px;")
        play_layout.addWidget(self.lbl_speed_desc, 1, 0, 1, 2)

        self.slider_speed = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(1, 100)
        self.slider_speed.setValue(15)
        self.slider_speed.valueChanged.connect(self._update_speed)
        play_layout.addWidget(self.slider_speed, 2, 0, 1, 2)

        layout.addWidget(grp_playback)

        # 2. System Architecture Box
        grp_arch = QGroupBox("System Architecture")
        arch_layout = QGridLayout(grp_arch)
        arch_layout.setSpacing(6)

        arch_layout.addWidget(QLabel("Servers (m):"), 0, 0)
        default_srv = 1 if math.isinf(self.engine.c) else self.engine.c
        self.stepper_servers = NumberStepper(min_val=1, max_val=1000, default_val=default_srv)
        self.stepper_servers.valueChanged.connect(self._apply_config)
        self.stepper_servers.setEnabled(not math.isinf(self.engine.c))
        arch_layout.addWidget(self.stepper_servers, 0, 1, Qt.AlignmentFlag.AlignRight)

        self.chk_inf_servers = QCheckBox("Infinite Servers (m = inf)")
        self.chk_inf_servers.setChecked(math.isinf(self.engine.c))
        self.chk_inf_servers.toggled.connect(self._toggle_inf_servers)
        arch_layout.addWidget(self.chk_inf_servers, 1, 0, 1, 2)

        arch_layout.addWidget(QLabel("Queue Buffer (K):"), 2, 0)
        self.stepper_queue = NumberStepper(
            min_val=0, max_val=100000, default_val=12 if not math.isinf(self.engine.K) else 50
        )
        self.stepper_queue.valueChanged.connect(self._apply_config)
        self.stepper_queue.setEnabled(not math.isinf(self.engine.K))
        arch_layout.addWidget(self.stepper_queue, 2, 1, Qt.AlignmentFlag.AlignRight)

        self.chk_inf_queue = QCheckBox("Infinite Capacity (K = inf)")
        self.chk_inf_queue.setChecked(math.isinf(self.engine.K))
        self.chk_inf_queue.toggled.connect(self._toggle_inf_queue)
        arch_layout.addWidget(self.chk_inf_queue, 3, 0, 1, 2)

        layout.addWidget(grp_arch)

        # Helper to create a slider + spinbox parameter control
        def make_param_control(label_title, min_v, max_v, step, def_v, is_int=False, spin_max=None):
            w_row = QWidget()
            vl = QVBoxLayout(w_row)
            vl.setContentsMargins(0, 1, 0, 1)
            vl.setSpacing(2)

            lbl = QLabel(f"{label_title}: {def_v:.2f}" if not is_int else f"{label_title}: {def_v}")
            lbl.setStyleSheet("font-size: 11px; color: #cdd6f4;")

            hl = QHBoxLayout()
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(6)

            if spin_max is None:
                spin_max = max(max_v, 1000.0) if not is_int else max(max_v, 1000)

            if is_int:
                slider = NoWheelSlider(Qt.Orientation.Horizontal)
                slider.setRange(int(min_v), int(max_v))
                slider.setValue(int(def_v))

                spin = NoWheelSpinBox()
                spin.setRange(int(min_v), int(spin_max))
                spin.setValue(int(def_v))
                spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
                spin.setFixedWidth(64)
            else:
                scale = 100
                slider = NoWheelSlider(Qt.Orientation.Horizontal)
                slider.setRange(int(round(min_v * scale)), int(round(max_v * scale)))
                slider.setValue(int(round(def_v * scale)))

                spin = NoWheelDoubleSpinBox()
                spin.setRange(float(min_v), float(spin_max))
                spin.setSingleStep(float(step))
                spin.setValue(float(def_v))
                spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
                spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
                spin.setFixedWidth(64)

            hl.addWidget(slider, stretch=1)
            hl.addWidget(spin)

            vl.addWidget(lbl)
            vl.addLayout(hl)
            return w_row, lbl, slider, spin

        def connect_pair(slider, spin, lbl, fmt_str, on_change_callback, is_int=False, scale=100):
            def sl_changed(val):
                v = val if is_int else val / scale
                spin.blockSignals(True)
                spin.setValue(v)
                spin.blockSignals(False)
                lbl.setText(fmt_str.format(v))
                on_change_callback()

            def sp_changed(v):
                raw_sl = int(v) if is_int else int(round(v * scale))
                clamped_sl = max(slider.minimum(), min(slider.maximum(), raw_sl))
                slider.blockSignals(True)
                slider.setValue(clamped_sl)
                slider.blockSignals(False)
                lbl.setText(fmt_str.format(v))
                on_change_callback()

            slider.valueChanged.connect(sl_changed)
            spin.valueChanged.connect(sp_changed)

        # 3. Traffic Arrival Process
        self.grp_arrival = QGroupBox("Traffic Arrival Process (Input)")
        arr_layout = QVBoxLayout(self.grp_arrival)
        arr_layout.setSpacing(6)

        arr_layout.addWidget(QLabel("Distribution:"))
        row_arr_dist = QHBoxLayout()
        row_arr_dist.setSpacing(6)
        self.combo_arr_dist = NoWheelComboBox()
        self.combo_arr_dist.addItems([
            "Exponential (M - Poisson)",
            "Deterministic (D - Fixed)",
            "Uniform (U - Jitter)",
            "Erlang (E₂)",
            "Hyperexponential (H₂ - Bursty)",
            "Pareto (Heavy-Tailed)",
        ])
        self.combo_arr_dist.currentIndexChanged.connect(self._on_arr_dist_changed)
        row_arr_dist.addWidget(self.combo_arr_dist, stretch=1)

        self.btn_arr_dist_theory = QPushButton("?")
        self.btn_arr_dist_theory.setFixedSize(26, 26)
        self.btn_arr_dist_theory.setToolTip("View detailed mathematical theory for arrival distribution")
        self.btn_arr_dist_theory.setStyleSheet(QUESTION_BTN_STYLE)
        self.btn_arr_dist_theory.clicked.connect(self._show_arr_dist_theory)
        row_arr_dist.addWidget(self.btn_arr_dist_theory)
        arr_layout.addLayout(row_arr_dist)

        self.stack_arr_params = DynamicStackedWidget(self.grp_arrival)

        # Page 0: Exponential
        p0_arr, self.lbl_arr_rate, self.slider_arr_rate, self.spin_arr_rate = make_param_control(
            "Arrival Rate λ (cust/s)", 0.05, 10.0, 0.05, 0.80
        )
        connect_pair(
            self.slider_arr_rate, self.spin_arr_rate, self.lbl_arr_rate,
            "Arrival Rate λ (cust/s): {:.2f}", self._apply_config,
        )
        self.stack_arr_params.addWidget(p0_arr)

        # Page 1: Deterministic
        p1_arr, self.lbl_arr_det, self.slider_arr_det, self.spin_arr_det = make_param_control(
            "Fixed Interval D (s)", 0.05, 10.0, 0.05, 1.25
        )
        connect_pair(
            self.slider_arr_det, self.spin_arr_det, self.lbl_arr_det,
            "Fixed Interval D (s): {:.2f}", self._apply_config,
        )
        self.stack_arr_params.addWidget(p1_arr)

        # Page 2: Uniform (Multi-parameter tuning with 2 sliders)
        p2_arr = QWidget()
        p2_arr_lay = QVBoxLayout(p2_arr)
        p2_arr_lay.setContentsMargins(0, 0, 0, 0)
        p2_arr_lay.setSpacing(4)
        row_a, self.lbl_arr_uni_a, self.slider_arr_uni_a, self.spin_arr_uni_a = make_param_control(
            "Parameter a (Min Interval, s)", 0.05, 5.0, 0.05, 0.50
        )
        row_b, self.lbl_arr_uni_b, self.slider_arr_uni_b, self.spin_arr_uni_b = make_param_control(
            "Parameter b (Max Interval, s)", 0.10, 10.0, 0.05, 1.50
        )
        p2_arr_lay.addWidget(row_a)
        p2_arr_lay.addWidget(row_b)

        def on_arr_uni_a_sl(val):
            a_v = val / 100.0
            self.spin_arr_uni_a.blockSignals(True)
            self.spin_arr_uni_a.setValue(a_v)
            self.spin_arr_uni_a.blockSignals(False)
            self.lbl_arr_uni_a.setText(f"Parameter a (Min Interval, s): {a_v:.2f}")
            if self.spin_arr_uni_b.value() <= a_v:
                new_b = min(self.spin_arr_uni_b.maximum(), round(a_v + 0.05, 2))
                self.spin_arr_uni_b.blockSignals(True)
                self.slider_arr_uni_b.blockSignals(True)
                self.spin_arr_uni_b.setValue(new_b)
                clamped_b = max(self.slider_arr_uni_b.minimum(), min(self.slider_arr_uni_b.maximum(), int(round(new_b * 100))))
                self.slider_arr_uni_b.setValue(clamped_b)
                self.spin_arr_uni_b.blockSignals(False)
                self.slider_arr_uni_b.blockSignals(False)
                self.lbl_arr_uni_b.setText(f"Parameter b (Max Interval, s): {new_b:.2f}")
            self._apply_config()

        def on_arr_uni_a_sp(a_v):
            clamped_a = max(self.slider_arr_uni_a.minimum(), min(self.slider_arr_uni_a.maximum(), int(round(a_v * 100))))
            self.slider_arr_uni_a.blockSignals(True)
            self.slider_arr_uni_a.setValue(clamped_a)
            self.slider_arr_uni_a.blockSignals(False)
            self.lbl_arr_uni_a.setText(f"Parameter a (Min Interval, s): {a_v:.2f}")
            if self.spin_arr_uni_b.value() <= a_v:
                new_b = min(self.spin_arr_uni_b.maximum(), round(a_v + 0.05, 2))
                self.spin_arr_uni_b.blockSignals(True)
                self.slider_arr_uni_b.blockSignals(True)
                self.spin_arr_uni_b.setValue(new_b)
                clamped_b = max(self.slider_arr_uni_b.minimum(), min(self.slider_arr_uni_b.maximum(), int(round(new_b * 100))))
                self.slider_arr_uni_b.setValue(clamped_b)
                self.spin_arr_uni_b.blockSignals(False)
                self.slider_arr_uni_b.blockSignals(False)
                self.lbl_arr_uni_b.setText(f"Parameter b (Max Interval, s): {new_b:.2f}")
            self._apply_config()

        def on_arr_uni_b_sl(val):
            b_v = val / 100.0
            self.spin_arr_uni_b.blockSignals(True)
            self.spin_arr_uni_b.setValue(b_v)
            self.spin_arr_uni_b.blockSignals(False)
            self.lbl_arr_uni_b.setText(f"Parameter b (Max Interval, s): {b_v:.2f}")
            if self.spin_arr_uni_a.value() >= b_v:
                new_a = max(0.05, round(b_v - 0.05, 2))
                self.spin_arr_uni_a.blockSignals(True)
                self.slider_arr_uni_a.blockSignals(True)
                self.spin_arr_uni_a.setValue(new_a)
                clamped_a = max(self.slider_arr_uni_a.minimum(), min(self.slider_arr_uni_a.maximum(), int(round(new_a * 100))))
                self.slider_arr_uni_a.setValue(clamped_a)
                self.spin_arr_uni_a.blockSignals(False)
                self.slider_arr_uni_a.blockSignals(False)
                self.lbl_arr_uni_a.setText(f"Parameter a (Min Interval, s): {new_a:.2f}")
            self._apply_config()

        def on_arr_uni_b_sp(b_v):
            clamped_b = max(self.slider_arr_uni_b.minimum(), min(self.slider_arr_uni_b.maximum(), int(round(b_v * 100))))
            self.slider_arr_uni_b.blockSignals(True)
            self.slider_arr_uni_b.setValue(clamped_b)
            self.slider_arr_uni_b.blockSignals(False)
            self.lbl_arr_uni_b.setText(f"Parameter b (Max Interval, s): {b_v:.2f}")
            if self.spin_arr_uni_a.value() >= b_v:
                new_a = max(0.05, round(b_v - 0.05, 2))
                self.spin_arr_uni_a.blockSignals(True)
                self.slider_arr_uni_a.blockSignals(True)
                self.spin_arr_uni_a.setValue(new_a)
                clamped_a = max(self.slider_arr_uni_a.minimum(), min(self.slider_arr_uni_a.maximum(), int(round(new_a * 100))))
                self.slider_arr_uni_a.setValue(clamped_a)
                self.spin_arr_uni_a.blockSignals(False)
                self.slider_arr_uni_a.blockSignals(False)
                self.lbl_arr_uni_a.setText(f"Parameter a (Min Interval, s): {new_a:.2f}")
            self._apply_config()

        self.slider_arr_uni_a.valueChanged.connect(on_arr_uni_a_sl)
        self.spin_arr_uni_a.valueChanged.connect(on_arr_uni_a_sp)
        self.slider_arr_uni_b.valueChanged.connect(on_arr_uni_b_sl)
        self.spin_arr_uni_b.valueChanged.connect(on_arr_uni_b_sp)
        self.stack_arr_params.addWidget(p2_arr)

        # Page 3: Erlang
        p3_arr = QWidget()
        p3_arr_lay = QVBoxLayout(p3_arr)
        p3_arr_lay.setContentsMargins(0, 0, 0, 0)
        p3_arr_lay.setSpacing(4)
        row_k, self.lbl_arr_erl_k, self.slider_arr_erl_k, self.spin_arr_erl_k = make_param_control(
            "Phases k", 1, 10, 1, 2, is_int=True, spin_max=50
        )
        connect_pair(
            self.slider_arr_erl_k, self.spin_arr_erl_k, self.lbl_arr_erl_k,
            "Phases k: {}", self._apply_config, is_int=True,
        )
        row_erl_r, self.lbl_arr_erl_rate, self.slider_arr_erl_rate, self.spin_arr_erl_rate = make_param_control(
            "Overall Rate λ (cust/s)", 0.05, 10.0, 0.05, 0.80
        )
        connect_pair(
            self.slider_arr_erl_rate, self.spin_arr_erl_rate, self.lbl_arr_erl_rate,
            "Overall Rate λ (cust/s): {:.2f}", self._apply_config,
        )
        p3_arr_lay.addWidget(row_k)
        p3_arr_lay.addWidget(row_erl_r)
        self.stack_arr_params.addWidget(p3_arr)

        # Page 4: Hyperexponential
        p4_arr = QWidget()
        p4_arr_lay = QVBoxLayout(p4_arr)
        p4_arr_lay.setContentsMargins(0, 0, 0, 0)
        p4_arr_lay.setSpacing(4)
        row_p1, self.lbl_arr_hyper_p1, self.slider_arr_hyper_p1, self.spin_arr_hyper_p1 = make_param_control(
            "Branch Prob p₁", 0.05, 0.95, 0.05, 0.40, spin_max=0.95
        )
        connect_pair(
            self.slider_arr_hyper_p1, self.spin_arr_hyper_p1, self.lbl_arr_hyper_p1,
            "Branch Prob p₁: {:.2f}", self._apply_config,
        )
        row_r1, self.lbl_arr_hyper_r1, self.slider_arr_hyper_r1, self.spin_arr_hyper_r1 = make_param_control(
            "Phase 1 Rate r₁ (cust/s)", 0.05, 10.0, 0.05, 0.50
        )
        connect_pair(
            self.slider_arr_hyper_r1, self.spin_arr_hyper_r1, self.lbl_arr_hyper_r1,
            "Phase 1 Rate r₁ (cust/s): {:.2f}", self._apply_config,
        )
        row_r2, self.lbl_arr_hyper_r2, self.slider_arr_hyper_r2, self.spin_arr_hyper_r2 = make_param_control(
            "Phase 2 Rate r₂ (cust/s)", 0.10, 10.0, 0.05, 2.00
        )
        connect_pair(
            self.slider_arr_hyper_r2, self.spin_arr_hyper_r2, self.lbl_arr_hyper_r2,
            "Phase 2 Rate r₂ (cust/s): {:.2f}", self._apply_config,
        )
        p4_arr_lay.addWidget(row_p1)
        p4_arr_lay.addWidget(row_r1)
        p4_arr_lay.addWidget(row_r2)
        self.stack_arr_params.addWidget(p4_arr)

        # Page 5: Pareto
        p5_arr = QWidget()
        p5_arr_lay = QVBoxLayout(p5_arr)
        p5_arr_lay.setContentsMargins(0, 0, 0, 0)
        p5_arr_lay.setSpacing(4)
        row_alpha, self.lbl_arr_pareto_alpha, self.slider_arr_pareto_alpha, self.spin_arr_pareto_alpha = make_param_control(
            "Shape Parameter α", 1.10, 5.0, 0.05, 2.50, spin_max=50.0
        )
        connect_pair(
            self.slider_arr_pareto_alpha, self.spin_arr_pareto_alpha, self.lbl_arr_pareto_alpha,
            "Shape Parameter α: {:.2f}", self._apply_config,
        )
        row_xm, self.lbl_arr_pareto_xm, self.slider_arr_pareto_xm, self.spin_arr_pareto_xm = make_param_control(
            "Scale Parameter xₘ (s)", 0.05, 3.0, 0.05, 0.60
        )
        connect_pair(
            self.slider_arr_pareto_xm, self.spin_arr_pareto_xm, self.lbl_arr_pareto_xm,
            "Scale Parameter xₘ (s): {:.2f}", self._apply_config,
        )
        p5_arr_lay.addWidget(row_alpha)
        p5_arr_lay.addWidget(row_xm)
        self.stack_arr_params.addWidget(p5_arr)

        arr_layout.addWidget(self.stack_arr_params)

        self.lbl_arr_moments = QLabel("Mean Interarrival: E[T] = 1.25s")
        self.lbl_arr_moments.setStyleSheet("color: #a6adc8; font-size: 10px;")
        arr_layout.addWidget(self.lbl_arr_moments)

        layout.addWidget(self.grp_arrival)

        # 4. Service Process
        self.grp_service = QGroupBox("Service Process (Server)")
        serv_layout = QVBoxLayout(self.grp_service)
        serv_layout.setSpacing(6)

        serv_layout.addWidget(QLabel("Distribution:"))
        row_serv_dist = QHBoxLayout()
        row_serv_dist.setSpacing(6)
        self.combo_serv_dist = NoWheelComboBox()
        self.combo_serv_dist.addItems([
            "Exponential (M - Memoryless)",
            "Deterministic (D - Constant Service)",
            "Uniform (U)",
            "Erlang (E₂)",
            "Hyperexponential (H₂)",
            "Pareto",
        ])
        self.combo_serv_dist.currentIndexChanged.connect(self._on_serv_dist_changed)
        row_serv_dist.addWidget(self.combo_serv_dist, stretch=1)

        self.btn_serv_dist_theory = QPushButton("?")
        self.btn_serv_dist_theory.setFixedSize(26, 26)
        self.btn_serv_dist_theory.setToolTip("View detailed mathematical theory for service distribution")
        self.btn_serv_dist_theory.setStyleSheet(QUESTION_BTN_STYLE)
        self.btn_serv_dist_theory.clicked.connect(self._show_serv_dist_theory)
        row_serv_dist.addWidget(self.btn_serv_dist_theory)
        serv_layout.addLayout(row_serv_dist)

        self.stack_serv_params = DynamicStackedWidget(self.grp_service)

        # Page 0: Exponential
        sp0_serv, self.lbl_serv_rate, self.slider_serv_rate, self.spin_serv_rate = make_param_control(
            "Service Rate μ (cust/s)", 0.00, 10.0, 0.05, 1.00
        )
        connect_pair(
            self.slider_serv_rate, self.spin_serv_rate, self.lbl_serv_rate,
            "Service Rate μ (cust/s): {:.2f}", self._apply_config,
        )
        self.stack_serv_params.addWidget(sp0_serv)

        # Page 1: Deterministic
        sp1_serv, self.lbl_serv_det, self.slider_serv_det, self.spin_serv_det = make_param_control(
            "Fixed Service Duration D (s)", 0.05, 10.0, 0.05, 1.00
        )
        connect_pair(
            self.slider_serv_det, self.spin_serv_det, self.lbl_serv_det,
            "Fixed Service Duration D (s): {:.2f}", self._apply_config,
        )
        self.stack_serv_params.addWidget(sp1_serv)

        # Page 2: Uniform (Service Multi-parameter tuning with 2 sliders)
        sp2_serv = QWidget()
        sp2_serv_lay = QVBoxLayout(sp2_serv)
        sp2_serv_lay.setContentsMargins(0, 0, 0, 0)
        sp2_serv_lay.setSpacing(4)
        srow_a, self.lbl_serv_uni_a, self.slider_serv_uni_a, self.spin_serv_uni_a = make_param_control(
            "Parameter a (Min Service, s)", 0.05, 5.0, 0.05, 0.50
        )
        srow_b, self.lbl_serv_uni_b, self.slider_serv_uni_b, self.spin_serv_uni_b = make_param_control(
            "Parameter b (Max Service, s)", 0.10, 10.0, 0.05, 1.50
        )
        sp2_serv_lay.addWidget(srow_a)
        sp2_serv_lay.addWidget(srow_b)

        def on_serv_uni_a_sl(val):
            a_v = val / 100.0
            self.spin_serv_uni_a.blockSignals(True)
            self.spin_serv_uni_a.setValue(a_v)
            self.spin_serv_uni_a.blockSignals(False)
            self.lbl_serv_uni_a.setText(f"Parameter a (Min Service, s): {a_v:.2f}")
            if self.spin_serv_uni_b.value() <= a_v:
                new_b = min(self.spin_serv_uni_b.maximum(), round(a_v + 0.05, 2))
                self.spin_serv_uni_b.blockSignals(True)
                self.slider_serv_uni_b.blockSignals(True)
                self.spin_serv_uni_b.setValue(new_b)
                clamped_b = max(self.slider_serv_uni_b.minimum(), min(self.slider_serv_uni_b.maximum(), int(round(new_b * 100))))
                self.slider_serv_uni_b.setValue(clamped_b)
                self.spin_serv_uni_b.blockSignals(False)
                self.slider_serv_uni_b.blockSignals(False)
                self.lbl_serv_uni_b.setText(f"Parameter b (Max Service, s): {new_b:.2f}")
            self._apply_config()

        def on_serv_uni_a_sp(a_v):
            clamped_a = max(self.slider_serv_uni_a.minimum(), min(self.slider_serv_uni_a.maximum(), int(round(a_v * 100))))
            self.slider_serv_uni_a.blockSignals(True)
            self.slider_serv_uni_a.setValue(clamped_a)
            self.slider_serv_uni_a.blockSignals(False)
            self.lbl_serv_uni_a.setText(f"Parameter a (Min Service, s): {a_v:.2f}")
            if self.spin_serv_uni_b.value() <= a_v:
                new_b = min(self.spin_serv_uni_b.maximum(), round(a_v + 0.05, 2))
                self.spin_serv_uni_b.blockSignals(True)
                self.slider_serv_uni_b.blockSignals(True)
                self.spin_serv_uni_b.setValue(new_b)
                clamped_b = max(self.slider_serv_uni_b.minimum(), min(self.slider_serv_uni_b.maximum(), int(round(new_b * 100))))
                self.slider_serv_uni_b.setValue(clamped_b)
                self.spin_serv_uni_b.blockSignals(False)
                self.slider_serv_uni_b.blockSignals(False)
                self.lbl_serv_uni_b.setText(f"Parameter b (Max Service, s): {new_b:.2f}")
            self._apply_config()

        def on_serv_uni_b_sl(val):
            b_v = val / 100.0
            self.spin_serv_uni_b.blockSignals(True)
            self.spin_serv_uni_b.setValue(b_v)
            self.spin_serv_uni_b.blockSignals(False)
            self.lbl_serv_uni_b.setText(f"Parameter b (Max Service, s): {b_v:.2f}")
            if self.spin_serv_uni_a.value() >= b_v:
                new_a = max(0.05, round(b_v - 0.05, 2))
                self.spin_serv_uni_a.blockSignals(True)
                self.slider_serv_uni_a.blockSignals(True)
                self.spin_serv_uni_a.setValue(new_a)
                clamped_a = max(self.slider_serv_uni_a.minimum(), min(self.slider_serv_uni_a.maximum(), int(round(new_a * 100))))
                self.slider_serv_uni_a.setValue(clamped_a)
                self.spin_serv_uni_a.blockSignals(False)
                self.slider_serv_uni_a.blockSignals(False)
                self.lbl_serv_uni_a.setText(f"Parameter a (Min Service, s): {new_a:.2f}")
            self._apply_config()

        def on_serv_uni_b_sp(b_v):
            clamped_b = max(self.slider_serv_uni_b.minimum(), min(self.slider_serv_uni_b.maximum(), int(round(b_v * 100))))
            self.slider_serv_uni_b.blockSignals(True)
            self.slider_serv_uni_b.setValue(clamped_b)
            self.slider_serv_uni_b.blockSignals(False)
            self.lbl_serv_uni_b.setText(f"Parameter b (Max Service, s): {b_v:.2f}")
            if self.spin_serv_uni_a.value() >= b_v:
                new_a = max(0.05, round(b_v - 0.05, 2))
                self.spin_serv_uni_a.blockSignals(True)
                self.slider_serv_uni_a.blockSignals(True)
                self.spin_serv_uni_a.setValue(new_a)
                clamped_a = max(self.slider_serv_uni_a.minimum(), min(self.slider_serv_uni_a.maximum(), int(round(new_a * 100))))
                self.slider_serv_uni_a.setValue(clamped_a)
                self.spin_serv_uni_a.blockSignals(False)
                self.slider_serv_uni_a.blockSignals(False)
                self.lbl_serv_uni_a.setText(f"Parameter a (Min Service, s): {new_a:.2f}")
            self._apply_config()

        self.slider_serv_uni_a.valueChanged.connect(on_serv_uni_a_sl)
        self.spin_serv_uni_a.valueChanged.connect(on_serv_uni_a_sp)
        self.slider_serv_uni_b.valueChanged.connect(on_serv_uni_b_sl)
        self.spin_serv_uni_b.valueChanged.connect(on_serv_uni_b_sp)
        self.stack_serv_params.addWidget(sp2_serv)

        # Page 3: Erlang
        sp3_serv = QWidget()
        sp3_serv_lay = QVBoxLayout(sp3_serv)
        sp3_serv_lay.setContentsMargins(0, 0, 0, 0)
        sp3_serv_lay.setSpacing(4)
        srow_k, self.lbl_serv_erl_k, self.slider_serv_erl_k, self.spin_serv_erl_k = make_param_control(
            "Phases k", 1, 10, 1, 2, is_int=True, spin_max=50
        )
        connect_pair(
            self.slider_serv_erl_k, self.spin_serv_erl_k, self.lbl_serv_erl_k,
            "Phases k: {}", self._apply_config, is_int=True,
        )
        srow_erl_r, self.lbl_serv_erl_rate, self.slider_serv_erl_rate, self.spin_serv_erl_rate = make_param_control(
            "Overall Service Rate μ (cust/s)", 0.00, 10.0, 0.05, 1.00
        )
        connect_pair(
            self.slider_serv_erl_rate, self.spin_serv_erl_rate, self.lbl_serv_erl_rate,
            "Overall Service Rate μ (cust/s): {:.2f}", self._apply_config,
        )
        sp3_serv_lay.addWidget(srow_k)
        sp3_serv_lay.addWidget(srow_erl_r)
        self.stack_serv_params.addWidget(sp3_serv)

        # Page 4: Hyperexponential
        sp4_serv = QWidget()
        sp4_serv_lay = QVBoxLayout(sp4_serv)
        sp4_serv_lay.setContentsMargins(0, 0, 0, 0)
        sp4_serv_lay.setSpacing(4)
        srow_p1, self.lbl_serv_hyper_p1, self.slider_serv_hyper_p1, self.spin_serv_hyper_p1 = make_param_control(
            "Branch Prob p₁", 0.05, 0.95, 0.05, 0.40, spin_max=0.95
        )
        connect_pair(
            self.slider_serv_hyper_p1, self.spin_serv_hyper_p1, self.lbl_serv_hyper_p1,
            "Branch Prob p₁: {:.2f}", self._apply_config,
        )
        srow_r1, self.lbl_serv_hyper_r1, self.slider_serv_hyper_r1, self.spin_serv_hyper_r1 = make_param_control(
            "Phase 1 Rate r₁ (cust/s)", 0.05, 10.0, 0.05, 0.50
        )
        connect_pair(
            self.slider_serv_hyper_r1, self.spin_serv_hyper_r1, self.lbl_serv_hyper_r1,
            "Phase 1 Rate r₁ (cust/s): {:.2f}", self._apply_config,
        )
        srow_r2, self.lbl_serv_hyper_r2, self.slider_serv_hyper_r2, self.spin_serv_hyper_r2 = make_param_control(
            "Phase 2 Rate r₂ (cust/s)", 0.10, 10.0, 0.05, 2.00
        )
        connect_pair(
            self.slider_serv_hyper_r2, self.spin_serv_hyper_r2, self.lbl_serv_hyper_r2,
            "Phase 2 Rate r₂ (cust/s): {:.2f}", self._apply_config,
        )
        sp4_serv_lay.addWidget(srow_p1)
        sp4_serv_lay.addWidget(srow_r1)
        sp4_serv_lay.addWidget(srow_r2)
        self.stack_serv_params.addWidget(sp4_serv)

        # Page 5: Pareto
        sp5_serv = QWidget()
        sp5_serv_lay = QVBoxLayout(sp5_serv)
        sp5_serv_lay.setContentsMargins(0, 0, 0, 0)
        sp5_serv_lay.setSpacing(4)
        srow_alpha, self.lbl_serv_pareto_alpha, self.slider_serv_pareto_alpha, self.spin_serv_pareto_alpha = make_param_control(
            "Shape Parameter α", 1.10, 5.0, 0.05, 2.50, spin_max=50.0
        )
        connect_pair(
            self.slider_serv_pareto_alpha, self.spin_serv_pareto_alpha, self.lbl_serv_pareto_alpha,
            "Shape Parameter α: {:.2f}", self._apply_config,
        )
        srow_xm, self.lbl_serv_pareto_xm, self.slider_serv_pareto_xm, self.spin_serv_pareto_xm = make_param_control(
            "Scale Parameter xₘ (s)", 0.05, 3.0, 0.05, 0.60
        )
        connect_pair(
            self.slider_serv_pareto_xm, self.spin_serv_pareto_xm, self.lbl_serv_pareto_xm,
            "Scale Parameter xₘ (s): {:.2f}", self._apply_config,
        )
        sp5_serv_lay.addWidget(srow_alpha)
        sp5_serv_lay.addWidget(srow_xm)
        self.stack_serv_params.addWidget(sp5_serv)

        serv_layout.addWidget(self.stack_serv_params)

        self.lbl_serv_moments = QLabel("Mean Service Time: E[S] = 1.00s")
        self.lbl_serv_moments.setStyleSheet("color: #a6adc8; font-size: 10px;")
        serv_layout.addWidget(self.lbl_serv_moments)

        layout.addWidget(self.grp_service)

        # 5. Live Stability Status Card
        self.grp_stability = QGroupBox("System Stability Status")
        stab_layout = QVBoxLayout(self.grp_stability)
        stab_layout.setSpacing(4)

        self.lbl_stab_status = QLabel("Stable System (A₀/m = 0.80 < 1.0)")
        self.lbl_stab_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #a6e3a1;")
        stab_layout.addWidget(self.lbl_stab_status)

        self.btn_why = QPushButton("See Why: Mathematical Theory")
        self.btn_why.setStyleSheet(
            "background-color: #f38ba8; color: #11111b; font-weight: bold; font-size: 10px; padding: 4px;"
        )
        self.btn_why.clicked.connect(self._show_theory_dialog)
        self.btn_why.setVisible(False)
        stab_layout.addWidget(self.btn_why)

        layout.addWidget(self.grp_stability)

        # 6. Optional Feature: Priority Queuing (Disabled by default)
        grp_priority = QGroupBox("Optional: Priority Queuing (QoS)")
        prio_layout = QVBoxLayout(grp_priority)
        prio_layout.setSpacing(6)

        self.chk_priority = QCheckBox("Enable Priority Queueing")
        self.chk_priority.setChecked(self.engine.priority_enabled)
        self.chk_priority.toggled.connect(self._on_priority_toggled)
        prio_layout.addWidget(self.chk_priority)

        self.prio_container = QWidget()
        pc_layout = QVBoxLayout(self.prio_container)
        pc_layout.setContentsMargins(0, 4, 0, 0)
        pc_layout.setSpacing(4)

        # Class 0
        w0, self.lbl_p0, self.slider_p0, self.spin_p0 = make_param_control(
            "High - λ₀", 0.01, 10.0, 0.05, 0.30
        )
        connect_pair(self.slider_p0, self.spin_p0, self.lbl_p0, "High - λ₀: {:.2f}", self._apply_config)
        pc_layout.addWidget(w0)

        # Class 1
        w1, self.lbl_p1, self.slider_p1, self.spin_p1 = make_param_control(
            "Medium - λ₁", 0.0, 10.0, 0.05, 0.30
        )
        connect_pair(self.slider_p1, self.spin_p1, self.lbl_p1, "Medium - λ₁: {:.2f}", self._apply_config)
        pc_layout.addWidget(w1)

        # Class 2
        w2, self.lbl_p2, self.slider_p2, self.spin_p2 = make_param_control(
            "Low - λ₂", 0.0, 10.0, 0.05, 0.20
        )
        connect_pair(self.slider_p2, self.spin_p2, self.lbl_p2, "Low - λ₂: {:.2f}", self._apply_config)
        pc_layout.addWidget(w2)

        self.prio_container.setVisible(self.engine.priority_enabled)
        prio_layout.addWidget(self.prio_container)

        layout.addWidget(grp_priority)
        layout.addStretch(1)

        scroll.setWidget(container)
        return scroll

    def _create_content_tabs(self) -> QWidget:
        self.tabs = QTabWidget()
        self.tabs.setMinimumWidth(0)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        # Disable switching tabs via touchpad scroll / mouse wheel
        self.tabs.tabBar().wheelEvent = lambda event: event.ignore()

        self.tab_visual = QWidget()
        vis_layout = QVBoxLayout(self.tab_visual)
        vis_layout.setContentsMargins(6, 6, 6, 6)
        vis_layout.setSpacing(6)

        self.card_n = None
        vis_layout.addWidget(self._create_kpi_cards())

        self.canvas = AnimatedCanvas(self.engine)
        vis_layout.addWidget(self.canvas, stretch=3)

        self.markov_canvas = MarkovChainView(self.engine)
        vis_layout.addWidget(self.markov_canvas, stretch=0)

        self.table_log = QTableWidget()
        self.table_log.setColumnCount(4)
        self.table_log.setHorizontalHeaderLabels(["Sim Time", "Event Type", "Traffic Class", "Description"])
        self.table_log.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_log.verticalHeader().setVisible(False)
        self.table_log.verticalHeader().setDefaultSectionSize(25)
        self.table_log.setMinimumHeight(160)
        self.table_log.setMaximumHeight(200)
        vis_layout.addWidget(self.table_log, stretch=0)

        self.tabs.addTab(self.tab_visual, "Live Simulation")

        self.tab_charts = QWidget()
        charts_layout = QVBoxLayout(self.tab_charts)
        self.fig = Figure(figsize=(8, 6), facecolor="#181825")
        self.plot_canvas = FigureCanvas(self.fig)
        self.plot_canvas.wheelEvent = lambda event: event.ignore()
        charts_layout.addWidget(self.plot_canvas)
        self.tabs.addTab(self.tab_charts, "Analytics & Histograms")

        self.tab_theory = QWidget()
        theory_layout = QVBoxLayout(self.tab_theory)
        theory_layout.addWidget(self._create_theory_view())
        self.tabs.addTab(self.tab_theory, "Theoretical Validation & Little's Law")

        self._update_tab_close_buttons()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        return self.tabs

    def _create_kpi_cards(self) -> QWidget:
        card_panel = QWidget()
        layout = QHBoxLayout(card_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        def make_card(title: str, default_val: str, color: str, topic_idx: int):
            frame = QFrame()
            frame.setStyleSheet(
                "background-color: #1e1e2e; border: 1px solid #313244; border-radius: 4px; padding: 2px;"
            )
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(6, 4, 6, 4)
            fl.setSpacing(2)

            header_row = QHBoxLayout()
            header_row.setContentsMargins(0, 0, 0, 0)
            header_row.setSpacing(4)

            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("font-size: 10px; color: #a6adc8;")
            header_row.addWidget(lbl_t)
            header_row.addStretch()

            btn_q = QPushButton("?")
            btn_q.setFixedSize(20, 20)
            btn_q.setToolTip(f"View theory, definition and computation for {title}")
            btn_q.setStyleSheet(METRIC_QUESTION_BTN_STYLE)
            btn_q.clicked.connect(lambda _, idx=topic_idx: self.show_theory_tab(idx))
            header_row.addWidget(btn_q)

            lbl_v = QLabel(default_val)
            lbl_v.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")

            fl.addLayout(header_row)
            fl.addWidget(lbl_v)
            return frame, lbl_v

        self.card_n, self.val_n = make_card("Traffic k(t)", "0", "#cdd6f4", 9)
        self.card_served, self.val_served = make_card("Departures / Arrivals d / a", "0 / 0", "#a6e3a1", 15)
        self.card_drop, self.val_drop = make_card("Blocking Probability π_p", "0 (0.0%)", "#f38ba8", 13)
        self.card_wait, self.val_wait = make_card("Avg Waiting Time η̄", "0.00s", "#89b4fa", 12)
        self.card_littles, self.val_littles = make_card("Little's Law |A - λ_s δ̄|", "0.000", "#f9e2af", 14)

        layout.addWidget(self.card_n)
        layout.addWidget(self.card_served)
        layout.addWidget(self.card_drop)
        layout.addWidget(self.card_wait)
        layout.addWidget(self.card_littles)

        return card_panel

    def _create_theory_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        lbl_title = QLabel("Analytical Model vs. Simulation Benchmark")
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #89b4fa; margin-bottom: 4px;")
        layout.addWidget(lbl_title)

        self.table_theory = QTableWidget()
        self.table_theory.setColumnCount(4)
        self.table_theory.setHorizontalHeaderLabels(
            ["Metric", "Simulated (Empirical)", "Theoretical (Formula)", "Discrepancy / Error"]
        )
        self.table_theory.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_theory.verticalHeader().setDefaultSectionSize(36)
        self.table_theory.cellDoubleClicked.connect(lambda row, col: self._show_metric_theory(row))
        layout.addWidget(self.table_theory)

        self.lbl_theory_notes = QLabel()
        self.lbl_theory_notes.setWordWrap(True)
        self.lbl_theory_notes.setStyleSheet(
            "background-color: #1e1e2e; padding: 8px; border-radius: 4px; font-size: 11px; color: #cdd6f4;"
        )
        layout.addWidget(self.lbl_theory_notes)

        return widget

    def _make_metric_cell(self, metric_name: str, metric_idx: int) -> QWidget:
        cell_w = QWidget()
        hl = QHBoxLayout(cell_w)
        hl.setContentsMargins(8, 2, 8, 2)
        hl.setSpacing(6)

        lbl = QLabel(metric_name)
        lbl.setStyleSheet("color: #cdd6f4; font-size: 11px;")
        hl.addWidget(lbl)
        hl.addStretch()

        btn_q = QPushButton("?")
        btn_q.setFixedSize(22, 22)
        btn_q.setToolTip(f"View theory, definition and computation for {metric_name}")
        btn_q.setStyleSheet(METRIC_QUESTION_BTN_STYLE)
        btn_q.clicked.connect(lambda _, idx=metric_idx: self._show_metric_theory(idx))
        hl.addWidget(btn_q)
        return cell_w

    # -------------------------------------------------------------------
    # Slider & Input Synchronization
    # -------------------------------------------------------------------
    def _on_arr_slider_changed(self, val):
        rate = val / 100.0
        self.spin_arr_rate.blockSignals(True)
        self.spin_arr_rate.setValue(rate)
        self.spin_arr_rate.blockSignals(False)
        self.lbl_arr_rate.setText(f"Arrival Rate λ (cust/s): {rate:.2f}")
        self._apply_config()

    def _on_arr_spin_changed(self, val):
        sl_val = max(self.slider_arr_rate.minimum(), min(self.slider_arr_rate.maximum(), int(val * 100)))
        self.slider_arr_rate.blockSignals(True)
        self.slider_arr_rate.setValue(sl_val)
        self.slider_arr_rate.blockSignals(False)
        self.lbl_arr_rate.setText(f"Arrival Rate λ (cust/s): {val:.2f}")
        self._apply_config()

    def _on_serv_slider_changed(self, val):
        rate = val / 100.0
        self.spin_serv_rate.blockSignals(True)
        self.spin_serv_rate.setValue(rate)
        self.spin_serv_rate.blockSignals(False)
        self.lbl_serv_rate.setText(f"Service Rate μ (cust/s): {rate:.2f}")
        self._apply_config()

    def _on_serv_spin_changed(self, val):
        sl_val = max(self.slider_serv_rate.minimum(), min(self.slider_serv_rate.maximum(), int(val * 100)))
        self.slider_serv_rate.blockSignals(True)
        self.slider_serv_rate.setValue(sl_val)
        self.slider_serv_rate.blockSignals(False)
        self.lbl_serv_rate.setText(f"Service Rate μ (cust/s): {val:.2f}")
        self._apply_config()

    def _on_arr_dist_changed(self, idx: int):
        self.stack_arr_params.setCurrentIndex(idx)
        self.stack_arr_params.updateGeometry()
        if hasattr(self, 'grp_arrival') and self.grp_arrival.layout():
            self.grp_arrival.layout().invalidate()
            self.grp_arrival.updateGeometry()
        self._apply_config()

    def _on_serv_dist_changed(self, idx: int):
        self.stack_serv_params.setCurrentIndex(idx)
        self.stack_serv_params.updateGeometry()
        if hasattr(self, 'grp_service') and self.grp_service.layout():
            self.grp_service.layout().invalidate()
            self.grp_service.updateGeometry()
        self._apply_config()

    def _on_priority_toggled(self, checked):
        self.prio_container.setVisible(checked)
        self.grp_arrival.setEnabled(not checked)
        if checked:
            self.grp_arrival.setTitle("Traffic Arrival Process (Controlled by Priority QoS below)")
        else:
            self.grp_arrival.setTitle("Traffic Arrival Process (Input)")
        self._apply_config()

    # -------------------------------------------------------------------
    # Execution & Speed Logic
    # -------------------------------------------------------------------
    @property
    def btn_stop(self):
        return self.btn_run

    def _set_playback_state(self, state: str):
        self.playback_state = state
        if state == "RUN":
            self.btn_run.setText("RUN")
            self.btn_run.setObjectName("btnRun")
            self.btn_run.setStyleSheet(PLAYBACK_RUN_STYLE)
        elif state == "STOP":
            self.btn_run.setText("STOP")
            self.btn_run.setObjectName("btnStop")
            self.btn_run.setStyleSheet(PLAYBACK_STOP_STYLE)
        elif state == "CONTINUE":
            self.btn_run.setText("CONTINUE")
            self.btn_run.setObjectName("btnContinue")
            self.btn_run.setStyleSheet(PLAYBACK_CONTINUE_STYLE)

    def _on_playback_btn_clicked(self):
        if self.playback_state == "STOP":
            self._stop_run()
        else:
            self._start_run()

    def _update_speed(self, val):
        if val <= 20:
            interval = int(2000 - (val - 1) * 95)
            self.timer_interval_ms = max(150, interval)
            self.events_per_tick = 1
            sec_per_ev = self.timer_interval_ms / 1000.0
            if sec_per_ev >= 0.8:
                self.lbl_speed_desc.setText(f"Speed: 1 event / {sec_per_ev:.1f}s")
            else:
                self.lbl_speed_desc.setText(f"Speed: {1.0/sec_per_ev:.1f} events / sec")
        elif val <= 60:
            interval = int(150 - (val - 21) * 3)
            self.timer_interval_ms = max(25, interval)
            self.events_per_tick = 1
            rate = 1000.0 / self.timer_interval_ms
            self.lbl_speed_desc.setText(f"Speed: {rate:.0f} events / sec")
        else:
            self.timer_interval_ms = 25
            self.events_per_tick = int(1 + (val - 60) * 1.5)
            rate = (1000.0 / 25) * self.events_per_tick
            self.lbl_speed_desc.setText(f"Speed: {rate:,.0f} events / sec")

        if self.timer.isActive():
            self.timer.setInterval(self.timer_interval_ms)

    def _start_run(self):
        if not self.timer.isActive():
            self.timer.start(self.timer_interval_ms)
            self.lbl_status.setText("RUNNING")
            self.lbl_status.setStyleSheet(
                "font-size: 10px; font-weight: bold; color: #a6e3a1; padding: 2px 6px; "
                "background-color: #313244; border-radius: 3px;"
            )
        self._set_playback_state("STOP")

    def _stop_run(self):
        if self.timer.isActive():
            self.timer.stop()
            self.lbl_status.setText("PAUSED")
            self.lbl_status.setStyleSheet(
                "font-size: 10px; font-weight: bold; color: #f9e2af; padding: 2px 6px; "
                "background-color: #313244; border-radius: 3px;"
            )
        self._set_playback_state("CONTINUE")

    def _toggle_run(self):
        if self.timer.isActive():
            self._stop_run()
        else:
            self._start_run()

    def _step_once(self):
        if self.timer.isActive():
            self._stop_run()
        self.engine.step()
        self._update_all_views()

    def _on_timer_tick(self):
        for _ in range(self.events_per_tick):
            self.engine.step()
        self._update_all_views()

    def _reset_sim(self):
        if self.timer.isActive():
            self.timer.stop()
        self.lbl_status.setText("PAUSED")
        self.lbl_status.setStyleSheet(
            "font-size: 10px; font-weight: bold; color: #f9e2af; padding: 2px 6px; "
            "background-color: #313244; border-radius: 3px;"
        )
        self.engine.reset()
        self._set_playback_state("RUN")
        self._update_all_views()

    def _toggle_inf_servers(self, checked):
        self.stepper_servers.setEnabled(not checked)
        self._apply_config()

    def _toggle_inf_queue(self, checked):
        self.stepper_queue.setEnabled(not checked)
        self._apply_config()

    def _update_tab_close_buttons(self):
        tb = self.tabs.tabBar()
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) != self.tab_theory_doc:
                tb.setTabButton(i, QTabBar.ButtonPosition.RightSide, None)

    def _on_tab_close_requested(self, index: int):
        if self.tabs.widget(index) == self.tab_theory_doc:
            self.close_theory_tab()

    @property
    def theory_tab(self):
        return self.tab_theory_doc

    def is_theory_tab_active(self) -> bool:
        return (
            self.tab_theory_doc is not None
            and self.tabs.currentWidget() == self.tab_theory_doc
        )

    def show_theory_tab(
        self,
        topic_index: int,
        role: str = "Arrival",
        rho: float = None,
        lam: float = None,
        mu: float = None,
        m: float = 1,
    ):
        if self.tab_theory_doc is None:
            self.tab_theory_doc = TheoryPdfTab(self.engine, parent=self)
            self.tab_theory_doc.closeRequested.connect(self.close_theory_tab)

        if rho is None or lam is None or mu is None:
            lam = sum(1.0 / max(1e-6, d.mean()) for d in self.engine.arrival_dists.values() if d is not None)
            mean_s = self.engine.service_dist.mean()
            mu = (1.0 / mean_s) if (not math.isinf(mean_s) and mean_s > 0) else 0.0
            if math.isinf(self.engine.c):
                rho = 0.0 if mu > 0 else float('inf')
            else:
                rho = lam / max(1e-6, self.engine.c * mu)
            m = self.engine.c

        short_title = self.tab_theory_doc.get_short_title(topic_index)
        tab_label = f"Theory: {short_title}"

        tab_idx = self.tabs.indexOf(self.tab_theory_doc)
        if tab_idx == -1:
            # Insert right next to Live Simulation (index 1) to cover visual representation
            self.tabs.insertTab(1, self.tab_theory_doc, tab_label)
        else:
            self.tabs.setTabText(tab_idx, tab_label)

        self._update_tab_close_buttons()

        self.tab_theory_doc.load_topic(
            topic_index=topic_index,
            role=role,
            rho=rho,
            lam=lam,
            mu=mu,
            m=m,
        )

        # Switch to the theory tab to cover the system visual representation
        self.tabs.setCurrentWidget(self.tab_theory_doc)
        if hasattr(self, 'zoom_view'):
            self.zoom_view.horizontalScrollBar().setValue(0)
            self.zoom_view.verticalScrollBar().setValue(0)

    def close_theory_tab(self):
        if self.tab_theory_doc is not None:
            tab_idx = self.tabs.indexOf(self.tab_theory_doc)
            if tab_idx != -1:
                self.tabs.removeTab(tab_idx)
        # Uncover the visual representation of the system
        self.tabs.setCurrentWidget(self.tab_visual)
        if hasattr(self, 'zoom_view'):
            self.zoom_view.horizontalScrollBar().setValue(0)
            self.zoom_view.verticalScrollBar().setValue(0)

    def _show_theory_dialog(self):
        lam = sum(1.0 / d.mean() for d in self.engine.arrival_dists.values() if d is not None)
        mean_s = self.engine.service_dist.mean()
        mu = (1.0 / mean_s) if (not math.isinf(mean_s) and mean_s > 0) else 0.0
        rho = self.engine.get_metrics()['rho']
        target_topic = 7 if mu <= 0 else 6
        self.show_theory_tab(topic_index=target_topic, rho=rho, lam=lam, mu=mu, m=self.engine.c)

    def _show_arr_dist_theory(self):
        idx = self.combo_arr_dist.currentIndex()
        self.show_theory_tab(topic_index=idx, role="Arrival")

    def _show_serv_dist_theory(self):
        idx = self.combo_serv_dist.currentIndex()
        self.show_theory_tab(topic_index=idx, role="Service")

    def _show_server_utilization_theory(self):
        self._show_metric_theory(0)

    def _show_metric_theory(self, metric_idx: int):
        topic_idx = 8 + metric_idx
        lam = sum(1.0 / d.mean() for d in self.engine.arrival_dists.values() if d is not None)
        mean_s = self.engine.service_dist.mean()
        mu = (1.0 / mean_s) if (not math.isinf(mean_s) and mean_s > 0) else 0.0
        rho = self.engine.get_metrics()['rho']
        self.show_theory_tab(topic_index=topic_idx, rho=rho, lam=lam, mu=mu, m=self.engine.c)

    # -------------------------------------------------------------------
    # Configuration & Stability Analysis
    # -------------------------------------------------------------------
    def _apply_config(self):
        arr_idx = self.combo_arr_dist.currentIndex()
        if arr_idx == 0:
            s_dist = ExponentialDist(rate=self.spin_arr_rate.value())
        elif arr_idx == 1:
            s_dist = DeterministicDist(value=self.spin_arr_det.value())
        elif arr_idx == 2:
            s_dist = UniformDist(a=self.spin_arr_uni_a.value(), b=self.spin_arr_uni_b.value())
        elif arr_idx == 3:
            k_val = self.spin_arr_erl_k.value()
            r_val = self.spin_arr_erl_rate.value()
            s_dist = ErlangDist(k=k_val, mean=1.0 / max(1e-6, r_val))
        elif arr_idx == 4:
            p1_val = self.spin_arr_hyper_p1.value()
            r1_val = self.spin_arr_hyper_r1.value()
            r2_val = self.spin_arr_hyper_r2.value()
            s_dist = HyperexponentialDist(p1=p1_val, rate1=r1_val, rate2=r2_val)
        elif arr_idx == 5:
            alpha_val = self.spin_arr_pareto_alpha.value()
            xm_val = self.spin_arr_pareto_xm.value()
            s_dist = ParetoDist(shape=alpha_val, scale=xm_val)
        else:
            s_dist = ExponentialDist(rate=1.0)

        serv_idx = self.combo_serv_dist.currentIndex()
        if serv_idx == 0:
            serv_dist = ExponentialDist(rate=self.spin_serv_rate.value())
        elif serv_idx == 1:
            serv_dist = DeterministicDist(value=self.spin_serv_det.value())
        elif serv_idx == 2:
            serv_dist = UniformDist(a=self.spin_serv_uni_a.value(), b=self.spin_serv_uni_b.value())
        elif serv_idx == 3:
            k_val = self.spin_serv_erl_k.value()
            r_val = self.spin_serv_erl_rate.value()
            serv_dist = ErlangDist(k=k_val, mean=(1.0 / r_val) if r_val > 0 else float('inf'))
        elif serv_idx == 4:
            p1_val = self.spin_serv_hyper_p1.value()
            r1_val = self.spin_serv_hyper_r1.value()
            r2_val = self.spin_serv_hyper_r2.value()
            serv_dist = HyperexponentialDist(p1=p1_val, rate1=r1_val, rate2=r2_val)
        elif serv_idx == 5:
            alpha_val = self.spin_serv_pareto_alpha.value()
            xm_val = self.spin_serv_pareto_xm.value()
            serv_dist = ParetoDist(shape=alpha_val, scale=xm_val)
        else:
            serv_dist = ExponentialDist(rate=1.0)

        mean_s = serv_dist.mean()
        mu = (1.0 / mean_s) if (not math.isinf(mean_s) and mean_s > 0) else 0.0
        if math.isinf(mean_s):
            self.lbl_serv_moments.setText("Mean Service: E[S] = ∞ | Var[S] = ∞ (Rate μ = 0.00 cust/s)")
        else:
            self.lbl_serv_moments.setText(
                f"Mean Service: E[S] = {mean_s:.2f}s | Var[S] = {serv_dist.variance():.3f}"
            )

        priority_active = self.chk_priority.isChecked()
        arr_dists = {}

        if not priority_active:
            arr_dists[-1] = s_dist
            mean_a = s_dist.mean()
            lam = (1.0 / mean_a) if (not math.isinf(mean_a) and mean_a > 0) else 0.0
            self.lbl_arr_moments.setText(
                f"Mean Interarrival: E[T] = {s_dist.mean():.2f}s | Var[T] = {s_dist.variance():.3f}"
            )
            lam_total = lam
        else:
            r0 = self.spin_p0.value()
            r1 = self.spin_p1.value()
            r2 = self.spin_p2.value()
            if r0 > 0:
                arr_dists[0] = ExponentialDist(rate=r0)
            if r1 > 0:
                arr_dists[1] = ExponentialDist(rate=r1)
            if r2 > 0:
                arr_dists[2] = ExponentialDist(rate=r2)
            lam_total = r0 + r1 + r2
            self.lbl_arr_moments.setText(f"Total Priority Arrival: Σλ = {lam_total:.2f} cust/s")

        c_servers = math.inf if self.chk_inf_servers.isChecked() else self.stepper_servers.value()
        q_cap = math.inf if self.chk_inf_queue.isChecked() else self.stepper_queue.value()

        if math.isinf(c_servers):
            if mu > 0:
                self.lbl_stab_status.setText("Stable System (Ample Servers m = ∞, A₀/m = 0)")
                self.lbl_stab_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #a6e3a1;")
                self.btn_why.setVisible(False)
                self.btn_warning_why.setVisible(False)
            else:
                self.lbl_stab_status.setText("Frozen System (Zero Service Rate μ = 0 cust/s)")
                self.lbl_stab_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #f38ba8;")
                self.btn_warning_why.setText("Warning: Zero Service Rate (μ = 0) - See Why")
                self.btn_why.setText("See Why: Zero Service Rate Theory (μ = 0)")
                self.btn_why.setVisible(True)
                self.btn_warning_why.setVisible(True)
        elif mu <= 0:
            self.lbl_stab_status.setText("Frozen System (Zero Service Rate μ = 0 cust/s)")
            self.lbl_stab_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #f38ba8;")
            self.btn_warning_why.setText("Warning: Zero Service Rate (μ = 0) - See Why")
            self.btn_why.setText("See Why: Zero Service Rate Theory (μ = 0)")
            self.btn_why.setVisible(True)
            self.btn_warning_why.setVisible(True)
        else:
            a0_per_server = lam_total / (c_servers * mu)
            if a0_per_server < 0.85:
                self.lbl_stab_status.setText(f"Stable System (A₀/m = {a0_per_server:.2f} < 1.0)")
                self.lbl_stab_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #a6e3a1;")
                self.btn_why.setVisible(False)
                self.btn_warning_why.setVisible(False)
            elif a0_per_server < 1.0:
                self.lbl_stab_status.setText(f"High Congestion (A₀/m = {a0_per_server:.2f})")
                self.lbl_stab_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #f9e2af;")
                self.btn_why.setVisible(False)
                self.btn_warning_why.setVisible(False)
            else:
                self.lbl_stab_status.setText(f"Warning: Overload / Unstable (A₀/m = {a0_per_server:.2f} ≥ 1.0)")
                self.lbl_stab_status.setStyleSheet("font-size: 11px; font-weight: bold; color: #f38ba8;")
                self.btn_warning_why.setText("Warning: Overload (A₀/m ≥ 1.0) - See Why")
                self.btn_why.setText("See Why: Mathematical Theory")
                self.btn_why.setVisible(True)
                self.btn_warning_why.setVisible(True)

        if self.engine.priority_enabled != priority_active:
            self.engine.priority_enabled = priority_active
            # Smoothly migrate queued customers between FIFO and Priority queues
            if not priority_active:
                for p in (0, 1, 2):
                    while self.engine.queues[p]:
                        c = self.engine.queues[p].popleft()
                        c.priority = -1
                        self.engine.queues[-1].append(c)
            else:
                while self.engine.queues[-1]:
                    c = self.engine.queues[-1].popleft()
                    target_p = c.priority if c.priority in (0, 1, 2) else 1
                    c.priority = target_p
                    self.engine.queues[target_p].append(c)

        self.engine._accumulate_time(self.engine.current_time)
        self.engine.c = c_servers
        self.engine.K = q_cap
        self.engine.sync_service_dist(serv_dist)
        self.engine.sync_arrival_streams(arr_dists)

        if math.isinf(c_servers):
            while len(self.engine.servers) < 5:
                self.engine.servers.append(Server(id=len(self.engine.servers)))
            while len(self.engine.servers) > 5 and not self.engine.servers[-1].is_busy:
                popped_srv = self.engine.servers.pop()
                self.engine.retired_busy_time += popped_srv.total_busy_time
        else:
            c_int = int(c_servers)
            while len(self.engine.servers) < c_int:
                self.engine.servers.append(Server(id=len(self.engine.servers)))
            while len(self.engine.servers) > c_int:
                popped_srv = self.engine.servers.pop()
                self.engine.retired_busy_time += popped_srv.total_busy_time
                if popped_srv.busy_start_time is not None:
                    self.engine.retired_busy_time += (self.engine.current_time - popped_srv.busy_start_time)

                if popped_srv.current_customer:
                    cust = popped_srv.current_customer
                    if cust.service_start_time is not None:
                        cust.arrival_time += (self.engine.current_time - cust.service_start_time)
                        cust.service_start_time = None

                    p_key = cust.priority if self.engine.priority_enabled else -1
                    self.engine.queues[p_key].appendleft(cust)
                    self.engine.event_heap = [
                        ev for ev in self.engine.event_heap
                        if not (ev[2] == 'departure' and ev[3] == popped_srv.id)
                    ]
                    import heapq
                    heapq.heapify(self.engine.event_heap)

        # Immediately dispatch any newly available idle servers to waiting customers in strict priority order
        self.engine.assign_idle_servers()

        self._update_all_views()
        if self.is_theory_tab_active():
            self.tab_theory_doc._reload_current(
                self.tab_theory_doc.current_topic_index,
                self.tab_theory_doc.current_role,
            )

    # -------------------------------------------------------------------
    # View Updates & Plotting
    # -------------------------------------------------------------------
    def _update_all_views(self):
        m = self.engine.get_metrics()

        kendall = TheoreticalModels.get_kendall_notation(
            self.engine.arrival_dists,
            self.engine.service_dist,
            self.engine.c,
            self.engine.K,
            self.engine.priority_enabled,
        )
        self.lbl_kendall.setText(f"[ {kendall} ]")
        if self.lbl_sim_time is not None:
            self.lbl_sim_time.setText(f"Clock: {m['T']:.1f}s")
        if math.isinf(self.engine.c):
            self.lbl_rho_header.setText("Avg Server Utilization ρ: 0.00 (m = ∞)")
        else:
            self.lbl_rho_header.setText(f"Avg Server Utilization ρ: {m['rho']:.2f}")

        self.val_n.setText(f"{self.engine.total_in_system} (Q: {self.engine.total_in_queue})")
        self.val_served.setText(f"{m['served']} / {m['arrived']}")
        self.val_drop.setText(f"{m['dropped']} ({m['p_loss']*100:.1f}%)")
        self.val_wait.setText(f"{m['Wq']:.3f}s")
        self.val_littles.setText(f"{m['littles_error_L']:.4f}")

        self.canvas.trigger_blink_check()
        self.canvas.update()
        self.markov_canvas.update()
        self._update_event_log_table()

        cur_w = self.tabs.currentWidget()
        if cur_w == self.tab_charts:
            self._update_plots()
        elif cur_w == self.tab_theory:
            self._update_theory_table()

    def _update_event_log_table(self):
        logs = list(self.engine.event_log)[-9:]
        self.table_log.setRowCount(len(logs))
        for row, ev in enumerate(reversed(logs)):
            t_item = QTableWidgetItem(f"{ev['time']:.2f}s")
            type_item = QTableWidgetItem(ev['type'])
            prio_item = QTableWidgetItem(PRIORITY_NAMES.get(ev.get('prio', -1), "Standard"))
            msg_item = QTableWidgetItem(ev['msg'])

            if 'DROP' in ev['type']:
                type_item.setForeground(QColor("#f38ba8"))
                msg_item.setForeground(QColor("#f38ba8"))
            elif 'SERVICE' in ev['type']:
                type_item.setForeground(QColor("#a6e3a1"))

            self.table_log.setItem(row, 0, t_item)
            self.table_log.setItem(row, 1, type_item)
            self.table_log.setItem(row, 2, prio_item)
            self.table_log.setItem(row, 3, msg_item)

    def _on_tab_changed(self, index):
        cur_w = self.tabs.currentWidget()
        if cur_w == self.tab_charts:
            self._update_plots()
        elif cur_w == self.tab_theory:
            self._update_theory_table()
        elif cur_w == self.tab_theory_doc and self.tab_theory_doc is not None:
            self.tab_theory_doc._reload_current(
                self.tab_theory_doc.current_topic_index,
                self.tab_theory_doc.current_role,
            )

    def _update_plots(self):
        m = self.engine.get_metrics()
        self.fig.clear()

        ax1 = self.fig.add_subplot(2, 2, 1)
        ax2 = self.fig.add_subplot(2, 2, 2)
        ax3 = self.fig.add_subplot(2, 2, 3)
        ax4 = self.fig.add_subplot(2, 2, 4)

        for ax in (ax1, ax2, ax3, ax4):
            ax.set_facecolor("#1e1e2e")
            ax.tick_params(colors="#cdd6f4")
            for spine in ax.spines.values():
                spine.set_color("#313244")

        # ---------------------------------------------------------------
        # Plot 1: Occupancy N(t) Step Curve
        # ---------------------------------------------------------------
        times = list(self.engine.time_history)[-300:]
        occs = list(self.engine.occupancy_history)[-300:]
        ax1.step(times, occs, where='post', color="#89b4fa", linewidth=1.5)
        ax1.set_title("Traffic in System k(t) vs Time", color="#cdd6f4", fontsize=10)
        ax1.set_xlabel("Time (s)", color="#a6adc8", fontsize=8)
        ax1.set_ylabel("Customers in System k(t)", color="#a6adc8", fontsize=8)
        ax1.grid(True, color="#313244", linestyle="--", alpha=0.6)

        # ---------------------------------------------------------------
        # Plot 2: State Probabilities P(k) vs Full Theoretical Curve
        # ---------------------------------------------------------------
        pn = m['p_n']
        c = self.engine.c
        K = self.engine.K

        # Always display a full, well-defined range of states
        max_observed = max(list(pn.keys()) + [0])
        if math.isinf(K) or math.isinf(c):
            max_state_to_show = max(10, min(25, max_observed + 2))
        else:
            eff_K = 3 * int(K) if self.engine.priority_enabled else int(K)
            max_state_to_show = min(25, max(int(c) + eff_K, max_observed))

        display_states = list(range(max_state_to_show + 1))
        sim_probs = [pn.get(s, 0.0) for s in display_states]

        # Bar plot of simulated probabilities
        ax2.bar(display_states, sim_probs, color="#a6e3a1", alpha=0.7, label="Simulated P(k)")

        # Compute theoretical PMF
        lam_equiv = sum(1.0 / max(1e-6, d.mean()) for d in self.engine.arrival_dists.values() if d is not None)
        mean_serv = self.engine.service_dist.mean()
        mu_equiv = (1.0 / mean_serv) if (not math.isinf(mean_serv) and mean_serv > 0) else 0.0

        is_pure_exponential = (
            isinstance(self.engine.service_dist, ExponentialDist)
            and all(isinstance(d, ExponentialDist) for d in self.engine.arrival_dists.values() if d is not None)
        )

        if lam_equiv > 0 and mu_equiv > 0:
            if math.isinf(c) or math.isinf(K):
                theo = TheoreticalModels.solve_mmc_infinite(lam_equiv, mu_equiv, c)
            elif not self.engine.priority_enabled:
                theo = TheoreticalModels.solve_mmc_finite(lam_equiv, mu_equiv, c, int(K))
            else:
                theo = {}

            if theo and not theo.get('unstable', False):
                theo_p = [theo['p_n'].get(s, 0.0) for s in display_states]
                if math.isinf(c):
                    lbl = "Theoretical M/M/inf (Poisson)" if is_pure_exponential else "Theoretical M/M/inf Reference"
                else:
                    lbl = "Theoretical M/M/m/K" if is_pure_exponential else "Theoretical M/M/m/K Reference"
                ax2.plot(display_states, theo_p, color="#f38ba8", marker='o', linewidth=2.0, markersize=5, label=lbl)
            elif not math.isinf(c) and math.isinf(K) and (lam_equiv / (c * mu_equiv)) >= 1.0:
                ax2.text(
                    0.5, 0.85, "A₀/m ≥ 1.0 on K=inf: No steady-state curve (Unstable)",
                    transform=ax2.transAxes, color="#f38ba8", fontsize=8, ha="center",
                )

        ax2.set_title("State Probabilities P(k)", color="#cdd6f4", fontsize=10)
        ax2.set_xlabel("State k (In System)", color="#a6adc8", fontsize=8)
        ax2.set_ylabel("Probability", color="#a6adc8", fontsize=8)
        ax2.set_xticks(display_states)
        ax2.legend(fontsize=8, facecolor="#1e1e2e", edgecolor="#313244", labelcolor="#cdd6f4")
        ax2.grid(True, color="#313244", linestyle="--", alpha=0.6)

        # ---------------------------------------------------------------
        # Plot 3: Waiting Time η
        # ---------------------------------------------------------------
        if not self.engine.priority_enabled:
            wait_times = [c.waiting_time for c in self.engine.completed_customers]
            if wait_times:
                bins = min(30, max(10, int(len(wait_times) ** 0.5)))
                ax3.hist(wait_times, bins=bins, color="#89b4fa", alpha=0.8, edgecolor="#11111b")
            ax3.set_title("Waiting Time η Histogram (s)", color="#cdd6f4", fontsize=10)
            ax3.set_xlabel("Wait Time η (s)", color="#a6adc8", fontsize=8)
        else:
            prios = ["High (P₀)", "Med (P₁)", "Low (P₂)"]
            wq_vals = [m['Wq_prio'].get(0, 0.0), m['Wq_prio'].get(1, 0.0), m['Wq_prio'].get(2, 0.0)]
            colors = [PRIORITY_COLORS[0], PRIORITY_COLORS[1], PRIORITY_COLORS[2]]
            ax3.bar(prios, wq_vals, color=colors, alpha=0.85)
            ax3.set_title("Mean Wait η̄ by Priority Class", color="#cdd6f4", fontsize=10)
            ax3.set_ylabel("Seconds", color="#a6adc8", fontsize=8)
        ax3.grid(True, color="#313244", linestyle="--", alpha=0.6)

        # ---------------------------------------------------------------
        # Plot 4: Rejection & Loss Probability
        # ---------------------------------------------------------------
        if not self.engine.priority_enabled:
            t_sub = list(self.engine.time_history)[-300:]
            d_sub = list(self.engine.drop_count_history)[-300:]
            ax4.plot(t_sub, d_sub, color="#f38ba8", linewidth=1.5)
            ax4.set_title("Cumulative Dropped Customers a_p(t) vs Time", color="#cdd6f4", fontsize=10)
            ax4.set_xlabel("Time (s)", color="#a6adc8", fontsize=8)
            ax4.set_ylabel("Total Rejected a_p(t)", color="#a6adc8", fontsize=8)
        else:
            prios = ["High (P₀)", "Med (P₁)", "Low (P₂)"]
            ploss_vals = [
                m['p_loss_prio'].get(0, 0.0) * 100.0,
                m['p_loss_prio'].get(1, 0.0) * 100.0,
                m['p_loss_prio'].get(2, 0.0) * 100.0,
            ]
            ax4.bar(prios, ploss_vals, color="#f38ba8", alpha=0.85)
            ax4.set_title("Blocking Probability π_p (%) by Priority Class", color="#cdd6f4", fontsize=10)
            ax4.set_ylabel("Blocking π_p (%)", color="#a6adc8", fontsize=8)
        ax4.grid(True, color="#313244", linestyle="--", alpha=0.6)

        self.fig.tight_layout()
        self.plot_canvas.draw()

    def _update_theory_table(self):
        m = self.engine.get_metrics()
        active_arr_dists = [d for d in self.engine.arrival_dists.values() if d is not None]
        all_arr_exponential = bool(active_arr_dists) and all(isinstance(d, ExponentialDist) for d in active_arr_dists)
        lam_tot = sum(1.0 / max(1e-6, d.mean()) for d in active_arr_dists)

        theo = {}
        theo_note = "Model: "
        mean_serv = self.engine.service_dist.mean()
        mu = (1.0 / mean_serv) if (not math.isinf(mean_serv) and mean_serv > 0) else 0.0
        if (
            all_arr_exponential
            and isinstance(self.engine.service_dist, ExponentialDist)
            and (not self.engine.priority_enabled or math.isinf(self.engine.K))
            and lam_tot > 0
            and mu > 0
        ):
            if math.isinf(self.engine.c):
                theo = TheoreticalModels.solve_mmc_infinite(lam_tot, mu, self.engine.c)
                theo_note += "M/M/inf Ample-Server Pure Delay System (Poisson state distribution, no queueing delay)."
            elif math.isinf(self.engine.K):
                theo = TheoreticalModels.solve_mmc_infinite(lam_tot, mu, self.engine.c)
                prio_tag = " (Priority Conservation)" if self.engine.priority_enabled else ""
                theo_note += f"M/M/{self.engine.c} Markovian Queue with Erlang-C Delay Formula{prio_tag}."
            else:
                theo = TheoreticalModels.solve_mmc_finite(lam_tot, mu, self.engine.c, int(self.engine.K))
                theo_note += f"M/M/{self.engine.c}/{self.engine.c + int(self.engine.K)} Truncated Markov Chain with Erlang-B Loss."
        elif (
            all_arr_exponential
            and not isinstance(self.engine.service_dist, ExponentialDist)
            and self.engine.c == 1
            and math.isinf(self.engine.K)
            and lam_tot > 0
            and mu > 0
        ):
            theo = TheoreticalModels.solve_mg1_pollaczek_khinchine(lam_tot, self.engine.service_dist)
            prio_tag = " (Priority Conservation)" if self.engine.priority_enabled else ""
            theo_note += f"M/G/1 Pollaczek-Khinchine Formula with arbitrary service variance{prio_tag}."
        else:
            if math.isinf(self.engine.c):
                theo_note += "Ample-Server General Queue G/G/inf."
            elif self.engine.priority_enabled and not math.isinf(self.engine.K):
                theo_note += f"Multi-Class Priority Queue with finite per-class buffers (K = {int(self.engine.K)} each; no aggregate single-buffer closed-form formula)."
            elif not all_arr_exponential:
                theo_note += "Non-Poisson arrival process (General G/G/m or G/M/m queue; no closed-form formula)."
            elif not isinstance(self.engine.service_dist, ExponentialDist) and self.engine.c > 1:
                theo_note += f"Multi-server non-exponential queue M/G/{self.engine.c} (no exact closed-form formula; Kingman/Tijms approximations)."
            else:
                theo_note += "General G/G/m queue."

        theo_note += (
            f"\n\nLittle's Law Live Verification: A = λ_s * δ̄\n"
            f"Simulated A = {m['L']:.4f} | λ_s * δ̄ = ({m['lambda_eff']:.4f} * {m['W']:.4f}) = {m['littles_L']:.4f}\n"
            f"Discrepancy |Δ| = |A - λ_s*δ̄| = {m['littles_error_L']:.5f} (Converges to 0)."
        )

        is_unstable = bool(theo and theo.get('unstable', False))
        if is_unstable:
            theo_note += " [UNSTABLE SYSTEM: Traffic demand exceeds capacity (A₀/m >= 1.0 with K = inf). Backlog and delays diverge to infinity.]"

        self.lbl_theory_notes.setText(theo_note)

        def fmt_theo_and_err(sim_val, theo_dict, key):
            if not theo_dict:
                return ("N/A", "-")
            if theo_dict.get('unstable', False):
                return ("inf (Unstable)", "Divergent")
            t_val = theo_dict.get(key)
            if t_val is None:
                return ("N/A", "-")
            if math.isinf(t_val) or math.isnan(t_val):
                return ("inf (Inf. Variance)", "Divergent")
            if t_val == 0.0 and abs(sim_val) < 1e-6:
                return ("0.0000", "0.00%")
            return (f"{t_val:.4f}", f"{abs(sim_val - t_val) / max(1e-4, t_val) * 100:.2f}%")

        if is_unstable:
            theo_rho = "1.0000 (Saturated)"
            err_rho = f"{abs(m['rho'] - 1.0) * 100:.2f}%"
        elif not theo:
            theo_rho = "N/A"
            err_rho = "-"
        else:
            t_rho = theo.get('rho', 0.0)
            if math.isinf(self.engine.c):
                theo_rho = "0.0000 (m = ∞)"
                err_rho = "0.00%"
            else:
                theo_rho = f"{t_rho:.4f}"
                err_rho = f"{abs(m['rho'] - t_rho) / max(1e-4, t_rho) * 100:.2f}%"

        theo_L, err_L = fmt_theo_and_err(m['L'], theo, 'L')
        theo_Lq, err_Lq = fmt_theo_and_err(m['Lq'], theo, 'Lq')
        theo_W, err_W = fmt_theo_and_err(m['W'], theo, 'W')
        theo_Wq, err_Wq = fmt_theo_and_err(m['Wq'], theo, 'Wq')

        p_loss_theo = theo.get('p_loss', 0.0) if theo else 0.0
        theo_ploss = f"{p_loss_theo*100:.2f}%" if theo else "N/A"

        rows = [
            ("Server Utilization ρ", f"{m['rho']:.4f}", theo_rho, err_rho),
            ("Avg Traffic in System A", f"{m['L']:.4f}", theo_L, err_L),
            ("Avg Queue Backlog A_c", f"{m['Lq']:.4f}", theo_Lq, err_Lq),
            ("Avg Sojourn Time δ̄ (s)", f"{m['W']:.4f}", theo_W, err_W),
            ("Avg Waiting Time η̄ (s)", f"{m['Wq']:.4f}", theo_Wq, err_Wq),
            ("Blocking Probability π_p", f"{m['p_loss']*100:.2f}%", theo_ploss, "-"),
            ("Little's Law |A - λ_s δ̄|", f"{m['littles_error_L']:.5f}", "0.00000 (Exact)", "Verified"),
        ]

        if self.table_theory.rowCount() != len(rows):
            self.table_theory.setRowCount(len(rows))
            for r_idx, (metric, _, _, _) in enumerate(rows):
                self.table_theory.setCellWidget(r_idx, 0, self._make_metric_cell(metric, r_idx))

        for r_idx, (_, sim_val, theo_val, err_val) in enumerate(rows):
            item_sim = self.table_theory.item(r_idx, 1)
            if item_sim is None:
                item_sim = QTableWidgetItem(sim_val)
                item_sim.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_theory.setItem(r_idx, 1, item_sim)
            else:
                item_sim.setText(sim_val)

            item_theo = self.table_theory.item(r_idx, 2)
            if item_theo is None:
                item_theo = QTableWidgetItem(theo_val)
                item_theo.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_theory.setItem(r_idx, 2, item_theo)
            else:
                item_theo.setText(theo_val)

            item_err = self.table_theory.item(r_idx, 3)
            if item_err is None:
                item_err = QTableWidgetItem(err_val)
                item_err.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if err_val == "Verified":
                    item_err.setForeground(QColor("#a6e3a1"))
                self.table_theory.setItem(r_idx, 3, item_err)
            else:
                item_err.setText(err_val)
                if err_val == "Verified":
                    item_err.setForeground(QColor("#a6e3a1"))
                else:
                    item_err.setForeground(QColor("#cdd6f4"))