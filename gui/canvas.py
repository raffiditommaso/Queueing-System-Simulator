"""
Interactive 2D vector canvas for visualizing the 4-stage queueing pipeline
and real-time customer animations.
"""

import math
import time
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from core.constants import PRIORITY_COLORS, to_subscript
from core.distributions import (
    ExponentialDist,
    DeterministicDist,
    UniformDist,
    ErlangDist,
    HyperexponentialDist,
    ParetoDist,
)
from core.engine import QueueSimEngine


class AnimatedCanvas(QWidget):
    def __init__(self, engine: QueueSimEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setMinimumHeight(320)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        # High-framerate animation timer for departure blinks and drifting particles
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(30)  # ~33 FPS
        self.anim_timer.timeout.connect(self._on_anim_tick)

    def trigger_blink_check(self):
        """Activate animation timer if any server is blinking or arrival is pulsing."""
        now = time.time()
        srv_active = any((now - s.last_departure_wall_time) < 0.40 for s in self.engine.servers)
        arr_active = (now - getattr(self.engine, 'last_arrival_wall_time', 0.0)) < 0.40
        if srv_active or arr_active:
            if not self.anim_timer.isActive():
                self.anim_timer.start()

    def _on_anim_tick(self):
        now = time.time()
        srv_active = any((now - s.last_departure_wall_time) < 0.40 for s in self.engine.servers)
        arr_active = (now - getattr(self.engine, 'last_arrival_wall_time', 0.0)) < 0.40
        self.update()
        if not srv_active and not arr_active:
            self.anim_timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()
        now = time.time()

        arr_dt = now - getattr(self.engine, 'last_arrival_wall_time', 0.0)
        is_arr_pulsing = (arr_dt < 0.40)
        arr_pulse_val = max(0.0, 1.0 - arr_dt / 0.40) if is_arr_pulsing else 0.0
        last_arr_prio = getattr(self.engine, 'last_arrival_prio', -1)
        last_arr_col = QColor(PRIORITY_COLORS.get(last_arr_prio, "#89b4fa"))
        last_arr_dropped = getattr(self.engine, 'last_arrival_dropped', False)

        # Background fill
        painter.fillRect(0, 0, w, h, QColor("#181825"))

        # Faint background grid for architectural polish
        painter.setPen(QPen(QColor(255, 255, 255, 8), 1))
        step = 32
        for gx in range(step // 2, w, step):
            for gy in range(step // 2, h, step):
                painter.drawPoint(gx, gy)

        # ---------------------------------------------------------------
        # Responsive 4-Stage Horizontal Geometry
        # [Stage 1: Source] -> [Stage 2: Buffer/Drops] -> [Stage 3: Servers] -> [Stage 4: Sink]
        # ---------------------------------------------------------------
        m_servers = self.engine.c
        max_servers = 5 if math.isinf(m_servers) else min(int(m_servers), 5)

        gap_x = max(18, min(32, int(w * 0.022)))
        src_w = max(195, min(225, int(w * 0.16)))
        buf_w = max(230, min(330, int(w * 0.24)))
        srv_w = max(185, min(215, int(w * 0.16))) if max_servers == 1 else max(195, min(245, int(w * 0.18)))
        sink_w = max(170, min(200, int(w * 0.14)))

        total_pipe_w = src_w + gap_x + buf_w + gap_x + srv_w + gap_x + sink_w
        start_x = max(14, (w - total_pipe_w) // 2)

        src_x = start_x
        buf_x = src_x + src_w + gap_x
        srv_x = buf_x + buf_w + gap_x
        sink_x = srv_x + srv_w + gap_x

        # Responsive Vertical Geometry
        if not self.engine.priority_enabled:
            buf_h = max(150, min(230, int(h * 0.44)))
        else:
            buf_h = max(200, min(265, int(h * 0.49)))
        buf_y = max(34, int(h * 0.08))
        mid_y = buf_y + buf_h // 2

        prio_lane_gap = 6
        prio_lane_h = (buf_h - 2 * prio_lane_gap) // 3
        prio_lane_y = [buf_y + i * (prio_lane_h + prio_lane_gap) for i in range(3)]
        prio_lane_centers = [y + prio_lane_h // 2 for y in prio_lane_y]

        # Compact Height for Traffic Source Generator (snug to content, zero empty space)
        if not self.engine.priority_enabled:
            d_dist_check = self.engine.arrival_dists.get(-1)
            has_param = isinstance(d_dist_check, (UniformDist, ErlangDist, HyperexponentialDist, ParetoDist))
            src_h = 126 if not has_param else 140
        else:
            src_h = 146
        src_y = mid_y - src_h // 2

        # Compact Height for Egress Sink (snug to 5 text lines, zero empty space)
        sink_h = 88
        sink_y = mid_y - sink_h // 2

        drop_y = buf_y + buf_h + max(14, int(h * 0.03))
        drop_w = max(240, min(buf_w, 350))
        drop_x = buf_x + (buf_w - drop_w) // 2
        drop_h = max(72, min(95, h - drop_y - 14))

        # Servers Bank Geometry (Compact when m = 1, multi-lane when m > 1)
        if max_servers == 1:
            srv_h = 56
            srv_gap = 0
            total_srv_h = srv_h
            srv_start_y = mid_y - srv_h // 2
        else:
            srv_gap = max(6, min(10, int(h * 0.015)))
            avail_h = max(buf_h + 20, int(h * 0.48))
            srv_h = max(42, min(68, (avail_h - (max_servers - 1) * srv_gap) // max_servers))
            total_srv_h = max_servers * srv_h + (max_servers - 1) * srv_gap
            srv_start_y = max(32, mid_y - total_srv_h // 2)

        server_rects = [
            QRectF(srv_x, srv_start_y + i * (srv_h + srv_gap), srv_w, srv_h)
            for i in range(max_servers)
        ]

        # ---------------------------------------------------------------
        # Vector Connecting Pipes & Transmission Links
        # ---------------------------------------------------------------
        # Link 1: Source -> Buffer
        if not self.engine.priority_enabled:
            pipe1_start = int(src_x + src_w)
            pipe1_end = int(buf_x)
            pipe_col = last_arr_col if is_arr_pulsing else QColor("#89b4fa")
            pipe_thick = 3 if is_arr_pulsing else 2
            painter.setPen(QPen(QColor("#24273a"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(pipe1_start, int(mid_y), pipe1_end, int(mid_y))
            painter.setPen(QPen(pipe_col, pipe_thick))
            painter.drawLine(pipe1_start, int(mid_y), pipe1_end, int(mid_y))

            # Directional Chevron (Source -> Buffer)
            arr1_x = pipe1_start + (pipe1_end - pipe1_start) // 2
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(pipe_col)
            painter.drawText(int(arr1_x - 4), int(mid_y + 4), ">")

            # In-flight Customer Gliding Tag from emitter into queue
            if is_arr_pulsing and not last_arr_dropped and self.engine.last_arrival_id:
                prog = 1.0 - arr_pulse_val
                cust_x = pipe1_start + prog * (pipe1_end - pipe1_start - 36)
                cust_rect = QRectF(cust_x, mid_y - 9, 36, 18)
                painter.setBrush(QBrush(QColor(pipe_col.red(), pipe_col.green(), pipe_col.blue(), int(230 * arr_pulse_val))))
                painter.setPen(QPen(QColor(17, 17, 27, int(200 * arr_pulse_val)), 1))
                painter.drawRoundedRect(cust_rect, 3, 3)
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor(17, 17, 27, int(255 * arr_pulse_val)))
                painter.drawText(cust_rect, Qt.AlignmentFlag.AlignCenter, f"#{self.engine.last_arrival_id % 1000}")
        else:
            pipe1_start = int(src_x + src_w)
            pipe1_end = int(buf_x)
            bus_in_x = pipe1_start + max(10, (pipe1_end - pipe1_start) // 3)

            trunk_col = last_arr_col if is_arr_pulsing else QColor("#89b4fa")
            trunk_thick = 3 if is_arr_pulsing else 2
            painter.setPen(QPen(QColor("#24273a"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(pipe1_start, int(mid_y), bus_in_x, int(mid_y))
            painter.setPen(QPen(trunk_col, trunk_thick))
            painter.drawLine(pipe1_start, int(mid_y), bus_in_x, int(mid_y))

            # Vertical distributor bus
            painter.setPen(QPen(QColor("#24273a"), 5))
            painter.drawLine(bus_in_x, int(prio_lane_centers[0]), bus_in_x, int(prio_lane_centers[2]))
            painter.setPen(QPen(QColor("#a6adc8"), 2))
            painter.drawLine(bus_in_x, int(prio_lane_centers[0]), bus_in_x, int(prio_lane_centers[2]))

            # 3 feeder lines into each individual priority queue lane
            for p_idx, l_cy in enumerate(prio_lane_centers):
                p_hex = PRIORITY_COLORS[p_idx]
                f_col = QColor(p_hex)
                f_thick = 3 if (is_arr_pulsing and last_arr_prio == p_idx) else 2
                painter.setPen(QPen(QColor("#24273a"), 5))
                painter.drawLine(bus_in_x, int(l_cy), pipe1_end, int(l_cy))
                painter.setPen(QPen(f_col, f_thick))
                painter.drawLine(bus_in_x, int(l_cy), pipe1_end, int(l_cy))

                arr_px = bus_in_x + (pipe1_end - bus_in_x) // 2
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(f_col)
                painter.drawText(int(arr_px - 4), int(l_cy + 4), ">")

                # In-flight Customer Gliding Tag into this priority lane
                if is_arr_pulsing and not last_arr_dropped and last_arr_prio == p_idx and self.engine.last_arrival_id:
                    prog = 1.0 - arr_pulse_val
                    cust_x = pipe1_start + prog * (pipe1_end - pipe1_start - 36)
                    cust_y = mid_y + prog * (l_cy - mid_y) - 9
                    cust_rect = QRectF(cust_x, cust_y, 36, 18)
                    painter.setBrush(QBrush(QColor(f_col.red(), f_col.green(), f_col.blue(), int(230 * arr_pulse_val))))
                    painter.setPen(QPen(QColor(17, 17, 27, int(200 * arr_pulse_val)), 1))
                    painter.drawRoundedRect(cust_rect, 3, 3)
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.setPen(QColor(17, 17, 27, int(255 * arr_pulse_val)))
                    painter.drawText(cust_rect, Qt.AlignmentFlag.AlignCenter, f"#{self.engine.last_arrival_id % 1000}")

        # Link 2: Buffer -> Servers Bank
        if not self.engine.priority_enabled:
            if max_servers == 1:
                pipe2_start = int(buf_x + buf_w)
                pipe2_end = int(srv_x)
                painter.setPen(QPen(QColor("#24273a"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(pipe2_start, int(mid_y), pipe2_end, int(mid_y))
                painter.setPen(QPen(QColor("#a6adc8"), 2))
                painter.drawLine(pipe2_start, int(mid_y), pipe2_end, int(mid_y))
                arr2_x = pipe2_start + (pipe2_end - pipe2_start) // 2
                painter.setPen(QColor("#a6adc8"))
                painter.drawText(int(arr2_x - 4), int(mid_y + 4), ">")
            else:
                bus_x = buf_x + buf_w + gap_x // 2
                # Trunk line from buffer exit to bus
                painter.setPen(QPen(QColor("#24273a"), 5))
                painter.drawLine(int(buf_x + buf_w), int(mid_y), int(bus_x), int(mid_y))
                painter.setPen(QPen(QColor("#a6adc8"), 2))
                painter.drawLine(int(buf_x + buf_w), int(mid_y), int(bus_x), int(mid_y))

                # Vertical dispatcher bus
                y_top = int(server_rects[0].center().y())
                y_bot = int(server_rects[-1].center().y())
                painter.setPen(QPen(QColor("#24273a"), 5))
                painter.drawLine(int(bus_x), y_top, int(bus_x), y_bot)
                painter.setPen(QPen(QColor("#a6adc8"), 2))
                painter.drawLine(int(bus_x), y_top, int(bus_x), y_bot)

                # Branches into each server
                for s_rect in server_rects:
                    sy_mid = int(s_rect.center().y())
                    painter.setPen(QPen(QColor("#24273a"), 4))
                    painter.drawLine(int(bus_x), sy_mid, int(srv_x), sy_mid)
                    painter.setPen(QPen(QColor("#a6adc8"), 1.8))
                    painter.drawLine(int(bus_x), sy_mid, int(srv_x), sy_mid)
                    painter.setPen(QColor("#a6adc8"))
                    painter.drawText(int(srv_x - 12), int(sy_mid + 4), ">")
        else:
            bus_x = buf_x + buf_w + gap_x // 2
            # 3 exit lines from each queue lane into bus_x
            for p_idx, l_cy in enumerate(prio_lane_centers):
                p_hex = PRIORITY_COLORS[p_idx]
                painter.setPen(QPen(QColor("#24273a"), 5))
                painter.drawLine(int(buf_x + buf_w), int(l_cy), int(bus_x), int(l_cy))
                painter.setPen(QPen(QColor(p_hex), 2))
                painter.drawLine(int(buf_x + buf_w), int(l_cy), int(bus_x), int(l_cy))

                arr2_px = int(buf_x + buf_w) + (int(bus_x) - int(buf_x + buf_w)) // 2
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor(p_hex))
                painter.drawText(int(arr2_px - 4), int(l_cy + 4), ">")

            # Vertical dispatcher bus spanning from top server/queue to bottom server/queue
            y_top = min(int(server_rects[0].center().y()), int(prio_lane_centers[0]))
            y_bot = max(int(server_rects[-1].center().y()), int(prio_lane_centers[2]))
            painter.setPen(QPen(QColor("#24273a"), 5))
            painter.drawLine(int(bus_x), y_top, int(bus_x), y_bot)
            painter.setPen(QPen(QColor("#a6adc8"), 2))
            painter.drawLine(int(bus_x), y_top, int(bus_x), y_bot)

            # Branches into each server
            for s_rect in server_rects:
                sy_mid = int(s_rect.center().y())
                painter.setPen(QPen(QColor("#24273a"), 4))
                painter.drawLine(int(bus_x), sy_mid, int(srv_x), sy_mid)
                painter.setPen(QPen(QColor("#a6adc8"), 1.8))
                painter.drawLine(int(bus_x), sy_mid, int(srv_x), sy_mid)
                painter.setPen(QColor("#a6adc8"))
                painter.drawText(int(srv_x - 12), int(sy_mid + 4), ">")

        # Link 3: Servers Bank -> Egress Sink
        for s_rect in server_rects:
            sy_mid = int(s_rect.center().y())
            painter.setPen(QPen(QColor("#24273a"), 5))
            painter.drawLine(int(srv_x + srv_w), sy_mid, int(sink_x), int(mid_y))
            painter.setPen(QPen(QColor("#a6e3a1"), 1.8))
            painter.drawLine(int(srv_x + srv_w), sy_mid, int(sink_x), int(mid_y))

        arr3_x = srv_x + srv_w + (sink_x - (srv_x + srv_w)) // 2
        painter.setPen(QColor("#a6e3a1"))
        painter.drawText(int(arr3_x - 4), int(mid_y + 4), ">")

        # Link 4: Buffer Inlet -> Drop-Tail Overflow (REJECTED)
        pipe_drop_x = int(buf_x + 36)
        drop_pulse = is_arr_pulsing and last_arr_dropped
        d_pen_col = QColor("#ff5555") if drop_pulse else QColor("#f38ba8")
        d_pen_w = 3 if drop_pulse else 2
        painter.setPen(QPen(d_pen_col, d_pen_w, Qt.PenStyle.DashLine))
        painter.drawLine(pipe_drop_x, int(buf_y + buf_h), pipe_drop_x, int(drop_y))
        painter.setPen(d_pen_col)
        painter.drawText(pipe_drop_x - 3, int(drop_y - 3), "v")
        painter.setFont(QFont("Segoe UI", 6))
        painter.setPen(d_pen_col)
        painter.drawText(pipe_drop_x + 6, int(buf_y + buf_h + (drop_y - (buf_y + buf_h)) // 2 + 3), "Drop-Tail")

        if drop_pulse and self.engine.last_arrival_id:
            prog = 1.0 - arr_pulse_val
            dcust_y = (buf_y + buf_h) + prog * (drop_y - (buf_y + buf_h) - 16)
            dcust_rect = QRectF(pipe_drop_x - 16, dcust_y, 32, 16)
            painter.setBrush(QBrush(QColor(243, 139, 168, int(240 * arr_pulse_val))))
            painter.setPen(QPen(QColor(17, 17, 27, int(200 * arr_pulse_val)), 1))
            painter.drawRoundedRect(dcust_rect, 3, 3)
            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
            painter.setPen(QColor(17, 17, 27, int(255 * arr_pulse_val)))
            painter.drawText(dcust_rect, Qt.AlignmentFlag.AlignCenter, f"#{self.engine.last_arrival_id % 1000}")

        # ---------------------------------------------------------------
        # STAGE 1: Explicit Traffic Arrival Stream (Source Generator)
        # ---------------------------------------------------------------
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#89b4fa"))
        painter.drawText(int(src_x), int(src_y - 8), "TRAFFIC SOURCE GENERATOR")

        painter.setPen(QPen(QColor("#313244"), 1.5))
        painter.setBrush(QBrush(QColor("#1e1e2e")))
        painter.drawRoundedRect(QRectF(src_x, src_y, src_w, src_h), 8, 8)

        # Emitter Port inside right border with expanding halo pulse
        if is_arr_pulsing:
            halo_r = 5.5 + (1.0 - arr_pulse_val) * 7.0
            painter.setPen(QPen(QColor(last_arr_col.red(), last_arr_col.green(), last_arr_col.blue(), int(180 * arr_pulse_val)), 2))
            painter.setBrush(QBrush(QColor(last_arr_col.red(), last_arr_col.green(), last_arr_col.blue(), int(60 * arr_pulse_val))))
            painter.drawEllipse(QPointF(src_x + src_w - 5.5, mid_y), halo_r, halo_r)

        emitter_col = last_arr_col if is_arr_pulsing else QColor("#89b4fa")
        painter.setPen(QPen(QColor("#11111b"), 2))
        painter.setBrush(QBrush(emitter_col))
        painter.drawEllipse(QRectF(src_x + src_w - 11, mid_y - 5.5, 11, 11))

        if not self.engine.priority_enabled:
            d_dist = self.engine.arrival_dists.get(-1, ExponentialDist(1.0))
            d_sym = d_dist.kendall_symbol()

            lam = 1.0 / max(1e-6, d_dist.mean())
            mean_t = d_dist.mean()
            var_t = d_dist.variance()
            var_str = f"{var_t:.2f}s²" if not math.isinf(var_t) else "inf"
            cv_val = d_dist.cv()

            if isinstance(d_dist, ExponentialDist):
                model_title = "Poisson Arrival Process"
                dist_model = "Model: Exponential (M)"
                param_line = None
                rate_line = f"Rate: λ = {d_dist.rate:.2f} cust/s"
            elif isinstance(d_dist, UniformDist):
                model_title = "Uniform Interarrival Process"
                dist_model = "Model: Continuous Uniform (U)"
                param_line = f"Bounds: a = {d_dist.a:.2f}s, b = {d_dist.b:.2f}s"
                rate_line = f"Rate: λ = {lam:.2f} cust/s"
            elif isinstance(d_dist, DeterministicDist):
                model_title = "Deterministic Arrival Process"
                dist_model = "Model: Fixed Interval (D)"
                param_line = f"Interval: D = {d_dist.value:.2f}s"
                rate_line = f"Rate: λ = {lam:.2f} cust/s"
            elif isinstance(d_dist, ErlangDist):
                model_title = f"Erlang-{to_subscript(d_dist.k)} Renewal Process"
                dist_model = f"Model: Erlang (E{to_subscript(d_dist.k)})"
                param_line = f"Phases: k = {d_dist.k}"
                rate_line = f"Rate: λ = {lam:.2f} cust/s"
            elif isinstance(d_dist, HyperexponentialDist):
                model_title = "2-Phase Hyperexponential (H₂)"
                dist_model = "Model: Hyperexponential (H₂)"
                param_line = f"Branch: p₁={d_dist.p1:.2f} | r₁={d_dist.r1:.2f}, r₂={d_dist.r2:.2f}"
                rate_line = f"Rate: λ = {lam:.2f} cust/s"
            elif isinstance(d_dist, ParetoDist):
                model_title = "Heavy-Tailed Pareto Process"
                dist_model = "Model: Pareto Heavy-Tailed"
                param_line = f"Shape: α = {d_dist.alpha:.2f} | Scale: xₘ = {d_dist.xm:.2f}s"
                rate_line = f"Rate: λ = {lam:.2f} cust/s"
            else:
                model_title = f"{d_dist.name} Arrival Process"
                dist_model = f"Model: {d_dist.name} ({d_sym})"
                param_line = f"Parameters: {d_dist.params}"
                rate_line = f"Rate: λ = {lam:.2f} cust/s"

            # Clean unified text breakdown with bold emphasis for readability
            y_pos = int(src_y + 16)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(int(src_x + 10), y_pos, model_title)

            y_pos += 14
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#cdd6f4"))
            painter.drawText(int(src_x + 10), y_pos, "Discipline: Single-Class FIFO")

            y_pos += 14
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor("#cdd6f4"))
            painter.drawText(int(src_x + 10), y_pos, dist_model)

            if param_line:
                y_pos += 14
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor("#cdd6f4"))
                painter.drawText(int(src_x + 10), y_pos, param_line)

            y_pos += 14
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(int(src_x + 10), y_pos, rate_line)

            y_pos += 14
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor("#cdd6f4"))
            painter.drawText(int(src_x + 10), y_pos, f"Mean: E[T] = {mean_t:.2f}s")

            y_pos += 13
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor("#a6adc8"))
            painter.drawText(int(src_x + 10), y_pos, f"Var[T] = {var_str} | Cv = {cv_val:.2f}")

            # Total Injected Box at bottom
            cbox_y = int(src_y + src_h - 25)
            painter.setPen(QPen(QColor("#313244"), 1))
            painter.setBrush(QBrush(QColor("#181825")))
            painter.drawRoundedRect(QRectF(src_x + 8, cbox_y, src_w - 16, 20), 4, 4)

            tot_arr = self.engine.customers_arrived_total
            obs_lam = tot_arr / max(1e-4, self.engine.current_time) if self.engine.current_time > 0 else 0.0
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                QRectF(src_x + 8, cbox_y, src_w - 16, 20),
                Qt.AlignmentFlag.AlignCenter,
                f"Injected: {tot_arr} cust (λ_obs = {obs_lam:.2f}/s)",
            )
        else:
            y_pos = int(src_y + 16)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(int(src_x + 10), y_pos, "Priority Traffic Source")

            y_pos += 14
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#cdd6f4"))
            painter.drawText(int(src_x + 10), y_pos, "Discipline: Priority Queuing (QoS)")

            p_rates = [
                (0, "High Class (P₀)", PRIORITY_COLORS[0]),
                (1, "Medium Class (P₁)", PRIORITY_COLORS[1]),
                (2, "Low Class (P₂)", PRIORITY_COLORS[2]),
            ]
            for p_id, p_title, p_col in p_rates:
                y_pos += 16
                d_p = self.engine.arrival_dists.get(p_id)
                r_p = 1.0 / max(1e-6, d_p.mean()) if d_p else 0.0

                painter.setPen(QPen(QColor("#11111b"), 1))
                painter.setBrush(QBrush(QColor(p_col)))
                painter.drawEllipse(QRectF(src_x + 10, y_pos - 6, 7, 7))

                sub_idx = to_subscript(p_id)
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor("#cdd6f4"))
                painter.drawText(int(src_x + 22), y_pos, f"{p_title}: λ{sub_idx} = {r_p:.2f}")

            tot_lam = sum(1.0 / max(1e-6, d.mean()) for d in self.engine.arrival_dists.values() if d is not None)
            y_pos += 16
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(int(src_x + 10), y_pos, f"Aggregate Arrival: Σλ = {tot_lam:.2f} cust/s")

            cbox_y = int(src_y + src_h - 25)
            painter.setPen(QPen(QColor("#313244"), 1))
            painter.setBrush(QBrush(QColor("#181825")))
            painter.drawRoundedRect(QRectF(src_x + 8, cbox_y, src_w - 16, 20), 4, 4)

            tot_arr = self.engine.customers_arrived_total
            obs_lam = tot_arr / max(1e-4, self.engine.current_time) if self.engine.current_time > 0 else 0.0
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                QRectF(src_x + 8, cbox_y, src_w - 16, 20),
                Qt.AlignmentFlag.AlignCenter,
                f"Injected: {tot_arr} cust (λ_obs = {obs_lam:.2f}/s)",
            )

        # ---------------------------------------------------------------
        # STAGE 2: Queue Buffer & Waiting Slots
        # ---------------------------------------------------------------
        k_text = "inf" if math.isinf(self.engine.K) else str(self.engine.K)

        if not self.engine.priority_enabled:
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#cdd6f4"))
            painter.drawText(int(buf_x), int(buf_y - 8), f"FIFO Queue Buffer (Cap: K = {k_text})")

            painter.setPen(QPen(QColor("#45475a"), 1.8))
            painter.setBrush(QBrush(QColor("#1e1e2e")))
            painter.drawRoundedRect(QRectF(buf_x, buf_y, buf_w, buf_h), 8, 8)

            # Sub-bar: Waiting Count + Occupancy Bar
            q_len = self.engine.total_in_queue
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor("#a6adc8"))
            painter.drawText(int(buf_x + 10), int(buf_y + 18), f"Waiting: {q_len} cust")

            # Mini Occupancy Progress Bar
            bar_x = buf_x + 10
            bar_y = buf_y + 24
            bar_w = buf_w - 20
            bar_h = 5
            painter.setPen(QPen(QColor("#313244"), 1))
            painter.setBrush(QBrush(QColor("#181825")))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

            if not math.isinf(self.engine.K) and self.engine.K > 0:
                pct = min(1.0, q_len / self.engine.K)
                fill_col = QColor("#f38ba8") if pct >= 0.9 else (QColor("#f9e2af") if pct >= 0.6 else QColor("#89b4fa"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(fill_col))
                painter.drawRoundedRect(QRectF(bar_x, bar_y, int(bar_w * pct), bar_h), 2, 2)

            # Queue Compartment Chamber (Storage Slots)
            slot_box_x = buf_x + 8
            slot_box_y = buf_y + 34
            slot_box_w = buf_w - 16
            slot_box_h = buf_h - 42

            painter.setPen(QPen(QColor("#313244"), 1))
            painter.setBrush(QBrush(QColor("#181825")))
            painter.drawRoundedRect(QRectF(slot_box_x, slot_box_y, slot_box_w, slot_box_h), 6, 6)

            # Flow Labels: Tail (Inlet) on left, HoL (Head of Line -> Servers) on right
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#6c7086"))
            painter.drawText(int(slot_box_x + 6), int(slot_box_y + 12), "< In")
            painter.setPen(QColor("#a6e3a1"))
            painter.drawText(int(slot_box_x + slot_box_w - 38), int(slot_box_y + 12), "HoL >")

            # Customers List
            display_customers = list(self.engine.queues[-1])

            slot_sz_w = 34
            slot_sz_h = 24
            slot_margin = 5
            area_w = slot_box_w - 16
            area_h = slot_box_h - 18

            cols = max(1, int(area_w // (slot_sz_w + slot_margin)))
            rows = max(1, int(area_h // (slot_sz_h + slot_margin)))
            max_draw = cols * rows

            start_slots_x = slot_box_x + 8
            start_slots_y = slot_box_y + 16

            # Render discrete slots
            if not math.isinf(self.engine.K) and self.engine.K <= max_draw:
                total_slots_to_show = int(self.engine.K)
            else:
                total_slots_to_show = max_draw

            for idx in range(total_slots_to_show):
                r = idx // cols
                c = (cols - 1) - (idx % cols)
                cx = start_slots_x + c * (slot_sz_w + slot_margin)
                cy = start_slots_y + r * (slot_sz_h + slot_margin)

                if idx < len(display_customers):
                    cust = display_customers[idx]
                    p_col = QColor(PRIORITY_COLORS.get(cust.priority, "#89b4fa"))
                    painter.setBrush(QBrush(p_col))
                    painter.setPen(QPen(QColor("#11111b"), 1.2))
                    painter.drawRoundedRect(QRectF(cx, cy, slot_sz_w, slot_sz_h), 4, 4)

                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.setPen(QColor("#11111b"))
                    painter.drawText(QRectF(cx, cy, slot_sz_w, slot_sz_h), Qt.AlignmentFlag.AlignCenter, f"#{cust.id % 1000}")
                else:
                    # Subtle outline for empty buffer slot
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor("#313244"), 1, Qt.PenStyle.DashLine))
                    painter.drawRoundedRect(QRectF(cx, cy, slot_sz_w, slot_sz_h), 4, 4)
                    painter.setFont(QFont("Segoe UI", 6))
                    painter.setPen(QColor("#45475a"))
                    painter.drawText(QRectF(cx, cy, slot_sz_w, slot_sz_h), Qt.AlignmentFlag.AlignCenter, f"{idx+1}")

            if len(display_customers) > max_draw:
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor("#f38ba8"))
                painter.drawText(
                    int(slot_box_x + 8),
                    int(slot_box_y + slot_box_h - 4),
                    f"+{len(display_customers) - max_draw} more waiting in buffer...",
                )
        else:
            # -----------------------------------------------------------
            # PRIORITY QUEUING: 3 INDIVIDUAL QUEUE BUFFERS (K each)
            # -----------------------------------------------------------
            tot_q = self.engine.total_in_queue
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#cdd6f4"))
            painter.drawText(
                int(buf_x),
                int(buf_y - 8),
                f"Individual Priority Queues (Cap: K = {k_text} each | Waiting: {tot_q})",
            )

            prio_configs = [
                (0, "High Queue (P₀)", PRIORITY_COLORS[0]),
                (1, "Medium Queue (P₁)", PRIORITY_COLORS[1]),
                (2, "Low Queue (P₂)", PRIORITY_COLORS[2]),
            ]

            for i, (p_id, p_name, p_hex) in enumerate(prio_configs):
                lane_y = prio_lane_y[i]
                lane_rect = QRectF(buf_x, lane_y, buf_w, prio_lane_h)
                p_col = QColor(p_hex)

                # Distinct Queue Card Frame with Priority Color accent
                painter.setPen(QPen(QColor(p_col.red(), p_col.green(), p_col.blue(), 160), 1.3))
                painter.setBrush(QBrush(QColor("#181825")))
                painter.drawRoundedRect(lane_rect, 6, 6)

                # Priority badge dot
                painter.setPen(QPen(QColor("#11111b"), 1))
                painter.setBrush(QBrush(p_col))
                painter.drawEllipse(QRectF(buf_x + 8, lane_y + 6, 6, 6))

                # Queue Title
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(p_col)
                painter.drawText(int(buf_x + 18), int(lane_y + 13), p_name)

                # Individual queue count
                q_custs = list(self.engine.queues[p_id])
                painter.setFont(QFont("Segoe UI", 7))
                painter.setPen(QColor("#a6adc8"))
                painter.drawText(int(buf_x + buf_w - 95), int(lane_y + 13), f"Waiting: {len(q_custs)}/{k_text}")

                # Mini Occupancy Progress Bar for this queue
                mbar_x = buf_x + 8
                mbar_y = lane_y + 17
                mbar_w = buf_w - 16
                mbar_h = 3
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor("#11111b")))
                painter.drawRoundedRect(QRectF(mbar_x, mbar_y, mbar_w, mbar_h), 1, 1)

                if not math.isinf(self.engine.K) and self.engine.K > 0:
                    pct = min(1.0, len(q_custs) / self.engine.K)
                    painter.setBrush(QBrush(p_col))
                    painter.drawRoundedRect(QRectF(mbar_x, mbar_y, int(mbar_w * pct), mbar_h), 1, 1)

                # Slot Compartment Chamber inside this queue
                slot_box_x = buf_x + 6
                slot_box_y = lane_y + 23
                slot_box_w = buf_w - 12
                slot_box_h = prio_lane_h - 27

                painter.setPen(QPen(QColor("#313244"), 1))
                painter.setBrush(QBrush(QColor("#13131e")))
                painter.drawRoundedRect(QRectF(slot_box_x, slot_box_y, slot_box_w, slot_box_h), 4, 4)

                # Flow Labels
                painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                painter.setPen(QColor("#6c7086"))
                painter.drawText(int(slot_box_x + 4), int(slot_box_y + slot_box_h // 2 + 3), "< In")
                painter.setPen(QColor("#a6e3a1"))
                painter.drawText(int(slot_box_x + slot_box_w - 28), int(slot_box_y + slot_box_h // 2 + 3), "HoL >")

                # Discrete slots for this queue
                slot_sz_w = 32
                slot_sz_h = max(15, min(20, int(slot_box_h - 4)))
                slot_margin = 4
                start_sx = slot_box_x + 28
                avail_sw = slot_box_w - 58
                max_lane_slots = max(1, int(avail_sw // (slot_sz_w + slot_margin)))

                if not math.isinf(self.engine.K) and self.engine.K <= max_lane_slots:
                    slots_to_show = int(self.engine.K)
                else:
                    slots_to_show = max_lane_slots

                sy = slot_box_y + (slot_box_h - slot_sz_h) // 2

                for s_idx in range(slots_to_show):
                    sx = start_sx + (slots_to_show - 1 - s_idx) * (slot_sz_w + slot_margin)
                    if s_idx < len(q_custs):
                        cust = q_custs[s_idx]
                        painter.setBrush(QBrush(p_col))
                        painter.setPen(QPen(QColor("#11111b"), 1.2))
                        painter.drawRoundedRect(QRectF(sx, sy, slot_sz_w, slot_sz_h), 3, 3)

                        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                        painter.setPen(QColor("#11111b"))
                        painter.drawText(QRectF(sx, sy, slot_sz_w, slot_sz_h), Qt.AlignmentFlag.AlignCenter, f"#{cust.id % 1000}")
                    else:
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.setPen(QPen(QColor("#313244"), 1, Qt.PenStyle.DashLine))
                        painter.drawRoundedRect(QRectF(sx, sy, slot_sz_w, slot_sz_h), 3, 3)
                        painter.setFont(QFont("Segoe UI", 6))
                        painter.setPen(QColor("#45475a"))
                        painter.drawText(QRectF(sx, sy, slot_sz_w, slot_sz_h), Qt.AlignmentFlag.AlignCenter, f"{s_idx+1}")

                if len(q_custs) > max_lane_slots:
                    painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                    painter.setPen(QColor("#f38ba8"))
                    painter.drawText(
                        int(slot_box_x + slot_box_w - 60),
                        int(slot_box_y + slot_box_h - 2),
                        f"+{len(q_custs) - max_lane_slots}",
                    )

        # ---------------------------------------------------------------
        # STAGE 2 (Lower): REJECTED Box (Buffer Overflow / Drop-Tail)
        # ---------------------------------------------------------------
        drop_border_col = QColor("#ff5555") if (is_arr_pulsing and last_arr_dropped) else QColor("#e06c75")
        drop_border_w = 3.0 if (is_arr_pulsing and last_arr_dropped) else 1.8
        painter.setPen(QPen(drop_border_col, drop_border_w))
        painter.setBrush(QBrush(QColor("#25141b")))
        painter.drawRoundedRect(QRectF(drop_x, drop_y, drop_w, drop_h), 6, 6)

        # Left Column: Statistics & Title strictly "REJECTED"
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#f38ba8"))
        painter.drawText(int(drop_x + 10), int(drop_y + 16), "REJECTED")

        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(int(drop_x + 10), int(drop_y + 36), f"Drops: {self.engine.customers_dropped_total}")

        tot_arr = max(1, self.engine.customers_arrived_total)
        ploss_pct = (self.engine.customers_dropped_total / tot_arr) * 100.0
        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QColor("#eba0ac"))
        if not self.engine.priority_enabled:
            painter.drawText(int(drop_x + 10), int(drop_y + 52), f"Loss Rate: {ploss_pct:.2f}%")
        else:
            d0 = self.engine.customers_dropped_by_prio[0]
            d1 = self.engine.customers_dropped_by_prio[1]
            d2 = self.engine.customers_dropped_by_prio[2]
            painter.drawText(int(drop_x + 10), int(drop_y + 49), f"Loss Rate: {ploss_pct:.1f}%")
            painter.drawText(int(drop_x + 10), int(drop_y + 61), f"P₀:{d0} P₁:{d1} P₂:{d2}")

        # Vertical divider
        painter.setPen(QPen(QColor("#3d232c"), 1, Qt.PenStyle.SolidLine))
        painter.drawLine(int(drop_x + 116), int(drop_y + 8), int(drop_x + 116), int(drop_y + drop_h - 8))

        # Right Column: Framed Recent Drops Tray
        tray_x = drop_x + 124
        tray_y = drop_y + 8
        tray_w = drop_w - 132
        tray_h = drop_h - 16

        painter.setPen(QPen(QColor("#542e39"), 1))
        painter.setBrush(QBrush(QColor("#180c12")))
        painter.drawRoundedRect(QRectF(tray_x, tray_y, tray_w, tray_h), 4, 4)

        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.setPen(QColor("#a6adc8"))
        painter.drawText(int(tray_x + 6), int(tray_y + 13), "Recent Drops:")

        recent = list(self.engine.recent_drops)[-4:]
        for d_idx, d_cust in enumerate(recent):
            row = d_idx // 2
            col = d_idx % 2
            cx = tray_x + 6 + col * 34
            cy = tray_y + 18 + row * 18

            painter.setBrush(QBrush(QColor("#f38ba8")))
            painter.setPen(QPen(QColor("#11111b"), 1))
            painter.drawRoundedRect(QRectF(cx, cy, 28, 14), 3, 3)

            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
            painter.setPen(QColor("#11111b"))
            painter.drawText(QRectF(cx, cy, 28, 14), Qt.AlignmentFlag.AlignCenter, f"#{d_cust.id % 1000}")

        # ---------------------------------------------------------------
        # STAGE 3: Servers Bank (m Servers) with Departure Blink
        # ---------------------------------------------------------------
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        m_str = "∞" if math.isinf(self.engine.c) else str(self.engine.c)
        painter.drawText(int(srv_x), int(srv_start_y - 8), f"Servers Bank (m = {m_str})")

        mean_s = self.engine.service_dist.mean()
        mu_rate = (1.0 / mean_s) if (not math.isinf(mean_s) and mean_s > 0) else 0.0

        for s_idx in range(max_servers):
            if s_idx >= len(self.engine.servers):
                break
            server = self.engine.servers[s_idx]
            s_rect = server_rects[s_idx]
            is_busy = server.is_busy

            # Departure Blink Calculation
            dt = now - server.last_departure_wall_time
            is_blinking = (dt < 0.38)
            blink_val = max(0.0, min(1.0, 1.0 - (dt / 0.38))) if is_blinking else 0.0

            # 1. Radiant Aura Glow on Departure
            if is_blinking:
                aura_rect = s_rect.adjusted(-6 * blink_val, -6 * blink_val, 6 * blink_val, 6 * blink_val)
                painter.setPen(QPen(QColor(166, 227, 161, int(200 * blink_val)), 2))
                painter.setBrush(QBrush(QColor(166, 227, 161, int(45 * blink_val))))
                painter.drawRoundedRect(aura_rect, 8, 8)

            # 2. Server Card Frame & Background
            if is_blinking:
                bg_col = QColor(34, 55, 42)
                border_col = QColor(220, 255, 230)
                border_w = 2.5
            elif is_busy:
                bg_col = QColor("#1e2a22")
                border_col = QColor("#a6e3a1")
                border_w = 2.0
            else:
                bg_col = QColor("#181825")
                border_col = QColor("#313244")
                border_w = 1.5

            painter.setPen(QPen(border_col, border_w))
            painter.setBrush(QBrush(bg_col))
            painter.drawRoundedRect(s_rect, 6, 6)

            # Server Title
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#cdd6f4"))
            painter.drawText(int(s_rect.x() + 8), int(s_rect.y() + 15), f"Server {s_idx + 1}")

            # Status Pill (Top Right)
            pill_w = 78 if is_blinking else 48
            pill_rect = QRectF(s_rect.right() - pill_w - 6, s_rect.y() + 4, pill_w, 16)

            if is_blinking and server.last_departed_customer_id:
                painter.setPen(QPen(QColor("#11111b"), 1))
                painter.setBrush(QBrush(QColor("#a6e3a1")))
                painter.drawRoundedRect(pill_rect, 3, 3)
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor("#11111b"))
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, f"SERVED #{server.last_departed_customer_id}")
            elif is_busy:
                painter.setPen(QPen(QColor("#a6e3a1"), 1))
                painter.setBrush(QBrush(QColor("#22332a")))
                painter.drawRoundedRect(pill_rect, 3, 3)
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor("#a6e3a1"))
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "BUSY")
            else:
                painter.setPen(QPen(QColor("#313244"), 1))
                painter.setBrush(QBrush(QColor("#1e1e2e")))
                painter.drawRoundedRect(pill_rect, 3, 3)
                painter.setFont(QFont("Segoe UI", 7))
                painter.setPen(QColor("#6c7086"))
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "IDLE")

            # Middle / Serving Details
            if is_busy and server.current_customer is not None:
                cust = server.current_customer
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#cdd6f4"))
                painter.drawText(int(s_rect.x() + 8), int(s_rect.y() + 29), f"Serving Cust #{cust.id}")

                # Serving Customer Chip
                chip_w = 48
                chip_h = 18
                chip_x = s_rect.right() - chip_w - 6
                chip_y = s_rect.y() + 22
                p_col = QColor(PRIORITY_COLORS.get(cust.priority, "#89b4fa"))
                painter.setBrush(QBrush(p_col))
                painter.setPen(QPen(QColor("#11111b"), 1))
                painter.drawRoundedRect(QRectF(chip_x, chip_y, chip_w, chip_h), 3, 3)

                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor("#11111b"))
                painter.drawText(QRectF(chip_x, chip_y, chip_w, chip_h), Qt.AlignmentFlag.AlignCenter, f"#{cust.id}")
            else:
                painter.setFont(QFont("Segoe UI", 7))
                painter.setPen(QColor("#a6adc8"))
                painter.drawText(int(s_rect.x() + 8), int(s_rect.y() + 29), "IDLE (Free)")

            # Bottom Stats (visible on all compact cards >= 48px)
            if s_rect.height() >= 48:
                painter.setFont(QFont("Segoe UI", 7))
                painter.setPen(QColor("#a6adc8"))
                painter.drawText(
                    int(s_rect.x() + 8),
                    int(s_rect.bottom() - 6),
                    f"μ = {mu_rate:.2f} cust/s | Served: {server.customers_served}",
                )

            # 3. Departing Particle Tag Animation
            if is_blinking and server.last_departed_customer_id:
                part_x = s_rect.right() + 4 + int((1.0 - blink_val) * 26)
                part_y = s_rect.center().y() - 9
                part_rect = QRectF(part_x, part_y, 48, 18)
                painter.setBrush(QBrush(QColor(166, 227, 161, int(230 * blink_val))))
                painter.setPen(QPen(QColor(17, 17, 27, int(180 * blink_val)), 1))
                painter.drawRoundedRect(part_rect, 3, 3)

                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor(17, 17, 27, int(255 * blink_val)))
                painter.drawText(part_rect, Qt.AlignmentFlag.AlignCenter, f"#{server.last_departed_customer_id}")

        if math.isinf(self.engine.c):
            extra_busy = max(0, self.engine.busy_servers_count - max_servers)
            more_txt = f"+{extra_busy} more busy servers (m = ∞)..." if extra_busy > 0 else "Ample Servers (m = ∞)..."
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor("#a6adc8"))
            painter.drawText(
                int(srv_x),
                int(srv_start_y + total_srv_h + 14),
                more_txt,
            )
        elif self.engine.c > max_servers:
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor("#a6adc8"))
            painter.drawText(
                int(srv_x),
                int(srv_start_y + total_srv_h + 14),
                f"+{self.engine.c - max_servers} more active servers...",
            )

        # ---------------------------------------------------------------
        # STAGE 4: Egress Sink (Completed Flow Card)
        # ---------------------------------------------------------------
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#cdd6f4"))
        painter.drawText(int(sink_x), int(sink_y - 8), "EGRESS SINK")

        painter.setPen(QPen(QColor("#313244"), 1.5))
        painter.setBrush(QBrush(QColor("#1e1e2e")))
        painter.drawRoundedRect(QRectF(sink_x, sink_y, sink_w, sink_h), 8, 8)

        # Receiver Port inside Left Edge
        painter.setPen(QPen(QColor("#11111b"), 2))
        painter.setBrush(QBrush(QColor("#a6e3a1")))
        painter.drawEllipse(QRectF(sink_x, mid_y - 5.5, 11, 11))

        # Sink Content (Snug, clean, readable with bold metrics)
        text_x = int(sink_x + 22)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#a6e3a1"))
        painter.drawText(text_x, int(sink_y + 16), "Completed Stream")

        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(text_x, int(sink_y + 33), f"Served: {self.engine.customers_served_total}")

        t_now = max(1e-6, self.engine.current_time)
        lam_eff = self.engine.customers_served_total / t_now
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#cdd6f4"))
        painter.drawText(text_x, int(sink_y + 49), f"Throughput: {lam_eff:.2f} cust/s")

        if self.engine.customers_served_total > 0:
            w_mean = self.engine.total_system_time / self.engine.customers_served_total
        else:
            w_mean = 0.0
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#cdd6f4"))
        painter.drawText(text_x, int(sink_y + 64), f"Mean System W: {w_mean:.2f}s")

        # Bottom Subtitle
        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QColor("#a6adc8"))
        painter.drawText(text_x, int(sink_y + 78), "Egress Network Sink")

        painter.end()