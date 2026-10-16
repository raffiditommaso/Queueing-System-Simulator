"""
Educational textbook-style theory generator and interactive TheoryDialog
with Computer Modern LaTeX formula rendering and synchronized zoom.
Designed as a didactic, student-friendly reference for Bachelor's and Master's
students in Network Design and Queueing Systems.
"""

import io
import re
import math
import base64
import struct
from functools import lru_cache
from typing import Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QFont

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from core.distributions import ExponentialDist
from core.engine import QueueSimEngine
from core.theory import TheoreticalModels

from .styles import get_theory_html_css, DIALOG_ZOOM_BTN_STYLE
from .widgets import NoWheelComboBox


def _sanitize_mathtext(latex_str: str) -> str:
    """Normalize shorthand LaTeX macros into forms supported by Matplotlib's mathtext parser."""
    s = re.sub(r"\\le(?![a-zA-Z])", r"\\leq", latex_str)
    s = re.sub(r"\\ge(?![a-zA-Z])", r"\\geq", s)
    return s


@lru_cache(maxsize=256)
def _render_latex_png_cached(latex_str: str, pt_size: float = 13.0, dpi: int = 220) -> Tuple[str, int, int]:
    """
    Render a LaTeX math string using Matplotlib's Computer Modern ('cm') font
    into a base64-encoded PNG image along with its pixel (width, height).
    """
    clean_latex = _sanitize_mathtext(latex_str)

    fig = Figure(figsize=(0.1, 0.1), dpi=dpi)
    FigureCanvasAgg(fig)
    fig.patch.set_facecolor("white")

    txt = fig.text(
        0.0,
        0.0,
        f"${clean_latex}$",
        fontsize=pt_size,
        color="#111111",
        math_fontfamily="cm",
        fontfamily="serif",
    )

    buf = io.BytesIO()
    try:
        fig.savefig(
            buf,
            format="png",
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0.04,
            facecolor="white",
            transparent=False,
        )
    except ValueError:
        # Fallback to plain text if an unsupported mathtext macro is encountered
        buf = io.BytesIO()
        txt.set_text(clean_latex.replace("\\", ""))
        fig.savefig(
            buf,
            format="png",
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0.04,
            facecolor="white",
            transparent=False,
        )

    png_bytes = buf.getvalue()

    # Extract exact pixel width & height from the PNG IHDR chunk (bytes 16..24)
    if len(png_bytes) >= 24 and png_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        w_px, h_px = struct.unpack(">II", png_bytes[16:24])
    else:
        w_px, h_px = 200, 40

    b64_str = base64.b64encode(png_bytes).decode("ascii")
    return b64_str, w_px, h_px


def latex_eq_row(latex_str: str, eq_num: Optional[int] = None, zoom_factor: float = 1.0) -> str:
    """
    Build a textbook-style centered display equation row with an optional
    right-aligned equation number (e.g., '(1)', '(2)'), matching LaTeX PDFs.
    """
    dpi = 220
    b64_str, w_px, h_px = _render_latex_png_cached(latex_str, pt_size=13.5, dpi=dpi)

    scale = (96.0 / dpi) * zoom_factor
    disp_w = max(1, int(round(w_px * scale)))
    disp_h = max(1, int(round(h_px * scale)))

    img_html = f'<img src="data:image/png;base64,{b64_str}" width="{disp_w}" height="{disp_h}">'
    num_str = f"({eq_num})" if eq_num is not None else ""

    return f"""
    <table class="eq-table" width="100%" cellspacing="0" cellpadding="4">
        <tr>
            <td width="10%"></td>
            <td width="80%" align="center" valign="middle">{img_html}</td>
            <td width="10%" align="right" valign="middle" class="eq-num">{num_str}</td>
        </tr>
    </table>
    """


