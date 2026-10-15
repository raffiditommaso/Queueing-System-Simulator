"""
Interactive Markov Chain State-Transition Diagram Widget.
Displays the continuous-time birth-death Markov chain representing the queueing system,
dynamically highlighting the active state n(t) in real time.
"""

import math
from typing import Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF

from core.engine import QueueSimEngine
from core.theory import TheoreticalModels


class MarkovChainView(QWidget):
    """
    Live 2D vector widget rendering the Markov chain state-transition diagram
    for M/M/c and general queueing systems (Birth-Death state space).
    """

    def __init__(self, engine: QueueSimEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setMinimumHeight(98)
        self.setMaximumHeight(108)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()

        # Background Container Card
        painter.setPen(QPen(QColor("#313244"), 1.2))
        painter.setBrush(QBrush(QColor("#181825")))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 6, 6)

        c = self.engine.c
        K = self.engine.K
        curr_n = self.engine.total_in_system
        busy_count = self.engine.busy_servers_count
        q_count = self.engine.total_in_queue

        # System Capacity
        is_inf_k = math.isinf(K)
        total_K = (3 * int(K)) if (self.engine.priority_enabled and not is_inf_k) else (math.inf if is_inf_k else int(K))
        N_max = math.inf if is_inf_k else (c + total_K)

        # Rates
        lam_tot = sum(1.0 / max(1e-6, d.mean()) for d in self.engine.arrival_dists.values() if d is not None)
        mu_rate = 1.0 / max(1e-6, self.engine.service_dist.mean())

        # -------------------------------------------------------------------
        # Header & Status Badges
        # -------------------------------------------------------------------
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#89b4fa"))
        painter.drawText(12, 17, "MARKOV CHAIN STATE-TRANSITION DIAGRAM")

        kendall = TheoreticalModels.get_kendall_notation(
            self.engine.arrival_dists,
            self.engine.service_dist,
            self.engine.c,
            self.engine.K,
            self.engine.priority_enabled,
        )

        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QColor("#a6adc8"))
        prio_tag = "QoS Priority" if self.engine.priority_enabled else "Birth-Death Chain"
        k_desc = f"Model: {kendall} ({prio_tag} | λ = {lam_tot:.2f}/s, μ = {mu_rate:.2f}/s)"
        painter.drawText(285, 17, k_desc)

        # Right Live State Badge Pill
        if self.engine.priority_enabled:
            q0 = len(self.engine.queues.get(0, []))
            q1 = len(self.engine.queues.get(1, []))
            q2 = len(self.engine.queues.get(2, []))
            cap_label = "∞" if is_inf_k else f"3x{int(K)}"
            badge_text = f"State n = {curr_n} (Busy: {busy_count}/{c} | Q: {q0}+{q1}+{q2}/{cap_label})"
            badge_w = 245
        else:
            k_str = "∞" if is_inf_k else str(int(K))
            badge_text = f"State n = {curr_n} (Busy: {busy_count}/{c} | Queued: {q_count}/{k_str})"
            badge_w = 210

        badge_rect = QRectF(w - badge_w - 12, 4, badge_w, 18)
        painter.setPen(QPen(QColor("#45475a"), 1))
        painter.setBrush(QBrush(QColor("#1e1e2e")))
        painter.drawRoundedRect(badge_rect, 4, 4)

        # Active state indicator dot
        painter.setPen(QPen(QColor("#11111b"), 1))
        painter.setBrush(QBrush(QColor("#a6e3a1")))
        painter.drawEllipse(QRectF(w - badge_w - 4, 9, 8, 8))

        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.setPen(QColor("#cdd6f4"))
        painter.drawText(
            QRectF(w - badge_w + 10, 4, badge_w - 14, 18),
            Qt.AlignmentFlag.AlignVCenter,
            badge_text,
        )

        # -------------------------------------------------------------------
        # State Nodes Window Calculation
        # -------------------------------------------------------------------
        margin_x = 44
        avail_w = w - 2 * margin_x
        min_node_spacing = 52
        max_visible = max(6, min(14, int(avail_w // min_node_spacing)))

        if is_inf_k or (N_max + 1) > max_visible:
            # Sliding window centered around active state curr_n
            half = max_visible // 2
            start_s = max(0, curr_n - half)
            if not is_inf_k and start_s + max_visible > N_max + 1:
                start_s = max(0, int(N_max + 1 - max_visible))
            end_s = start_s + max_visible - 1
            if not is_inf_k:
                end_s = min(int(N_max), end_s)
        else:
            start_s = 0
            end_s = int(N_max)

        visible_states = list(range(start_s, end_s + 1))
        n_vis = len(visible_states)
        spacing = avail_w / max(1, n_vis - 1)

        yc = 60
        r = 12.5

        # Left Ellipsis if window shifted
        if start_s > 0:
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor("#6c7086"))
            painter.drawText(QRectF(10, yc - 10, 24, 20), Qt.AlignmentFlag.AlignCenter, "...")

        # Right Ellipsis if more states exist
        if is_inf_k or end_s < N_max:
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor("#6c7086"))
            painter.drawText(QRectF(w - 34, yc - 10, 24, 20), Qt.AlignmentFlag.AlignCenter, "...")

        # -------------------------------------------------------------------
        # Transition Arcs (Forward Birth & Backward Death)
        # -------------------------------------------------------------------
        for i in range(n_vis - 1):
            s_from = visible_states[i]
            s_to = visible_states[i + 1]

            xc1 = margin_x + i * spacing
            xc2 = margin_x + (i + 1) * spacing

            # 1. Forward Arc (Top): Birth Transition s -> s+1 with rate λ
            p_fwd = QPainterPath()
            p1 = QPointF(xc1 + r * 0.5, yc - r * 0.866)
            p2 = QPointF(xc2 - r * 0.5, yc - r * 0.866)
            mid_x = (p1.x() + p2.x()) / 2
            mid_y = yc - r - 12
            p_fwd.moveTo(p1)
            p_fwd.quadTo(QPointF(mid_x, mid_y), p2)

            painter.setPen(QPen(QColor("#89b4fa"), 1.3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(p_fwd)

            # Arrowhead pointing right towards s+1
            arrow_fwd = QPolygonF([
                p2,
                QPointF(p2.x() - 5, p2.y() - 3.5),
                QPointF(p2.x() - 2, p2.y()),
                QPointF(p2.x() - 5, p2.y() + 3.5),
            ])
            painter.setBrush(QBrush(QColor("#89b4fa")))
            painter.drawPolygon(arrow_fwd)

            # Forward rate label λ
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#89b4fa"))
            painter.drawText(QRectF(mid_x - 15, mid_y - 8, 30, 12), Qt.AlignmentFlag.AlignCenter, "λ")

            # 2. Backward Arc (Bottom): Death Transition s+1 -> s with rate min(s+1, c)μ
            p_bwd = QPainterPath()
            bp1 = QPointF(xc2 - r * 0.5, yc + r * 0.866)
            bp2 = QPointF(xc1 + r * 0.5, yc + r * 0.866)
            bmid_x = (bp1.x() + bp2.x()) / 2
            bmid_y = yc + r + 12
            p_bwd.moveTo(bp1)
            p_bwd.quadTo(QPointF(bmid_x, bmid_y), bp2)

            painter.setPen(QPen(QColor("#a6e3a1"), 1.3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(p_bwd)

            # Arrowhead pointing left towards s
            arrow_bwd = QPolygonF([
                bp2,
                QPointF(bp2.x() + 5, bp2.y() - 3.5),
                QPointF(bp2.x() + 2, bp2.y()),
                QPointF(bp2.x() + 5, bp2.y() + 3.5),
            ])
            painter.setBrush(QBrush(QColor("#a6e3a1")))
            painter.drawPolygon(arrow_bwd)

            # Backward rate label min(s_to, c)μ
            mu_multiplier = min(s_to, c)
            b_label = "μ" if mu_multiplier == 1 else f"{mu_multiplier}μ"

            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QColor("#a6e3a1"))
            painter.drawText(QRectF(bmid_x - 15, bmid_y - 2, 30, 14), Qt.AlignmentFlag.AlignCenter, b_label)

        # -------------------------------------------------------------------
        # State Nodes (Circles)
        # -------------------------------------------------------------------
        for i, s in enumerate(visible_states):
            xc = margin_x + i * spacing
            is_active = (s == curr_n)

            if is_active:
                # Glowing outer halo
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(166, 227, 161, 65)))
                painter.drawEllipse(QPointF(xc, yc), r + 5.5, r + 5.5)

                # Vibrant Active Circle
                painter.setPen(QPen(QColor("#11111b"), 1.5))
                painter.setBrush(QBrush(QColor("#a6e3a1")))
                painter.drawEllipse(QPointF(xc, yc), r, r)

                # Active State Number (Dark bold)
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#11111b"))
                painter.drawText(QRectF(xc - r, yc - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, str(s))

                # Active Marker Indicator above the state
                painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                painter.setPen(QColor("#a6e3a1"))
                painter.drawText(QRectF(xc - 15, yc - r - 13, 30, 12), Qt.AlignmentFlag.AlignCenter, "▼")
            else:
                # Inactive Node styling
                is_capacity_limit = (not is_inf_k and s == N_max)
                if is_capacity_limit:
                    border_col = QColor("#f38ba8")  # Red for full capacity / drop boundary state
                elif s >= c:
                    border_col = QColor("#585b70")  # Servers saturated, queue occupied
                else:
                    border_col = QColor("#45475a")  # Free server capacity available

                painter.setPen(QPen(border_col, 1.4))
                painter.setBrush(QBrush(QColor("#1e1e2e")))
                painter.drawEllipse(QPointF(xc, yc), r, r)

                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor("#cdd6f4"))
                painter.drawText(QRectF(xc - r, yc - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, str(s))

        painter.end()