def generate_theory_html(
    topic_index: int,
    role: str = "Arrival",
    engine: Optional[QueueSimEngine] = None,
    rho: Optional[float] = None,
    lam: Optional[float] = None,
    mu: Optional[float] = None,
    m: int = 1,
    zoom_factor: float = 1.0,
) -> Tuple[str, str]:
    """
    Generate student-friendly educational theory pages with Computer Modern
    LaTeX equations, clear parameter breakdowns, and intuitive network explanations.
    """
    topics = [
        ("Exponential Distribution (Kendall: M)", "M"),
        ("Deterministic Distribution (Kendall: D)", "D"),
        ("Uniform Distribution (Kendall: U)", "U"),
        ("Erlang Distribution (Kendall: E_k)", "E_k"),
        ("Hyperexponential Distribution (Kendall: H_2)", "H_2"),
        ("Pareto Distribution (Kendall: Heavy-Tailed)", "Pareto"),
        ("Stochastic Stability Theory & Ergodicity", "Instability"),
        ("Metric Theory: Average Server Utilization ρ (Offered Traffic A₀)", "rho"),
        ("Metric Theory: Avg System Customers L", "L"),
        ("Metric Theory: Avg Queue Length Lq", "Lq"),
        ("Metric Theory: Avg System Time W", "W"),
        ("Metric Theory: Avg Wait Time Wq", "Wq"),
        ("Metric Theory: Loss Probability P_loss", "P_loss"),
        ("Metric Theory: Little's Law Invariance L_diff", "Littles"),
        ("Metric Theory: Customer Throughput & Accounting (Served / Arrived)", "Served / Arrived"),
    ]

    if not (0 <= topic_index < len(topics)):
        topic_index = 0

    title, _ = topics[topic_index]
    is_arrival = "arr" in role.lower()
    role_label = "Arrival Stream (Input Traffic)" if is_arrival else "Service Process (Server Transmission)"
    rv_sym = "T" if is_arrival else "S"
    rv_name = "interarrival time" if is_arrival else "customer service time"
    rate_tex = r"\lambda" if is_arrival else r"\mu"
    rate_html = "<i>&lambda;</i>" if is_arrival else "<i>&mu;</i>"
    rate_desc = "average arrival rate" if is_arrival else "average service rate"

    css = get_theory_html_css(zoom_factor)

    # Check if active distribution in engine matches topic
    curr_d = None
    if engine is not None:
        if is_arrival:
            if not getattr(engine, "priority_enabled", False):
                curr_d = getattr(engine, "arrival_dists", {}).get(-1)
        else:
            curr_d = getattr(engine, "service_dist", None)

    # -------------------------------------------------------------------
    # Topic 0: Exponential Distribution (M)
    # -------------------------------------------------------------------
    if topic_index == 0:
        rate = 0.80 if is_arrival else 1.00
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "ExponentialDist":
            rate = getattr(curr_d, "rate", rate)
            is_live = True

        mean_v = 1.0 / max(1e-6, rate)
        var_v = 1.0 / (rate * rate)
        src_status = "Live Simulator Parameters" if is_live else "Reference Benchmark Values"

        eq1 = latex_eq_row(
            rf"f_{{{rv_sym}}}(t) = {rate_tex}\,e^{{-{rate_tex} t}}, \qquad F_{{{rv_sym}}}(t) = 1 - e^{{-{rate_tex} t}} \quad (t \geq 0)",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"\mathrm{{E}}[{rv_sym}] = \frac{{1}}{{{rate_tex}}}, \qquad \mathrm{{Var}}[{rv_sym}] = \frac{{1}}{{{rate_tex}^2}}, \qquad C_v^2 = \frac{{\mathrm{{Var}}[{rv_sym}]}}{{\mathrm{{E}}[{rv_sym}]^2}} = 1",
            eq_num=2,
            zoom_factor=zoom_factor,
        )
        eq3 = latex_eq_row(
            rf"\mathrm{{P}}({rv_sym} > t + s \mid {rv_sym} > s) = \mathrm{{P}}({rv_sym} > t) = e^{{-{rate_tex} t}}",
            eq_num=3,
            zoom_factor=zoom_factor,
        )

        html = f"""{css}
        <h1>Exponential Distribution (Kendall Symbol: <i>M</i>)</h1>
        <div class="meta-line">
            <b>Role:</b> {role_label} &nbsp;|&nbsp; <b>Property:</b> Memoryless / Markovian &nbsp;|&nbsp; <b>Source:</b> {src_status}
        </div>

        <h2>I. What is this Distribution?</h2>
        <p>
            The <b>Exponential distribution</b> (denoted by the Kendall symbol <b><i>M</i></b> for <i>Markovian</i> or <i>Memoryless</i>)
            is the standard baseline model for random processes in telecommunications and queueing theory.
            In queueing systems, it represents the time elapsed between completely independent, uncoordinated customer arrivals
            at a service facility, or the service duration of customers whose processing requirements follow an exponential pattern.
        </p>

        <h2>II. Parameters Involved</h2>
        <ul>
            <li><b>{rate_html} ({rate_desc}):</b> The rate parameter, measured in <b>customers per second (cust/s)</b>. It defines how many events occur per unit time on average.</li>
            <li><b>E[<i>{rv_sym}</i>] = 1 / {rate_html} (Mean duration):</b> The average time elapsed between two consecutive arrivals or the average service time of a customer, in <b>seconds</b>.</li>
            <li><b>Var[<i>{rv_sym}</i>] = 1 / {rate_html}<sup>2</sup> (Variance):</b> The spread of durations around the average, in <b>seconds<sup>2</sup></b>.</li>
            <li><b><i>C<sub>v</sub></i><sup>2</sup> = 1 (Squared coefficient of variation):</b> The ratio of variance to the squared mean. For an exponential process, <i>C<sub>v</sub></i><sup>2</sup> is always exactly 1, serving as the universal standard for "pure randomness".</li>
        </ul>

        <h2>III. Mathematical Formulas</h2>
        <p>The probability density function (PDF) and cumulative distribution function (CDF) for duration <i>{rv_sym}</i> &ge; 0 are:</p>
        {eq1}
        <p>The first moment (mean), variance, and squared coefficient of variation are:</p>
        {eq2}

        <h2>IV. Key Properties</h2>
        <ul>
            <li><b>The Memoryless Property:</b> The Exponential distribution is the <i>only</i> continuous distribution where the past has no effect on the future:</li>
        </ul>
        {eq3}
        <ul>
            <li><b>Physical meaning:</b> If a customer has already been in service for <i>s</i> seconds, the probability that it needs at least another <i>t</i> seconds to finish is identical to a brand new customer. The server has no "memory" of how long it has been working.</li>
            <li><b>Poisson Arrivals:</b> When interarrival times are independent and exponentially distributed with rate <i>&lambda;</i>, the count of customers arriving in any interval of length <i>t</i> follows a Poisson distribution with mean <i>&lambda;t</i>.</li>
            <li><b>PASTA Property (Poisson Arrivals See Time Averages):</b> An arriving customer finds the queue in the exact same statistical state as an outside observer watching continuously over time.</li>
        </ul>

        <h2>V. Current Simulator Values &amp; Worked Check</h2>
        <table class="book-table">
            <tr><th>Parameter / Metric</th><th>Analytical Formula</th><th>Current Value</th></tr>
            <tr><td>Rate ({rate_html})</td><td>Configured rate</td><td>{rate:.2f} cust/s</td></tr>
            <tr><td>Mean Duration E[<i>{rv_sym}</i>]</td><td>1 / {rate_html}</td><td>{mean_v:.3f} s</td></tr>
            <tr><td>Variance Var[<i>{rv_sym}</i>]</td><td>1 / {rate_html}<sup>2</sup></td><td>{var_v:.3f} s<sup>2</sup></td></tr>
            <tr class="bottom-rule"><td>Squared Coeff. of Variation (<i>C<sub>v</sub></i><sup>2</sup>)</td><td>Var / Mean<sup>2</sup></td><td>1.000</td></tr>
        </table>
        <div class="example-box">
            <p class="example-title">Numerical Example with Current Settings ({rate_html} = {rate:.2f} cust/s)</p>
            <ol>
                <li><b>Expected Duration:</b> On average, each event takes E[<i>{rv_sym}</i>] = 1 / {rate:.2f} = <b>{mean_v:.3f} s</b>.</li>
                <li><b>Short Duration Probability:</b> The chance that an interval is shorter than 0.50 s is
                    <i>F</i>(0.50) = 1 &minus; <i>e</i><sup>&minus;{rate:.2f} &times; 0.50</sup> = <b>{(1.0 - math.exp(-rate*0.50))*100:.2f}%</b>.</li>
                <li><b>Long Duration Probability:</b> The chance that an interval exceeds 2.00 s is
                    P(<i>{rv_sym}</i> &gt; 2.00) = <i>e</i><sup>&minus;{rate:.2f} &times; 2.00</sup> = <b>{math.exp(-rate*2.00)*100:.2f}%</b>.</li>
            </ol>
        </div>
        """
        return title, html

    # -------------------------------------------------------------------
    # Topic 1: Deterministic Distribution (D)
    # -------------------------------------------------------------------
    elif topic_index == 1:
        d_val = 1.25 if is_arrival else 1.00
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "DeterministicDist":
            d_val = getattr(curr_d, "val", d_val)
            is_live = True

        rate_eq = 1.0 / max(1e-6, d_val)
        src_status = "Live Simulator Parameters" if is_live else "Reference Benchmark Values"

        eq1 = latex_eq_row(
            rf"f_{{{rv_sym}}}(t) = \delta(t - D), \qquad \mathrm{{E}}[{rv_sym}] = D, \qquad \mathrm{{Var}}[{rv_sym}] = 0, \qquad C_v^2 = 0",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            r"W_q^{(M/D/1)} = \frac{\rho}{2\mu(1 - \rho)} = \frac{1}{2}\,W_q^{(M/M/1)}",
            eq_num=2,
            zoom_factor=zoom_factor,
        )

        html = f"""{css}
        <h1>Deterministic Distribution (Kendall Symbol: <i>D</i>)</h1>
        <div class="meta-line">
            <b>Role:</b> {role_label} &nbsp;|&nbsp; <b>Property:</b> Zero Variance (Constant) &nbsp;|&nbsp; <b>Source:</b> {src_status}
        </div>

        <h2>I. What is this Distribution?</h2>
        <p>
            The <b>Deterministic distribution</b> (denoted by <b><i>D</i></b>) represents a process where every event takes the exact same fixed duration <i>D</i>, with zero randomness or variation.
            In queueing systems, this models customers with fixed, identical service requirements (such as automated deterministic processing steps or constant transmissions over a fixed-rate channel), or scheduled periodic customer arrivals.
        </p>

        <h2>II. Parameters Involved</h2>
        <ul>
            <li><b><i>D</i> (Constant Duration):</b> The fixed time duration, in <b>seconds</b>. Every single customer service or arrival interval takes exactly <i>D</i> seconds.</li>
            <li><b>{rate_html} = 1 / <i>D</i> (Equivalent Rate):</b> The processing or arrival throughput, in <b>customers per second (cust/s)</b>.</li>
            <li><b>Var[<i>{rv_sym}</i>] = 0 (Variance):</b> Exactly zero variance, reflecting the total absence of jitter.</li>
            <li><b><i>C<sub>v</sub></i><sup>2</sup> = 0 (Squared Coefficient of Variation):</b> Zero coefficient of variation.</li>
        </ul>

        <h2>III. Mathematical Formulas</h2>
        <p>Using the Dirac delta generalized function <i>&delta;</i>(<i>t</i> &minus; <i>D</i>), the density and moments are:</p>
        {eq1}
        <p>The queueing waiting time in an <i>M</i>/<i>D</i>/1 queue compared to an <i>M</i>/<i>M</i>/1 queue is:</p>
        {eq2}

        <h2>IV. Key Properties</h2>
        <ul>
            <li><b>The 50% Delay Reduction Rule:</b> Eliminating service-time variance (replacing exponential service times with fixed service times of the same average) cuts average queue waiting time <i>W<sub>q</sub></i> and average queue length <i>L<sub>q</sub></i> <b>exactly in half</b> across all stable utilization levels (0 &lt; <i>&rho;</i> &lt; 1).</li>
            <li><b>Zero Jitter:</b> Because service duration is perfectly constant, any buffering delay is caused purely by customer arrival randomness, never by customer service time variations.</li>
        </ul>

        <h2>V. Current Simulator Values &amp; Worked Check</h2>
        <table class="book-table">
            <tr><th>Parameter / Metric</th><th>Formula</th><th>Current Value</th></tr>
            <tr><td>Constant Duration (<i>D</i>)</td><td>Input parameter</td><td>{d_val:.3f} s</td></tr>
            <tr><td>Equivalent Rate ({rate_html})</td><td>1 / <i>D</i></td><td>{rate_eq:.2f} cust/s</td></tr>
            <tr><td>Variance Var[<i>{rv_sym}</i>]</td><td>0</td><td>0.000 s<sup>2</sup></td></tr>
            <tr class="bottom-rule"><td>Squared Coeff. of Variation (<i>C<sub>v</sub></i><sup>2</sup>)</td><td>0</td><td>0.000</td></tr>
        </table>
        <div class="example-box">
            <p class="example-title">Numerical Comparison (M/M/1 vs. M/D/1 at &rho; = 0.80)</p>
            <p>Assume service time is fixed at <i>D</i> = {d_val:.2f} s (<i>&mu;</i> = {rate_eq:.2f} cust/s) with offered traffic <i>A</i><sub>0</sub> = 0.80 Erlang (server utilization <i>&rho;</i> = 0.80):</p>
            <ol>
                <li><b>With Exponential Customers (<i>M</i>/<i>M</i>/1):</b>
                    <i>W<sub>q</sub></i> = [0.80 / (1 &minus; 0.80)] &times; {d_val:.2f} = 4.0 &times; {d_val:.2f} = <b>{4.0*d_val:.2f} s</b>.</li>
                <li><b>With Fixed Customers (<i>M</i>/<i>D</i>/1):</b>
                    <i>W<sub>q</sub></i> = &frac12; &times; {4.0*d_val:.2f} = <b>{2.0*d_val:.2f} s</b> (saving {2.0*d_val:.2f} s of waiting delay per customer).</li>
            </ol>
        </div>
        """
        return title, html

    # -------------------------------------------------------------------
    # Topic 2: Continuous Uniform Distribution (U)
    # -------------------------------------------------------------------
    elif topic_index == 2:
        a_val = 0.50
        b_val = 1.50
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "UniformDist":
            a_val = getattr(curr_d, "a", a_val)
            b_val = getattr(curr_d, "b", b_val)
            is_live = True

        mean_v = (a_val + b_val) / 2.0
        var_v = ((b_val - a_val) ** 2) / 12.0
        cv2 = var_v / max(1e-12, mean_v * mean_v)
        pk_factor = (1.0 + cv2) / 2.0
        src_status = "Live Simulator Parameters" if is_live else "Reference Benchmark Values"

        eq1 = latex_eq_row(
            rf"f_{{{rv_sym}}}(t) = \frac{{1}}{{b - a}}, \qquad F_{{{rv_sym}}}(t) = \frac{{t - a}}{{b - a}} \quad (a \leq t \leq b)",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"\mathrm{{E}}[{rv_sym}] = \frac{{a + b}}{{2}}, \qquad \mathrm{{Var}}[{rv_sym}] = \frac{{(b - a)^2}}{{12}}, \qquad C_v^2 = \frac{{(b - a)^2}}{{3(a + b)^2}} \leq \frac{{1}}{{3}}",
            eq_num=2,
            zoom_factor=zoom_factor,
        )

        html = f"""{css}
        <h1>Continuous Uniform Distribution (Kendall Symbol: <i>U</i>)</h1>
        <div class="meta-line">
            <b>Role:</b> {role_label} &nbsp;|&nbsp; <b>Property:</b> Bounded Interval [<i>a</i>, <i>b</i>] &nbsp;|&nbsp; <b>Source:</b> {src_status}
        </div>

        <h2>I. What is this Distribution?</h2>
        <p>
            The <b>Continuous Uniform distribution</b> (denoted by <b><i>U</i></b>) models random durations that are equally likely to fall anywhere within a strictly bounded interval [<i>a</i>, <i>b</i>].
            In queueing systems, it describes service times when customer service durations vary uniformly between a minimum and maximum bound, or arrival streams subject to bounded jitter.
        </p>

        <h2>II. Parameters Involved</h2>
        <ul>
            <li><b><i>a</i> (Minimum Bound):</b> The minimum possible duration, in <b>seconds</b>. Durations can never be smaller than <i>a</i>.</li>
            <li><b><i>b</i> (Maximum Bound):</b> The maximum possible duration, in <b>seconds</b>. Durations can never exceed <i>b</i>.</li>
            <li><b><i>b</i> &minus; <i>a</i> (Spread):</b> The total interval width and maximum peak-to-peak jitter spread.</li>
            <li><b>E[<i>{rv_sym}</i>] = (<i>a</i> + <i>b</i>) / 2 (Mean):</b> The center and average duration, in <b>seconds</b>.</li>
            <li><b>Var[<i>{rv_sym}</i>] = (<i>b</i> &minus; <i>a</i>)<sup>2</sup> / 12 (Variance):</b> The spread of durations in <b>seconds<sup>2</sup></b>.</li>
            <li><b><i>C<sub>v</sub></i><sup>2</sup> &le; 1/3 &approx; 0.333:</b> The squared coefficient of variation is strictly bounded below 0.333 whenever <i>a</i> &gt; 0.</li>
        </ul>

        <h2>III. Mathematical Formulas</h2>
        <p>For <i>a</i> &le; <i>t</i> &le; <i>b</i> (and zero outside), the PDF and CDF are:</p>
        {eq1}
        <p>The mean, variance, and squared coefficient of variation are:</p>
        {eq2}

        <h2>IV. Key Properties</h2>
        <ul>
            <li><b>Strict Worst-Case Limit:</b> Unlike Exponential or Pareto distributions (which have unbounded tails), a Uniform variable has a hard worst-case bound (<i>b</i>). A customer service never stalls past <i>b</i>.</li>
            <li><b>Lower Delays than Exponential:</b> Because <i>C<sub>v</sub></i><sup>2</sup> &lt; 0.333 &lt; 1, queueing delay in an <i>M</i>/<i>U</i>/1 queue is always significantly lower than in an <i>M</i>/<i>M</i>/1 queue with the same average service duration.</li>
        </ul>

        <h2>V. Current Simulator Values &amp; Worked Check</h2>
        <table class="book-table">
            <tr><th>Parameter / Metric</th><th>Formula</th><th>Current Value</th></tr>
            <tr><td>Interval Bounds [<i>a</i>, <i>b</i>]</td><td>[<i>a</i>, <i>b</i>]</td><td>[{a_val:.2f} s, {b_val:.2f} s]</td></tr>
            <tr><td>Mean Duration E[<i>{rv_sym}</i>]</td><td>(<i>a</i> + <i>b</i>) / 2</td><td>{mean_v:.3f} s</td></tr>
            <tr><td>Variance Var[<i>{rv_sym}</i>]</td><td>(<i>b</i> &minus; <i>a</i>)<sup>2</sup> / 12</td><td>{var_v:.4f} s<sup>2</sup></td></tr>
            <tr class="bottom-rule"><td>Squared Coeff. of Variation (<i>C<sub>v</sub></i><sup>2</sup>)</td><td>Var / Mean<sup>2</sup></td><td>{cv2:.3f} (&lt; 0.333)</td></tr>
        </table>
        <div class="example-box">
            <p class="example-title">Numerical Example (Bounds a = {a_val:.2f} s, b = {b_val:.2f} s)</p>
            <ol>
                <li><b>Mean Duration:</b> E[<i>{rv_sym}</i>] = ({a_val:.2f} + {b_val:.2f}) / 2 = <b>{mean_v:.3f} s</b>.</li>
                <li><b>Delay Multiplier:</b> The Pollaczek-Khinchine factor (1 + <i>C<sub>v</sub></i><sup>2</sup>) / 2 is <b>{pk_factor:.3f}</b>, cutting average waiting time by {(1.0 - pk_factor)*100:.1f}% compared to an exponential server with the same mean.</li>
            </ol>
        </div>
        """
        return title, html

    # -------------------------------------------------------------------
    # Topic 3: Erlang-k Distribution (E_k)
    # -------------------------------------------------------------------
    elif topic_index == 3:
        k_val = 2
        r_val = 0.80 if is_arrival else 1.00
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "ErlangDist":
            k_val = getattr(curr_d, "k", k_val)
            mean_raw = getattr(curr_d, "mean_val", 1.0 / r_val)
            r_val = 1.0 / max(1e-6, mean_raw)
            is_live = True

        mean_v = 1.0 / max(1e-6, r_val)
        var_v = (mean_v ** 2) / k_val
        cv2 = 1.0 / k_val
        pk_factor = (1.0 + cv2) / 2.0
        src_status = "Live Simulator Parameters" if is_live else "Reference Benchmark Values"

        eq1 = latex_eq_row(
            rf"{rv_sym} = \sum_{{i=1}}^{{k}} X_i, \qquad f_{{{rv_sym}}}(t) = \frac{{(k{rate_tex})^k\, t^{{k-1}}\, e^{{-k{rate_tex} t}}}}{{(k - 1)!}} \quad (t \geq 0)",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"\mathrm{{E}}[{rv_sym}] = \frac{{1}}{{{rate_tex}}}, \qquad \mathrm{{Var}}[{rv_sym}] = \frac{{1}}{{k\,{rate_tex}^2}}, \qquad C_v^2 = \frac{{1}}{{k}}",
            eq_num=2,
            zoom_factor=zoom_factor,
        )

        html = f"""{css}
        <h1>Erlang-<i>k</i> Distribution (Kendall Symbol: <i>E<sub>{k_val}</sub></i>)</h1>
        <div class="meta-line">
            <b>Role:</b> {role_label} &nbsp;|&nbsp; <b>Stages:</b> <i>k</i> = {k_val} Sequential Phases &nbsp;|&nbsp; <b>Source:</b> {src_status}
        </div>

        <h2>I. What is this Distribution?</h2>
        <p>
            The <b>Erlang-<i>k</i> distribution</b> (denoted by <b><i>E<sub>k</sub></i></b>) models the total time required to complete <b><i>k</i> independent and identical exponential stages in series</b>.
            In queueing systems, it represents multi-stage customer service pipelines—for example, a customer passing through <i>k</i> sequential service steps in series—where each phase is exponential.
        </p>

        <h2>II. Parameters Involved</h2>
        <ul>
            <li><b><i>k</i> (Number of Stages):</b> The number of sequential phases (integer <i>k</i> &ge; 1).</li>
            <li><b>{rate_html} (Overall Completion Rate):</b> The rate of completing all <i>k</i> stages, in <b>customers per second (cust/s)</b>.</li>
            <li><b><i>k</i>{rate_html} (Internal Phase Rate):</b> The transition speed of each individual stage.</li>
            <li><b>E[<i>{rv_sym}</i>] = 1 / {rate_html} (Overall Mean Duration):</b> The average total processing time, in <b>seconds</b>.</li>
            <li><b>Var[<i>{rv_sym}</i>] = 1 / (<i>k</i>{rate_html}<sup>2</sup>) (Variance):</b> Decreases proportionally with 1/<i>k</i>.</li>
            <li><b><i>C<sub>v</sub></i><sup>2</sup> = 1 / <i>k</i> (Squared Coefficient of Variation):</b> Controls the regularity of the process.</li>
        </ul>

        <h2>III. Mathematical Formulas</h2>
        <p>If <i>k</i> sequential exponential phases each operate at rate <i>k</i>{rate_html}, the total duration <i>{rv_sym}</i> has PDF:</p>
        {eq1}
        <p>The overall moments are:</p>
        {eq2}

        <h2>IV. Key Properties</h2>
        <ul>
            <li><b>Bridging Random and Deterministic Behavior:</b>
                <ul>
                    <li>For <b><i>k</i> = 1</b>: <i>C<sub>v</sub></i><sup>2</sup> = 1 &mdash; identical to the purely random <b>Exponential (<i>M</i>)</b> distribution.</li>
                    <li>For <b><i>k</i> &gt; 1</b>: <i>C<sub>v</sub></i><sup>2</sup> = 1/<i>k</i> &lt; 1 &mdash; averaging over <i>k</i> serial phases smooths out randomness.</li>
                    <li>As <b><i>k</i> &rarr; &infin;</b>: Var &rarr; 0 and <i>C<sub>v</sub></i><sup>2</sup> &rarr; 0 &mdash; converges directly to the <b>Deterministic (<i>D</i>)</b> distribution.</li>
                </ul>
            </li>
            <li><b>Lower Queueing Delay:</b> In an <i>M</i>/<i>E<sub>k</sub></i>/1 queue, average queue waiting time scales with (1 + 1/<i>k</i>) / 2, reducing delay compared to <i>M</i>/<i>M</i>/1.</li>
        </ul>

        <h2>V. Current Simulator Values &amp; Worked Check</h2>
        <table class="book-table">
            <tr><th>Parameter / Metric</th><th>Formula</th><th>Current Value</th></tr>
            <tr><td>Number of Stages (<i>k</i>)</td><td><i>k</i></td><td>{k_val} stages</td></tr>
            <tr><td>Overall Mean E[<i>{rv_sym}</i>]</td><td>1 / {rate_html}</td><td>{mean_v:.3f} s</td></tr>
            <tr><td>Variance Var[<i>{rv_sym}</i>]</td><td>1 / (<i>k</i> &middot; {rate_html}<sup>2</sup>)</td><td>{var_v:.4f} s<sup>2</sup></td></tr>
            <tr class="bottom-rule"><td>Squared Coeff. of Variation (<i>C<sub>v</sub></i><sup>2</sup>)</td><td>1 / <i>k</i></td><td>{cv2:.3f}</td></tr>
        </table>
        <div class="example-box">
            <p class="example-title">Numerical Example (k = {k_val} Stages, Overall Rate {rate_html} = {r_val:.2f} cust/s)</p>
            <ol>
                <li><b>Stage Mean:</b> Each internal phase takes 1 / ({k_val} &times; {r_val:.2f}) = <b>{mean_v/k_val:.3f} s</b> on average, summing to E[<i>{rv_sym}</i>] = <b>{mean_v:.3f} s</b>.</li>
                <li><b>Queue Delay Savings:</b> Since <i>C<sub>v</sub></i><sup>2</sup> = 1/{k_val} = {cv2:.3f}, the delay multiplier (1 + 1/{k_val})/2 is <b>{pk_factor:.3f}</b> (a {(1.0 - pk_factor)*100:.1f}% reduction in waiting time compared to <i>M</i>/<i>M</i>/1).</li>
            </ol>
        </div>
        """
        return title, html

    # -------------------------------------------------------------------
    # Topic 4: Hyperexponential Distribution (H_2)
    # -------------------------------------------------------------------
    elif topic_index == 4:
        p1 = 0.40
        r1 = 0.50
        r2 = 2.00
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "HyperexponentialDist":
            p1 = getattr(curr_d, "p1", p1)
            r1 = getattr(curr_d, "r1", r1)
            r2 = getattr(curr_d, "r2", r2)
            is_live = True

        p2 = 1.0 - p1
        mean_v = (p1 / r1) + (p2 / r2)
        ex2 = 2.0 * ((p1 / (r1 * r1)) + (p2 / (r2 * r2)))
        var_v = max(0.0, ex2 - mean_v * mean_v)
        cv2 = var_v / max(1e-12, mean_v * mean_v)
        pk_factor = (1.0 + cv2) / 2.0
        src_status = "Live Simulator Parameters" if is_live else "Reference Benchmark Values"

        eq1 = latex_eq_row(
            rf"f_{{{rv_sym}}}(t) = p_1 r_1 e^{{-r_1 t}} + p_2 r_2 e^{{-r_2 t}} \quad (t \geq 0,\; p_1 + p_2 = 1)",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"\mathrm{{E}}[{rv_sym}] = \frac{{p_1}}{{r_1}} + \frac{{p_2}}{{r_2}}, \qquad \mathrm{{E}}[{rv_sym}^2] = 2\left(\frac{{p_1}}{{r_1^2}} + \frac{{p_2}}{{r_2^2}}\right), \qquad C_v^2 = \frac{{\mathrm{{E}}[{rv_sym}^2]}}{{\mathrm{{E}}[{rv_sym}]^2}} - 1 \geq 1",
            eq_num=2,
            zoom_factor=zoom_factor,
        )

        html = f"""{css}
        <h1>Hyperexponential Distribution (Kendall Symbol: <i>H</i><sub>2</sub>)</h1>
        <div class="meta-line">
            <b>Role:</b> {role_label} &nbsp;|&nbsp; <b>Property:</b> High-Variance Parallel Mixture (<i>C<sub>v</sub></i> &gt; 1) &nbsp;|&nbsp; <b>Source:</b> {src_status}
        </div>

        <h2>I. What is this Distribution?</h2>
        <p>
            The <b>2-Phase Hyperexponential distribution</b> (denoted by <b><i>H</i><sub>2</sub></b>) models a probabilistic mixture of two parallel exponential branches.
            With probability <i>p</i><sub>1</sub>, an event is drawn from rate <i>r</i><sub>1</sub>; with probability <i>p</i><sub>2</sub> = 1 &minus; <i>p</i><sub>1</sub>, it is drawn from rate <i>r</i><sub>2</sub>.
            In queueing systems, this models <b>bursty, bimodal traffic</b>—for example, a system carrying a mixture of short transactions or customers (fast rate <i>r</i><sub>2</sub>) and long batch processing jobs (slow rate <i>r</i><sub>1</sub>).
        </p>

        <h2>II. Parameters Involved</h2>
        <ul>
            <li><b><i>p</i><sub>1</sub>, <i>p</i><sub>2</sub> (Branch Selection Probabilities):</b> The probability of picking Branch 1 vs. Branch 2 (with <i>p</i><sub>1</sub> + <i>p</i><sub>2</sub> = 1).</li>
            <li><b><i>r</i><sub>1</sub>, <i>r</i><sub>2</sub> (Branch Rates):</b> The processing speeds of the two branches, in <b>cust/s</b>.</li>
            <li><b>E[<i>{rv_sym}</i>] = <i>p</i><sub>1</sub>/<i>r</i><sub>1</sub> + <i>p</i><sub>2</sub>/<i>r</i><sub>2</sub> (Overall Mean):</b> Average duration, in <b>seconds</b>.</li>
            <li><b><i>C<sub>v</sub></i><sup>2</sup> &gt; 1 (Squared Coefficient of Variation):</b> Strictly greater than 1 whenever <i>r</i><sub>1</sub> &ne; <i>r</i><sub>2</sub>, reflecting elevated burstiness and variance.</li>
        </ul>

        <h2>III. Mathematical Formulas</h2>
        <p>The probability density function is the convex combination of the two exponential branches:</p>
        {eq1}
        <p>The first moment, second moment, and squared coefficient of variation are:</p>
        {eq2}

        <h2>IV. Key Properties</h2>
        <ul>
            <li><b>Series vs. Parallel Contrast:</b> Erlang puts stages in series (averaging out randomness, <i>C<sub>v</sub></i><sup>2</sup> &lt; 1), while Hyperexponential puts stages in parallel (amplifying randomness, <i>C<sub>v</sub></i><sup>2</sup> &gt; 1).</li>
            <li><b>Head-of-Line Blocking Penalty:</b> When service times follow <i>H</i><sub>2</sub>, occasional large jobs from the slow branch block the server while many small jobs pile up behind them. This inflates average waiting time by the Pollaczek-Khinchine factor (1 + <i>C<sub>v</sub></i><sup>2</sup>) / 2 = <b>{pk_factor:.2f}&times;</b> compared to an exponential server of the same average speed!</li>
        </ul>

        <h2>V. Current Simulator Values &amp; Worked Check</h2>
        <table class="book-table">
            <tr><th>Parameter / Metric</th><th>Formula</th><th>Current Value</th></tr>
            <tr><td>Branch Probabilities (<i>p</i><sub>1</sub>, <i>p</i><sub>2</sub>)</td><td><i>p</i><sub>1</sub>, 1 &minus; <i>p</i><sub>1</sub></td><td>{p1:.2f}, {p2:.2f}</td></tr>
            <tr><td>Branch Rates (<i>r</i><sub>1</sub>, <i>r</i><sub>2</sub>)</td><td><i>r</i><sub>1</sub>, <i>r</i><sub>2</sub></td><td>{r1:.2f} cust/s, {r2:.2f} cust/s</td></tr>
            <tr><td>Overall Mean E[<i>{rv_sym}</i>]</td><td><i>p</i><sub>1</sub>/<i>r</i><sub>1</sub> + <i>p</i><sub>2</sub>/<i>r</i><sub>2</sub></td><td>{mean_v:.3f} s</td></tr>
            <tr><td>Variance Var[<i>{rv_sym}</i>]</td><td>E[<i>{rv_sym}</i><sup>2</sup>] &minus; E[<i>{rv_sym}</i>]<sup>2</sup></td><td>{var_v:.4f} s<sup>2</sup></td></tr>
            <tr class="bottom-rule"><td>Squared Coeff. of Variation (<i>C<sub>v</sub></i><sup>2</sup>)</td><td>Var / Mean<sup>2</sup></td><td>{cv2:.3f} (&gt; 1.0)</td></tr>
        </table>
        <div class="example-box">
            <p class="example-title">Numerical Example (p<sub>1</sub> = {p1:.2f}, r<sub>1</sub> = {r1:.2f} cust/s, r<sub>2</sub> = {r2:.2f} cust/s)</p>
            <ol>
                <li><b>Overall Average Duration:</b> E[<i>{rv_sym}</i>] = ({p1:.2f} / {r1:.2f}) + ({p2:.2f} / {r2:.2f}) = <b>{mean_v:.3f} s</b>.</li>
                <li><b>Burstiness Penalty:</b> Since <i>C<sub>v</sub></i><sup>2</sup> = {cv2:.3f}, average queue delay in an <i>M</i>/<i>H</i><sub>2</sub>/1 queue is <b>{(pk_factor - 1.0)*100:.1f}% higher</b> than in an <i>M</i>/<i>M</i>/1 queue with identical server utilization.</li>
            </ol>
        </div>
        """
        return title, html

    # -------------------------------------------------------------------
    # Topic 5: Pareto Heavy-Tailed Distribution
    # -------------------------------------------------------------------
    elif topic_index == 5:
        alpha = 2.50
        xm = 0.60
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "ParetoDist":
            alpha = getattr(curr_d, "alpha", alpha)
            xm = getattr(curr_d, "xm", xm)
            is_live = True

        mean_v = (alpha * xm) / (alpha - 1.0) if alpha > 1.0 else float("inf")
        var_v = (alpha * (xm * xm)) / (((alpha - 1.0) ** 2) * (alpha - 2.0)) if alpha > 2.0 else float("inf")
        cv2 = (var_v / (mean_v * mean_v)) if (not math.isinf(var_v) and not math.isinf(mean_v)) else float("inf")
        src_status = "Live Simulator Parameters" if is_live else "Reference Benchmark Values"

        eq1 = latex_eq_row(
            rf"f_{{{rv_sym}}}(t) = \frac{{\alpha\, x_m^\alpha}}{{t^{{\alpha + 1}}}}, \qquad \mathrm{{P}}({rv_sym} > t) = \left(\frac{{x_m}}{{t}}\right)^\alpha \quad (t \geq x_m)",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"\mathrm{{E}}[{rv_sym}] = \frac{{\alpha\, x_m}}{{\alpha - 1}} \quad (\alpha > 1), \qquad \mathrm{{Var}}[{rv_sym}] = \frac{{\alpha\, x_m^2}}{{(\alpha - 1)^2(\alpha - 2)}} \quad (\alpha > 2)",
            eq_num=2,
            zoom_factor=zoom_factor,
        )

        html = f"""{css}
        <h1>Pareto Distribution (Heavy-Tailed Power Law)</h1>
        <div class="meta-line">
            <b>Role:</b> {role_label} &nbsp;|&nbsp; <b>Tail Index:</b> &alpha; = {alpha:.2f}, Scale <i>x<sub>m</sub></i> = {xm:.2f} s &nbsp;|&nbsp; <b>Source:</b> {src_status}
        </div>

        <h2>I. What is this Distribution?</h2>
        <p>
            The <b>Pareto distribution</b> is the classic <b>heavy-tailed (power-law)</b> distribution. While an exponential tail decays extremely fast as <i>e</i><sup>&minus;&lambda;<i>t</i></sup>, a Pareto tail decays very slowly as <i>t</i><sup>&minus;&alpha;</sup>.
            In Internet traffic engineering, it models file sizes, video stream flow lengths, and web transfers—giving rise to the famous <b>"Mice and Elephants"</b> phenomenon, where a tiny fraction of massive flows ("elephants") account for the vast majority of network bytes.
        </p>

        <h2>II. Parameters Involved</h2>
        <ul>
            <li><b><i>x<sub>m</sub></i> (Scale Parameter / Minimum Threshold):</b> The absolute minimum possible duration, in <b>seconds</b>. Durations strictly cannot be smaller than <i>x<sub>m</sub></i>.</li>
            <li><b><i>&alpha;</i> (Shape Parameter / Tail Index):</b> Dimensionless exponent controlling how heavy the tail is. Smaller <i>&alpha;</i> means heavier tails and more frequent extreme outliers.</li>
            <li><b>E[<i>{rv_sym}</i>] = &alpha;<i>x<sub>m</sub></i> / (&alpha; &minus; 1):</b> The mean duration (finite only when <i>&alpha;</i> &gt; 1).</li>
            <li><b>Var[<i>{rv_sym}</i>]:</b> The variance (finite only when <i>&alpha;</i> &gt; 2). When <i>&alpha;</i> &le; 2, the variance is mathematically infinite!</li>
        </ul>

        <h2>III. Mathematical Formulas</h2>
        <p>For duration <i>t</i> &ge; <i>x<sub>m</sub></i>, the PDF and survival probability (tail) are:</p>
        {eq1}
        <p>The existence of moments depends strictly on the tail index <i>&alpha;</i>:</p>
        {eq2}

        <h2>IV. Key Properties</h2>
        <ul>
            <li><b>The Infinite Variance Trap (1 &lt; <i>&alpha;</i> &le; 2):</b> When <i>&alpha;</i> &le; 2, the mean is finite, but the second moment is infinite. In an infinite-buffer queue, the Pollaczek-Khinchine formula predicts that average queueing delay becomes <b>infinite (<i>W<sub>q</sub></i> &rarr; &infin;)</b> even when server utilization is well below 100% (<i>&rho;</i> &lt; 1)!</li>
            <li><b>Buffer Overflow:</b> In finite queue buffers, Pareto traffic produces massive burst pile-ups that cause severe customer loss.</li>
        </ul>

        <h2>V. Current Simulator Values &amp; Worked Check</h2>
        <table class="book-table">
            <tr><th>Parameter / Metric</th><th>Formula / Condition</th><th>Current Value</th></tr>
            <tr><td>Shape Parameter (<i>&alpha;</i>)</td><td>Input parameter</td><td>&alpha; = {alpha:.2f}</td></tr>
            <tr><td>Scale Threshold (<i>x<sub>m</sub></i>)</td><td>Input parameter</td><td><i>x<sub>m</sub></i> = {xm:.2f} s</td></tr>
            <tr><td>Mean Duration E[<i>{rv_sym}</i>]</td><td>&alpha;<i>x<sub>m</sub></i> / (&alpha; &minus; 1)</td><td>{f"{mean_v:.3f} s" if not math.isinf(mean_v) else "&infin; (Infinite)"}</td></tr>
            <tr class="bottom-rule"><td>Variance Var[<i>{rv_sym}</i>]</td><td>Finite only if &alpha; &gt; 2</td><td>{f"{var_v:.4f} s<sup>2</sup>" if not math.isinf(var_v) else "&infin; (Infinite Variance)"}</td></tr>
        </table>
        <div class="example-box">
            <p class="example-title">Numerical Example (Outlier Comparison at &alpha; = {alpha:.2f}, x<sub>m</sub> = {xm:.2f} s)</p>
            <ol>
                <li><b>Mean Duration:</b> E[<i>{rv_sym}</i>] = ({alpha:.2f} &times; {xm:.2f}) / ({alpha:.2f} &minus; 1) = <b>{mean_v:.3f} s</b>.</li>
                <li><b>Extreme Outlier Probability (&gt; 5.0 s):</b> Under Pareto, the probability of exceeding 5.0 s is ({xm:.2f} / 5.0)<sup>{alpha:.2f}</sup> = <b>{((xm/5.0)**alpha)*100:.3f}%</b>.
                    Under an Exponential distribution with the exact same mean ({mean_v:.3f} s), that probability is only <b>{math.exp(-5.0/mean_v)*100:.4f}%</b> (nearly 100 times smaller!).</li>
            </ol>
        </div>
        """
        return title, html

    # -------------------------------------------------------------------
    # Topic 6: Stochastic Stability Theory & Ergodicity
    # -------------------------------------------------------------------
    elif topic_index == 6:
        if lam is None:
            lam = 2.50
        if mu is None:
            mu = 1.00
        if m is None or m <= 0:
            m = 1
        a0 = lam / max(1e-6, mu)
        a0_per_server = a0 / m
        if rho is None:
            if engine is not None and hasattr(engine, "get_metrics"):
                rho = engine.get_metrics().get('rho', min(1.0, a0_per_server))
            else:
                rho = min(1.0, a0_per_server)

        eq1 = latex_eq_row(
            r"\frac{A_0}{m} = \frac{\lambda}{m \cdot \mu} < 1 \quad \iff \quad A_0 < m",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            r"\frac{\mathrm{d}}{\mathrm{d}t}\mathrm{E}[Q(t)] = \lambda - m\mu > 0 \quad \Longrightarrow \quad Q(t) \approx (\lambda - m\mu)\,t \to \infty",
            eq_num=2,
            zoom_factor=zoom_factor,
        )
        eq3 = latex_eq_row(
            r"\pi_p \geq 1 - \frac{m\mu}{\lambda} = 1 - \frac{m}{A_0} = 1 - \frac{1}{A_0/m}",
            eq_num=3,
            zoom_factor=zoom_factor,
        )

        min_loss_pct = max(0.0, (1.0 - (m * mu) / max(1e-6, lam)) * 100.0)

        html = f"""{css}
        <h1>Stochastic Stability &amp; Ergodicity Theory</h1>
        <div class="meta-line">
            <b>Offered Traffic:</b> <i>A</i><sub>0</sub> = {a0:.2f} Erl &nbsp;|&nbsp;
            <b>Offered Load per Server:</b> <i>A</i><sub>0</sub> / <i>m</i> = {a0_per_server:.2f} &nbsp;|&nbsp;
            <b>Carried Server Utilization:</b> <i>&rho;</i> = {rho:.2f} &nbsp;|&nbsp;
            <b>Arrival Rate:</b> &lambda; = {lam:.2f} cust/s &nbsp;|&nbsp;
            <b>Total Capacity:</b> <i>m&mu;</i> = {m} &times; {mu:.2f} = {m*mu:.2f} cust/s
        </div>

        <h2>I. What is Stability?</h2>
        <p>
            A queueing system is <b>stable (ergodic)</b> if its queue backlog does not grow toward infinity and reaches a steady-state equilibrium probability distribution as time <i>t</i> &rarr; &infin;.
            In queueing facilities and networks, stability ensures that buffers do not permanently overflow and waiting times do not diverge without bound.
        </p>

        <h2>II. Parameters Involved &amp; Distinction Between <i>A</i><sub>0</sub> / <i>m</i> and <i>&rho;</i></h2>
        <p>
            It is critical to distinguish between incoming traffic demand (offered load) and actual server busy time (utilization):
        </p>
        <ul>
            <li><b><i>&lambda;</i> (Arrival Rate):</b> The aggregate rate of incoming customers arriving at the queue, in <b>cust/s</b>.</li>
            <li><b><i>&mu;</i> (Service Rate per Server):</b> The processing speed of a single server, in <b>cust/s</b>.</li>
            <li><b><i>m</i> (Number of Servers):</b> The number of identical servers working in parallel.</li>
            <li><b><i>m&mu;</i> (Total Service Capacity):</b> The maximum departure throughput when all <i>m</i> servers are actively busy, in <b>cust/s</b>.</li>
            <li><b><i>A</i><sub>0</sub> = <i>&lambda;</i> / <i>&mu;</i> (Offered Traffic):</b> Total incoming traffic volume offered to the system, in <b>Erlangs</b>.</li>
            <li><b><i>A</i><sub>0</sub> / <i>m</i> = <i>&lambda;</i> / (<i>m&mu;</i>) (Offered Load per Server):</b> The ratio of incoming work to total server capacity. If <i>A</i><sub>0</sub> / <i>m</i> &ge; 1 (i.e. <i>A</i><sub>0</sub> &ge; <i>m</i>), incoming demand exceeds capacity and the system is in overload.</li>
            <li><b><i>&rho;</i> = <i>A</i><sub>s</sub> / <i>m</i> = <i>&lambda;</i><sub>eff</sub> / (<i>m&mu;</i>) (Carried Server Utilization):</b> The actual fraction of time servers are busy serving admitted customers. Because physical servers cannot be more than 100% busy, <b>0 &le; <i>&rho;</i> &le; 1</b>.</li>
            <li><b><i>K</i> (Buffer Capacity):</b> The maximum number of customers that can wait in the queue.</li>
        </ul>

        <h2>III. Mathematical Condition &amp; What Happens When <i>A</i><sub>0</sub> / <i>m</i> &ge; 1</h2>
        <p>For an open queue with infinite capacity, Loynes' stability theorem states that the system is stable if and only if:</p>
        {eq1}
        <p>When <i>A</i><sub>0</sub> / <i>m</i> &gt; 1 (traffic arrives faster than servers can process it, <i>&lambda;</i> &gt; <i>m&mu;</i>), a positive queue drift occurs:</p>
        {eq2}
        <ul>
            <li><b>Infinite Buffer (<i>K</i> = &infin;):</b> The queue backlog <i>Q</i>(<i>t</i>) grows linearly with time without bound, and waiting latency <i>W</i> diverges to infinity. No steady state exists.</li>
            <li><b>Finite Buffer (<i>K</i> &lt; &infin;):</b> The buffer stays permanently full, and incoming customers are continuously dropped, enforcing a strict minimum loss probability &pi;<sub>p</sub>:</li>
        </ul>
        {eq3}
        <ul>
            <li><b>Critical Boundary (<i>A</i><sub>0</sub> / <i>m</i> = 1):</b> Even when arrival rate exactly equals service capacity (<i>&lambda;</i> = <i>m&mu;</i>), random fluctuations make an infinite-capacity queue unstable because idle server time can never be recovered to clear future bursts.</li>
        </ul>

        <h2>IV. Current System Diagnosis</h2>
        <div class="example-box">
            <p class="example-title">Live Analysis (&lambda; = {lam:.2f} cust/s, m&mu; = {m*mu:.2f} cust/s)</p>
            <p>
                At the current configuration, total offered traffic is <b><i>A</i><sub>0</sub> = {a0:.2f} Erlang</b> and offered load per server is <b><i>A</i><sub>0</sub> / <i>m</i> = {a0_per_server:.2f}</b> (while carried server utilization is <b>&rho; = {rho:.2f}</b>).
                {"Because <b><i>A</i><sub>0</sub> / <i>m</i> &ge; 1.0</b> (<i>A</i><sub>0</sub> &ge; <i>m</i>), the system is <b>overloaded</b>! In a finite buffer, at least <b>" + f"{min_loss_pct:.1f}%" + "</b> of all incoming customers will be dropped." if a0_per_server >= 1.0 else "Because <b><i>A</i><sub>0</sub> / <i>m</i> &lt; 1.0</b> (<i>A</i><sub>0</sub> &lt; <i>m</i>), the system is currently <b>stable</b> and operating inside the ergodic steady-state region."}
            </p>
            <p>
                <b>How to restore stability:</b> Increase the number of servers <i>m</i>, increase the service rate <i>&mu;</i>, or throttle the input arrival rate <i>&lambda;</i>.
            </p>
        </div>
        """
        return title, html

    # -------------------------------------------------------------------
    # Topics 7 to 13: Performance Metrics
    # -------------------------------------------------------------------
    else:
        m_stats = engine.get_metrics() if engine is not None and hasattr(engine, "get_metrics") else {}
        lam_val = (
            lam
            if lam is not None
            else (
                sum(1.0 / max(1e-6, d.mean()) for d in engine.arrival_dists.values() if d is not None)
                if engine and hasattr(engine, "arrival_dists")
                else 0.8
            )
        )
        if lam_val <= 0:
            lam_val = 0.8
        mu_val = (
            mu
            if mu is not None
            else (
                1.0 / max(1e-6, engine.service_dist.mean())
                if engine and hasattr(engine, "service_dist") and engine.service_dist is not None
                else 1.0
            )
        )
        c_val = m if m is not None else (engine.c if engine else 1)
        K_val = engine.K if engine else float("inf")

        active_arr_dists = (
            [d for d in engine.arrival_dists.values() if d is not None]
            if engine and hasattr(engine, "arrival_dists") and engine.arrival_dists
            else []
        )
        all_arr_exponential = (
            bool(active_arr_dists) and all(isinstance(d, ExponentialDist) for d in active_arr_dists)
            if active_arr_dists
            else (engine is None)
        )
        service_is_exponential = (
            isinstance(engine.service_dist, ExponentialDist)
            if (engine and hasattr(engine, "service_dist") and engine.service_dist is not None)
            else (engine is None)
        )

        theo = {}
        if lam_val > 0 and mu_val > 0:
            if (
                service_is_exponential
                and all_arr_exponential
                and (not getattr(engine, "priority_enabled", False) or math.isinf(K_val))
            ):
                if math.isinf(K_val):
                    theo = TheoreticalModels.solve_mmc_infinite(lam_val, mu_val, c_val)
                else:
                    theo = TheoreticalModels.solve_mmc_finite(lam_val, mu_val, c_val, int(K_val))
            elif (
                all_arr_exponential
                and not service_is_exponential
                and c_val == 1
                and math.isinf(K_val)
                and engine is not None
                and hasattr(engine, "service_dist")
                and engine.service_dist is not None
            ):
                theo = TheoreticalModels.solve_mg1_pollaczek_khinchine(lam_val, engine.service_dist)
            else:
                theo = {}

        is_unstable = bool(theo and theo.get("unstable", False))

        # ---------------------------------------------------------------
        # Topic 7: Average Server Utilization rho & Offered Traffic A_0
        # ---------------------------------------------------------------
        if topic_index == 7:
            a0_val = lam_val / max(1e-6, mu_val)
            rho_offered_per_server = a0_val / c_val
            rho_sim = m_stats.get("rho", 0.0)
            p_loss_theo = theo.get("p_loss", 0.0) if theo else 0.0
            if is_unstable:
                rho_carried_theo = 1.0
                rho_theo_display = "1.0000 (Saturated)"
            elif not theo:
                rho_carried_theo = 0.0
                rho_theo_display = "N/A"
            else:
                rho_carried_theo = theo.get("rho", rho_offered_per_server * (1.0 - p_loss_theo))
                rho_theo_display = f"{rho_carried_theo:.4f}"

            eq1 = latex_eq_row(
                r"A_0 = \frac{\lambda}{\mu}, \qquad \frac{A_0}{m} = \frac{\lambda}{m \cdot \mu}, \qquad \rho = \frac{A_s}{m} = \frac{\lambda_{\mathrm{eff}}}{m \cdot \mu} = \frac{A_0\left(1 - \pi_p\right)}{m}",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\bar{\rho}_{\mathrm{sim}} = \frac{1}{m \cdot T_{\mathrm{end}}} \sum_{k=1}^{m} \int_{0}^{T_{\mathrm{end}}} \mathrm{I}_{k}(t)\,\mathrm{d}t = \frac{\text{Total Busy Time Across All Servers}}{m \cdot T_{\mathrm{end}}}",
                eq_num=2,
                zoom_factor=zoom_factor,
            )

            html = f"""{css}
            <h1>Metric Theory: Average Server Utilization (<i>&rho;</i>) &amp; Offered Traffic (<i>A</i><sub>0</sub>)</h1>
            <div class="meta-line">
                <b>Metric Symbol:</b> <i>&rho;</i> (Server Utilization) &nbsp;|&nbsp; <b>Offered Traffic:</b> <i>A</i><sub>0</sub> (Erlangs) &nbsp;|&nbsp; <b>Dimension:</b> Dimensionless Ratio [0, 1]
            </div>

            <h2>I. What is this Metric?</h2>
            <p>
                In queueing systems and teletraffic engineering, this metric measures how busy the servers are. It is crucial to distinguish between two fundamental concepts:
            </p>
            <ul>
                <li><b>Offered Traffic (<i>A</i><sub>0</sub>) &amp; Offered Load per Server (<i>A</i><sub>0</sub> / <i>m</i>):</b> <i>A</i><sub>0</sub> = <i>&lambda;</i> / <i>&mu;</i> is the total volume of traffic demand arriving at the system in Erlangs. Across <i>m</i> parallel servers, the normalized offered load per server is <i>A</i><sub>0</sub> / <i>m</i> = <i>&lambda;</i> / (<i>m&mu;</i>). If traffic arrives faster than servers can process it (<i>A</i><sub>0</sub> / <i>m</i> &ge; 1, i.e., <i>A</i><sub>0</sub> &ge; <i>m</i>), the system is in overload.</li>
                <li><b>Average Server Utilization (<i>&rho;</i>):</b> The carried server utilization, defined as the actual fraction of time that servers are actively busy processing admitted customers: <i>&rho;</i> = <i>A</i><sub>s</sub> / <i>m</i> = <i>&lambda;</i><sub>eff</sub> / (<i>m&mu;</i>) = <i>A</i><sub>0</sub>(1 &minus; &pi;<sub>p</sub>) / <i>m</i>. Because a physical server cannot be busy more than 100% of the time, <i>&rho;</i> is strictly bounded in <b>[0, 1]</b> (0 &le; <i>&rho;</i> &le; 1).</li>
            </ul>

            <h2>II. Parameters Involved</h2>
            <ul>
                <li><b><i>&lambda;</i> (Arrival Rate):</b> The average number of customers arriving at the queue per second, in <b>cust/s</b>.</li>
                <li><b><i>&mu;</i> (Service Rate per Server):</b> The processing speed of a single server, in <b>cust/s</b>.</li>
                <li><b><i>m</i> (Number of Servers):</b> The number of parallel servers working concurrently.</li>
                <li><b><i>m&mu;</i> (Total Capacity):</b> The maximum departure rate when all <i>m</i> servers are actively busy, in <b>cust/s</b>.</li>
                <li><b><i>A</i><sub>0</sub> = <i>&lambda;</i> / <i>&mu;</i> (Offered Traffic):</b> Total incoming traffic volume in Erlangs (with per-server offered load <i>A</i><sub>0</sub> / <i>m</i>).</li>
                <li><b><i>&pi;</i><sub>p</sub> (Blocking / Loss Probability):</b> The fraction of customers dropped because the buffer was full upon arrival.</li>
                <li><b><i>&lambda;</i><sub>eff</sub> = <i>&lambda;</i>(1 &minus; &pi;<sub>p</sub>):</b> The effective arrival rate of customers admitted into the system.</li>
                <li><b><i>T</i><sub>end</sub> (Simulation Time):</b> The total elapsed simulation clock time, in <b>seconds</b>.</li>
                <li><b>I<sub><i>k</i></sub>(<i>t</i>) &isin; &#123;0, 1&#125; (Server Busy Indicator):</b> Equal to 1 when server <i>k</i> is actively serving a customer at time <i>t</i>, and 0 when it is idle.</li>
            </ul>

            <h2>III. Mathematical Formulas &amp; Runtime Computation</h2>
            <p>The analytical expressions for Offered Traffic (<i>A</i><sub>0</sub>) and Server Utilization (<i>&rho;</i>) are:</p>
            {eq1}
            <p>
                In the simulation engine, <b>Average Server Utilization</b> is computed continuously at runtime via time integration:
            </p>
            {eq2}
            <p>
                The simulator tracks the exact start and end times of every service event, computes the total active busy time accumulated across all <i>m</i> servers, and divides by the total available server-time (<i>m &times; T</i><sub>end</sub>).
            </p>

            <h2>IV. Key Properties</h2>
            <ul>
                <li><b>Infinite Buffer (<i>K</i> = &infin;) &amp; Stable (<i>A</i><sub>0</sub> / <i>m</i> &lt; 1):</b> No customers are ever dropped (&pi;<sub>p</sub> = 0), so server utilization equals the offered load per server: <b><i>&rho;</i> = <i>A</i><sub>0</sub> / <i>m</i></b>.</li>
                <li><b>Finite Buffer (<i>K</i> &lt; &infin;) &amp; Overload (<i>A</i><sub>0</sub> &ge; <i>m</i>):</b> When <i>A</i><sub>0</sub> &ge; <i>m</i>, the buffer frequently fills up and drops excess customers. The admitted traffic rate cannot exceed total capacity (<i>&lambda;</i><sub>eff</sub> &le; <i>m&mu;</i>), so server utilization saturates near <b><i>&rho;</i> &approx; 1.0 (100%)</b>, while offered load <i>A</i><sub>0</sub> / <i>m</i> reflects the high incoming demand.</li>
                <li><b>Physical Interpretation:</b> If <i>&rho;</i> = 0.80, servers are busy on average 80% of the time and idle 20% of the time.</li>
            </ul>

            <h2>V. Current Simulator Values &amp; Comparison</h2>
            <table class="book-table">
                <tr><th>Parameter / Metric</th><th>Formula / Expression</th><th>Live Simulator Value</th></tr>
                <tr><td>Aggregate Arrival Rate (<i>&lambda;</i>)</td><td>Input parameter</td><td>{lam_val:.4f} cust/s</td></tr>
                <tr><td>Total Service Capacity (<i>m&mu;</i>)</td><td>{c_val} &times; {mu_val:.4f}</td><td>{c_val * mu_val:.4f} cust/s</td></tr>
                <tr><td>Offered Traffic (<i>A</i><sub>0</sub>)</td><td><i>&lambda;</i> / <i>&mu;</i></td><td>{a0_val:.4f} Erlang</td></tr>
                <tr><td>Offered Load per Server (<i>A</i><sub>0</sub> / <i>m</i>)</td><td><i>&lambda;</i> / (<i>m&mu;</i>)</td><td>{rho_offered_per_server:.4f}</td></tr>
                <tr><td>Theoretical Server Utilization (<i>&rho;</i><sub>theo</sub>)</td><td><i>A</i><sub>s</sub> / <i>m</i> = <i>&lambda;</i>(1 &minus; &pi;<sub>p</sub>) / (<i>m&mu;</i>)</td><td>{rho_theo_display}</td></tr>
                <tr class="bottom-rule"><td>Simulated Server Utilization (<i>&rho;</i><sub>sim</sub>)</td><td>Continuous time integral (Eq. 2)</td><td>{rho_sim:.4f}</td></tr>
            </table>
            """
            return title, html

        # ---------------------------------------------------------------
        # Topic 8: Average Traffic in System (A)
        # ---------------------------------------------------------------
        elif topic_index == 8:
            title = "Metric Theory: Average Traffic in System A (k(t))"
            L_val = theo.get("A", theo.get("L")) if theo else None
            L_sim = m_stats.get("A", m_stats.get("L", 0.0))
            littles_L = m_stats.get("littles_L", 0.0)

            if is_unstable:
                L_theo_str = "&infin; (Unstable)"
            elif L_val is None:
                L_theo_str = "N/A"
            elif math.isinf(L_val) or math.isnan(L_val):
                L_theo_str = "&infin; (Infinite Variance)"
            else:
                L_theo_str = f"{L_val:.4f} Erlang"

            eq1 = latex_eq_row(
                r"A = \mathrm{E}[k(t)] = \sum_{k=0}^{\infty} k\, P_k = A_c + A_s = \lambda_s \bar{\delta}",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\bar{A}_{\mathrm{sim}} = \frac{1}{T_{\mathrm{end}}} \int_{0}^{T_{\mathrm{end}}} k(t)\,\mathrm{d}t = \frac{1}{T_{\mathrm{end}}} \sum_{k} k \cdot \Delta t_k",
                eq_num=2,
                zoom_factor=zoom_factor,
            )

            html = f"""{css}
            <h1>Metric Theory: Average Traffic in System (<i>A</i>)</h1>
            <div class="meta-line">
                <b>Metric Symbol:</b> <i>A</i> = E[<i>k</i>(<i>t</i>)] &nbsp;|&nbsp; <b>Scope:</b> Queue Backlog (<i>A<sub>c</sub></i>) + Carried Traffic (<i>A<sub>s</sub></i>) &nbsp;|&nbsp; <b>Unit:</b> Erlang (E) / customers
            </div>

            <h2>I. What is this Metric?</h2>
            <p>
                In teletraffic systems, <b><i>A</i></b> is the average traffic intensity in the system, defined as the long-run time-average value of the customer occupancy stochastic process <b><i>k</i>(<i>t</i>)</b>.
                By observing the system as a whole, the total traffic inside decomposes into the traffic waiting in queue (<i>A<sub>c</sub></i>) and the traffic currently being served by the servers (<i>A<sub>s</sub></i>):
                <b><i>A</i> = <i>A<sub>c</sub></i> + <i>A<sub>s</sub></i></b>.
            </p>

            <h2>II. Parameters Involved</h2>
            <ul>
                <li><b><i>k</i>(<i>t</i>) = <i>k</i>(0) + <i>a</i>(<i>t</i>) &minus; <i>d</i>(<i>t</i>):</b> The instantaneous traffic (number of customers) in the system at time <i>t</i>, where <i>a</i>(<i>t</i>) is cumulative arrivals and <i>d</i>(<i>t</i>) is cumulative departures.</li>
                <li><b><i>P<sub>k</sub></i>:</b> The steady-state probability that exactly <i>k</i> customers are in the system.</li>
                <li><b><i>A<sub>c</sub></i> = <i>&lambda;<sub>s</sub></i> &eta;&#772;:</b> Average number of customers waiting in the queue buffer.</li>
                <li><b><i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub></i> &vartheta;&#772; = (1 &minus; &pi;<sub>p</sub>)<i>A</i><sub>0</sub>:</b> Average traffic served or carried by the servers (<i>A<sub>s</sub></i> = <i>m &middot; &rho;</i>).</li>
                <li><b>&Delta;<i>t<sub>k</sub></i>:</b> Cumulative duration of time that the system spent in state <i>k</i>.</li>
            </ul>

            <h2>III. Mathematical Formulas &amp; Runtime Computation</h2>
            <p>In steady state, the expected system traffic is the first moment of the state distribution, satisfying Little's Law:</p>
            {eq1}
            <p>The simulation engine tracks the exact time &Delta;<i>t<sub>k</sub></i> spent in each state <i>k</i> to compute the continuous time-average:</p>
            {eq2}

            <h2>IV. Key Properties</h2>
            <ul>
                <li><b>Little's Law Relation:</b> Across the entire queuing system, <b><i>A</i> = <i>&lambda;<sub>s</sub></i> &middot; &delta;&#772;</b>, connecting average traffic directly to average sojourn time &delta;&#772;.</li>
                <li><b>Single-Server System ($M/M/1$):</b> When <i>m</i> = 1 and <i>K</i> = &infin;, <b><i>A</i> = <i>A<sub>s</sub></i> + <i>A<sub>c</sub></i> = <i>&rho;</i> + <i>&rho;</i><sup>2</sup>/(1 &minus; <i>&rho;</i>) = <i>&rho;</i> / (1 &minus; <i>&rho;</i>) = <i>A</i><sub>0</sub> / (1 &minus; <i>A</i><sub>0</sub>)</b>.</li>
                <li><b>Multiple Servers ($M/M/m$):</b> With unlimited waiting space, <b><i>A</i> = <i>A</i><sub>0</sub> + &Ccedil;(<i>m</i>, <i>A</i><sub>0</sub>) &middot; <i>A</i><sub>0</sub> / (<i>m</i> &minus; <i>A</i><sub>0</sub>)</b>, where &Ccedil;(<i>m</i>, <i>A</i><sub>0</sub>) is Erlang's C formula.</li>
                <li><b>Finite Waiting Space ($M/M/1/L$):</b> Under heavy overload, the traffic saturates at the physical capacity ceiling: <b>lim<sub><i>A</i><sub>0</sub> &rarr; &infin;</sub> <i>A</i> = <i>L</i> + 1</b>.</li>
            </ul>

            <h2>V. Current Simulator Values &amp; Comparison</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Formula / Method</th><th>Live Simulator Value</th></tr>
                <tr><td>Theoretical Average Traffic (<i>A</i><sub>theo</sub>)</td><td>Analytical model (Eq. 1)</td><td>{L_theo_str}</td></tr>
                <tr><td>Simulated Time-Average (<i>A</i><sub>sim</sub>)</td><td>Time integral (Eq. 2)</td><td>{L_sim:.4f} Erlang</td></tr>
                <tr class="bottom-rule"><td>Little's Law Product (<i>&lambda;</i><sub>s</sub> &middot; &delta;&#772;<sub>sim</sub>)</td><td>Conservation check</td><td>{littles_L:.4f} Erlang</td></tr>
            </table>
            """
            return title, html

        # ---------------------------------------------------------------
        # Topic 9: Average Queue Backlog (A_c)
        # ---------------------------------------------------------------
        elif topic_index == 9:
            title = "Metric Theory: Average Queue Backlog A_c"
            Lq_val = theo.get("A_c", theo.get("Lq")) if theo else None
            Lq_sim = m_stats.get("A_c", m_stats.get("Lq", 0.0))
            littles_Lq = m_stats.get("littles_Lq", 0.0)

            if is_unstable:
                Lq_theo_str = "&infin; (Unstable)"
            elif Lq_val is None:
                Lq_theo_str = "N/A"
            elif math.isinf(Lq_val) or math.isnan(Lq_val):
                Lq_theo_str = "&infin; (Infinite Variance)"
            else:
                Lq_theo_str = f"{Lq_val:.4f} cust"

            eq1 = latex_eq_row(
                r"A_c = \sum_{k=m}^{\infty} (k - m)\,P_k = \mathcal{C}(m, A_0)\frac{A_0}{m - A_0}, \qquad A_c^{(M/G/1)} = \frac{\rho^2\left(1 + C_s^2\right)}{2(1 - \rho)}",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\bar{A}_{c,\mathrm{sim}} = \frac{1}{T_{\mathrm{end}}} \int_{0}^{T_{\mathrm{end}}} \max\left(0,\, k(t) - m\right)\mathrm{d}t",
                eq_num=2,
                zoom_factor=zoom_factor,
            )

            html = f"""{css}
            <h1>Metric Theory: Average Queue Backlog (<i>A<sub>c</sub></i>)</h1>
            <div class="meta-line">
                <b>Metric Symbol:</b> <i>A<sub>c</sub></i> &nbsp;|&nbsp; <b>Scope:</b> Waiting Space Only (Excludes Servers) &nbsp;|&nbsp; <b>Unit:</b> Erlang (E) / customers
            </div>

            <h2>I. What is this Metric?</h2>
            <p>
                <b><i>A<sub>c</sub></i></b> is the average number of customers waiting in the queue buffer, strictly excluding customers that are actively being served by one of the <i>m</i> servers.
                By Little's Law applied to the queue subsystem, <b><i>A<sub>c</sub></i> = <i>&lambda;<sub>s</sub></i> &middot; &eta;&#772;</b>, where &eta;&#772; is the average waiting time for a generic customer.
            </p>

            <h2>II. Parameters Involved</h2>
            <ul>
                <li><b><i>k<sub>q</sub></i>(<i>t</i>) = max(0, <i>k</i>(<i>t</i>) &minus; <i>m</i>):</b> The instantaneous queue backlog at time <i>t</i>.</li>
                <li><b><i>K</i> (or <i>L</i>):</b> The maximum queue buffer size (number of waiting slots).</li>
                <li><b>&eta;&#772; (Average Waiting Time):</b> The average time spent waiting in queue for a generic customer, in <b>seconds</b>.</li>
                <li><b><i>&lambda;<sub>s</sub></i> = (1 &minus; &pi;<sub>p</sub>)<i>&lambda;</i>:</b> Rate of customers entering the system (admitted throughput).</li>
                <li><b>&Ccedil;(<i>m</i>, <i>A</i><sub>0</sub>):</b> Erlang's C formula, representing the congestion probability &pi;<sub>r</sub> that an arrival finds all <i>m</i> servers busy.</li>
            </ul>

            <h2>III. Mathematical Formulas &amp; Runtime Computation</h2>
            <p>From the state probabilities <i>P<sub>k</sub></i> (and via Erlang-C for <i>M</i>/<i>M</i>/<i>m</i> or Pollaczek-Khinchine for <i>M</i>/<i>G</i>/1 queues):</p>
            {eq1}
            <p>The simulator tracks the continuous backlog <i>k<sub>q</sub></i>(<i>t</i>) over time:</p>
            {eq2}

            <h2>IV. Key Propertiess</h2>
            <ul>
                <li><b>Non-linear Queue Explosion:</b> In single-server queues ($M/M/1$), <b><i>A<sub>c</sub></i> = <i>&rho;</i><sup>2</sup> / (1 &minus; <i>&rho;</i>) = <i>A</i><sub>0</sub><sup>2</sup> / (1 &minus; <i>A</i><sub>0</sub>)</b>. As server utilization approaches 100%, queue backlog explodes to infinity.</li>
                <li><b>Little's Law for Queues:</b> Just like total system traffic, <b><i>A<sub>c</sub></i> = <i>&lambda;<sub>s</sub></i> &middot; &eta;&#772;</b> holds universally regardless of distributions or scheduling disciplines.</li>
            </ul>

            <h2>V. Current Simulator Values &amp; Comparison</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Formula / Method</th><th>Live Simulator Value</th></tr>
                <tr><td>Theoretical Queue Backlog (<i>A</i><sub><i>c</i>,theo</sub>)</td><td>Analytical model (Eq. 1)</td><td>{Lq_theo_str}</td></tr>
                <tr><td>Simulated Queue Backlog (<i>A</i><sub><i>c</i>,sim</sub>)</td><td>Time integral (Eq. 2)</td><td>{Lq_sim:.4f} cust</td></tr>
                <tr class="bottom-rule"><td>Little's Law Product (<i>&lambda;</i><sub>s</sub> &middot; &eta;&#772;<sub>sim</sub>)</td><td>Conservation check</td><td>{littles_Lq:.4f} cust</td></tr>
            </table>
            """
            return title, html

        # ---------------------------------------------------------------
        # Topic 10: Average Sojourn Time (\bar{\delta})
        # ---------------------------------------------------------------
        elif topic_index == 10:
            title = "Metric Theory: Average Sojourn Time δ̄"
            W_val = theo.get("delta_bar", theo.get("W")) if theo else None
            W_sim = m_stats.get("delta_bar", m_stats.get("W", 0.0))
            Wq_sim = m_stats.get("eta_bar", m_stats.get("Wq", 0.0))
            es_val = 1.0 / max(1e-6, mu_val)

            if is_unstable:
                W_theo_str = "&infin; (Unstable)"
            elif W_val is None:
                W_theo_str = "N/A"
            elif math.isinf(W_val) or math.isnan(W_val):
                W_theo_str = "&infin; (Infinite Variance)"
            else:
                W_theo_str = f"{W_val:.4f} s"

            eq1 = latex_eq_row(
                r"\bar{\delta} = \bar{\eta} + \bar{\vartheta} = \bar{\eta} + \frac{1}{\mu} = \frac{A}{\lambda_s}",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\bar{\delta}_{\mathrm{sim}} = \frac{1}{d(T_{\mathrm{end}})} \sum_{i=1}^{d(T_{\mathrm{end}})} \delta_i = \frac{1}{d(T_{\mathrm{end}})} \sum_{i=1}^{d(T_{\mathrm{end}})} \left(t_{\mathrm{dep},i} - t_{\mathrm{arr},i}\right)",
                eq_num=2,
                zoom_factor=zoom_factor,
            )

            html = f"""{css}
            <h1>Metric Theory: Average Sojourn Time (&delta;&#772;)</h1>
            <div class="meta-line">
                <b>Metric Symbol:</b> &delta;&#772; &nbsp;|&nbsp; <b>Decomposition:</b> &delta;&#772; = &eta;&#772; + &vartheta;&#772; &nbsp;|&nbsp; <b>Unit:</b> seconds
            </div>

            <h2>I. What is this Metric?</h2>
            <p>
                <b>&delta;&#772;</b> (average sojourn time) is the average total time that an admitted customer spends in the queuing system, from the instant it enters the system until its service is completed and it leaves the system.
                As established in traffic theory, average sojourn time is the sum of average waiting time in queue (&eta;&#772;) and average service time (&vartheta;&#772; = 1/&mu;):
                <b>&delta;&#772; = &eta;&#772; + &vartheta;&#772;</b>.
            </p>

            <h2>II. Parameters Involved</h2>
            <ul>
                <li><b>&delta;<sub><i>i</i></sub> = <i>t</i><sub>dep,<i>i</i></sub> &minus; <i>t</i><sub>arr,<i>i</i></sub>:</b> The sojourn time of the <i>i</i>-th completed customer.</li>
                <li><b>&eta;&#772;:</b> Average waiting time spent in the queue buffer, in <b>seconds</b>.</li>
                <li><b>&vartheta;&#772; = 1 / <i>&mu;</i>:</b> Average service time in the server, in <b>seconds</b>.</li>
                <li><b><i>d</i>(<i>T</i><sub>end</sub>):</b> Total number of customer departures up to time <i>T</i><sub>end</sub>.</li>
                <li><b><i>&lambda;<sub>s</sub></i> = (1 &minus; &pi;<sub>p</sub>)<i>&lambda;</i>:</b> Average rate of customers admitted into the system.</li>
            </ul>

            <h2>III. Mathematical Formulas &amp; Runtime Computation</h2>
            <p>By linearity of expectation and Little's Law, average sojourn time satisfies:</p>
            {eq1}
            <p>In the simulator, &delta;&#772; is computed as the exact sample average over all departed customers:</p>
            {eq2}

            <h2>IV. Key Properties</h2>
            <ul>
                <li><b>Decomposition Identity:</b> Multiplying &delta;&#772; = &eta;&#772; + &vartheta;&#772; by <i>&lambda;<sub>s</sub></i> yields the traffic relation: <b><i>A</i> = <i>A<sub>c</sub></i> + <i>A<sub>s</sub></i></b>.</li>
                <li><b>Single Server ($M/M/1$):</b> <b>&delta;&#772; = &vartheta;&#772; / (1 &minus; <i>&rho;</i>) = 1 / (&mu; &minus; &lambda;)</b>.</li>
                <li><b>Multiple Servers ($M/M/m$):</b> <b>&delta;&#772; = &vartheta;&#772; + &Ccedil;(<i>m</i>, <i>A</i><sub>0</sub>) &middot; &vartheta;&#772; / (<i>m</i> &minus; <i>A</i><sub>0</sub>)</b>.</li>
                <li><b>Finite Waiting Space ($M/M/1/L$):</b> <b>&delta;&#772; = <i>A</i> / [(1 &minus; &pi;<sub>p</sub>)&lambda;] = <i>A</i> / <i>&lambda;<sub>s</sub></i></b>.</li>
            </ul>

            <h2>V. Current Simulator Values &amp; Comparison</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Formula / Method</th><th>Live Simulator Value</th></tr>
                <tr><td>Theoretical Sojourn Time (&delta;&#772;<sub>theo</sub>)</td><td>Analytical model (Eq. 1)</td><td>{W_theo_str}</td></tr>
                <tr><td>Simulated Sojourn Time (&delta;&#772;<sub>sim</sub>)</td><td>Sample average (Eq. 2)</td><td>{W_sim:.4f} s</td></tr>
                <tr class="bottom-rule"><td>Decomposition Check (&eta;&#772;<sub>sim</sub> + &vartheta;&#772;)</td><td>{Wq_sim:.4f} s + {es_val:.4f} s</td><td>{Wq_sim + es_val:.4f} s</td></tr>
            </table>
            """
            return title, html

        # ---------------------------------------------------------------
        # Topic 11: Average Waiting Time in Queue (\bar{\eta} and \bar{\varepsilon})
        # ---------------------------------------------------------------
        elif topic_index == 11:
            title = "Metric Theory: Average Waiting Time η̄ (and ε̄)"
            Wq_val = theo.get("eta_bar", theo.get("Wq")) if theo else None
            Wq_sim = m_stats.get("eta_bar", m_stats.get("Wq", 0.0))

            if is_unstable:
                Wq_theo_str = "&infin; (Unstable)"
                disc_str = "Divergent"
            elif Wq_val is None:
                Wq_theo_str = "N/A"
                disc_str = "-"
            elif math.isinf(Wq_val) or math.isnan(Wq_val):
                Wq_theo_str = "&infin; (Infinite Variance)"
                disc_str = "Divergent"
            else:
                Wq_theo_str = f"{Wq_val:.4f} s"
                disc_str = f"{abs(Wq_sim - Wq_val):.4f} s"

            eq1 = latex_eq_row(
                r"\bar{\eta} = \frac{A_c}{\lambda_s} = \mathcal{C}(m, A_0)\frac{\bar{\vartheta}}{m - A_0}, \qquad \bar{\varepsilon} = \frac{\bar{\eta}}{\mathcal{C}(m, A_0)} = \frac{\bar{\vartheta}}{m - A_0}",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\bar{\eta}_{\mathrm{sim}} = \frac{1}{d(T_{\mathrm{end}})} \sum_{i=1}^{d(T_{\mathrm{end}})} \left(t_{\mathrm{start},i} - t_{\mathrm{arr},i}\right)",
                eq_num=2,
                zoom_factor=zoom_factor,
            )

            html = f"""{css}
            <h1>Metric Theory: Average Waiting Time (&eta;&#772; and &epsilon;&#772;)</h1>
            <div class="meta-line">
                <b>Metric Symbols:</b> &eta;&#772; (Generic Customer) &nbsp;|&nbsp; &epsilon;&#772; (Customer that Joins Queue) &nbsp;|&nbsp; <b>Unit:</b> seconds
            </div>

            <h2>I. What is this Metric?</h2>
            <p>
                <b>&eta;&#772;</b> is the average time spent in queue (waiting time) by a generic customer entering the system, including customers that find an idle server upon arrival and experience zero wait (&eta; = 0).
                In multiserver systems ($M/M/m$), traffic theory also defines <b>&epsilon;&#772;</b> as the average waiting time for a customer that actually joins the queue:
                <b>&epsilon;&#772; = &eta;&#772; / &Ccedil;(<i>m</i>, <i>A</i><sub>0</sub>) = &vartheta;&#772; / (<i>m</i> &minus; <i>A</i><sub>0</sub>)</b>.
            </p>

            <h2>II. Parameters Involved</h2>
            <ul>
                <li><b>&eta;<sub><i>i</i></sub> = <i>t</i><sub>start,<i>i</i></sub> &minus; <i>t</i><sub>arr,<i>i</i></sub>:</b> Time customer <i>i</i> waited in line before a server began its service.</li>
                <li><b>&Ccedil;(<i>m</i>, <i>A</i><sub>0</sub>):</b> Erlang's C formula &pi;<sub>r</sub>, the probability that all <i>m</i> servers are busy and a customer must wait.</li>
                <li><b>&epsilon;&#772;:</b> Conditional average waiting time for customers that actually had to wait in queue.</li>
                <li><b><i>A<sub>c</sub></i>:</b> Average queue backlog (customers in buffer).</li>
                <li><b><i>&lambda;<sub>s</sub></i>:</b> Admitted arrival rate entering the system.</li>
                <li><b><i>C<sub>s</sub></i><sup>2</sup>:</b> Squared coefficient of variation of service time (in $M/G/1$).</li>
            </ul>

            <h2>III. Mathematical Formulas &amp; Runtime Computation</h2>
            <p>In steady state, the analytical expressions for &eta;&#772; and &epsilon;&#772; are:</p>
            {eq1}
            <p>Across all departed customers, the simulator calculates the empirical waiting time mean:</p>
            {eq2}

            <h2>IV. Key Properties</h2>
            <ul>
                <li><b>Single-Server System ($M/M/1$):</b> Here &Ccedil;(1, <i>A</i><sub>0</sub>) = <i>&rho;</i>, so <b>&eta;&#772; = &vartheta;&#772; &middot; <i>&rho;</i> / (1 &minus; <i>&rho;</i>) = <i>&rho;</i> / [&mu;(1 &minus; <i>&rho;</i>)]</b> and <b>&epsilon;&#772; = &vartheta;&#772; / (1 &minus; <i>&rho;</i>)</b>.</li>
                <li><b>Pollaczek-Khinchine Formula ($M/G/1$):</b> With general service variance, <b>&eta;&#772; = &vartheta;&#772; &middot; [<i>&rho;</i> / (1 &minus; <i>&rho;</i>)] &middot; [(1 + <i>C<sub>s</sub></i><sup>2</sup>) / 2]</b>.</li>
                <li><b>Invariance:</b> Average waiting times are valid for any work-conserving queueing discipline (FIFO, LIFO, Random Choice).</li>
            </ul>

            <h2>V. Current Simulator Values &amp; Comparison</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Formula / Method</th><th>Live Simulator Value</th></tr>
                <tr><td>Theoretical Mean Wait (&eta;&#772;<sub>theo</sub>)</td><td>Analytical model (Eq. 1)</td><td>{Wq_theo_str}</td></tr>
                <tr><td>Simulated Mean Wait (&eta;&#772;<sub>sim</sub>)</td><td>Sample average (Eq. 2)</td><td>{Wq_sim:.4f} s</td></tr>
                <tr class="bottom-rule"><td>Absolute Discrepancy |&eta;&#772;<sub>sim</sub> &minus; &eta;&#772;<sub>theo</sub>|</td><td>Empirical convergence error</td><td>{disc_str}</td></tr>
            </table>
            """
            return title, html

        # ---------------------------------------------------------------
        # Topic 12: Blocking Probability (\pi_p) & Erlang-B Formula
        # ---------------------------------------------------------------
        elif topic_index == 12:
            title = "Metric Theory: Blocking Probability π_p"
            p_loss_theo = theo.get("pi_p", theo.get("p_loss", 0.0)) if theo else 0.0
            p_loss_theo_str = f"{p_loss_theo*100.0:.2f}%" if theo else "N/A"
            p_loss_sim = m_stats.get("pi_p", m_stats.get("p_loss", 0.0))
            arr_tot = m_stats.get("arrived", 0)
            drop_tot = m_stats.get("dropped", 0)

            eq1 = latex_eq_row(
                r"\mathcal{B}(m, A_0) = \frac{A_0^m / m!}{\sum_{k=0}^{m} A_0^k / k!}, \qquad \pi_p = P_{m+K}, \qquad \lambda_s = (1 - \pi_p)\lambda",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\bar{\pi}_{p,\mathrm{sim}} = \frac{a_p(T_{\mathrm{end}})}{a(T_{\mathrm{end}})} = \frac{N_{\mathrm{dropped}}}{N_{\mathrm{arrived}}}, \qquad A_0 = A_s + A_p = (1 - \pi_p)A_0 + \pi_p A_0",
                eq_num=2,
                zoom_factor=zoom_factor,
            )

            html = f"""{css}
            <h1>Metric Theory: Blocking Probability (&pi;<sub>p</sub>) &amp; Erlang's B Formula</h1>
            <div class="meta-line">
                <b>Metric Symbol:</b> &pi;<sub>p</sub> &nbsp;|&nbsp; <b>Traffic Breakdown:</b> <i>A</i><sub>0</sub> = <i>A<sub>s</sub></i> + <i>A<sub>p</sub></i> &nbsp;|&nbsp; <b>Buffer Capacity:</b> <i>K</i> = {'&infin;' if math.isinf(K_val) else int(K_val)} slots
            </div>

            <h2>I. What is this Metric?</h2>
            <p>
                In a real queuing system with finite waiting space (<i>K</i> &lt; &infin;), any customer that finds all servers busy and the buffer full cannot enter the system and is rejected (**loss system**).
                <b>&pi;<sub>p</sub></b> is the **blocking probability** (or loss probability), defined as the probability that an arriving customer is rejected.
                Lost customers generate rejected traffic <b><i>A<sub>p</sub></i> = &pi;<sub>p</sub> <i>A</i><sub>0</sub></b>, leaving carried traffic <b><i>A<sub>s</sub></i> = (1 &minus; &pi;<sub>p</sub>)<i>A</i><sub>0</sub></b>.
            </p>

            <h2>II. Parameters Involved</h2>
            <ul>
                <li><b><i>a</i>(<i>t</i>):</b> Cumulative total number of customer arrivals up to time <i>t</i>.</li>
                <li><b><i>a<sub>p</sub></i>(<i>t</i>):</b> Cumulative total number of customer arrivals rejected up to time <i>t</i>.</li>
                <li><b><i>A</i><sub>0</sub> = &lambda;&vartheta;&#772;:</b> Offered traffic in Erlangs.</li>
                <li><b><i>A<sub>s</sub></i> = &lambda;<sub>s</sub>&vartheta;&#772; = (1 &minus; &pi;<sub>p</sub>)<i>A</i><sub>0</sub>:</b> Served or carried traffic in Erlangs.</li>
                <li><b><i>A<sub>p</sub></i> = &lambda;<sub>p</sub>&vartheta;&#772; = &pi;<sub>p</sub> <i>A</i><sub>0</sub>:</b> Rejected or lost traffic in Erlangs.</li>
                <li><b><i>&lambda;<sub>s</sub></i> = (1 &minus; &pi;<sub>p</sub>)<i>&lambda;</i>:</b> Admitted arrival rate (throughput).</li>
            </ul>

            <h2>III. Mathematical Formulas &amp; Runtime Computation</h2>
            <p>For systems without waiting space ($M/M/m/0$), blocking is given by <b>Erlang's B formula</b>; for finite queues, it is the full-state probability:</p>
            {eq1}
            <p>The simulator measures empirical blocking from arrival and drop event counters:</p>
            {eq2}

            <h2>IV. Key Properties</h2>
            <ul>
                <li><b>Traffic Decomposition:</b> Offered traffic is always conserved: <b><i>A</i><sub>0</sub> = <i>A<sub>s</sub></i> + <i>A<sub>p</sub></i></b>.</li>
                <li><b>Insensitivity of Erlang-B:</b> Erlang's B formula does not depend on the service time distribution, holding for general $M/G/m/0$ queues.</li>
                <li><b>Single Server with Limited Queue ($M/M/1/L$):</b> <b>&pi;<sub>p</sub> = <i>P</i><sub><i>L</i>+1</sub> = [(1 &minus; <i>A</i><sub>0</sub>)/(1 &minus; <i>A</i><sub>0</sub><sup><i>L</i>+2</sup>)] <i>A</i><sub>0</sub><sup><i>L</i>+1</sup></b>.
                As <i>L</i> &rarr; &infin;, <b>lim<sub><i>L</i>&rarr;&infin;</sub> &pi;<sub>p</sub> = (<i>A</i><sub>0</sub> &minus; 1)/<i>A</i><sub>0</sub></b> when <i>A</i><sub>0</sub> &gt; 1, and <b>0</b> when <i>A</i><sub>0</sub> &le; 1.</li>
            </ul>

            <h2>V. Current Simulator Values &amp; Comparison</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Formula / Method</th><th>Live Simulator Value</th></tr>
                <tr><td>Theoretical Blocking Probability (&pi;<sub>p,theo</sub>)</td><td>Analytical model (Eq. 1)</td><td>{p_loss_theo_str}</td></tr>
                <tr><td>Simulated Blocking Probability (&pi;<sub>p,sim</sub>)</td><td><i>a<sub>p</sub></i> / <i>a</i> (Eq. 2)</td><td>{p_loss_sim*100.0:.2f}%</td></tr>
                <tr class="bottom-rule"><td>Rejected Arrivals / Total Arrivals</td><td><i>a<sub>p</sub></i>(<i>T</i>) / <i>a</i>(<i>T</i>)</td><td>{drop_tot:,} / {arr_tot:,} cust</td></tr>
            </table>
            """
            return title, html

        # ---------------------------------------------------------------
        # Topic 13: Little's Law Invariance (A = \lambda_s \bar{\delta})
        # ---------------------------------------------------------------
        elif topic_index == 13:
            title = "Metric Theory: Little's Law Invariance (A = λ_s δ̄)"
            L_sim = m_stats.get("A", m_stats.get("L", 0.0))
            W_sim = m_stats.get("delta_bar", m_stats.get("W", 0.0))
            lam_eff = m_stats.get("lambda_s", m_stats.get("lambda_eff", 0.0))
            littles_L = m_stats.get("littles_L", 0.0)
            littles_err = m_stats.get("littles_error_A", m_stats.get("littles_error_L", 0.0))

            eq1 = latex_eq_row(
                r"A = \lambda_s \bar{\delta}, \qquad A_c = \lambda_s \bar{\eta}, \qquad A_s = \lambda_s \bar{\vartheta}",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\left| \bar{A}_{\mathrm{sim}} - \lambda_{s,\mathrm{sim}} \cdot \bar{\delta}_{\mathrm{sim}} \right| \xrightarrow[T_{\mathrm{end}} \to \infty]{} 0, \qquad A = A_c + A_s = \lambda_s\left(\bar{\eta} + \bar{\vartheta}\right)",
                eq_num=2,
                zoom_factor=zoom_factor,
            )

            html = f"""{css}
            <h1>Metric Theory: Little's Law Invariance (<i>A</i> = <i>&lambda;<sub>s</sub></i> &delta;&#772;)</h1>
            <div class="meta-line">
                <b>Theorem:</b> John D. C. Little (1961) &nbsp;|&nbsp; <b>Fundamental Relations:</b> <i>A</i> = <i>&lambda;<sub>s</sub></i> &delta;&#772; &nbsp;|&nbsp; <i>A<sub>c</sub></i> = <i>&lambda;<sub>s</sub></i> &eta;&#772; &nbsp;|&nbsp; <i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub></i> &vartheta;&#772;
            </div>

            <h2>I. What is this Theorem?</h2>
            <p>
                <b>Little's Law</b> is the most celebrated and fundamental relation in traffic theory and queueing systems.
                It states that the average traffic intensity in any stationary queuing system (<b><i>A</i></b>) is identically equal to the rate of customers admitted into the system (<b><i>&lambda;<sub>s</sub></i></b>) multiplied by the average sojourn time spent by customers in the system (<b>&delta;&#772;</b>):
                <br/><center><b><i>A</i> = <i>&lambda;<sub>s</sub></i> &middot; &delta;&#772;</b></center>
            </p>

            <h2>II. Parameters Involved</h2>
            <ul>
                <li><b><i>A</i>:</b> Average traffic in the entire queuing system, in Erlang (E).</li>
                <li><b><i>A<sub>c</sub></i>:</b> Average traffic waiting in the queue buffer, in Erlang (E).</li>
                <li><b><i>A<sub>s</sub></i>:</b> Average traffic being served in the servers, in Erlang (E) (<i>A<sub>s</sub></i> = <i>m &middot; &rho;</i>).</li>
                <li><b><i>&lambda;<sub>s</sub></i> = (1 &minus; &pi;<sub>p</sub>)<i>&lambda;</i>:</b> Admitted rate of customers entering the system, in cust/s.</li>
                <li><b>&delta;&#772;:</b> Average sojourn time in the system, in seconds.</li>
                <li><b>&eta;&#772;:</b> Average waiting time in the queue, in seconds.</li>
                <li><b>&vartheta;&#772; = 1/&mu;:</b> Average service time in the servers, in seconds.</li>
            </ul>

            <h2>III. Mathematical Formulas &amp; Runtime Computation</h2>
            <p>Little's Law applies to the entire queuing system and to each of its subsystems (the queue and the servers):</p>
            {eq1}
            <p>In a finite simulation run, the absolute error measures convergence to the exact theoretical identity:</p>
            {eq2}

            <h2>IV. Key Properties</h2>
            <ul>
                <li><b>Universal &amp; Distribution-Free:</b> Little's Law holds for any arrival process distribution and any service distribution!</li>
                <li><b>Subsystem Additivity:</b> Because &delta;&#772; = &eta;&#772; + &vartheta;&#772;, multiplying both sides by <i>&lambda;<sub>s</sub></i> gives:
                <b><i>A</i> = <i>&lambda;<sub>s</sub></i> &delta;&#772; = <i>&lambda;<sub>s</sub></i> &eta;&#772; + <i>&lambda;<sub>s</sub></i> &vartheta;&#772; = <i>A<sub>c</sub></i> + <i>A<sub>s</sub></i></b>.</li>
                <li><b>Scheduling-Agnostic:</b> Holds under FIFO, LIFO, Random Choice, and Priority disciplines.</li>
            </ul>

            <h2>V. Current Simulator Values &amp; Verification</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Formula / Method</th><th>Live Simulator Value</th></tr>
                <tr><td>Simulated System Traffic (<i>A</i><sub>sim</sub>)</td><td>Continuous time integral</td><td>{L_sim:.5f} Erlang</td></tr>
                <tr><td>Admitted Arrival Rate (<i>&lambda;</i><sub>s,sim</sub>)</td><td><i>N</i><sub>admitted</sub> / <i>T</i><sub>end</sub></td><td>{lam_eff:.5f} cust/s</td></tr>
                <tr><td>Simulated Sojourn Time (&delta;&#772;<sub>sim</sub>)</td><td>Sample mean over completed customers</td><td>{W_sim:.5f} s</td></tr>
                <tr><td>Little's Law Product (<i>&lambda;</i><sub>s,sim</sub> &middot; &delta;&#772;<sub>sim</sub>)</td><td>Conservation product</td><td>{littles_L:.5f} Erlang</td></tr>
                <tr class="bottom-rule"><td>Conservation Error (|<i>A</i><sub>sim</sub> &minus; <i>&lambda;</i><sub>s,sim</sub>&delta;&#772;<sub>sim</sub>|)</td><td>Absolute discrepancy</td><td>{littles_err:.5f} (Verified)</td></tr>
            </table>
            """
            return title, html

        # ---------------------------------------------------------------
        # Topic 14: Traffic Accounting & Throughput (d(t) / a(t))
        # ---------------------------------------------------------------
        else:
            title = "Metric Theory: Traffic Accounting & Throughput (d(t) / a(t))"
            arr_tot = m_stats.get("arrived", 0)
            served_tot = m_stats.get("served", 0)
            dropped_tot = m_stats.get("dropped", 0)
            in_sys_tot = (engine.total_in_system if engine else max(0, arr_tot - served_tot - dropped_tot))
            t_sim = max(1e-4, m_stats.get("T", 0.0))
            lam_eff = m_stats.get("lambda_s", m_stats.get("lambda_eff", 0.0))
            throughput_sim = served_tot / t_sim if t_sim > 0.01 else 0.0

            eq1 = latex_eq_row(
                r"k(t) = k(0) + a(t) - d(t) = k(0) + a_s(t) - d(t)",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"a(t) = d(t) + k(t) + a_p(t), \qquad \lim_{t\to\infty} \frac{d(t)}{t} = \lambda_s = (1 - \pi_p)\lambda \le m\mu",
                eq_num=2,
                zoom_factor=zoom_factor,
            )

            html = f"""{css}
            <h1>Metric Theory: Traffic Accounting &amp; Throughput (<i>d</i>(<i>t</i>) / <i>a</i>(<i>t</i>))</h1>
            <div class="meta-line">
                <b>Metric Symbol:</b> <i>d</i>(<i>t</i>) / <i>a</i>(<i>t</i>) &nbsp;|&nbsp; <b>Traffic Balance:</b> <i>A</i><sub>0</sub> = <i>A<sub>s</sub></i> + <i>A<sub>p</sub></i> &nbsp;|&nbsp; <b>Customer Balance:</b> <i>k</i>(<i>t</i>) = <i>k</i>(0) + <i>a</i>(<i>t</i>) &minus; <i>d</i>(<i>t</i>)
            </div>

            <h2>I. What is this Metric?</h2>
            <p>
                <b>Departures <i>d</i>(<i>t</i>) / Arrivals <i>a</i>(<i>t</i>)</b> displays customer accounting from the outside of the teletraffic system as a black box:
            </p>
            <ul>
                <li><b>Total Arrivals <i>a</i>(<i>t</i>):</b> The cumulative total number of customers that arrived at the system up to time <i>t</i>.</li>
                <li><b>Departures <i>d</i>(<i>t</i>):</b> The cumulative total number of customers that completed service and left the system up to time <i>t</i>.</li>
                <li><b>Rejected Arrivals <i>a<sub>p</sub></i>(<i>t</i>):</b> The cumulative total number of customers dropped due to buffer capacity being full.</li>
                <li><b>Traffic in System <i>k</i>(<i>t</i>):</b> The instantaneous number of customers inside the system at time <i>t</i>.</li>
            </ul>

            <h2>II. Parameters Involved</h2>
            <ul>
                <li><b><i>a</i>(<i>t</i>):</b> Total arrivals up to time <i>t</i>.</li>
                <li><b><i>d</i>(<i>t</i>):</b> Total departures up to time <i>t</i>.</li>
                <li><b><i>a<sub>p</sub></i>(<i>t</i>):</b> Total rejected arrivals up to time <i>t</i>.</li>
                <li><b><i>k</i>(<i>t</i>):</b> Instantaneous customer count (resource occupancy).</li>
                <li><b><i>A</i><sub>0</sub> = &lambda;&vartheta;&#772;:</b> Offered traffic in Erlangs.</li>
                <li><b><i>A<sub>s</sub></i> = &lambda;<sub>s</sub>&vartheta;&#772; = (1 &minus; &pi;<sub>p</sub>)<i>A</i><sub>0</sub>:</b> Served or carried traffic in Erlangs.</li>
                <li><b><i>A<sub>p</sub></i> = &lambda;<sub>p</sub>&vartheta;&#772; = &pi;<sub>p</sub> <i>A</i><sub>0</sub>:</b> Rejected or lost traffic in Erlangs.</li>
                <li><b><i>&lambda;<sub>s</sub></i>:</b> Rate of customers entering the system (system throughput).</li>
            </ul>

            <h2>III. Mathematical Formulas &amp; Runtime Computation</h2>
            <p>The fundamental equation of traffic in the system relates arrivals, departures, and state:</p>
            {eq1}
            <p>Customer conservation across admitted, waiting, and dropped streams leads to:</p>
            {eq2}

            <h2>IV. Key Properties</h2>
            <ul>
                <li><b>Lossless Systems (<i>K</i> = &infin;, <i>&rho;</i> &lt; 1):</b> No customers are ever rejected (<i>a<sub>p</sub></i> = 0, &pi;<sub>p</sub> = 0), so carried traffic equals offered traffic: <b><i>A<sub>s</sub></i> = <i>A</i><sub>0</sub></b>.</li>
                <li><b>Finite Buffer Loss (<i>K</i> &lt; &infin;):</b> Dropped customers produce lost traffic <b><i>A<sub>p</sub></i> = &pi;<sub>p</sub> <i>A</i><sub>0</sub></b>, leaving carried throughput <b><i>&lambda;<sub>s</sub></i> = (1 &minus; &pi;<sub>p</sub>)&lambda;</b>.</li>
                <li><b>Capacity Bottleneck (<i>m&mu;</i>):</b> The system departure throughput can never exceed total server capacity: <b><i>&lambda;<sub>s</sub></i> &le; <i>m &middot; &mu;</i></b>.</li>
            </ul>

            <h2>V. Current Simulator Values &amp; Flow Accounting</h2>
            <table class="book-table">
                <tr><th>Accounting Item</th><th>Formula / Origin</th><th>Live Simulator Count / Value</th></tr>
                <tr><td>Total Customer Arrivals (<i>a</i>(<i>t</i>))</td><td>Arrival generator counter</td><td>{arr_tot} cust</td></tr>
                <tr><td>Completed &amp; Served (<i>d</i>(<i>t</i>))</td><td>Departure counter</td><td>{served_tot} cust</td></tr>
                <tr><td>Currently in System (<i>k</i>(<i>t</i>))</td><td>Queue backlog + active servers</td><td>{in_sys_tot} cust</td></tr>
                <tr><td>Rejected Drops (<i>a<sub>p</sub></i>(<i>t</i>))</td><td>Buffer overflow discards</td><td>{dropped_tot} cust</td></tr>
                <tr class="bottom-rule"><td>Flow Balance Check (<i>d</i>(<i>t</i>) + <i>k</i>(<i>t</i>) + <i>a<sub>p</sub></i>(<i>t</i>))</td><td>Eq. (2) Conservation</td><td>{served_tot + in_sys_tot + dropped_tot} cust (Matches <i>a</i>(<i>t</i>): {arr_tot})</td></tr>
            </table>
            """
            return title, html


class TheoryDialog(QDialog):
    current_instance = None

    def __init__(
        self,
        dist_index: Optional[int] = None,
        process_type: str = "Arrival",
        engine: Optional[QueueSimEngine] = None,
        rho: Optional[float] = None,
        lam: Optional[float] = None,
        mu: Optional[float] = None,
        m: int = 1,
        c: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        if c is not None:
            m = c
        TheoryDialog.current_instance = self
        self.engine = engine
        self.init_rho = rho
        self.init_lam = lam
        self.init_mu = mu
        self.init_m = m
        self.resize(920, 740)
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")
        self.zoom_steps = 0
        self._pinch_accum = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Header toolbar with topic selector, role selector, zoom buttons and tip
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_topic = QLabel("Topic:")
        lbl_topic.setStyleSheet("font-size: 11px; color: #a6adc8; font-weight: bold;")
        top_bar.addWidget(lbl_topic)

        self.combo_topic = NoWheelComboBox()
        self.combo_topic.addItems([
            "Exponential (M - Poisson)",
            "Deterministic (D - Fixed)",
            "Uniform (U - Bounded Jitter)",
            "Erlang (E₂)",
            "Hyperexponential (H₂ - Bursty)",
            "Pareto (Heavy-Tailed)",
            "System Instability & Ergodicity (ρ ≥ 1.0)",
            "Metric Theory: Server Utilization ρ (Offered Traffic A₀)",
            "Metric Theory: Avg Traffic in System A (k(t))",
            "Metric Theory: Avg Queue Backlog A_c",
            "Metric Theory: Avg Sojourn Time δ̄",
            "Metric Theory: Avg Waiting Time η̄ (and ε̄)",
            "Metric Theory: Blocking Probability π_p",
            "Metric Theory: Little's Law Invariance (A = λ_s δ̄)",
            "Metric Theory: Traffic Accounting & Throughput (d(t) / a(t))",
        ])
        self.combo_topic.setStyleSheet(
            "background-color: #313244; color: #cdd6f4; font-size: 11px; "
            "border: 1px solid #45475a; border-radius: 4px; padding: 2px 6px;"
        )
        top_bar.addWidget(self.combo_topic)

        lbl_role = QLabel("Role:")
        lbl_role.setStyleSheet("font-size: 11px; color: #a6adc8; font-weight: bold;")
        top_bar.addWidget(lbl_role)

        self.combo_role = NoWheelComboBox()
        self.combo_role.addItems(["Arrival Process (Input)", "Service Process (Server)"])
        self.combo_role.setStyleSheet(
            "background-color: #313244; color: #cdd6f4; font-size: 11px; "
            "border: 1px solid #45475a; border-radius: 4px; padding: 2px 6px;"
        )
        if "serv" in process_type.lower():
            self.combo_role.setCurrentIndex(1)
        else:
            self.combo_role.setCurrentIndex(0)
        top_bar.addWidget(self.combo_role)

        top_bar.addSpacing(6)

        lbl_hint = QLabel("Zoom:")
        lbl_hint.setStyleSheet("font-size: 11px; color: #a6adc8; font-weight: bold;")
        top_bar.addWidget(lbl_hint)

        self.btn_zoom_out = QPushButton("Zoom -")
        self.btn_zoom_out.setFixedSize(62, 26)
        self.btn_zoom_out.setToolTip("Zoom Out")
        self.btn_zoom_out.setStyleSheet(DIALOG_ZOOM_BTN_STYLE)
        self.btn_zoom_out.clicked.connect(lambda: self.zoom_out(1))

        self.lbl_zoom_val = QLabel("100%")
        self.lbl_zoom_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #89b4fa; padding: 0 4px;")

        self.btn_zoom_in = QPushButton("Zoom +")
        self.btn_zoom_in.setFixedSize(62, 26)
        self.btn_zoom_in.setToolTip("Zoom In")
        self.btn_zoom_in.setStyleSheet(DIALOG_ZOOM_BTN_STYLE)
        self.btn_zoom_in.clicked.connect(lambda: self.zoom_in(1))

        self.btn_zoom_reset = QPushButton("Reset Zoom")
        self.btn_zoom_reset.setFixedHeight(26)
        self.btn_zoom_reset.setStyleSheet(DIALOG_ZOOM_BTN_STYLE)
        self.btn_zoom_reset.clicked.connect(self.reset_zoom)

        top_bar.addWidget(self.btn_zoom_out)
        top_bar.addWidget(self.lbl_zoom_val)
        top_bar.addWidget(self.btn_zoom_in)
        top_bar.addWidget(self.btn_zoom_reset)
        top_bar.addStretch()

        lbl_tip = QLabel("Tip: Pinch trackpad or Ctrl+Wheel to zoom")
        lbl_tip.setStyleSheet("font-size: 10px; color: #6c7086;")
        top_bar.addWidget(lbl_tip)

        layout.addLayout(top_bar)

        # Clean PDF-viewer style frame hosting the white textbook page
        self.browser = QTextBrowser()
        self.browser.setStyleSheet(
            "QTextBrowser { background-color: #ffffff; color: #111111; "
            "border: 2px solid #45475a; border-radius: 6px; padding: 6px; }"
        )
        self.browser.setFont(QFont("Cambria", 11))
        self.browser.installEventFilter(self)
        self.browser.viewport().installEventFilter(self)
        layout.addWidget(self.browser)

        btn_close = QPushButton("Understood (Return to Simulator)")
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet(
            "background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 6px;"
        )
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

        # Connect topic & role changes
        self.combo_topic.currentIndexChanged.connect(self._on_topic_or_role_changed)
        self.combo_role.currentIndexChanged.connect(self._on_topic_or_role_changed)

        # Set initial topic
        if dist_index is not None and 0 <= dist_index <= 14:
            self.combo_topic.setCurrentIndex(dist_index)
        else:
            self.combo_topic.setCurrentIndex(6)  # Instability
        self._on_topic_or_role_changed()

    @property
    def current_zoom_factor(self) -> float:
        return max(0.6, 1.0 + self.zoom_steps * 0.15)

    def _render_current_page(self, preserve_scroll: bool = False):
        vbar = self.browser.verticalScrollBar()
        scroll_ratio = (vbar.value() / max(1, vbar.maximum())) if (preserve_scroll and vbar.maximum() > 0) else 0.0

        topic_idx = self.combo_topic.currentIndex()
        is_dist = topic_idx < 6
        self.combo_role.setEnabled(is_dist)
        role_str = "Service" if self.combo_role.currentIndex() == 1 else "Arrival"

        title, html = generate_theory_html(
            topic_index=topic_idx,
            role=role_str,
            engine=self.engine,
            rho=self.init_rho,
            lam=self.init_lam,
            mu=self.init_mu,
            m=self.init_m,
            zoom_factor=self.current_zoom_factor,
        )
        self.setWindowTitle(title)
        self.browser.setHtml(html)

        if preserve_scroll and vbar.maximum() > 0:
            vbar.setValue(int(round(scroll_ratio * vbar.maximum())))

    def _on_topic_or_role_changed(self):
        self._render_current_page(preserve_scroll=False)

    def zoom_in(self, steps: int = 1):
        if self.zoom_steps + steps <= 10:
            self.zoom_steps += steps
            pct = int(round(self.current_zoom_factor * 100))
            self.lbl_zoom_val.setText(f"{pct}%")
            self._render_current_page(preserve_scroll=True)

    def zoom_out(self, steps: int = 1):
        if self.zoom_steps - steps >= -3:
            self.zoom_steps -= steps
            pct = int(round(self.current_zoom_factor * 100))
            self.lbl_zoom_val.setText(f"{pct}%")
            self._render_current_page(preserve_scroll=True)

    def reset_zoom(self):
        self.zoom_steps = 0
        self._pinch_accum = 0.0
        self.lbl_zoom_val.setText("100%")
        self._render_current_page(preserve_scroll=True)

    def apply_dialog_zoom(self, delta: float):
        self._pinch_accum += delta
        threshold = 0.02
        if self._pinch_accum >= threshold:
            steps = max(1, int(self._pinch_accum / threshold))
            self.zoom_in(steps)
            self._pinch_accum = 0.0
        elif self._pinch_accum <= -threshold:
            steps = max(1, int(abs(self._pinch_accum) / threshold))
            self.zoom_out(steps)
            self._pinch_accum = 0.0

    def done(self, r):
        TheoryDialog.current_instance = None
        super().done(r)

    def closeEvent(self, event):
        TheoryDialog.current_instance = None
        super().closeEvent(event)

    def reject(self):
        TheoryDialog.current_instance = None
        super().reject()

    def eventFilter(self, obj, event):
        if obj in (self.browser, self.browser.viewport()):
            if event.type() == QEvent.Type.NativeGesture:
                if hasattr(event, "gestureType") and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                    self.apply_dialog_zoom(event.value())
                    return True
            elif event.type() == QEvent.Type.Wheel:
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    if event.angleDelta().y() > 0:
                        self.zoom_in(1)
                    elif event.angleDelta().y() < 0:
                        self.zoom_out(1)
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def event(self, event):
        if event.type() == QEvent.Type.NativeGesture:
            if hasattr(event, "gestureType") and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                self.apply_dialog_zoom(event.value())
                return True
        elif event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if event.angleDelta().y() > 0:
                    self.zoom_in(1)
                elif event.angleDelta().y() < 0:
                    self.zoom_out(1)
                event.accept()
                return True
        return super().event(event)