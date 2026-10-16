"""
Educational textbook-style theory generator and interactive TheoryDialog
with Computer Modern LaTeX formula rendering and synchronized zoom.
Adapted to the teletraffic and queueing theory notation of Alma Mater Studiorum
- Università di Bologna (Prof. slides: 03-Traffic and 05-ErlangFormulas).
"""

import io
import re
import math
import base64
import struct
from functools import lru_cache
from typing import Optional, Tuple, List

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
            transparent=True,
        )
    except ValueError:
        buf = io.BytesIO()
        txt.set_text(clean_latex.replace("\\", ""))
        fig.savefig(
            buf,
            format="png",
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0.04,
            facecolor="white",
            transparent=True,
        )

    png_bytes = buf.getvalue()

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
    <table class="eq-table" width="100%" cellspacing="0" cellpadding="2">
        <tr>
            <td width="6%"></td>
            <td width="88%" align="center" valign="middle">{img_html}</td>
            <td width="6%" align="right" valign="middle" class="eq-num" style="white-space: nowrap;">{num_str}</td>
        </tr>
    </table>
    """


def where_list(items: List[Tuple[str, str]]) -> str:
    """
    Render a formal textbook 'where:' parameter nomenclature block immediately
    following a mathematical equation or group of equations.
    """
    rows = "".join(
        f'<li><b>{sym}</b> &mdash; {desc}</li>' for sym, desc in items
    )
    return f'<p class="where-label">where:</p><ul class="param-list">{rows}</ul>'


def _get_textbook_extra_css(zoom_factor: float = 1.0) -> str:
    """Supplementary textbook CSS rules ensuring clean academic layout."""
    sec_tag_pt = round(7.5 * zoom_factor, 1)
    title_pt = round(11.5 * zoom_factor, 1)
    sec_pt = round(10.0 * zoom_factor, 1)
    sub_pt = round(9.0 * zoom_factor, 1)
    base_pt = round(9.5 * zoom_factor, 1)
    return f"""
    <style>
        .doc-title {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {title_pt}pt;
            font-weight: bold;
            color: #111111;
            text-align: center;
            margin-top: 2px;
            margin-bottom: 4px;
            line-height: 1.25;
            background-color: #ffffff;
        }}
        .sec-title {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {sec_pt}pt;
            font-weight: bold;
            text-align: left;
            color: #111111;
            margin-top: 10px;
            margin-bottom: 4px;
            padding-bottom: 2px;
            page-break-after: avoid;
            break-after: avoid;
            background-color: #ffffff;
        }}
        .subsec-title {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {sub_pt}pt;
            font-weight: bold;
            font-style: italic;
            color: #111111;
            margin-top: 8px;
            margin-bottom: 3px;
            page-break-after: avoid;
            break-after: avoid;
            background-color: #ffffff;
        }}
        .section-tag {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {sec_tag_pt}pt;
            font-weight: bold;
            letter-spacing: 0.6px;
            text-transform: uppercase;
            color: #333333;
            text-align: center;
            margin-top: 2px;
            margin-bottom: 2px;
            background-color: #ffffff;
        }}
        .param-list {{
            margin-top: 4px;
            margin-bottom: 12px;
            padding-left: 22px;
            font-family: 'Cambria', 'Georgia', serif;
            background-color: #ffffff;
        }}
        .param-list li {{
            margin-bottom: 4px;
            line-height: 1.44;
            font-family: 'Cambria', 'Georgia', serif;
            background-color: #ffffff;
        }}
        .def-paragraph {{
            font-family: 'Cambria', 'Georgia', serif;
            font-size: {base_pt}pt;
            text-align: justify;
            margin-top: 4px;
            margin-bottom: 10px;
            background-color: #ffffff;
        }}
    </style>
    """


def _format_theory_html(html: str) -> str:
    """
    Format theory HTML for QTextDocument.
    Replaces <h1>, <h2>, <h3> with styled <div> elements because QTextDocument's
    internal HTML parser hardcodes heading tags (h1 to 18pt, h2 to 13.5pt)
    and ignores CSS font-size rules on heading tags.
    Also fixes HTML entities not supported by Qt's QTextDocument rich text parser.
    """
    entity_fixes = {
        "&approx;": "&#8776;",
        "&frac23;": "&#8532;",
        "&langle;": "&#10216;",
        "&rangle;": "&#10217;",
        "&varepsilon;": "&#949;",
        "&vartheta;": "&#977;",
    }
    res = (
        html.replace("<h1>", '<div class="doc-title">')
        .replace("</h1>", "</div>")
        .replace("<h2>", '<div class="sec-title">')
        .replace("</h2>", "</div>")
        .replace("<h3>", '<div class="subsec-title">')
        .replace("</h3>", "</div>")
    )
    for ent, fixed in entity_fixes.items():
        res = res.replace(ent, fixed)
    return res


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
    Generate university textbook-style queueing theory pages aligned with the
    course notation:
      - Inter-arrival time: tau (mean bar{tau} = 1/lambda, variance sigma_tau^2)
      - Service time: vartheta (mean bar{vartheta} = 1/mu, variance sigma_vartheta^2)
      - Residual service time: zeta (mean bar{zeta})
      - System occupancy at time t: k(t), with time-average traffic A = <k(t)>
      - Queue occupancy: A_c, Served/carried traffic: A_s, Offered traffic: A_0, Lost traffic: A_p
      - Arrival rate: lambda, Admitted rate: lambda_s, Rejected rate: lambda_p
      - Sojourn time: delta (mean bar{delta}), Waiting time: eta (mean bar{eta}),
        Waiting time of queued customers: varepsilon (mean bar{varepsilon})
      - Blocking probability: pi_p (Erlang-B: B(m, A_0)), Congestion probability: pi_r (Erlang-C: C(m, A_0))
    """
    topics = [
        ("Exponential Distribution (Kendall: M)", "M"),
        ("Deterministic Distribution (Kendall: D)", "D"),
        ("Uniform Distribution (Kendall: U)", "U"),
        ("Erlang Distribution (Kendall: E_r)", "E_k"),
        ("Hyperexponential Distribution (Kendall: H_2)", "H_2"),
        ("Pareto Distribution (Kendall: Heavy-Tailed)", "Pareto"),
        ("Stochastic Stability Theory & Ergodicity", "Instability"),
        ("Metric Theory: Server Utilization ρ & Traffic Intensity", "rho"),
        ("Metric Theory: Average Traffic in the System A (L)", "L"),
        ("Metric Theory: Average Customers in Queue A_c (Lq)", "Lq"),
        ("Metric Theory: Average Sojourn Time δ̄ (W)", "W"),
        ("Metric Theory: Average Waiting Time η̄ (Wq)", "Wq"),
        ("Metric Theory: Blocking Probability π_p (P_loss)", "P_loss"),
        ("Metric Theory: Little's Law A = λ_s δ̄ (L_diff)", "Littles"),
        ("Metric Theory: Customer Flow Balance & Carried Traffic (Served / Arrived)", "Served / Arrived"),
    ]

    if not (0 <= topic_index < len(topics)):
        topic_index = 0

    title, _ = topics[topic_index]
    is_arrival = "arr" in role.lower()

    # Course notation for Arrival (tau, lambda) vs Service (vartheta, mu)
    rv_tex = r"\tau" if is_arrival else r"\vartheta"
    rv_html = "<i>&tau;</i>" if is_arrival else "<i>&vartheta;</i>"
    rv_bar_tex = r"\overline{\tau}" if is_arrival else r"\overline{\vartheta}"
    rv_bar_html = "<i>&tau;&#772;</i>" if is_arrival else "<i>&vartheta;&#772;</i>"
    rv_var_tex = r"\sigma_{\tau}^2" if is_arrival else r"\sigma_{\vartheta}^2"
    rv_var_html = "<i>&sigma;<sub>&tau;</sub></i><sup>2</sup>" if is_arrival else "<i>&sigma;<sub>&vartheta;</sub></i><sup>2</sup>"
    rate_tex = r"\lambda" if is_arrival else r"\mu"
    rate_html = "<i>&lambda;</i>" if is_arrival else "<i>&mu;</i>"

    role_label = (
        "Arrival Process (Inter-arrival Time &tau;)"
        if is_arrival
        else "Service Process (Service Time &vartheta;)"
    )
    rv_desc = (
        "the inter-arrival time between two consecutive customer arrivals"
        if is_arrival
        else "the service time required by a server to provision service to a generic customer"
    )
    rate_desc = (
        "the average customer arrival rate"
        if is_arrival
        else "the average per-server service rate"
    )

    css = get_theory_html_css(zoom_factor) + _get_textbook_extra_css(zoom_factor)

    # Extract system-wide rates from engine if available
    active_arr_list = (
        [d for d in engine.arrival_dists.values() if d is not None]
        if (engine is not None and hasattr(engine, "arrival_dists") and engine.arrival_dists)
        else []
    )
    sys_lam = (
        lam
        if (lam is not None and lam > 0)
        else (
            sum(1.0 / max(1e-6, d.mean()) for d in active_arr_list)
            if active_arr_list
            else 0.80
        )
    )
    sys_mu = (
        mu
        if (mu is not None and mu > 0)
        else (
            1.0 / max(1e-6, engine.service_dist.mean())
            if (engine is not None and getattr(engine, "service_dist", None) is not None)
            else 1.00
        )
    )
    sys_c = m if (m is not None and m >= 1) else (engine.c if engine is not None else 1)

    curr_d = None
    if engine is not None:
        if is_arrival:
            if not getattr(engine, "priority_enabled", False):
                curr_d = getattr(engine, "arrival_dists", {}).get(-1)
        else:
            curr_d = getattr(engine, "service_dist", None)

    # ===================================================================
    # Topic 0: Exponential Distribution (M)
    # ===================================================================
    if topic_index == 0:
        rate = 0.80 if is_arrival else 1.00
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "ExponentialDist":
            rate = getattr(curr_d, "rate", rate)
            is_live = True

        mean_v = 1.0 / max(1e-6, rate)
        var_v = 1.0 / (rate * rate)
        ex2_v = 2.0 / (rate * rate)
        src_note = (
            f"Active Simulation Configuration ({role_label})"
            if is_live
            else f"Reference Benchmark Configuration ({role_label})"
        )

        eq1 = latex_eq_row(
            r"P(k, T) = \frac{(\lambda T)^k}{k!}\,e^{-\lambda T}, \qquad \overline{k} = \lambda T, \qquad \mathrm{var}(k) = \lambda T \quad (k = 0, 1, 2, \dots)",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"f_{{{rv_tex}}}(t) = {rate_tex}\,e^{{-{rate_tex} t}}, \qquad F_{{{rv_tex}}}(t) = 1 - e^{{-{rate_tex} t}} \quad (t \geq 0), \qquad {rv_bar_tex} = \frac{{1}}{{{rate_tex}}}, \qquad {rv_var_tex} = \frac{{1}}{{{rate_tex}^2}}",
            eq_num=2,
            zoom_factor=zoom_factor,
        )
        eq3 = latex_eq_row(
            r"f_{\zeta}(t) = \frac{1 - F_{\vartheta}(t)}{\overline{\vartheta}} = \frac{e^{-\mu t}}{1/\mu} = \mu\,e^{-\mu t} = f_{\vartheta}(t) \quad (t \geq 0), \qquad \overline{\zeta} = \frac{\mathrm{E}[\vartheta^2]}{2\overline{\vartheta}} = \frac{\sigma_{\vartheta}^2 + \overline{\vartheta}^2}{2\overline{\vartheta}} = \overline{\vartheta}",
            eq_num=3,
            zoom_factor=zoom_factor,
        )

        params_eq1_eq2 = where_list([
            ("<i>P</i>(<i>k</i>, <i>T</i>)", "Poisson's formula giving the probability of observing exactly <i>k</i> arrivals within an observation interval of duration <i>T</i> (s)."),
            ("<i>k&#772;</i>, var(<i>k</i>)", "Average value and variance of the number of arrivals <i>k</i> within interval <i>T</i>, both equal to <i>&lambda;T</i>."),
            (f"{rv_html} &ge; 0", f"Continuous random variable denoting {rv_desc}, measured in seconds (s)."),
            ("<i>t</i> &ge; 0", "Time argument at which the probability density or cumulative distribution function is evaluated, in seconds (s) (for <i>t</i> &lt; 0, both functions are 0)."),
            (f"{rate_html} &gt; 0", f"Rate parameter representing {rate_desc}, measured in customers per second (cust/s)."),
            (f"<i>f<sub>{rv_html}</sub></i>(<i>t</i>), <i>F<sub>{rv_html}</sub></i>(<i>t</i>)", f"Probability density function (in s<sup>&minus;1</sup>) and cumulative distribution function of {rv_html}."),
            (f"{rv_bar_html} = E[{rv_html}] = 1 / {rate_html}", f"Average value (mean) of {rv_html}, measured in seconds (s)."),
            (f"{rv_var_html} = Var[{rv_html}] = 1 / {rate_html}<sup>2</sup>", f"Variance of {rv_html}, measured in seconds squared (s<sup>2</sup>); the squared coefficient of variation is <i>C<sub>v</sub></i><sup>2</sup> = {rv_var_html} / {rv_bar_html}<sup>2</sup> = 1."),
        ])

        params_eq3 = where_list([
            ("<i>&zeta;</i> &ge; 0", "Residual service time (or residual inter-arrival time), defined as the remaining time until completion when observing a busy server starting from a randomly chosen instant <i>t</i><sub>1</sub>, in seconds (s)."),
            ("<i>f<sub>&zeta;</sub></i>(<i>t</i>)", "Probability density function of the residual service time <i>&zeta;</i>, in inverse seconds (s<sup>&minus;1</sup>)."),
            ("<i>&zeta;&#772;</i> = E[<i>&zeta;</i>]", "Mean residual service time, equal to (<i>&sigma;<sub>&vartheta;</sub></i><sup>2</sup> + <i>&vartheta;&#772;</i><sup>2</sup>) / (2<i>&vartheta;&#772;</i>), in seconds (s)."),
        ])

        t_short = round(0.5 * mean_v, 2)
        t_long = round(2.0 * mean_v, 2)
        p_short = 1.0 - math.exp(-rate * t_short)
        p_long = math.exp(-rate * t_long)

        html = f"""{css}
        <h1>The Exponential Distribution and Poisson Process (Kendall Notation: <i>&#8499;</i>)</h1>
        <div class="meta-line">{src_note}</div>

        <h2>1. Definition and Physical Interpretation</h2>
        <p class="def-paragraph">
            <b>Definition.</b> In Kendall's notation (<i>&#8497;</i>/<i>&#8492;</i>/<i>m</i>/<i>n</i>/<i>p</i>/<i>&#8499;</i>),
            the symbol <b><i>&#8499;</i></b> denotes a <i>memoryless random process</i>. For the arrival process, it corresponds
            to a <b>Poisson process</b> (non-simultaneous random arrivals from a very large population of independent customers)
            characterized by independent and identically distributed (i.i.d.) negative exponential inter-arrival times
            <i>&tau;</i> with rate <i>&lambda;</i> &gt; 0. For the service process, it corresponds to i.i.d. negative exponential
            service times <i>&vartheta;</i> with rate <i>&mu;</i> = 1/<i>&vartheta;&#772;</i> &gt; 0.
        </p>

        <h2>2. Mathematical Formulation</h2>
        <p>
            <b>Poisson Arrival Counting Process.</b> The probability <i>P</i>(<i>k</i>, <i>T</i>) of observing <i>k</i> arrivals
            within an interval of duration <i>T</i> is given by Poisson's formula:
        </p>
        {eq1}
        <p>
            <b>Exponential Inter-arrival / Service Time Distribution.</b> The continuous random variable {rv_html} has probability
            density function <i>f<sub>{rv_html}</sub></i>(<i>t</i>), cumulative distribution function <i>F<sub>{rv_html}</sub></i>(<i>t</i>)
            (for <i>t</i> &ge; 0, and 0 for <i>t</i> &lt; 0), mean {rv_bar_html}, and variance {rv_var_html}:
        </p>
        {eq2}
        {params_eq1_eq2}

        <h2>3. Residual Time and the Memoryless Property</h2>
        <p>
            Let <i>&zeta;</i> denote the <b>residual service time</b>, defined as the remaining service duration still to be
            completed when observing a busy server at a randomly chosen instant <i>t</i><sub>1</sub>. For a general distribution
            <i>F<sub>&vartheta;</sub></i>(<i>t</i>), the density and mean of <i>&zeta;</i> are given by renewal theory, and for an
            exponential random variable <i>&vartheta;</i> they reduce to the exact same exponential law:
        </p>
        {eq3}
        {params_eq3}
        <ul>
            <li><b>Memoryless Property:</b> Because <i>f<sub>&zeta;</sub></i>(<i>t</i>) = <i>f<sub>&vartheta;</sub></i>(<i>t</i>) and <i>&zeta;&#772;</i> = <i>&vartheta;&#772;</i> = 1/<i>&mu;</i>, the remaining time to complete an ongoing service (or until the next arrival) has the exact same distribution as a freshly started interval, independent of how much time has already elapsed.</li>
            <li><b>Composition and Decomposition of Poisson Processes:</b> Merging <i>N</i> independent Poisson processes with rates <i>&lambda;</i><sub>1</sub>, &hellip;, <i>&lambda;<sub>N</sub></i> yields a Poisson process with rate <i>&lambda;</i> = &sum;<sub><i>i</i>=1</sub><sup><i>N</i></sup> <i>&lambda;<sub>i</sub></i>. Conversely, randomly splitting a Poisson process of rate <i>&lambda;</i> with probabilities <i>P<sub>i</sub></i> (&sum; <i>P<sub>i</sub></i> = 1) produces independent Poisson processes of rates <i>&lambda;<sub>i</sub></i> = <i>P<sub>i</sub>&lambda;</i>.</li>
        </ul>

        <h2>4. Worked Numerical Example</h2>
        <div class="example-box">
            <p class="example-title">Example 1 ({'Evaluation with Active Simulation Parameters' if is_live else 'Illustrative Calculation with Reference Parameters'}: {rate_html} = {rate:.2f} cust/s)</p>
            <p>
                Consider {rv_desc} modeled by an exponential random variable {rv_html} with parameter {rate_html} = <b>{rate:.2f} cust/s</b>:
            </p>
            <ol>
                <li><b>Mean, Variance, and Residual Mean (Eqs. 2&ndash;3):</b>
                    <br>{rv_bar_html} = 1 / {rate_html} = 1 / {rate:.2f} = <b>{mean_v:.4f} s</b>, &nbsp;&nbsp;
                    {rv_var_html} = 1 / ({rate:.2f})<sup>2</sup> = <b>{var_v:.4f} s<sup>2</sup></b>, &nbsp;&nbsp;
                    E[{rv_html}<sup>2</sup>] = {rv_var_html} + {rv_bar_html}<sup>2</sup> = <b>{ex2_v:.4f} s<sup>2</sup></b>.
                    <br>By Eq. (3), the mean residual duration at a random observation instant is <i>&zeta;&#772;</i> = {ex2_v:.4f} / (2 &times; {mean_v:.4f}) = <b>{mean_v:.4f} s</b> = {rv_bar_html}.</li>
                <li><b>Cumulative Probability (Eq. 2):</b> The probability that {rv_html} does not exceed <i>t</i> = {t_short:.2f} s is:
                    <br><i>F<sub>{rv_html}</sub></i>({t_short:.2f}) = 1 &minus; <i>e</i><sup>&minus;{rate:.2f} &times; {t_short:.2f}</sup> = <b>{p_short:.4f}</b> ({p_short*100:.2f}%).</li>
                <li><b>Complementary Survival Probability (Eq. 2):</b> The probability that {rv_html} exceeds <i>t</i> = {t_long:.2f} s is:
                    <br>1 &minus; <i>F<sub>{rv_html}</sub></i>({t_long:.2f}) = <i>e</i><sup>&minus;{rate:.2f} &times; {t_long:.2f}</sup> = <b>{p_long:.4f}</b> ({p_long*100:.2f}%).</li>
            </ol>
        </div>

        <h2>5. Summary of Parameters and Moments</h2>
        <table class="book-table">
            <tr><th>Quantity</th><th>Course Symbol</th><th>Analytical Formula</th><th>Evaluated Value</th></tr>
            <tr><td>Rate Parameter</td><td>{rate_html}</td><td>1 / {rv_bar_html}</td><td>{rate:.4f} cust/s</td></tr>
            <tr><td>Mean Value</td><td>{rv_bar_html}</td><td>1 / {rate_html}</td><td>{mean_v:.4f} s</td></tr>
            <tr><td>Variance</td><td>{rv_var_html}</td><td>1 / {rate_html}<sup>2</sup></td><td>{var_v:.4f} s<sup>2</sup></td></tr>
            <tr><td>Mean Residual Duration</td><td><i>&zeta;&#772;</i></td><td>({rv_var_html} + {rv_bar_html}<sup>2</sup>) / (2{rv_bar_html})</td><td>{mean_v:.4f} s</td></tr>
            <tr class="bottom-rule"><td>Squared Coeff. of Variation</td><td><i>C<sub>v</sub></i><sup>2</sup></td><td>{rv_var_html} / {rv_bar_html}<sup>2</sup></td><td>1.0000</td></tr>
        </table>
        """
        return title, _format_theory_html(html)

    # ===================================================================
    # Topic 1: Deterministic Distribution (D)
    # ===================================================================
    elif topic_index == 1:
        d_val = 1.25 if is_arrival else 1.00
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "DeterministicDist":
            d_val = getattr(curr_d, "val", d_val)
            is_live = True

        rate_eq = 1.0 / max(1e-6, d_val)
        ex2_v = d_val * d_val
        zeta_bar = d_val / 2.0
        param_0_tex = r"\tau_0" if is_arrival else r"\vartheta_0"
        param_0_html = "<i>&tau;</i><sub>0</sub>" if is_arrival else "<i>&vartheta;</i><sub>0</sub>"

        src_note = (
            f"Active Simulation Configuration ({role_label})"
            if is_live
            else f"Reference Benchmark Configuration ({role_label})"
        )

        eq1 = latex_eq_row(
            rf"f_{{{rv_tex}}}(t) = \delta(t - {param_0_tex}), \qquad F_{{{rv_tex}}}(t) = 0 \;\; (t < {param_0_tex}), \qquad F_{{{rv_tex}}}(t) = 1 \;\; (t \geq {param_0_tex})",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"{rv_bar_tex} = {param_0_tex} = \frac{{1}}{{{rate_tex}}}, \qquad {rv_var_tex} = 0, \qquad \mathrm{{E}}[{rv_tex}^2] = {param_0_tex}^2, \qquad \overline{{\zeta}} = \frac{{\sigma_{{{rv_tex}}}^2 + {rv_bar_tex}^2}}{{2{rv_bar_tex}}} = \frac{{{param_0_tex}}}{{2}}",
            eq_num=2,
            zoom_factor=zoom_factor,
        )
        eq3 = latex_eq_row(
            r"\overline{\eta}^{(M/D/1)} = \frac{\lambda\,\overline{\vartheta}^2}{2(1 - \rho)} = \overline{\vartheta}\,\frac{\rho}{2(1 - \rho)} = \frac{1}{2}\,\overline{\eta}^{(M/M/1)} \quad (\rho = \lambda\overline{\vartheta} < 1)",
            eq_num=3,
            zoom_factor=zoom_factor,
        )

        params_eq1_eq2 = where_list([
            (f"{rv_html}", f"Random variable representing {rv_desc}, which is always equal to the constant {param_0_html}, in seconds (s)."),
            (f"{param_0_html} &gt; 0", "Fixed deterministic duration of every customer service or inter-arrival interval (labeled <i>D</i> in the simulator sidebar), in seconds (s)."),
            (f"<i>&delta;</i>(<i>t</i> &minus; {param_0_html})", f"Dirac delta function centered at <i>t</i> = {param_0_html}, in inverse seconds (s<sup>&minus;1</sup>)."),
            (f"<i>F<sub>{rv_html}</sub></i>(<i>t</i>)", f"Cumulative distribution function, which steps from 0 (for <i>t</i> &lt; {param_0_html}) to 1 (for <i>t</i> &ge; {param_0_html})."),
            (f"{rv_bar_html} = {param_0_html}, {rv_var_html} = 0", f"Mean value (in s) and variance (0 s<sup>2</sup>) of {rv_html}."),
            (f"{rate_html} = 1 / {rv_bar_html}", f"Average rate ({rate_desc}), measured in customers per second (cust/s)."),
            (f"<i>&zeta;&#772;</i> = {param_0_html} / 2", "Mean residual duration when observing the deterministic process at a random instant, equal to exactly half of the constant interval."),
        ])

        params_eq3 = where_list([
            ("<i>&lambda;</i>", "Average arrival rate of the Poisson arrival process, in customers per second (cust/s)."),
            ("<i>&vartheta;&#772;</i> = <i>&vartheta;</i><sub>0</sub> = 1 / <i>&mu;</i>", "Constant service time of each customer, in seconds (s)."),
            ("<i>&rho;</i> = <i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i>", "Server utilization (equal to offered traffic in Erlangs for a single-server lossless queue, 0 &le; <i>&rho;</i> &lt; 1)."),
            ("<i>&eta;&#772;</i><sup>(<i>M</i>/<i>D</i>/1)</sup>, <i>&eta;&#772;</i><sup>(<i>M</i>/<i>M</i>/1)</sup>", "Average waiting time in the queue (labeled <i>W<sub>q</sub></i> in the simulator) for deterministic vs. exponential service times, in seconds (s)."),
        ])

        ex_lam = sys_lam if (sys_lam * d_val < 0.98) else round(0.80 / d_val, 2)
        ex_rho = ex_lam * d_val
        eta_mm1 = d_val * ex_rho / max(1e-6, 1.0 - ex_rho)
        eta_md1 = 0.5 * eta_mm1

        html = f"""{css}
        <h1>The Deterministic Distribution (Kendall Notation: <i>&#119967;</i>)</h1>
        <div class="meta-line">{src_note}</div>

        <h2>1. Definition and Physical Interpretation</h2>
        <p class="def-paragraph">
            <b>Definition.</b> In Kendall's notation, the symbol <b><i>&#119967;</i></b> represents a <i>deterministic process</i>
            in which the random variable {rv_html} is always equal to a positive constant {param_0_html} &gt; 0 with probability 1,
            so that its variance is identically zero ({rv_var_html} = 0).
        </p>
        <p>
            <b>Physical Interpretation.</b> A deterministic service process models systems where every customer requests the exact
            same service duration <i>&vartheta;</i> = <i>&vartheta;</i><sub>0</sub> (such as fixed-length packet transmission over a
            constant-bit-rate link or synchronous time-slotted switching). A deterministic arrival process models strictly periodic
            arrivals separated by constant inter-arrival time <i>&tau;</i> = <i>&tau;</i><sub>0</sub>.
        </p>

        <h2>2. Mathematical Formulation</h2>
        <p>
            The probability density function (expressed via the Dirac delta impulse) and cumulative distribution function of {rv_html} are:
        </p>
        {eq1}
        <p>
            The mean value, variance, second moment, and mean residual time <i>&zeta;&#772;</i> are:
        </p>
        {eq2}
        {params_eq1_eq2}

        <h2>3. Theoretical Properties and Queueing Analysis</h2>
        <p>
            <b>Residual Service Time and Waiting Time Reduction.</b> From Eq. (2), because <i>&sigma;<sub>&vartheta;</sub></i><sup>2</sup> = 0,
            the mean residual service time of a busy deterministic server observed at a random instant is
            <i>&zeta;&#772;</i> = <i>&vartheta;</i><sub>0</sub>/2 (half that of an exponential server of the same mean <i>&vartheta;&#772;</i> = <i>&vartheta;</i><sub>0</sub>,
            where <i>&zeta;&#772;</i> = <i>&vartheta;&#772;</i>). Consequently, in an <i>&#8499;</i>/<i>&#119967;</i>/1 queue, the average waiting time
            <i>&eta;&#772;</i> is exactly half that of an <i>&#8499;</i>/<i>&#8499;</i>/1 queue:
        </p>
        {eq3}
        {params_eq3}

        <h2>4. Worked Numerical Example</h2>
        <div class="example-box">
            <p class="example-title">Example 1 ({'Evaluation with Active Simulation Parameters' if is_live else 'Illustrative Calculation with Reference Parameters'}: {param_0_html} = {d_val:.2f} s)</p>
            <p>
                Let {rv_html} be deterministic with constant value {param_0_html} = <b>{d_val:.2f} s</b>, and consider a single-server queue with Poisson arrival rate <i>&lambda;</i> = <b>{ex_lam:.2f} cust/s</b>:
            </p>
            <ol>
                <li><b>Moments and Mean Residual Time (Eq. 2):</b>
                    <br>{rv_bar_html} = {param_0_html} = <b>{d_val:.4f} s</b>, &nbsp;&nbsp;
                    {rate_html} = 1 / {rv_bar_html} = <b>{rate_eq:.4f} cust/s</b>, &nbsp;&nbsp;
                    {rv_var_html} = <b>0.0000 s<sup>2</sup></b>, &nbsp;&nbsp;
                    <i>&zeta;&#772;</i> = {param_0_html} / 2 = {d_val:.2f} / 2 = <b>{zeta_bar:.4f} s</b>.</li>
                <li><b>Average Waiting Time Comparison (Eq. 3):</b> With utilization <i>&rho;</i> = <i>&lambda;&vartheta;&#772;</i> = {ex_lam:.2f} &times; {d_val:.2f} = <b>{ex_rho:.4f}</b>:
                    <br>&bull; In an <i>&#8499;</i>/<i>&#8499;</i>/1 system: <i>&eta;&#772;</i><sup>(<i>M</i>/<i>M</i>/1)</sup> = <i>&vartheta;&#772;</i> &middot; <i>&rho;</i> / (1 &minus; <i>&rho;</i>) = {d_val:.2f} &times; {ex_rho:.4f} / (1 &minus; {ex_rho:.4f}) = <b>{eta_mm1:.4f} s</b>.
                    <br>&bull; In an <i>&#8499;</i>/<i>&#119967;</i>/1 system: <i>&eta;&#772;</i><sup>(<i>M</i>/<i>D</i>/1)</sup> = &frac12; <i>&eta;&#772;</i><sup>(<i>M</i>/<i>M</i>/1)</sup> = <b>{eta_md1:.4f} s</b>.</li>
            </ol>
        </div>

        <h2>5. Summary of Parameters and Moments</h2>
        <table class="book-table">
            <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Analytical Formula</th><th>Evaluated Value</th></tr>
            <tr><td>Constant Duration</td><td>{param_0_html} (<i>D</i>)</td><td>Configured parameter</td><td>{d_val:.4f} s</td></tr>
            <tr><td>Average Rate</td><td>{rate_html}</td><td>1 / {rv_bar_html}</td><td>{rate_eq:.4f} cust/s</td></tr>
            <tr><td>Mean Value</td><td>{rv_bar_html}</td><td>{param_0_html}</td><td>{d_val:.4f} s</td></tr>
            <tr><td>Variance</td><td>{rv_var_html}</td><td>0</td><td>0.0000 s<sup>2</sup></td></tr>
            <tr class="bottom-rule"><td>Mean Residual Duration</td><td><i>&zeta;&#772;</i></td><td>{param_0_html} / 2</td><td>{zeta_bar:.4f} s</td></tr>
        </table>
        """
        return title, _format_theory_html(html)

    # ===================================================================
    # Topic 2: Continuous Uniform Distribution (U)
    # ===================================================================
    elif topic_index == 2:
        a_val = 0.50
        b_val = 1.50
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "UniformDist":
            a_val = getattr(curr_d, "a", a_val)
            b_val = getattr(curr_d, "b", b_val)
            is_live = True

        mean_v = (a_val + b_val) / 2.0
        rate_eq = 1.0 / max(1e-6, mean_v)
        var_v = ((b_val - a_val) ** 2) / 12.0
        ex2_v = var_v + mean_v * mean_v
        zeta_bar = ex2_v / max(1e-6, 2.0 * mean_v)
        cv2 = var_v / max(1e-12, mean_v * mean_v)

        min_tex = r"\tau_m" if is_arrival else r"\vartheta_m"
        max_tex = r"\tau_M" if is_arrival else r"\vartheta_M"
        min_html = "<i>&tau;<sub>m</sub></i>" if is_arrival else "<i>&vartheta;<sub>m</sub></i>"
        max_html = "<i>&tau;<sub>M</sub></i>" if is_arrival else "<i>&vartheta;<sub>M</sub></i>"

        src_note = (
            f"Active Simulation Configuration ({role_label})"
            if is_live
            else f"Reference Benchmark Configuration ({role_label})"
        )

        eq1 = latex_eq_row(
            rf"f_{{{rv_tex}}}(t) = \frac{{1}}{{{max_tex} - {min_tex}}}, \qquad F_{{{rv_tex}}}(t) = \frac{{t - {min_tex}}}{{{max_tex} - {min_tex}}} \quad ({min_tex} \leq t \leq {max_tex})",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"{rv_bar_tex} = \frac{{{max_tex} + {min_tex}}}{{2}}, \qquad {rv_var_tex} = \frac{{({max_tex} - {min_tex})^2}}{{12}}, \qquad \overline{{\zeta}} = \frac{{{rv_var_tex} + {rv_bar_tex}^2}}{{2{rv_bar_tex}}}",
            eq_num=2,
            zoom_factor=zoom_factor,
        )

        params_eq1_eq2 = where_list([
            (f"{rv_html}", f"Continuous random variable representing {rv_desc}, bounded within [{min_html}, {max_html}], in seconds (s)."),
            (f"{min_html} &ge; 0", "Minimum bound of the uniform interval (labeled <i>a</i> in the simulator sidebar), in seconds (s)."),
            (f"{max_html} &gt; {min_html}", "Maximum bound of the uniform interval (labeled <i>b</i> in the simulator sidebar), in seconds (s)."),
            (f"<i>f<sub>{rv_html}</sub></i>(<i>t</i>)", f"Probability density function, equal to 1/({max_html} &minus; {min_html}) for {min_html} &le; <i>t</i> &le; {max_html} and 0 elsewhere, in inverse seconds (s<sup>&minus;1</sup>)."),
            (f"<i>F<sub>{rv_html}</sub></i>(<i>t</i>)", f"Cumulative distribution function, equal to 0 for <i>t</i> &lt; {min_html}, (<i>t</i> &minus; {min_html})/({max_html} &minus; {min_html}) for {min_html} &le; <i>t</i> &le; {max_html}, and 1 for <i>t</i> &gt; {max_html}."),
            (f"{rv_bar_html}, {rv_var_html}", f"Average value (in s) and variance (in s<sup>2</sup>) of {rv_html}."),
            ("<i>&zeta;&#772;</i>", "Mean residual duration when observing the process at a random time instant, in seconds (s)."),
        ])

        html = f"""{css}
        <h1>The Uniform Distribution (Kendall Notation: <i>&#119984;</i>)</h1>
        <div class="meta-line">{src_note}</div>

        <h2>1. Definition and Physical Interpretation</h2>
        <p class="def-paragraph">
            <b>Definition.</b> In Kendall's notation, the symbol <b><i>&#119984;</i></b> denotes a random process whose inter-arrival
            or service times {rv_html} follow a continuous <i>Uniform distribution</i> over a bounded interval
            {min_html} &le; {rv_html} &le; {max_html} (with 0 &le; {min_html} &lt; {max_html}).
        </p>
        <p>
            <b>Physical Interpretation.</b> A uniform process models durations that vary with constant probability density between a
            strictly guaranteed minimum threshold {min_html} and a worst-case upper bound {max_html}. In communication networks,
            this characterizes protocol timers randomized uniformly over a contention window or variable packet sizes bounded by
            minimum and maximum frame lengths.
        </p>

        <h2>2. Mathematical Formulation</h2>
        <p>
            For {min_html} &le; <i>t</i> &le; {max_html}, the probability density function and cumulative distribution function are:
        </p>
        {eq1}
        <p>
            The mean value {rv_bar_html}, variance {rv_var_html}, and mean residual time <i>&zeta;&#772;</i> are given by:
        </p>
        {eq2}
        {params_eq1_eq2}

        <h2>3. Theoretical Properties and Queueing Analysis</h2>
        <ul>
            <li><b>Bounded Dispersion (<i>C<sub>v</sub></i><sup>2</sup> &le; 1/3):</b> Because 0 &le; {min_html} &lt; {max_html}, the ratio {rv_var_html} / {rv_bar_html}<sup>2</sup> = ({max_html} &minus; {min_html})<sup>2</sup> / [3({max_html} + {min_html})<sup>2</sup>] never exceeds 1/3 &approx; 0.3333.</li>
            <li><b>Reduced Residual Service Time:</b> Because {rv_var_html} &le; {rv_bar_html}<sup>2</sup>/3, the mean residual service time <i>&zeta;&#772;</i> = ({rv_var_html} + {rv_bar_html}<sup>2</sup>)/(2{rv_bar_html}) satisfies &frac12;{rv_bar_html} &le; <i>&zeta;&#772;</i> &le; &frac23;{rv_bar_html}, which is strictly smaller than that of an exponential server (<i>&zeta;&#772;</i> = {rv_bar_html}).</li>
        </ul>

        <h2>4. Worked Numerical Example</h2>
        <div class="example-box">
            <p class="example-title">Example 1 ({'Evaluation with Active Simulation Parameters' if is_live else 'Illustrative Calculation with Reference Parameters'}: {min_html} = {a_val:.2f} s, {max_html} = {b_val:.2f} s)</p>
            <p>
                Consider a uniform random variable {rv_html} supported on [{min_html}, {max_html}] = [<b>{a_val:.2f} s</b>, <b>{b_val:.2f} s</b>]:
            </p>
            <ol>
                <li><b>Mean Value and Average Rate (Eq. 2):</b>
                    <br>{rv_bar_html} = ({b_val:.2f} + {a_val:.2f}) / 2 = <b>{mean_v:.4f} s</b>, &nbsp;&nbsp;
                    {rate_html} = 1 / {rv_bar_html} = <b>{rate_eq:.4f} cust/s</b>.</li>
                <li><b>Variance and Second Moment (Eq. 2):</b>
                    <br>{rv_var_html} = ({b_val:.2f} &minus; {a_val:.2f})<sup>2</sup> / 12 = ({b_val - a_val:.2f})<sup>2</sup> / 12 = <b>{var_v:.4f} s<sup>2</sup></b>,
                    <br>E[{rv_html}<sup>2</sup>] = {rv_var_html} + {rv_bar_html}<sup>2</sup> = {var_v:.4f} + ({mean_v:.4f})<sup>2</sup> = <b>{ex2_v:.4f} s<sup>2</sup></b>.</li>
                <li><b>Mean Residual Duration (Eq. 2):</b>
                    <br><i>&zeta;&#772;</i> = ({var_v:.4f} + {mean_v*mean_v:.4f}) / (2 &times; {mean_v:.4f}) = {ex2_v:.4f} / {2.0*mean_v:.4f} = <b>{zeta_bar:.4f} s</b>.</li>
            </ol>
        </div>

        <h2>5. Summary of Parameters and Moments</h2>
        <table class="book-table">
            <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Analytical Formula</th><th>Evaluated Value</th></tr>
            <tr><td>Interval Bounds</td><td>[{min_html}, {max_html}] ([<i>a</i>, <i>b</i>])</td><td>Configured bounds</td><td>[{a_val:.2f} s, {b_val:.2f} s]</td></tr>
            <tr><td>Mean Value</td><td>{rv_bar_html}</td><td>({max_html} + {min_html}) / 2</td><td>{mean_v:.4f} s</td></tr>
            <tr><td>Average Rate</td><td>{rate_html}</td><td>1 / {rv_bar_html}</td><td>{rate_eq:.4f} cust/s</td></tr>
            <tr><td>Variance</td><td>{rv_var_html}</td><td>({max_html} &minus; {min_html})<sup>2</sup> / 12</td><td>{var_v:.4f} s<sup>2</sup></td></tr>
            <tr class="bottom-rule"><td>Mean Residual Duration</td><td><i>&zeta;&#772;</i></td><td>({rv_var_html} + {rv_bar_html}<sup>2</sup>) / (2{rv_bar_html})</td><td>{zeta_bar:.4f} s</td></tr>
        </table>
        """
        return title, _format_theory_html(html)

    # ===================================================================
    # Topic 3: Erlang Distribution (E_r)
    # ===================================================================
    elif topic_index == 3:
        r_stages = 2
        rate_val = 0.80 if is_arrival else 1.00
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "ErlangDist":
            r_stages = getattr(curr_d, "k", r_stages)
            mean_raw = getattr(curr_d, "mean_val", 1.0 / rate_val)
            rate_val = 1.0 / max(1e-6, mean_raw)
            is_live = True

        mean_v = 1.0 / max(1e-6, rate_val)
        stage_mean_0 = mean_v / r_stages
        stage_rate = r_stages * rate_val
        var_v = r_stages * (stage_mean_0 ** 2)
        ex2_v = var_v + mean_v * mean_v
        zeta_bar = ex2_v / max(1e-6, 2.0 * mean_v)
        cv2 = 1.0 / r_stages

        sub_i_tex = r"\tau_i" if is_arrival else r"\vartheta_i"
        sub_0_tex = r"\overline{\tau}_0" if is_arrival else r"\overline{\vartheta}_0"
        sub_i_html = "<i>&tau;<sub>i</sub></i>" if is_arrival else "<i>&vartheta;<sub>i</sub></i>"
        sub_0_html = "<i>&tau;&#772;</i><sub>0</sub>" if is_arrival else "<i>&vartheta;&#772;</i><sub>0</sub>"

        src_note = (
            f"Active Simulation Configuration ({role_label})"
            if is_live
            else f"Reference Benchmark Configuration ({role_label})"
        )

        eq1 = latex_eq_row(
            rf"{rv_tex} = \sum_{{i=1}}^{{r}} {sub_i_tex}, \qquad {rv_bar_tex} = \frac{{1}}{{{rate_tex}}} = r\,{sub_0_tex}, \qquad {rv_var_tex} = r\,{sub_0_tex}^2 = \frac{{1}}{{r\,{rate_tex}^2}}",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"f_{{r,{rv_tex}}}(t) = \frac{{(r{rate_tex} t)^{{r-1}}}}{{(r - 1)!}}\,r{rate_tex}\,e^{{-r{rate_tex} t}}, \qquad F_{{r,{rv_tex}}}(t) = 1 - e^{{-r{rate_tex} t}} \sum_{{j=0}}^{{r-1}} \frac{{(r{rate_tex} t)^j}}{{j!}} \quad (t \geq 0)",
            eq_num=2,
            zoom_factor=zoom_factor,
        )

        params_eq1_eq2 = where_list([
            (f"{rv_html} &ge; 0", f"Total Erlang random variable representing {rv_desc}, obtained as the sum of <i>r</i> i.i.d. exponential stages, in seconds (s)."),
            ("<i>r</i> &isin; &#123;1, 2, &hellip;&#125;", "Number of independent exponential stages in series (labeled <i>k</i> in the simulator sidebar)."),
            (f"{sub_i_html}", f"Exponential random variable of the <i>i</i>-th stage (<i>i</i> = 1, &hellip;, <i>r</i>), each with mean {sub_0_html} = 1/(<i>r</i>{rate_html}), in seconds (s)."),
            (f"{sub_0_html} = {rv_bar_html} / <i>r</i>", "Mean duration of a single exponential stage, in seconds (s)."),
            (f"{rate_html} = 1 / {rv_bar_html}", f"Overall average completion rate ({rate_desc}), in customers per second (cust/s); each individual stage has rate <i>r</i>{rate_html}."),
            (f"<i>f<sub>r,{rv_html}</sub></i>(<i>t</i>), <i>F<sub>r,{rv_html}</sub></i>(<i>t</i>)", "Probability density function (obtained as the <i>r</i>-fold convolution of exponential PDFs, in s<sup>&minus;1</sup>) and cumulative distribution function for <i>t</i> &ge; 0."),
            (f"{rv_bar_html}, {rv_var_html}", f"Overall mean (<i>r</i>{sub_0_html}, in s) and variance (<i>r</i>{sub_0_html}<sup>2</sup> = {rv_bar_html}<sup>2</sup>/<i>r</i>, in s<sup>2</sup>)."),
        ])

        html = f"""{css}
        <h1>The Erlang Distribution (<i>E<sub>{r_stages}</sub></i>, Stages <i>r</i> = {r_stages})</h1>
        <div class="meta-line">{src_note}</div>

        <h2>1. Definition and Physical Interpretation</h2>
        <p class="def-paragraph">
            <b>Definition.</b> An <i>Erlang random variable</i> {rv_html} of order <i>r</i> &ge; 1 is obtained as the sum of
            <i>r</i> independent and identically distributed exponential random variables {sub_i_html} (<i>i</i> = 1, &hellip;, <i>r</i>),
            each having mean equal to {sub_0_html} (rate <i>r</i>{rate_html} = 1/{sub_0_html}).
        </p>
        <p>
            <b>Physical Interpretation.</b> In teletraffic engineering, an Erlang service time <i>&vartheta;</i> models a service
            provisioned across <i>r</i> sequential exponential sub-tasks (stages) in series. As the number of stages <i>r</i>
            increases while keeping the total mean {rv_bar_html} = <i>r</i>{sub_0_html} = 1/{rate_html} constant, the variance
            {rv_var_html} = {rv_bar_html}<sup>2</sup>/<i>r</i> decreases inversely with <i>r</i>. For <i>r</i> = 1, the Erlang
            distribution coincides with the Exponential distribution (<i>&#8499;</i>); as <i>r</i> &rarr; &infin;, {rv_var_html} &rarr; 0
            and the distribution converges to a Deterministic process (<i>&#119967;</i>).
        </p>

        <h2>2. Mathematical Formulation</h2>
        <p>
            Expressing {rv_html} as the sum of <i>r</i> i.i.d. exponential stages {sub_i_html} gives the mean and variance:
        </p>
        {eq1}
        <p>
            Computing the <i>r</i>-fold convolution of the stage density functions yields the Erlang PDF and CDF (for <i>t</i> &ge; 0, and 0 for <i>t</i> &lt; 0):
        </p>
        {eq2}
        {params_eq1_eq2}

        <h2>3. Theoretical Properties and Queueing Analysis</h2>
        <ul>
            <li><b>Variance Reduction (<i>C<sub>v</sub></i><sup>2</sup> = 1 / <i>r</i>):</b> Dividing the variance {rv_var_html} = <i>r</i>{sub_0_html}<sup>2</sup> by {rv_bar_html}<sup>2</sup> = (<i>r</i>{sub_0_html})<sup>2</sup> gives <i>C<sub>v</sub></i><sup>2</sup> = 1/<i>r</i> &le; 1.</li>
            <li><b>Mean Residual Service Time:</b> Substituting {rv_var_html} = {rv_bar_html}<sup>2</sup>/<i>r</i> into the residual service time formula gives <i>&zeta;&#772;</i> = ({rv_var_html} + {rv_bar_html}<sup>2</sup>)/(2{rv_bar_html}) = {rv_bar_html}(1 + 1/<i>r</i>)/2, which decreases monotonically from {rv_bar_html} (at <i>r</i> = 1) down to {rv_bar_html}/2 (as <i>r</i> &rarr; &infin;).</li>
        </ul>

        <h2>4. Worked Numerical Example</h2>
        <div class="example-box">
            <p class="example-title">Example 1 ({'Evaluation with Active Simulation Parameters' if is_live else 'Illustrative Calculation with Reference Parameters'}: r = {r_stages}, {rate_html} = {rate_val:.2f} cust/s)</p>
            <p>
                Consider an Erlang distribution with <i>r</i> = <b>{r_stages} stages</b> and overall rate {rate_html} = <b>{rate_val:.2f} cust/s</b>:
            </p>
            <ol>
                <li><b>Overall Mean and Single-Stage Mean (Eq. 1):</b>
                    <br>{rv_bar_html} = 1 / {rate_html} = 1 / {rate_val:.2f} = <b>{mean_v:.4f} s</b>, &nbsp;&nbsp;
                    {sub_0_html} = {rv_bar_html} / <i>r</i> = {mean_v:.4f} / {r_stages} = <b>{stage_mean_0:.4f} s</b> (stage rate <i>r</i>{rate_html} = <b>{stage_rate:.4f} s<sup>&minus;1</sup></b>).</li>
                <li><b>Variance and Dispersion (Eq. 1):</b>
                    <br>{rv_var_html} = <i>r</i>{sub_0_html}<sup>2</sup> = {r_stages} &times; ({stage_mean_0:.4f})<sup>2</sup> = <b>{var_v:.4f} s<sup>2</sup></b>, &nbsp;&nbsp;
                    <i>C<sub>v</sub></i><sup>2</sup> = 1 / {r_stages} = <b>{cv2:.4f}</b>.</li>
                <li><b>Mean Residual Duration:</b>
                    <br><i>&zeta;&#772;</i> = ({var_v:.4f} + {mean_v*mean_v:.4f}) / (2 &times; {mean_v:.4f}) = <b>{zeta_bar:.4f} s</b>.</li>
            </ol>
        </div>

        <h2>5. Summary of Parameters and Moments</h2>
        <table class="book-table">
            <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Analytical Formula</th><th>Evaluated Value</th></tr>
            <tr><td>Number of Stages</td><td><i>r</i> (<i>k</i>)</td><td>Configured integer parameter</td><td>{r_stages}</td></tr>
            <tr><td>Single-Stage Mean</td><td>{sub_0_html}</td><td>{rv_bar_html} / <i>r</i> = 1 / (<i>r</i>{rate_html})</td><td>{stage_mean_0:.4f} s</td></tr>
            <tr><td>Overall Mean Value</td><td>{rv_bar_html}</td><td><i>r</i>{sub_0_html} = 1 / {rate_html}</td><td>{mean_v:.4f} s</td></tr>
            <tr><td>Variance</td><td>{rv_var_html}</td><td><i>r</i>{sub_0_html}<sup>2</sup> = 1 / (<i>r</i>{rate_html}<sup>2</sup>)</td><td>{var_v:.4f} s<sup>2</sup></td></tr>
            <tr class="bottom-rule"><td>Mean Residual Duration</td><td><i>&zeta;&#772;</i></td><td>{rv_bar_html}(1 + 1/<i>r</i>) / 2</td><td>{zeta_bar:.4f} s</td></tr>
        </table>
        """
        return title, _format_theory_html(html)

    # ===================================================================
    # Topic 4: Hyperexponential Distribution (H_2)
    # ===================================================================
    elif topic_index == 4:
        p1 = 0.40
        r1 = 0.50
        r2 = 2.00
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "HyperexponentialDist":
            p1 = getattr(curr_d, "p1", p1)
            r1 = getattr(curr_d, "rate1", getattr(curr_d, "r1", r1))
            r2 = getattr(curr_d, "rate2", getattr(curr_d, "r2", r2))
            is_live = True

        p2 = 1.0 - p1
        mean_v = (p1 / r1) + (p2 / r2)
        rate_eq = 1.0 / max(1e-6, mean_v)
        ex2_v = 2.0 * ((p1 / (r1 * r1)) + (p2 / (r2 * r2)))
        var_v = max(0.0, ex2_v - mean_v * mean_v)
        zeta_bar = ex2_v / max(1e-6, 2.0 * mean_v)
        cv2 = var_v / max(1e-12, mean_v * mean_v)

        src_note = (
            f"Active Simulation Configuration ({role_label})"
            if is_live
            else f"Reference Benchmark Configuration ({role_label})"
        )

        eq1 = latex_eq_row(
            rf"f_{{{rv_tex}}}(t) = p_1 r_1 e^{{-r_1 t}} + p_2 r_2 e^{{-r_2 t}}, \qquad F_{{{rv_tex}}}(t) = 1 - p_1 e^{{-r_1 t}} - p_2 e^{{-r_2 t}} \quad (t \geq 0)",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"{rv_bar_tex} = \frac{{p_1}}{{r_1}} + \frac{{p_2}}{{r_2}}, \qquad \mathrm{{E}}[{rv_tex}^2] = 2\left(\frac{{p_1}}{{r_1^2}} + \frac{{p_2}}{{r_2^2}}\right), \qquad {rv_var_tex} = \mathrm{{E}}[{rv_tex}^2] - {rv_bar_tex}^2",
            eq_num=2,
            zoom_factor=zoom_factor,
        )
        eq3 = latex_eq_row(
            rf"\overline{{\zeta}} = \frac{{\mathrm{{E}}[{rv_tex}^2]}}{{2{rv_bar_tex}}} = \frac{{{rv_var_tex} + {rv_bar_tex}^2}}{{2{rv_bar_tex}}} \geq {rv_bar_tex}, \qquad C_v^2 = \frac{{{rv_var_tex}}}{{{rv_bar_tex}^2}} \geq 1",
            eq_num=3,
            zoom_factor=zoom_factor,
        )

        params_eq1_eq3 = where_list([
            (f"{rv_html} &ge; 0", f"Continuous random variable representing {rv_desc}, in seconds (s)."),
            ("<i>p</i><sub>1</sub>, <i>p</i><sub>2</sub> = 1 &minus; <i>p</i><sub>1</sub>", "Probabilities of selecting exponential Branch 1 and Branch 2, respectively (<i>p</i><sub>1</sub> + <i>p</i><sub>2</sub> = 1)."),
            ("<i>r</i><sub>1</sub> &gt; 0, <i>r</i><sub>2</sub> &gt; 0", "Exponential rates of Branch 1 and Branch 2, measured in customers per second (cust/s)."),
            (f"{rv_bar_html}, {rv_var_html}", f"Overall mean value (in s) and variance (in s<sup>2</sup>) of {rv_html}."),
            (f"{rate_html} = 1 / {rv_bar_html}", f"Overall average rate ({rate_desc}), in customers per second (cust/s)."),
            ("<i>&zeta;&#772;</i> &ge; " + rv_bar_html, "Mean residual duration at a random observation epoch, which strictly exceeds the mean " + rv_bar_html + " whenever <i>r</i><sub>1</sub> &ne; <i>r</i><sub>2</sub>."),
        ])

        html = f"""{css}
        <h1>The Hyperexponential Distribution (Kendall Notation: <i>H</i><sub>2</sub>)</h1>
        <div class="meta-line">{src_note}</div>

        <h2>1. Definition and Physical Interpretation</h2>
        <p class="def-paragraph">
            <b>Definition.</b> A continuous random variable {rv_html} follows a <i>2-Phase Hyperexponential distribution</i>
            (<i>H</i><sub>2</sub>) if each realization is drawn independently from an exponential distribution with parameter
            <i>r</i><sub>1</sub> (mean 1/<i>r</i><sub>1</sub>) with probability <i>p</i><sub>1</sub>, or from an exponential
            distribution with parameter <i>r</i><sub>2</sub> (mean 1/<i>r</i><sub>2</sub>) with probability
            <i>p</i><sub>2</sub> = 1 &minus; <i>p</i><sub>1</sub>.
        </p>
        <p>
            <b>Physical Interpretation.</b> While an Erlang process places exponential stages in series (reducing variance below
            that of an exponential process), a Hyperexponential process places exponential branches in parallel. This models a
            population composed of two distinct customer types—for example, frequent short transactions (large rate <i>r</i><sub>2</sub>)
            mixed with infrequent long transfers (small rate <i>r</i><sub>1</sub>)—yielding high variance ({rv_var_html} &gt; {rv_bar_html}<sup>2</sup>).
        </p>

        <h2>2. Mathematical Formulation</h2>
        <p>
            By total probability across the two parallel branches, the PDF and CDF for <i>t</i> &ge; 0 are:
        </p>
        {eq1}
        <p>
            The mean value {rv_bar_html}, second moment E[{rv_html}<sup>2</sup>], variance {rv_var_html}, and mean residual duration <i>&zeta;&#772;</i> are:
        </p>
        {eq2}
        {eq3}
        {params_eq1_eq3}

        <h2>3. Theoretical Properties and Queueing Analysis</h2>
        <ul>
            <li><b>Residual Service Time Amplification (<i>&zeta;&#772;</i> &gt; {rv_bar_html}):</b> Because {rv_var_html} &gt; {rv_bar_html}<sup>2</sup> whenever <i>r</i><sub>1</sub> &ne; <i>r</i><sub>2</sub>, the mean residual service time <i>&zeta;&#772;</i> = ({rv_var_html} + {rv_bar_html}<sup>2</sup>)/(2{rv_bar_html}) is strictly larger than the unconditional mean service time {rv_bar_html} (the <i>inspection paradox</i>: a random observer is more likely to sample the server during a long Branch-1 job than during a short Branch-2 job).</li>
        </ul>

        <h2>4. Worked Numerical Example</h2>
        <div class="example-box">
            <p class="example-title">Example 1 ({'Evaluation with Active Simulation Parameters' if is_live else 'Illustrative Calculation with Reference Parameters'}: p<sub>1</sub> = {p1:.2f}, r<sub>1</sub> = {r1:.2f} cust/s, r<sub>2</sub> = {r2:.2f} cust/s)</p>
            <ol>
                <li><b>Mean Value and Average Rate (Eq. 2):</b> With <i>p</i><sub>1</sub> = {p1:.2f} and <i>p</i><sub>2</sub> = {p2:.2f}:
                    <br>{rv_bar_html} = ({p1:.2f} / {r1:.2f}) + ({p2:.2f} / {r2:.2f}) = {p1/r1:.4f} + {p2/r2:.4f} = <b>{mean_v:.4f} s</b>, &nbsp;&nbsp;
                    {rate_html} = 1 / {rv_bar_html} = <b>{rate_eq:.4f} cust/s</b>.</li>
                <li><b>Second Moment and Variance (Eq. 2):</b>
                    <br>E[{rv_html}<sup>2</sup>] = 2 &times; [({p1:.2f} / {r1:.2f}<sup>2</sup>) + ({p2:.2f} / {r2:.2f}<sup>2</sup>)] = <b>{ex2_v:.4f} s<sup>2</sup></b>,
                    <br>{rv_var_html} = {ex2_v:.4f} &minus; ({mean_v:.4f})<sup>2</sup> = <b>{var_v:.4f} s<sup>2</sup></b>, &nbsp;&nbsp;
                    <i>C<sub>v</sub></i><sup>2</sup> = {var_v:.4f} / ({mean_v:.4f})<sup>2</sup> = <b>{cv2:.4f}</b>.</li>
                <li><b>Mean Residual Duration (Eq. 3):</b>
                    <br><i>&zeta;&#772;</i> = {ex2_v:.4f} / (2 &times; {mean_v:.4f}) = <b>{zeta_bar:.4f} s</b> (strictly greater than {rv_bar_html} = {mean_v:.4f} s).</li>
            </ol>
        </div>

        <h2>5. Summary of Parameters and Moments</h2>
        <table class="book-table">
            <tr><th>Quantity</th><th>Course Symbol</th><th>Analytical Formula</th><th>Evaluated Value</th></tr>
            <tr><td>Branch Probabilities</td><td><i>p</i><sub>1</sub>, <i>p</i><sub>2</sub></td><td><i>p</i><sub>1</sub>, 1 &minus; <i>p</i><sub>1</sub></td><td>{p1:.2f}, {p2:.2f}</td></tr>
            <tr><td>Branch Rates</td><td><i>r</i><sub>1</sub>, <i>r</i><sub>2</sub></td><td>Configured branch rates</td><td>{r1:.2f} cust/s, {r2:.2f} cust/s</td></tr>
            <tr><td>Mean Value</td><td>{rv_bar_html}</td><td><i>p</i><sub>1</sub>/<i>r</i><sub>1</sub> + <i>p</i><sub>2</sub>/<i>r</i><sub>2</sub></td><td>{mean_v:.4f} s</td></tr>
            <tr><td>Variance</td><td>{rv_var_html}</td><td>E[{rv_html}<sup>2</sup>] &minus; {rv_bar_html}<sup>2</sup></td><td>{var_v:.4f} s<sup>2</sup></td></tr>
            <tr class="bottom-rule"><td>Mean Residual Duration</td><td><i>&zeta;&#772;</i></td><td>({rv_var_html} + {rv_bar_html}<sup>2</sup>) / (2{rv_bar_html})</td><td>{zeta_bar:.4f} s</td></tr>
        </table>
        """
        return title, _format_theory_html(html)

    # ===================================================================
    # Topic 5: Pareto Heavy-Tailed Distribution
    # ===================================================================
    elif topic_index == 5:
        alpha = 2.50
        t0 = 0.60
        is_live = False
        if curr_d is not None and curr_d.__class__.__name__ == "ParetoDist":
            alpha = getattr(curr_d, "alpha", alpha)
            t0 = getattr(curr_d, "xm", t0)
            is_live = True

        mean_v = (alpha * t0) / (alpha - 1.0) if alpha > 1.0 else float("inf")
        rate_eq = (1.0 / mean_v) if (not math.isinf(mean_v) and mean_v > 0) else 0.0
        var_v = ((t0 / (alpha - 1.0)) ** 2) * (alpha / (alpha - 2.0)) if alpha > 2.0 else float("inf")
        ex2_v = (alpha * (t0 * t0)) / (alpha - 2.0) if alpha > 2.0 else float("inf")
        zeta_bar = (ex2_v / (2.0 * mean_v)) if (not math.isinf(ex2_v) and not math.isinf(mean_v)) else float("inf")

        src_note = (
            f"Active Simulation Configuration ({role_label})"
            if is_live
            else f"Reference Benchmark Configuration ({role_label})"
        )

        eq1 = latex_eq_row(
            rf"f_{{{rv_tex}}}(t) = \frac{{\alpha\,t_0^\alpha}}{{t^{{\alpha + 1}}}}, \qquad F_{{{rv_tex}}}(t) = 1 - \left(\frac{{t_0}}{{t}}\right)^\alpha \quad (t \geq t_0)",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            rf"{rv_bar_tex} = \frac{{\alpha\,t_0}}{{\alpha - 1}} \;\; (\alpha > 1), \qquad {rv_var_tex} = \left(\frac{{t_0}}{{\alpha - 1}}\right)^2 \frac{{\alpha}}{{\alpha - 2}} \;\; (\alpha > 2)",
            eq_num=2,
            zoom_factor=zoom_factor,
        )
        eq3 = latex_eq_row(
            rf"{rv_bar_tex} = \infty \;\; (\alpha \leq 1), \qquad {rv_var_tex} = \infty \;\; (1 < \alpha \leq 2), \qquad \overline{{\zeta}} = \frac{{{rv_var_tex} + {rv_bar_tex}^2}}{{2{rv_bar_tex}}}",
            eq_num=3,
            zoom_factor=zoom_factor,
        )

        params_eq1_eq3 = where_list([
            (f"{rv_html} &ge; <i>t</i><sub>0</sub>", f"Continuous random variable representing {rv_desc}, supported on [<i>t</i><sub>0</sub>, &infin;), in seconds (s)."),
            ("<i>t</i><sub>0</sub> &gt; 0", "Positive scale parameter (minimum possible value of " + rv_html + ", labeled <i>x<sub>m</sub></i> in the simulator sidebar), in seconds (s)."),
            ("<i>&alpha;</i> &gt; 0", "Positive dimensionless shape parameter governing the power-law tail decay."),
            (f"<i>f<sub>{rv_html}</sub></i>(<i>t</i>), <i>F<sub>{rv_html}</sub></i>(<i>t</i>)", "Probability density function (in s<sup>&minus;1</sup>) and cumulative distribution function for <i>t</i> &ge; <i>t</i><sub>0</sub> (both are 0 for <i>t</i> &lt; <i>t</i><sub>0</sub>)."),
            (f"{rv_bar_html}, {rv_var_html}", f"Mean value (finite only for <i>&alpha;</i> &gt; 1, in s) and variance (finite only for <i>&alpha;</i> &gt; 2, in s<sup>2</sup>)."),
            ("<i>&zeta;&#772;</i>", "Mean residual service time (in s), which becomes infinite whenever 1 &lt; <i>&alpha;</i> &le; 2."),
        ])

        t_tail = round(5.0 * mean_v, 2) if not math.isinf(mean_v) else 5.0
        p_pareto_tail = (t0 / t_tail) ** alpha if t_tail >= t0 else 1.0
        p_exp_tail = math.exp(-t_tail / mean_v) if not math.isinf(mean_v) else 0.0

        html = f"""{css}
        <h1>The Pareto Distribution (Scale <i>t</i><sub>0</sub>, Shape <i>&alpha;</i>)</h1>
        <div class="meta-line">{src_note}</div>

        <h2>1. Definition and Physical Interpretation</h2>
        <p class="def-paragraph">
            <b>Definition.</b> A random variable {rv_html} follows a <i>Pareto distribution</i> with positive scale parameter
            <i>t</i><sub>0</sub> &gt; 0 and shape parameter <i>&alpha;</i> &gt; 0 if its complementary cumulative distribution
            decays as a power law (<i>t</i><sub>0</sub> / <i>t</i>)<sup><i>&alpha;</i></sup> for <i>t</i> &ge; <i>t</i><sub>0</sub>.
        </p>
        <p>
            <b>Physical Interpretation.</b> A Pareto random variable exhibits a <b>heavy-tailed behavior</b>, meaning that the
            probability of observing realizations much longer than the mean value {rv_bar_html} is not negligible compared to an
            exponential distribution. In packet-switched networks (e.g., Ethernet and Internet traffic), Pareto distributions
            characterize burst lengths and file sizes whose aggregation produces <i>self-similar</i> traffic across multiple time scales.
        </p>

        <h2>2. Mathematical Formulation</h2>
        <p>
            For <i>t</i> &ge; <i>t</i><sub>0</sub> (and 0 for <i>t</i> &lt; <i>t</i><sub>0</sub>), the probability density function and cumulative distribution function are:
        </p>
        {eq1}
        <p>
            The mean value {rv_bar_html} and variance {rv_var_html} depend on the shape parameter <i>&alpha;</i>:
        </p>
        {eq2}
        {eq3}
        {params_eq1_eq3}

        <h2>3. Theoretical Properties and Queueing Analysis</h2>
        <ul>
            <li><b>Finite Mean and Undefined Variance for 1 &lt; <i>&alpha;</i> &le; 2:</b> When 1 &lt; <i>&alpha;</i> &le; 2, {rv_bar_html} = <i>&alpha;t</i><sub>0</sub>/(&alpha; &minus; 1) is finite, but the integral defining E[{rv_html}<sup>2</sup>] diverges, so {rv_var_html} = &infin; and the mean residual service time is <i>&zeta;&#772;</i> = &infin;.</li>
            <li><b>Tail Comparison with Exponential:</b> On a log-linear plot of <i>f<sub>&vartheta;</sub></i>(<i>t</i>) versus <i>t</i>, an exponential density decays as a straight line, whereas the Pareto density <i>&alpha;t</i><sub>0</sub><sup><i>&alpha;</i></sup>/<i>t</i><sup><i>&alpha;</i>+1</sup> flattens out and remains orders of magnitude higher for large <i>t</i>.</li>
        </ul>

        <h2>4. Worked Numerical Example</h2>
        <div class="example-box">
            <p class="example-title">Example 1 ({'Evaluation with Active Simulation Parameters' if is_live else 'Illustrative Calculation with Reference Parameters'}: t<sub>0</sub> = {t0:.2f} s, &alpha; = {alpha:.2f})</p>
            <ol>
                <li><b>Mean Value and Average Rate (Eq. 2):</b> Since <i>&alpha;</i> = {alpha:.2f} &gt; 1:
                    <br>{rv_bar_html} = (&alpha;<i>t</i><sub>0</sub>) / (&alpha; &minus; 1) = ({alpha:.2f} &times; {t0:.2f}) / ({alpha:.2f} &minus; 1) = <b>{mean_v:.4f} s</b>, &nbsp;&nbsp;
                    {rate_html} = 1 / {rv_bar_html} = <b>{rate_eq:.4f} cust/s</b>.</li>
                <li><b>Variance and Mean Residual Time (Eqs. 2&ndash;3):</b>
                    {f"<br>Since &alpha; = {alpha:.2f} &gt; 2:<br>{rv_var_html} = [{t0:.2f} / ({alpha:.2f} &minus; 1)]<sup>2</sup> &times; [{alpha:.2f} / ({alpha:.2f} &minus; 2)] = <b>{var_v:.4f} s<sup>2</sup></b>, &nbsp;&nbsp; <i>&zeta;&#772;</i> = ({var_v:.4f} + {mean_v*mean_v:.4f}) / (2 &times; {mean_v:.4f}) = <b>{zeta_bar:.4f} s</b>." if alpha > 2.0 else f"<br>Because 1 &lt; &alpha; = {alpha:.2f} &le; 2, the variance and mean residual duration diverge: {rv_var_html} = <b>&infin;</b> and <i>&zeta;&#772;</i> = <b>&infin;</b>."}</li>
                <li><b>Tail Probability at <i>t</i> = {t_tail:.2f} s (5{rv_bar_html}):</b>
                    <br>1 &minus; <i>F<sub>{rv_html}</sub></i>({t_tail:.2f}) = ({t0:.2f} / {t_tail:.2f})<sup>{alpha:.2f}</sup> = <b>{p_pareto_tail:.5f}</b> ({p_pareto_tail*100:.3f}%), compared to <i>e</i><sup>&minus;5</sup> = <b>{p_exp_tail:.5f}</b> ({p_exp_tail*100:.3f}%) for an exponential random variable with the same mean.</li>
            </ol>
        </div>

        <h2>5. Summary of Parameters and Moments</h2>
        <table class="book-table">
            <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Analytical Formula</th><th>Evaluated Value</th></tr>
            <tr><td>Scale &amp; Shape Parameters</td><td><i>t</i><sub>0</sub> (<i>x<sub>m</sub></i>), <i>&alpha;</i></td><td>Configured parameters</td><td><i>t</i><sub>0</sub> = {t0:.2f} s, <i>&alpha;</i> = {alpha:.2f}</td></tr>
            <tr><td>Mean Value</td><td>{rv_bar_html}</td><td>&alpha;<i>t</i><sub>0</sub> / (&alpha; &minus; 1) &nbsp;(&alpha; &gt; 1)</td><td>{f"{mean_v:.4f} s" if not math.isinf(mean_v) else "&infin;"}</td></tr>
            <tr><td>Variance</td><td>{rv_var_html}</td><td>[<i>t</i><sub>0</sub>/(&alpha;&minus;1)]<sup>2</sup> &alpha;/(&alpha;&minus;2) &nbsp;(&alpha; &gt; 2)</td><td>{f"{var_v:.4f} s<sup>2</sup>" if not math.isinf(var_v) else "&infin; (Undefined)"}</td></tr>
            <tr class="bottom-rule"><td>Mean Residual Duration</td><td><i>&zeta;&#772;</i></td><td>({rv_var_html} + {rv_bar_html}<sup>2</sup>) / (2{rv_bar_html})</td><td>{f"{zeta_bar:.4f} s" if not math.isinf(zeta_bar) else "&infin; (Divergent)"}</td></tr>
        </table>
        """
        return title, _format_theory_html(html)

    # ===================================================================
    # Topic 6: Stochastic Stability Theory & Ergodicity
    # ===================================================================
    elif topic_index == 6:
        lam_v = sys_lam
        mu_v = sys_mu
        c_v = sys_c
        A0_v = lam_v / max(1e-6, mu_v)
        rho_0 = A0_v / c_v
        K_v = engine.K if engine is not None else float("inf")

        eq1 = latex_eq_row(
            r"I(T) = \frac{1}{T} \int_{0}^{T} k(t)\,\mathrm{d}t, \qquad A = \lim_{T \to \infty} I(T) = \langle k(t) \rangle = \sum_{k=0}^{\infty} k\,P_k",
            eq_num=1,
            zoom_factor=zoom_factor,
        )
        eq2 = latex_eq_row(
            r"A_0 = \lambda\,\overline{\vartheta} = \frac{\lambda}{\mu}, \qquad \rho = \frac{A_0}{m} = \frac{\lambda}{m\mu} < 1 \quad \Longleftrightarrow \quad A_0 < m \quad (\text{Unlimited Waiting Space})",
            eq_num=2,
            zoom_factor=zoom_factor,
        )
        eq3 = latex_eq_row(
            r"\lim_{L \to \infty} \pi_p = \frac{A_0 - m}{A_0} = 1 - \frac{m}{A_0} \quad (A_0 > m), \qquad \lim_{L \to \infty} \pi_p = 0 \quad (A_0 \leq m)",
            eq_num=3,
            zoom_factor=zoom_factor,
        )

        params_eq1_eq3 = where_list([
            ("<i>k</i>(<i>t</i>)", "Traffic in the system at time <i>t</i>, defined as the instantaneous number of customers in the system at time <i>t</i> (labeled <i>N</i>(<i>t</i>) in the simulator)."),
            ("<i>I</i>(<i>T</i>)", "Average traffic in the system over a finite observation interval of duration <i>T</i>, in Erlangs (E)."),
            ("<i>A</i> = &langle;<i>k</i>(<i>t</i>)&rangle;", "Average traffic intensity in the system (steady-state time average of <i>k</i>(<i>t</i>), labeled <i>L</i> in the simulator), measured in Erlangs (E)."),
            ("<i>P<sub>k</sub></i>", "Steady-state probability of having <i>k</i> customers in the system."),
            ("<i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i> = <i>&lambda;</i> / <i>&mu;</i>", "Traffic offered to the system, in Erlangs (E)."),
            ("<i>m</i>", "Number of parallel servers in the system."),
            ("<i>&rho;</i> = <i>A</i><sub>0</sub> / <i>m</i> = <i>&lambda;</i> / (<i>m&mu;</i>)", "Server utilization in a lossless system with unlimited waiting space, required to satisfy <i>&rho;</i> &lt; 1 for stability."),
            ("<i>L</i> (or <i>n</i>, GUI: <i>K</i>)", "Size of the finite waiting space (queue capacity)."),
            ("<i>&pi;<sub>p</sub></i>", "Blocking probability (fraction of arriving customers rejected due to the queue being full)."),
        ])

        min_loss_frac = max(0.0, (A0_v - c_v) / max(1e-6, A0_v))

        html = f"""{css}
        <h1>Ergodicity and Stability of Queueing Systems (<i>&rho;</i> = <i>A</i><sub>0</sub>/<i>m</i> &lt; 1)</h1>
        <div class="meta-line">
            Active Parameters: <i>&lambda;</i> = {lam_v:.2f} cust/s, <i>m</i> = {c_v}, <i>&mu;</i> = {mu_v:.2f} cust/s,
            Offered Traffic <i>A</i><sub>0</sub> = {A0_v:.3f} E, <i>A</i><sub>0</sub>/<i>m</i> = {rho_0:.3f}
        </div>

        <h2>1. Definition and Physical Interpretation</h2>
        <p class="def-paragraph">
            <b>Definition (Steady Behavior and Ergodicity).</b> Let <i>k</i>(<i>t</i>) denote the number of customers in the
            system at time <i>t</i>. The system exhibits a steady behavior over time if the time-average limit
            <i>A</i> = lim<sub><i>T</i>&rarr;&infin;</sub> <i>I</i>(<i>T</i>) = &langle;<i>k</i>(<i>t</i>)&rangle; exists and is finite.
            If <i>k</i>(<i>t</i>) is an <i>ergodic process</i>, <i>A</i> always exists and equals the statistical expectation
            &sum; <i>kP<sub>k</sub></i> at a generic time.
        </p>

        <h2>2. Mathematical Formulation</h2>
        <p>
            The average traffic over an observation interval <i>T</i> and its asymptotic time-average limit <i>A</i> are defined as:
        </p>
        {eq1}
        <p>
            <b>Stability of Systems with Unlimited Waiting Space (<i>&#8499;</i>/<i>&#8499;</i>/<i>m</i> and <i>&#119970;</i>/<i>&#119970;</i>/<i>m</i>).</b>
            When the waiting space is unlimited, no customers are rejected (<i>&lambda;<sub>p</sub></i> = 0, <i>A<sub>s</sub></i> = <i>A</i><sub>0</sub>).
            The geometric series in the normalization constant <i>P</i><sub>0</sub> converges if and only if the offered traffic
            <i>A</i><sub>0</sub> is strictly less than the number of servers <i>m</i>:
        </p>
        {eq2}
        <p>
            <b>Systems with Limited Waiting Space (<i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i> and <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i>/0).</b>
            A finite-state Markov chain with limited queue size <i>L</i> &lt; &infin; is <i>always stable</i> for any <i>A</i><sub>0</sub> &gt; 0.
            However, when <i>A</i><sub>0</sub> &gt; <i>m</i>, it is impossible to dimension the queue size <i>L</i> to achieve an arbitrarily
            small blocking probability <i>&pi;<sub>p</sub></i>, because as <i>L</i> &rarr; &infin; the blocking probability converges to a
            strictly positive asymptote:
        </p>
        {eq3}
        {params_eq1_eq3}

        <h2>3. Theoretical Properties and Queueing Analysis</h2>
        <ul>
            <li><b>General Single-Server Equilibrium Identity (<i>P</i><sub>0</sub> = 1 &minus; <i>&rho;</i>):</b> For any ergodic single-server system (<i>&#119970;</i>/<i>&#119970;</i>/1) with finite mean inter-arrival and service times, partitioning an observation interval <i>T</i> into busy time <i>B</i>(<i>T</i>) = <i>T</i>(1 &minus; <i>P</i><sub>0</sub>) and idle time <i>I</i>(<i>T</i>) = <i>TP</i><sub>0</sub> and equating departures <i>d</i>(<i>T</i>) = <i>B</i>(<i>T</i>)<i>&mu;</i> to arrivals <i>a</i>(<i>T</i>) = <i>&lambda;T</i> yields <i>T</i>(1 &minus; <i>P</i><sub>0</sub>)<i>&mu;</i> = <i>&lambda;T</i> &rArr; <b><i>P</i><sub>0</sub> = 1 &minus; <i>&lambda;</i>/<i>&mu;</i> = 1 &minus; <i>&rho;</i></b>, which holds strictly only when <i>&rho;</i> &lt; 1.</li>
        </ul>

        <h2>4. Worked Numerical Example</h2>
        <div class="example-box">
            <p class="example-title">Example 1 (Stability Evaluation under Active Parameters: &lambda; = {lam_v:.2f} cust/s, m = {c_v}, &mu; = {mu_v:.2f} cust/s)</p>
            <ol>
                <li><b>Offered Traffic <i>A</i><sub>0</sub> and Ratio <i>A</i><sub>0</sub>/<i>m</i> (Eq. 2):</b>
                    <br><i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i> = {lam_v:.2f} / {mu_v:.2f} = <b>{A0_v:.4f} E</b>, &nbsp;&nbsp;
                    <i>A</i><sub>0</sub> / <i>m</i> = {A0_v:.4f} / {c_v} = <b>{rho_0:.4f}</b>.</li>
                <li><b>Unlimited Queue Assessment (Eq. 2):</b>
                    {f"<br>Since <i>A</i><sub>0</sub> = {A0_v:.4f} &lt; <i>m</i> = {c_v} (<i>&rho;</i> = {rho_0:.4f} &lt; 1), an unlimited-queue system is <b>ergodic and stable</b> (for <i>m</i> = 1, the empty-system probability is <i>P</i><sub>0</sub> = 1 &minus; <i>&rho;</i> = <b>{1.0 - rho_0:.4f}</b>)." if rho_0 < 1.0 else f"<br>Because <i>A</i><sub>0</sub> = {A0_v:.4f} &ge; <i>m</i> = {c_v} (<i>A</i><sub>0</sub>/<i>m</i> = {rho_0:.4f} &ge; 1), an unlimited-queue system is <b>unstable</b>: the limit <i>A</i> = lim<sub><i>T</i>&rarr;&infin;</sub> <i>I</i>(<i>T</i>) does not exist and <i>k</i>(<i>t</i>) grows without bound."}</li>
                <li><b>Asymptotic Blocking Floor for Finite Queue <i>L</i> (Eq. 3):</b>
                    {f"<br>Because <i>A</i><sub>0</sub> &gt; <i>m</i>, even if the finite waiting space <i>L</i> is made arbitrarily large (<i>L</i> &rarr; &infin;), the blocking probability cannot be reduced below (<i>A</i><sub>0</sub> &minus; <i>m</i>)/<i>A</i><sub>0</sub> = ({A0_v:.4f} &minus; {c_v}) / {A0_v:.4f} = <b>{min_loss_frac:.4f}</b> ({min_loss_frac*100:.2f}%)." if rho_0 > 1.0 else f"<br>Since <i>A</i><sub>0</sub> &le; <i>m</i>, lim<sub><i>L</i>&rarr;&infin;</sub> <i>&pi;<sub>p</sub></i> = 0, so any desired blocking probability <i>&pi;<sub>p</sub></i> &gt; 0 can be achieved by choosing a sufficiently large queue size <i>L</i>."}</li>
            </ol>
        </div>

        <h2>5. Summary of Stability Quantities</h2>
        <table class="book-table">
            <tr><th>Quantity</th><th>Course Symbol</th><th>Analytical Formula</th><th>Active Value</th></tr>
            <tr><td>Offered Traffic</td><td><i>A</i><sub>0</sub></td><td><i>&lambda;&vartheta;&#772;</i> = <i>&lambda;</i> / <i>&mu;</i></td><td>{A0_v:.4f} E</td></tr>
            <tr><td>Number of Servers</td><td><i>m</i></td><td>Configured server count</td><td>{c_v}</td></tr>
            <tr><td>Offered Load per Server</td><td><i>A</i><sub>0</sub> / <i>m</i></td><td><i>&lambda;</i> / (<i>m&mu;</i>)</td><td>{rho_0:.4f} ({'Stable for L=&infin;' if rho_0 < 1.0 else 'Unstable for L=&infin;'})</td></tr>
            <tr class="bottom-rule"><td>Asymptotic Blocking Floor (<i>L</i>&rarr;&infin;)</td><td>lim<sub><i>L</i>&rarr;&infin;</sub> <i>&pi;<sub>p</sub></i></td><td>max(0, (<i>A</i><sub>0</sub> &minus; <i>m</i>)/<i>A</i><sub>0</sub>)</td><td>{min_loss_frac*100:.2f}%</td></tr>
        </table>
        """
        return title, _format_theory_html(html)

    # ===================================================================
    # Topics 7 to 14: Performance Metrics
    # ===================================================================
    else:
        m_stats = engine.get_metrics() if (engine is not None and hasattr(engine, "get_metrics")) else {}
        lam_val = sys_lam
        mu_val = sys_mu
        vartheta_bar = 1.0 / max(1e-6, mu_val)
        c_val = sys_c
        K_val = engine.K if engine is not None else float("inf")
        prio_on = bool(engine and getattr(engine, "priority_enabled", False))

        all_arr_exponential = (
            bool(active_arr_list) and all(isinstance(d, ExponentialDist) for d in active_arr_list)
            if active_arr_list
            else (engine is None)
        )
        service_is_exponential = (
            isinstance(engine.service_dist, ExponentialDist)
            if (engine and getattr(engine, "service_dist", None) is not None)
            else (engine is None)
        )

        theo = {}
        model_tag = "G/G/m"
        if lam_val > 0 and mu_val > 0:
            if service_is_exponential and all_arr_exponential and (not prio_on or math.isinf(K_val)):
                if math.isinf(K_val):
                    theo = TheoreticalModels.solve_mmc_infinite(lam_val, mu_val, c_val)
                    model_tag = f"M/M/{c_val}"
                else:
                    theo = TheoreticalModels.solve_mmc_finite(lam_val, mu_val, c_val, int(K_val))
                    model_tag = f"M/M/{c_val}/{int(K_val)}" if c_val == 1 else f"M/M/{c_val}/{c_val + int(K_val)}"
            elif (
                all_arr_exponential
                and not service_is_exponential
                and c_val == 1
                and math.isinf(K_val)
                and engine is not None
                and getattr(engine, "service_dist", None) is not None
            ):
                theo = TheoreticalModels.solve_mg1_pollaczek_khinchine(lam_val, engine.service_dist)
                model_tag = f"M/{engine.service_dist.kendall_symbol()}/1"

        is_unstable = bool(theo and theo.get("unstable", False))
        sim_T = m_stats.get("T", 0.0) if m_stats else 0.0
        has_sim_data = (engine is not None and getattr(engine, "current_time", 0.0) > 0.01 and m_stats.get("arrived", 0) > 0)

        # ---------------------------------------------------------------
        # Topic 7: Server Utilization (rho) and Traffic Definitions (A_0, A_s, A_p)
        # ---------------------------------------------------------------
        if topic_index == 7:
            A0_val = lam_val * vartheta_bar
            rho_offered_ratio = A0_val / c_val
            rho_sim = m_stats.get("rho", 0.0)
            pi_p_theo = theo.get("p_loss", 0.0) if theo else 0.0

            if is_unstable:
                rho_theo_val = 1.0
                As_theo_val = float(c_val)
                rho_theo_display = "1.0000 (Saturated)"
            elif not theo:
                rho_theo_val = min(1.0, rho_offered_ratio)
                As_theo_val = rho_theo_val * c_val
                rho_theo_display = "N/A (No Closed Form)"
            else:
                rho_theo_val = theo.get("rho", (1.0 - pi_p_theo) * A0_val / c_val)
                As_theo_val = rho_theo_val * c_val
                rho_theo_display = f"{rho_theo_val:.4f}"

            eq1 = latex_eq_row(
                r"A_0 = \lambda\,\overline{\vartheta} = \frac{\lambda}{\mu}, \qquad A_s = \lambda_s\,\overline{\vartheta} = (1 - \pi_p)A_0, \qquad A_p = \lambda_p\,\overline{\vartheta} = \pi_p A_0, \qquad A_0 = A_s + A_p",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\rho = \frac{A_s}{m} = \frac{(1 - \pi_p)A_0}{m} \quad (0 \leq \rho \leq 1), \qquad \rho^{(\text{lossless})} = \frac{A_0}{m} = \frac{\lambda}{m\mu}",
                eq_num=2,
                zoom_factor=zoom_factor,
            )
            eq3 = latex_eq_row(
                r"\hat{\rho}_{\mathrm{sim}} = \frac{1}{m\,T} \sum_{i=1}^{m} B_i(T) = \frac{B_{\mathrm{total}}(T)}{m\,T}",
                eq_num=3,
                zoom_factor=zoom_factor,
            )

            params_eq1_eq3 = where_list([
                ("<i>&lambda;</i>, <i>&lambda;<sub>s</sub></i>, <i>&lambda;<sub>p</sub></i>", "Average arrival rate offered to the system (<i>&lambda;</i>), average rate of customers entering the system (<i>&lambda;<sub>s</sub></i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>&lambda;</i>), and average rate of rejected customers (<i>&lambda;<sub>p</sub></i> = <i>&pi;<sub>p</sub>&lambda;</i>), in customers per second (cust/s)."),
                ("<i>&vartheta;&#772;</i> = 1 / <i>&mu;</i>", "Average service time of a generic customer, in seconds (s)."),
                ("<i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i>", "<b>Traffic offered</b> to the system (average number of busy servers in a hypothetical system with infinite servers), in Erlangs (E)."),
                ("<i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub>&vartheta;&#772;</i>", "<b>Traffic served (or carried)</b> by the system (average number of customers being served simultaneously), in Erlangs (E)."),
                ("<i>A<sub>p</sub></i> = <i>&lambda;<sub>p</sub>&vartheta;&#772;</i>", "<b>Traffic rejected (or lost)</b> by the system, in Erlangs (E)."),
                ("<i>&pi;<sub>p</sub></i>", "Blocking probability (fraction of arriving customers rejected by the system)."),
                ("<i>m</i>", "Number of parallel servers in the system."),
                ("<i>&rho;</i> = <i>A<sub>s</sub></i> / <i>m</i>", "<b>Server utilization</b> (labeled <i>U</i> in the simulator header), satisfying 0 &le; <i>&rho;</i> &le; 1 by definition; in an ergodic system, <i>&rho;</i> equals the average fraction of time a generic server is busy."),
                ("<i>B<sub>i</sub></i>(<i>T</i>), <i>B</i><sub>total</sub>(<i>T</i>)", "Busy time of the <i>i</i>-th server and total busy time across all <i>m</i> servers during observation interval <i>T</i>, in seconds (s)."),
            ])

            if has_sim_data:
                b_tot = rho_sim * c_val * sim_T
                emp_step = (
                    f"<b>Empirical Simulator Evaluation (Eq. 3, Live Run at <i>T</i> = {sim_T:.2f} s):</b> "
                    f"Over observation interval <i>T</i> = {sim_T:.2f} s across <i>m</i> = {c_val} server(s), total busy time is "
                    f"<i>B</i><sub>total</sub>(<i>T</i>) = <b>{b_tot:.2f} s</b> out of <i>mT</i> = <b>{c_val*sim_T:.2f} s</b>: "
                    f"<br><i>&rho;&#770;</i><sub>sim</sub> = {b_tot:.2f} / {c_val*sim_T:.2f} = <b>{rho_sim:.4f}</b> (carried traffic <i>A&#770;<sub>s</sub></i> = <i>m&rho;&#770;</i><sub>sim</sub> = <b>{c_val*rho_sim:.4f} E</b>)."
                )
            else:
                ref_T = 100.0
                ref_B = round(rho_theo_val * c_val * ref_T, 2)
                emp_step = (
                    f"<b>Empirical Simulator Evaluation (Eq. 3, Illustrative Observation Interval <i>T</i> = {ref_T:.1f} s):</b> "
                    f"Suppose over <i>T</i> = {ref_T:.1f} s the <i>m</i> = {c_val} server(s) accumulate <i>B</i><sub>total</sub>(<i>T</i>) = {ref_B:.2f} s of busy time. "
                    f"Then Eq. (3) gives: <br><i>&rho;&#770;</i><sub>sim</sub> = {ref_B:.2f} / ({c_val} &times; {ref_T:.1f}) = <b>{ref_B/(c_val*ref_T):.4f}</b>."
                )

            html = f"""{css}
            <h1>Offered Traffic (<i>A</i><sub>0</sub>), Carried Traffic (<i>A<sub>s</sub></i>), and Server Utilization (<i>&rho;</i>)</h1>
            <div class="meta-line">Active Model: {model_tag} &nbsp;|&nbsp; Parameters: <i>&lambda;</i> = {lam_val:.2f} cust/s, <i>&vartheta;&#772;</i> = {vartheta_bar:.4f} s, <i>m</i> = {c_val}</div>

            <h2>1. Definition and Physical Interpretation</h2>
            <p class="def-paragraph">
                <b>Definition.</b> In teletraffic theory, the <i>offered traffic</i> <i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i>
                is decomposed into the <i>carried (served) traffic</i> <i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub>&vartheta;&#772;</i>
                and the <i>rejected (lost) traffic</i> <i>A<sub>p</sub></i> = <i>&lambda;<sub>p</sub>&vartheta;&#772;</i>.
                The <b>server utilization</b> is defined as <b><i>&rho;</i> = <i>A<sub>s</sub></i> / <i>m</i></b> (denoted <i>U</i> in the
                simulator header bar to distinguish carried utilization from the offered load ratio <i>A</i><sub>0</sub>/<i>m</i>).
            </p>
            <p>
                <b>Physical Interpretation.</b> By Little's Law applied to the set of <i>m</i> servers (<i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub>&vartheta;&#772;</i>),
                <i>A<sub>s</sub></i> is the average number of customers simultaneously being served. Because at most <i>m</i> customers
                can be in service at any instant, 0 &le; <i>A<sub>s</sub></i> &le; <i>m</i>, and therefore server utilization
                <i>&rho;</i> = <i>A<sub>s</sub></i>/<i>m</i> always satisfies <b>0 &le; <i>&rho;</i> &le; 1</b>. In an ergodic system,
                <i>&rho;</i> equals the average percentage of time during which a generic server is busy.
            </p>

            <h2>2. Mathematical Formulation</h2>
            <p>
                The offered traffic <i>A</i><sub>0</sub>, carried traffic <i>A<sub>s</sub></i>, and lost traffic <i>A<sub>p</sub></i> (all expressed in Erlangs, E) satisfy:
            </p>
            {eq1}
            <p>
                Dividing the carried traffic <i>A<sub>s</sub></i> by the number of servers <i>m</i> yields the server utilization <i>&rho;</i>:
            </p>
            {eq2}
            <p>
                Over a simulated observation interval <i>T</i>, empirical server utilization is computed from the server busy times <i>B<sub>i</sub></i>(<i>T</i>):
            </p>
            {eq3}
            {params_eq1_eq3}

            <h2>3. Theoretical Properties and Queueing Analysis</h2>
            <ul>
                <li><b>Lossless vs. Loss Systems:</b> In a system with unlimited waiting space (<i>&pi;<sub>p</sub></i> = 0), <i>A<sub>p</sub></i> = 0 and <i>A<sub>s</sub></i> = <i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i>, so <i>&rho;</i> = <i>A</i><sub>0</sub>/<i>m</i> = <i>&lambda;</i>/(<i>m&mu;</i>). In a loss system (such as <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i>/0 or <i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i>), <i>A<sub>s</sub></i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>A</i><sub>0</sub> &lt; <i>A</i><sub>0</sub>. In particular, for <i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i>, <i>A<sub>s</sub></i> = <i>&rho;</i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>A</i><sub>0</sub> = 1 &minus; <i>P</i><sub>0</sub>.</li>
                <li><b>Trunking Efficiency:</b> In multi-server loss systems (<i>&#8499;</i>/<i>&#8499;</i>/<i>m</i>/0), for a given target blocking probability <i>&pi;<sub>p</sub></i>, larger systems (larger <i>m</i>) subject to higher offered traffic <i>A</i><sub>0</sub> achieve a higher server utilization <i>&rho;</i>.</li>
            </ul>

            <h2>4. Worked Numerical Example</h2>
            <div class="example-box">
                <p class="example-title">Example 1 (Evaluation of A<sub>0</sub>, A<sub>s</sub>, and Server Utilization &rho;)</p>
                <ol>
                    <li><b>Offered Traffic (Eq. 1):</b> With <i>&lambda;</i> = {lam_val:.2f} cust/s and <i>&vartheta;&#772;</i> = 1/{mu_val:.2f} = {vartheta_bar:.4f} s:
                        <br><i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i> = {lam_val:.2f} &times; {vartheta_bar:.4f} = <b>{A0_val:.4f} E</b>, &nbsp;&nbsp;
                        <i>A</i><sub>0</sub> / <i>m</i> = {A0_val:.4f} / {c_val} = <b>{rho_offered_ratio:.4f}</b>.</li>
                    <li><b>Carried Traffic and Server Utilization (Eqs. 1&ndash;2):</b>
                        {f"With theoretical blocking probability <i>&pi;<sub>p</sub></i> = {pi_p_theo:.4f}:<br><i>A<sub>s</sub></i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>A</i><sub>0</sub> = (1 &minus; {pi_p_theo:.4f}) &times; {A0_val:.4f} = <b>{As_theo_val:.4f} E</b>, &nbsp;&nbsp; <i>&rho;</i> = <i>A<sub>s</sub></i> / <i>m</i> = {As_theo_val:.4f} / {c_val} = <b>{rho_theo_val:.4f}</b>." if theo and not is_unstable else f"Under the active regime ({model_tag}), carried server utilization is <i>&rho;</i> = <b>{rho_theo_val:.4f}</b> (<i>A<sub>s</sub></i> = <b>{As_theo_val:.4f} E</b>)."}</li>
                    <li>{emp_step}</li>
                </ol>
            </div>

            <h2>5. Analytical vs. Empirical Benchmark Table</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Formula / Estimator</th><th>Value</th></tr>
                <tr><td>Offered Traffic</td><td><i>A</i><sub>0</sub></td><td><i>&lambda;&vartheta;&#772;</i> = <i>&lambda;</i> / <i>&mu;</i></td><td>{A0_val:.4f} E</td></tr>
                <tr><td>Offered Load per Server</td><td><i>A</i><sub>0</sub> / <i>m</i> (<i>&rho;</i><sub>offered</sub>)</td><td><i>&lambda;</i> / (<i>m&mu;</i>)</td><td>{rho_offered_ratio:.4f}</td></tr>
                <tr><td>Theoretical Server Utilization</td><td><i>&rho;</i> (<i>U</i><sub>theo</sub>)</td><td><i>A<sub>s</sub></i> / <i>m</i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>A</i><sub>0</sub> / <i>m</i></td><td>{rho_theo_display}</td></tr>
                <tr class="bottom-rule"><td>Simulated Server Utilization</td><td><i>&rho;&#770;</i><sub>sim</sub> (<i>U</i><sub>sim</sub>)</td><td><i>B</i><sub>total</sub>(<i>T</i>) / (<i>mT</i>)</td><td>{rho_sim:.4f}</td></tr>
            </table>
            """
            return title, _format_theory_html(html)

        # ---------------------------------------------------------------
        # Topic 8: Average Traffic in the System A (GUI: L)
        # ---------------------------------------------------------------
        elif topic_index == 8:
            A_val = theo.get("L") if theo else None
            Ac_val = theo.get("Lq") if theo else None
            rho_theo = theo.get("rho", 0.0) if theo else 0.0
            As_val = c_val * rho_theo
            A_sim = m_stats.get("L", 0.0)
            littles_A = m_stats.get("littles_L", 0.0)

            if is_unstable:
                A_theo_str = "&infin; (Unstable)"
            elif A_val is None:
                A_theo_str = "N/A (No Closed Form)"
            elif math.isinf(A_val) or math.isnan(A_val):
                A_theo_str = "&infin; (Infinite Variance)"
            else:
                A_theo_str = f"{A_val:.4f} E (cust)"

            eq1 = latex_eq_row(
                r"I(T) = \frac{1}{T} \int_{0}^{T} k(t)\,\mathrm{d}t, \qquad A = \lim_{T \to \infty} I(T) = \langle k(t) \rangle = \sum_{k} k\,P_k = A_c + A_s",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"A^{(M/M/m)} = A_0 + \mathcal{C}(m, A_0)\,\frac{A_0}{m - A_0}, \qquad A^{(M/M/1)} = \frac{\rho}{1 - \rho} = \frac{A_0}{1 - A_0} \quad (\rho < 1)",
                eq_num=2,
                zoom_factor=zoom_factor,
            )
            eq3 = latex_eq_row(
                r"I_{\mathrm{sim}}(T) = \frac{1}{T} \int_{0}^{T} k(t)\,\mathrm{d}t = \frac{1}{T} \sum_{k=0}^{k_{\max}} k\,\Delta t_k = \sum_{k=0}^{k_{\max}} k\,\hat{P}_k",
                eq_num=3,
                zoom_factor=zoom_factor,
            )

            params_eq1_eq3 = where_list([
                ("<i>k</i>(<i>t</i>)", "Traffic in the system at time <i>t</i>, defined as the number of customers inside the system at time <i>t</i> (labeled <i>N</i>(<i>t</i>) in the simulator)."),
                ("<i>I</i>(<i>T</i>)", "Average traffic in the system over observation interval <i>T</i>, in Erlangs (E) (or customers)."),
                ("<i>A</i> = &langle;<i>k</i>(<i>t</i>)&rangle;", "<b>Average traffic intensity in the system</b> (time-average number of customers in the system, labeled <i>L</i> in the simulator table), in Erlangs (E)."),
                ("<i>P<sub>k</sub></i>", "Steady-state probability of having <i>k</i> customers in the system."),
                ("<i>A<sub>c</sub></i>, <i>A<sub>s</sub></i>", "Average number of customers waiting in the queue (<i>A<sub>c</sub></i>, labeled <i>L<sub>q</sub></i>) and average number of customers being served (<i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub>&vartheta;&#772;</i>)."),
                ("<i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>) = <i>&pi;<sub>r</sub></i>", "Erlang's C formula giving the congestion probability Pr&#123;<i>k</i> &ge; <i>m</i>&#125; in an <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i> system."),
                ("&Delta;<i>t<sub>k</sub></i>, <i>P&#770;<sub>k</sub></i> = &Delta;<i>t<sub>k</sub></i> / <i>T</i>", "Cumulative duration spent in state <i>k</i>(<i>t</i>) = <i>k</i> during [0, <i>T</i>] (in s) and empirical state probability."),
            ])

            if A_val is not None and not is_unstable and not math.isinf(A_val):
                ana_step = (
                    f"<b>Analytical Calculation ({model_tag}, Eqs. 1&ndash;2):</b> "
                    f"For <i>&lambda;</i> = {lam_val:.2f} cust/s, <i>&mu;</i> = {mu_val:.2f} cust/s, and <i>m</i> = {c_val}, "
                    f"the average number of customers being served is <i>A<sub>s</sub></i> = <b>{As_val:.4f} E</b> and the average number waiting in the queue is <i>A<sub>c</sub></i> = <b>{Ac_val:.4f} E</b>. "
                    f"By Eq. (1): <br><i>A</i> = <i>A<sub>c</sub></i> + <i>A<sub>s</sub></i> = {Ac_val:.4f} + {As_val:.4f} = <b>{A_val:.4f} E (cust)</b>."
                )
            else:
                ana_step = (
                    "<b>Analytical Calculation (Reference <i>&#8499;</i>/<i>&#8499;</i>/1 Benchmark at <i>&rho;</i> = <i>A</i><sub>0</sub> = 0.80 E, Eq. 2):</b> "
                    "With <i>A<sub>s</sub></i> = <i>&rho;</i> = 0.80 E and <i>A<sub>c</sub></i> = <i>&rho;</i><sup>2</sup>/(1 &minus; <i>&rho;</i>) = 3.20 E: "
                    "<br><i>A</i> = <i>A<sub>s</sub></i> + <i>A<sub>c</sub></i> = <i>&rho;</i> / (1 &minus; <i>&rho;</i>) = 0.80 / (1 &minus; 0.80) = <b>4.0000 E (cust)</b>."
                )

            if has_sim_data:
                area_k = A_sim * sim_T
                emp_step = (
                    f"<b>Empirical Simulator Evaluation (Eq. 3, Live Run at <i>T</i> = {sim_T:.2f} s):</b> "
                    f"Integrating <i>k</i>(<i>t</i>) over [0, {sim_T:.2f} s] gives &int; <i>k</i>(<i>t</i>) d<i>t</i> = &sum; <i>k</i>&Delta;<i>t<sub>k</sub></i> = <b>{area_k:.2f} cust&middot;s</b>. "
                    f"Dividing by <i>T</i> = {sim_T:.2f} s yields: "
                    f"<br><i>I</i><sub>sim</sub>(<i>T</i>) = {area_k:.2f} / {sim_T:.2f} = <b>{A_sim:.4f} E (cust)</b>."
                )
            else:
                emp_step = (
                    "<b>Empirical Simulator Evaluation (Eq. 3, Sample-Path Illustration from Course Slides):</b> "
                    "Consider an observation window <i>T</i> = 10.0 s in which <i>k</i>(<i>t</i>) = 0 for 3.0 s, <i>k</i>(<i>t</i>) = 1 for 4.0 s, and <i>k</i>(<i>t</i>) = 2 for 3.0 s. "
                    "Then Eq. (3) gives: <br><i>I</i><sub>sim</sub>(<i>T</i>) = (0&times;3.0 + 1&times;4.0 + 2&times;3.0) / 10.0 = 10.0 / 10.0 = <b>1.0000 E (cust)</b>."
                )

            html = f"""{css}
            <h1>Average Traffic Intensity in the System (<i>A</i> = &langle;<i>k</i>(<i>t</i>)&rangle;, GUI: <i>L</i>)</h1>
            <div class="meta-line">Active Model: {model_tag} &nbsp;|&nbsp; Course Symbol: <i>A</i> (Simulator Label: <i>L</i>)</div>

            <h2>1. Definition and Physical Interpretation</h2>
            <p class="def-paragraph">
                <b>Definition.</b> Let <i>k</i>(<i>t</i>) denote the <i>traffic in the system at time t</i>, defined as the number
                of customers inside the system at time <i>t</i> (resource occupancy). The <b>average traffic intensity in the system</b>,
                denoted <b><i>A</i></b> (and labeled <i>L</i> in the simulator benchmark table), is the time-average value
                <i>A</i> = lim<sub><i>T</i>&rarr;&infin;</sub> <i>I</i>(<i>T</i>) = &langle;<i>k</i>(<i>t</i>)&rangle;.
            </p>
            <p>
                <b>Physical Interpretation.</b> By definition, <i>A</i> is a dimensionless quantity whose unit of measurement is
                the <b>Erlang (E)</b>: 1 Erlang corresponds to an average occupancy of 1 customer in the system. If <i>k</i>(<i>t</i>)
                is ergodic, the time average <i>A</i> = &langle;<i>k</i>(<i>t</i>)&rangle; coincides with the statistical expectation
                &sum; <i>kP<sub>k</sub></i> at a generic instant, and decomposes into the sum of queued customers <i>A<sub>c</sub></i>
                plus customers being served <i>A<sub>s</sub></i>: <b><i>A</i> = <i>A<sub>c</sub></i> + <i>A<sub>s</sub></i></b>.
            </p>

            <h2>2. Mathematical Formulation</h2>
            <p>
                The sample-path average traffic <i>I</i>(<i>T</i>) over interval <i>T</i> and its ergodic steady-state limit <i>A</i> are:
            </p>
            {eq1}
            <p>
                For Markovian <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i> and <i>&#8499;</i>/<i>&#8499;</i>/1 systems with unlimited waiting space (<i>&rho;</i> = <i>A</i><sub>0</sub>/<i>m</i> &lt; 1):
            </p>
            {eq2}
            <p>
                In the discrete-event simulator, <i>I</i><sub>sim</sub>(<i>T</i>) is evaluated continuously by integrating <i>k</i>(<i>t</i>) over [0, <i>T</i>]:
            </p>
            {eq3}
            {params_eq1_eq3}

            <h2>3. Theoretical Properties and Queueing Analysis</h2>
            <ul>
                <li><b>Subsystem Decomposition (<i>A</i> = <i>A<sub>c</sub></i> + <i>A<sub>s</sub></i>):</b> Applying Little's Law to the whole system (<i>A</i> = <i>&lambda;<sub>s</sub>&delta;&#772;</i>), the queue (<i>A<sub>c</sub></i> = <i>&lambda;<sub>s</sub>&eta;&#772;</i>), and the servers (<i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub>&vartheta;&#772;</i>) together with <i>&delta;&#772;</i> = <i>&eta;&#772;</i> + <i>&vartheta;&#772;</i> immediately yields <i>A</i> = <i>A<sub>c</sub></i> + <i>A<sub>s</sub></i>.</li>
                <li><b>Saturation Limit in Finite Queues (<i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i>):</b> In a single-server system with finite queue size <i>L</i>, as offered traffic grows large (<i>A</i><sub>0</sub> &rarr; &infin;), the system remains full almost surely and lim<sub><i>A</i><sub>0</sub>&rarr;&infin;</sub> <i>A</i> = <i>L</i> + 1.</li>
            </ul>

            <h2>4. Worked Numerical Example</h2>
            <div class="example-box">
                <p class="example-title">Example 1 (Analytical and Empirical Evaluation of A)</p>
                <ol>
                    <li>{ana_step}</li>
                    <li>{emp_step}</li>
                </ol>
            </div>

            <h2>5. Analytical vs. Empirical Benchmark Table</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Formula / Estimator</th><th>Value</th></tr>
                <tr><td>Theoretical Average Traffic</td><td><i>A</i> (<i>L</i><sub>theo</sub>)</td><td>&sum; <i>kP<sub>k</sub></i> = <i>A<sub>c</sub></i> + <i>A<sub>s</sub></i></td><td>{A_theo_str}</td></tr>
                <tr><td>Simulated Average Traffic</td><td><i>I</i><sub>sim</sub>(<i>T</i>) (<i>L</i><sub>sim</sub>)</td><td>(1/<i>T</i>) &int; <i>k</i>(<i>t</i>) d<i>t</i></td><td>{A_sim:.4f} E (cust)</td></tr>
                <tr class="bottom-rule"><td>Little's Law Product</td><td><i>&lambda;<sub>s</sub>&delta;&#772;</i> (<i>&lambda;</i><sub>eff</sub><i>W</i>)</td><td><i>&lambda;</i><sub><i>s</i>,sim</sub> &middot; <i>&delta;&#772;</i><sub>sim</sub></td><td>{littles_A:.4f} E (cust)</td></tr>
            </table>
            """
            return title, _format_theory_html(html)

        # ---------------------------------------------------------------
        # Topic 9: Average Customers Waiting in Queue A_c (GUI: Lq)
        # ---------------------------------------------------------------
        elif topic_index == 9:
            Ac_val = theo.get("Lq") if theo else None
            Ac_sim = m_stats.get("Lq", 0.0)
            littles_Ac = m_stats.get("littles_Lq", 0.0)
            A0_val = lam_val * vartheta_bar
            rho_offered = A0_val / c_val

            if is_unstable:
                Ac_theo_str = "&infin; (Unstable)"
            elif Ac_val is None:
                Ac_theo_str = "N/A (No Closed Form)"
            elif math.isinf(Ac_val) or math.isnan(Ac_val):
                Ac_theo_str = "&infin; (Infinite Variance)"
            else:
                Ac_theo_str = f"{Ac_val:.4f} E (cust)"

            eq1 = latex_eq_row(
                r"A_c = \sum_{k=m}^{\infty} (k - m)\,P_k = \mathcal{C}(m, A_0)\,\frac{A_0}{m - A_0}, \qquad \pi_r = \mathrm{Pr}\{k \geq m\} = \frac{A_0^m}{m!}\,\frac{m}{m - A_0}\,P_0 = \mathcal{C}(m, A_0)",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"A_c^{(M/M/1)} = \mathcal{C}(1, A_0)\,\frac{A_0}{1 - A_0} = \frac{\rho^2}{1 - \rho}, \qquad A_c^{(M/M/1/L)} = \frac{-(L + 1)A_0^L(1 - A_0) + 1 - A_0^{L+1}}{(1 - A_0)^2}\,A_0^2 P_0",
                eq_num=2,
                zoom_factor=zoom_factor,
            )
            eq3 = latex_eq_row(
                r"\hat{A}_{c,\mathrm{sim}} = \frac{1}{T} \int_{0}^{T} \max\left(0,\,k(t) - m\right)\mathrm{d}t = \lambda_{s,\mathrm{sim}}\,\overline{\eta}_{\mathrm{sim}}",
                eq_num=3,
                zoom_factor=zoom_factor,
            )

            params_eq1_eq3 = where_list([
                ("<i>A<sub>c</sub></i>", "<b>Average number of customers waiting in the queue</b> (labeled <i>L<sub>q</sub></i> in the simulator), measured in Erlangs (E) or customers."),
                ("<i>k</i>, <i>m</i>", "Total number of customers in the system (<i>k</i>) and number of servers (<i>m</i>); the number of waiting customers in state <i>k</i> &ge; <i>m</i> is (<i>k</i> &minus; <i>m</i>)."),
                ("<i>P<sub>k</sub></i>, <i>P</i><sub>0</sub>", "Steady-state probability of state <i>k</i> and of the empty state <i>k</i> = 0."),
                ("<i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i> = <i>&lambda;</i> / <i>&mu;</i>", "Traffic offered to the system, in Erlangs (E)."),
                ("<i>&pi;<sub>r</sub></i> = Pr&#123;<i>k</i> &ge; <i>m</i>&#125; = <i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>)", "<b>Congestion probability</b> (given by <b>Erlang's C formula</b>), i.e., the probability that an arriving customer finds all <i>m</i> servers busy and joins the queue."),
                ("<i>L</i> (GUI: <i>K</i>)", "Size of the finite waiting space in an <i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i> system (where max <i>k</i>(<i>t</i>) = <i>L</i> + 1)."),
                ("<i>&lambda;<sub>s</sub></i>, <i>&eta;&#772;</i>", "Average rate of admitted customers (cust/s) and average waiting time in the queue (s), linked by Little's Law <i>A<sub>c</sub></i> = <i>&lambda;<sub>s</sub>&eta;&#772;</i>."),
            ])

            if Ac_val is not None and not is_unstable and not math.isinf(Ac_val):
                if math.isinf(K_val) and service_is_exponential and all_arr_exponential:
                    pc_val = theo.get("p_c", rho_offered)
                    ana_step = (
                        f"<b>Analytical Calculation ({model_tag}, Eqs. 1&ndash;2):</b> "
                        f"With offered traffic <i>A</i><sub>0</sub> = {A0_val:.4f} E and <i>m</i> = {c_val}, the Erlang-C congestion probability is "
                        f"<i>&pi;<sub>r</sub></i> = <i>&#8493;</i>({c_val}, {A0_val:.4f}) = <b>{pc_val:.4f}</b>. Applying Eq. (1): "
                        f"<br><i>A<sub>c</sub></i> = <i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>) &middot; <i>A</i><sub>0</sub> / (<i>m</i> &minus; <i>A</i><sub>0</sub>) = "
                        f"{pc_val:.4f} &times; {A0_val:.4f} / ({c_val} &minus; {A0_val:.4f}) = <b>{Ac_val:.4f} E (cust)</b>."
                    )
                else:
                    ana_step = (
                        f"<b>Analytical Calculation ({model_tag}, Eqs. 1&ndash;2):</b> "
                        f"Evaluating the queue backlog expectation for <i>A</i><sub>0</sub> = {A0_val:.4f} E and <i>m</i> = {c_val} gives: "
                        f"<br><i>A<sub>c</sub></i> = &sum;<sub><i>k</i>&ge;{c_val}</sub> (<i>k</i> &minus; {c_val})<i>P<sub>k</sub></i> = <b>{Ac_val:.4f} E (cust)</b>."
                    )
            else:
                ana_step = (
                    "<b>Analytical Calculation (Reference <i>&#8499;</i>/<i>&#8499;</i>/1 Benchmark at <i>&rho;</i> = <i>A</i><sub>0</sub> = 0.80 E, Eq. 2):</b> "
                    "Since <i>&#8493;</i>(1, <i>A</i><sub>0</sub>) = <i>A</i><sub>0</sub> = <i>&rho;</i> = 0.80: "
                    "<br><i>A<sub>c</sub></i> = <i>&rho;</i><sup>2</sup> / (1 &minus; <i>&rho;</i>) = (0.80)<sup>2</sup> / (1 &minus; 0.80) = 0.64 / 0.20 = <b>3.2000 E (cust)</b>."
                )

            if has_sim_data:
                area_q = Ac_sim * sim_T
                emp_step = (
                    f"<b>Empirical Simulator Evaluation (Eq. 3, Live Run at <i>T</i> = {sim_T:.2f} s):</b> "
                    f"Integrating max(0, <i>k</i>(<i>t</i>) &minus; {c_val}) over [0, {sim_T:.2f} s] gives cumulative waiting customer-seconds "
                    f"<b>{area_q:.2f} cust&middot;s</b>. Dividing by <i>T</i> = {sim_T:.2f} s yields: "
                    f"<br><i>A&#770;</i><sub><i>c</i>,sim</sub> = {area_q:.2f} / {sim_T:.2f} = <b>{Ac_sim:.4f} E (cust)</b>."
                )
            else:
                emp_step = (
                    "<b>Empirical Simulator Evaluation (Eq. 3, Sample-Path Illustration):</b> "
                    "Over an observation interval <i>T</i> = 10.0 s with <i>m</i> = 1 server, if max(0, <i>k</i>(<i>t</i>) &minus; 1) equals 0 for 6.0 s, "
                    "1 for 3.0 s, and 2 for 1.0 s, then Eq. (3) yields: "
                    "<br><i>A&#770;</i><sub><i>c</i>,sim</sub> = (0&times;6.0 + 1&times;3.0 + 2&times;1.0) / 10.0 = 5.0 / 10.0 = <b>0.5000 E (cust)</b>."
                )

            html = f"""{css}
            <h1>Average Number of Customers Waiting in the Queue (<i>A<sub>c</sub></i>, GUI: <i>L<sub>q</sub></i>)</h1>
            <div class="meta-line">Active Model: {model_tag} &nbsp;|&nbsp; Course Symbol: <i>A<sub>c</sub></i> (Simulator Label: <i>L<sub>q</sub></i>)</div>

            <h2>1. Definition and Physical Interpretation</h2>
            <p class="def-paragraph">
                <b>Definition.</b> The <b>average number of customers waiting in the queue</b>, denoted <b><i>A<sub>c</sub></i></b>
                (and labeled <i>L<sub>q</sub></i> in the simulator), is the steady-state expected value of the number of customers
                residing in the waiting space, excluding customers currently being served in the <i>m</i> servers.
            </p>
            <p>
                <b>Physical Interpretation.</b> Whenever <i>k</i> &lt; <i>m</i>, all present customers are in service and the queue
                is empty. Whenever <i>k</i> &ge; <i>m</i>, all <i>m</i> servers are busy and (<i>k</i> &minus; <i>m</i>) customers are
                waiting in the queue. By the PASTA property, the probability that an arriving customer finds all servers busy and must
                join the queue is the <b>congestion probability</b> <i>&pi;<sub>r</sub></i> = Pr&#123;<i>k</i> &ge; <i>m</i>&#125; = <i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>),
                given by <b>Erlang's C formula</b>.
            </p>

            <h2>2. Mathematical Formulation</h2>
            <p>
                For an <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i> system with unlimited waiting space (<i>&rho;</i> = <i>A</i><sub>0</sub>/<i>m</i> &lt; 1),
                <i>A<sub>c</sub></i> and Erlang's C formula <i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>) are given by:
            </p>
            {eq1}
            <p>
                For a single-server system with unlimited waiting space (<i>&#8499;</i>/<i>&#8499;</i>/1, where <i>&#8493;</i>(1, <i>A</i><sub>0</sub>) = <i>A</i><sub>0</sub> = <i>&rho;</i>)
                and with limited waiting space <i>L</i> (<i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i>, for <i>A</i><sub>0</sub> &ne; 1):
            </p>
            {eq2}
            <p>
                In the discrete-event simulator, <i>A&#770;</i><sub><i>c</i>,sim</sub> is computed by integrating the instantaneous queue length max(0, <i>k</i>(<i>t</i>) &minus; <i>m</i>) over [0, <i>T</i>]:
            </p>
            {eq3}
            {params_eq1_eq3}

            <h2>3. Theoretical Properties and Queueing Analysis</h2>
            <ul>
                <li><b>Relation Between Erlang's C and Erlang's B Formulas:</b> Erlang's C formula <i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>) can be computed directly from Erlang's B formula <i>&#8492;</i>(<i>m</i>, <i>A</i><sub>0</sub>) via <b><i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>) = <i>m&#8492;</i>(<i>m</i>, <i>A</i><sub>0</sub>) / [<i>m</i> &minus; <i>A</i><sub>0</sub> + <i>A</i><sub>0</sub><i>&#8492;</i>(<i>m</i>, <i>A</i><sub>0</sub>)]</b>.</li>
                <li><b>Pollaczek-Khinchine Generalization for <i>&#8499;</i>/<i>&#119970;</i>/1:</b> When service times follow a general distribution with mean <i>&vartheta;&#772;</i> and residual mean <i>&zeta;&#772;</i> = (<i>&sigma;<sub>&vartheta;</sub></i><sup>2</sup> + <i>&vartheta;&#772;</i><sup>2</sup>)/(2<i>&vartheta;&#772;</i>), Little's Law yields <i>A<sub>c</sub></i> = <i>&lambda;&eta;&#772;</i> = [<i>&rho;</i><sup>2</sup>/(1 &minus; <i>&rho;</i>)] &middot; (<i>&zeta;&#772;</i>/<i>&vartheta;&#772;</i>).</li>
            </ul>

            <h2>4. Worked Numerical Example</h2>
            <div class="example-box">
                <p class="example-title">Example 1 (Analytical and Empirical Evaluation of A<sub>c</sub>)</p>
                <ol>
                    <li>{ana_step}</li>
                    <li>{emp_step}</li>
                </ol>
            </div>

            <h2>5. Analytical vs. Empirical Benchmark Table</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Formula / Estimator</th><th>Value</th></tr>
                <tr><td>Theoretical Average Queue Size</td><td><i>A<sub>c</sub></i> (<i>L</i><sub><i>q</i>,theo</sub>)</td><td>&sum;<sub><i>k</i>&ge;<i>m</i></sub> (<i>k</i> &minus; <i>m</i>)<i>P<sub>k</sub></i></td><td>{Ac_theo_str}</td></tr>
                <tr><td>Simulated Average Queue Size</td><td><i>A&#770;</i><sub><i>c</i>,sim</sub> (<i>L</i><sub><i>q</i>,sim</sub>)</td><td>(1/<i>T</i>) &int; max(0, <i>k</i>(<i>t</i>)&minus;<i>m</i>) d<i>t</i></td><td>{Ac_sim:.4f} E (cust)</td></tr>
                <tr class="bottom-rule"><td>Little's Law Queue Product</td><td><i>&lambda;<sub>s</sub>&eta;&#772;</i> (<i>&lambda;</i><sub>eff</sub><i>W<sub>q</sub></i>)</td><td><i>&lambda;</i><sub><i>s</i>,sim</sub> &middot; <i>&eta;&#772;</i><sub>sim</sub></td><td>{littles_Ac:.4f} E (cust)</td></tr>
            </table>
            """
            return title, _format_theory_html(html)

        # ---------------------------------------------------------------
        # Topic 10: Average Sojourn Time \bar{\delta} (GUI: W)
        # ---------------------------------------------------------------
        elif topic_index == 10:
            delta_val = theo.get("W") if theo else None
            eta_val = theo.get("Wq") if theo else None
            delta_sim = m_stats.get("W", 0.0)
            eta_sim = m_stats.get("Wq", 0.0)
            served_cnt = m_stats.get("served", 0)

            if is_unstable:
                delta_theo_str = "&infin; (Unstable)"
            elif delta_val is None:
                delta_theo_str = "N/A (No Closed Form)"
            elif math.isinf(delta_val) or math.isnan(delta_val):
                delta_theo_str = "&infin; (Infinite Variance)"
            else:
                delta_theo_str = f"{delta_val:.4f} s"

            eq1 = latex_eq_row(
                r"\delta = \eta + \vartheta, \qquad \overline{\delta} = \overline{\eta} + \overline{\vartheta} = \frac{A}{\lambda_s} = \frac{A}{(1 - \pi_p)\lambda}",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\overline{\delta}^{(M/M/m)} = \overline{\vartheta} + \mathcal{C}(m, A_0)\,\frac{\overline{\vartheta}}{m - A_0}, \qquad \overline{\delta}^{(M/M/1)} = \frac{\overline{\vartheta}}{1 - \rho} = \frac{1}{\mu - \lambda}, \qquad f_{\delta}(t) = (\mu - \lambda)e^{-(\mu - \lambda)t}",
                eq_num=2,
                zoom_factor=zoom_factor,
            )
            eq3 = latex_eq_row(
                r"\overline{\delta}_{\mathrm{sim}} = \frac{1}{d(T)} \sum_{n=1}^{d(T)} \delta_n = \frac{1}{d(T)} \sum_{n=1}^{d(T)} \left(t_{\mathrm{dep},n} - t_{\mathrm{arr},n}\right)",
                eq_num=3,
                zoom_factor=zoom_factor,
            )

            params_eq1_eq3 = where_list([
                ("<i>&delta;</i> (<i>&delta;<sub>n</sub></i>)", "Time spent in the system (<b>sojourn time</b>) by a generic customer (or by the <i>n</i>-th customer that has left the system), in seconds (s)."),
                ("<i>&delta;&#772;</i>", "<b>Average sojourn time</b> spent by a customer in the system (labeled <i>W</i> in the simulator), in seconds (s)."),
                ("<i>&eta;</i>, <i>&eta;&#772;</i>", "Time spent in queue (waiting time) by a generic customer and its average value (labeled <i>W<sub>q</sub></i> in the simulator), in seconds (s)."),
                ("<i>&vartheta;</i>, <i>&vartheta;&#772;</i> = 1 / <i>&mu;</i>", "Time spent being served (service time) by a generic customer and its average value, in seconds (s)."),
                ("<i>A</i>, <i>&lambda;<sub>s</sub></i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>&lambda;</i>", "Average traffic in the system (in E) and average rate of admitted customers entering the system (in cust/s)."),
                ("<i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>)", "Erlang's C congestion probability for an <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i> system."),
                ("<i>f<sub>&delta;</sub></i>(<i>t</i>)", "Probability density function of the sojourn time <i>&delta;</i> in a FIFO <i>&#8499;</i>/<i>&#8499;</i>/1 system (for <i>t</i> &gt; 0), which is exponential with rate <i>&mu;</i> &minus; <i>&lambda;</i>."),
                ("<i>d</i>(<i>T</i>)", "Total number of departures from the system up to time <i>T</i> (labeled <i>N</i><sub>served</sub>)."),
            ])

            if delta_val is not None and not is_unstable and not math.isinf(delta_val):
                ana_step = (
                    f"<b>Analytical Calculation ({model_tag}, Eqs. 1&ndash;2):</b> "
                    f"With average waiting time <i>&eta;&#772;</i> = {eta_val:.4f} s and average service time <i>&vartheta;&#772;</i> = 1/{mu_val:.2f} = {vartheta_bar:.4f} s, "
                    f"Eq. (1) yields: <br><i>&delta;&#772;</i> = <i>&eta;&#772;</i> + <i>&vartheta;&#772;</i> = {eta_val:.4f} + {vartheta_bar:.4f} = <b>{delta_val:.4f} s</b>."
                )
            else:
                ana_step = (
                    "<b>Analytical Calculation (Reference <i>&#8499;</i>/<i>&#8499;</i>/1 Benchmark at <i>&lambda;</i> = 0.80 cust/s, <i>&mu;</i> = 1.00 cust/s, Eq. 2):</b> "
                    "With <i>&vartheta;&#772;</i> = 1.00 s and <i>&rho;</i> = 0.80: "
                    "<br><i>&delta;&#772;</i> = <i>&vartheta;&#772;</i> / (1 &minus; <i>&rho;</i>) = 1.00 / (1 &minus; 0.80) = <b>5.0000 s</b> "
                    "(comprising <i>&eta;&#772;</i> = 4.0000 s waiting in queue plus <i>&vartheta;&#772;</i> = 1.0000 s being served)."
                )

            if has_sim_data and served_cnt > 0:
                tot_delta = delta_sim * served_cnt
                emp_step = (
                    f"<b>Empirical Simulator Evaluation (Eq. 3, Live Run with <i>d</i>(<i>T</i>) = {served_cnt} departed customers):</b> "
                    f"Summing the individual sojourn times <i>&delta;<sub>n</sub></i> across all <i>d</i>(<i>T</i>) = {served_cnt} departures gives "
                    f"&sum; <i>&delta;<sub>n</sub></i> = <b>{tot_delta:.2f} s</b>. Dividing by <i>d</i>(<i>T</i>) yields: "
                    f"<br><i>&delta;&#772;</i><sub>sim</sub> = {tot_delta:.2f} / {served_cnt} = <b>{delta_sim:.4f} s</b>."
                )
            else:
                emp_step = (
                    "<b>Empirical Simulator Evaluation (Eq. 3, Illustrative Sample of <i>d</i>(<i>T</i>) = 3 Departures):</b> "
                    "Suppose the first <i>d</i>(<i>T</i>) = 3 customers experience sojourn times <i>&delta;</i><sub>1</sub> = 0.90 s, <i>&delta;</i><sub>2</sub> = 1.40 s, and <i>&delta;</i><sub>3</sub> = 1.50 s. "
                    "By Eq. (3): <br><i>&delta;&#772;</i><sub>sim</sub> = (0.90 + 1.40 + 1.50) / 3 = 3.80 / 3 = <b>1.2667 s</b>."
                )

            html = f"""{css}
            <h1>Average Sojourn Time in the System (<i>&delta;&#772;</i>, GUI: <i>W</i>)</h1>
            <div class="meta-line">Active Model: {model_tag} &nbsp;|&nbsp; Course Symbol: <i>&delta;&#772;</i> (Simulator Label: <i>W</i>)</div>

            <h2>1. Definition and Physical Interpretation</h2>
            <p class="def-paragraph">
                <b>Definition.</b> Let <i>&delta;</i> denote the <b>sojourn time</b> (time spent in the system) of a generic
                admitted customer from the instant it enters the system and joins the queue until its service is completed and it
                leaves the system. Its statistical average is denoted <b><i>&delta;&#772;</i></b> (and labeled <i>W</i> in the simulator).
            </p>
            <p>
                <b>Physical Interpretation.</b> Because the transfer time from the queue to a free server is negligible, the
                sojourn time <i>&delta;</i> of every admitted customer is the sum of its waiting time in the queue <i>&eta;</i>
                plus its service time <i>&vartheta;</i>: <b><i>&delta;</i> = <i>&eta;</i> + <i>&vartheta;</i></b>.
            </p>

            <h2>2. Mathematical Formulation</h2>
            <p>
                Taking the expectation of <i>&delta;</i> = <i>&eta;</i> + <i>&vartheta;</i> and applying Little's Law (<i>A</i> = <i>&lambda;<sub>s</sub>&delta;&#772;</i>) yields:
            </p>
            {eq1}
            <p>
                For Markovian <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i> and FIFO <i>&#8499;</i>/<i>&#8499;</i>/1 systems with unlimited waiting space (<i>&rho;</i> &lt; 1):
            </p>
            {eq2}
            <p>
                In the discrete-event simulator, <i>&delta;&#772;</i><sub>sim</sub> is evaluated over all <i>d</i>(<i>T</i>) customers that have departed up to time <i>T</i>:
            </p>
            {eq3}
            {params_eq1_eq3}

            <h2>3. Theoretical Properties and Queueing Analysis</h2>
            <ul>
                <li><b>Sojourn Time Distribution in FIFO <i>&#8499;</i>/<i>&#8499;</i>/1:</b> Under a FIFO queueing policy, the sojourn time <i>&delta;</i> in an <i>&#8499;</i>/<i>&#8499;</i>/1 queue is exponentially distributed with parameter (<i>&mu;</i> &minus; <i>&lambda;</i>), so <i>f<sub>&delta;</sub></i>(<i>t</i>) = (<i>&mu;</i> &minus; <i>&lambda;</i>)<i>e</i><sup>&minus;(<i>&mu;</i>&minus;<i>&lambda;</i>)<i>t</i></sup> and <i>F<sub>&delta;</sub></i>(<i>t</i>) = 1 &minus; <i>e</i><sup>&minus;(<i>&mu;</i>&minus;<i>&lambda;</i>)<i>t</i></sup> for <i>t</i> &gt; 0.</li>
                <li><b>Comparing <i>&#8499;</i>/<i>&#8499;</i>/1 and <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i> Systems:</b> When comparing a single fast server of rate <i>m&mu;</i> against <i>m</i> slow servers each of rate <i>&mu;</i> under the same offered arrival rate <i>&lambda;</i> (same <i>&rho;</i>), the single fast server achieves a smaller average sojourn time <i>&delta;&#772;</i> because resources are never left idle while customers are present.</li>
            </ul>

            <h2>4. Worked Numerical Example</h2>
            <div class="example-box">
                <p class="example-title">Example 1 (Analytical and Empirical Evaluation of &delta;&#772;)</p>
                <ol>
                    <li>{ana_step}</li>
                    <li>{emp_step}</li>
                </ol>
            </div>

            <h2>5. Analytical vs. Empirical Benchmark Table</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Formula / Estimator</th><th>Value</th></tr>
                <tr><td>Theoretical Average Sojourn Time</td><td><i>&delta;&#772;</i> (<i>W</i><sub>theo</sub>)</td><td><i>&eta;&#772;</i> + <i>&vartheta;&#772;</i> = <i>A</i> / <i>&lambda;<sub>s</sub></i></td><td>{delta_theo_str}</td></tr>
                <tr><td>Simulated Average Sojourn Time</td><td><i>&delta;&#772;</i><sub>sim</sub> (<i>W</i><sub>sim</sub>)</td><td>[1/<i>d</i>(<i>T</i>)] &sum; <i>&delta;<sub>n</sub></i></td><td>{delta_sim:.4f} s</td></tr>
                <tr class="bottom-rule"><td>Simulated Time Decomposition</td><td><i>&eta;&#772;</i><sub>sim</sub> + <i>&vartheta;&#772;</i></td><td>{eta_sim:.4f} s + {vartheta_bar:.4f} s</td><td>{eta_sim + vartheta_bar:.4f} s</td></tr>
            </table>
            """
            return title, _format_theory_html(html)

        # ---------------------------------------------------------------
        # Topic 11: Average Waiting Time in Queue \bar{\eta} and \bar{\varepsilon} (GUI: Wq)
        # ---------------------------------------------------------------
        elif topic_index == 11:
            eta_val = theo.get("Wq") if theo else None
            eta_sim = m_stats.get("Wq", 0.0)
            served_cnt = m_stats.get("served", 0)
            A0_val = lam_val * vartheta_bar
            rho_offered = A0_val / c_val

            if is_unstable:
                eta_theo_str = "&infin; (Unstable)"
                disc_str = "Divergent"
            elif eta_val is None:
                eta_theo_str = "N/A (No Closed Form)"
                disc_str = "-"
            elif math.isinf(eta_val) or math.isnan(eta_val):
                eta_theo_str = "&infin; (Infinite Variance)"
                disc_str = "Divergent"
            else:
                eta_theo_str = f"{eta_val:.4f} s"
                disc_str = f"{abs(eta_sim - eta_val):.4f} s"

            eq1 = latex_eq_row(
                r"\overline{\eta} = \frac{A_c}{\lambda_s} = \mathcal{C}(m, A_0)\,\frac{\overline{\vartheta}}{m - A_0}, \qquad \overline{\varepsilon} = \frac{A_{c \mid k \geq m}}{\lambda} = \frac{\overline{\eta}}{\mathcal{C}(m, A_0)} = \frac{\overline{\vartheta}}{m - A_0}",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"f_{\eta}(t) = \delta(t)\left(1 - \mathcal{C}(m, A_0)\right) + \mathcal{C}(m, A_0)(m\mu - \lambda)e^{-(m\mu - \lambda)t}, \qquad F_{\eta}(t) = 1 - \mathcal{C}(m, A_0)e^{-(m\mu - \lambda)t} \;\; (t > 0)",
                eq_num=2,
                zoom_factor=zoom_factor,
            )
            eq3 = latex_eq_row(
                r"\overline{\eta}^{(M/G/1)} = \frac{\lambda\,\mathrm{E}[\vartheta^2]}{2(1 - \rho)} = \frac{\rho}{1 - \rho}\,\overline{\zeta}, \qquad \overline{\eta}_{\mathrm{sim}} = \frac{1}{d(T)} \sum_{n=1}^{d(T)} \eta_n = \frac{1}{d(T)} \sum_{n=1}^{d(T)} \left(t_{\mathrm{start},n} - t_{\mathrm{arr},n}\right)",
                eq_num=3,
                zoom_factor=zoom_factor,
            )

            params_eq1_eq3 = where_list([
                ("<i>&eta;</i>, <i>&eta;&#772;</i>", "Waiting time in the queue for a <b>generic admitted customer</b> (including those that find a server free and do not wait, <i>&eta;</i> = 0) and its average value (labeled <i>W<sub>q</sub></i> in the simulator), in seconds (s)."),
                ("<i>&varepsilon;</i>, <i>&varepsilon;&#772;</i>", "Waiting time in the queue for a customer that <b>actually joins the queue</b> (conditioned on <i>k</i> &ge; <i>m</i>) and its average value, in seconds (s)."),
                ("<i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>) = <i>&pi;<sub>r</sub></i>", "Erlang's C congestion probability Pr&#123;<i>k</i> &ge; <i>m</i>&#125;."),
                ("<i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i>, <i>m</i>", "Offered traffic (in Erlangs) and number of servers."),
                ("<i>&delta;</i>(<i>t</i>)", "Dirac delta impulse at <i>t</i> = 0 in <i>f<sub>&eta;</sub></i>(<i>t</i>), accounting for the probability 1 &minus; <i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>) that an arriving customer finds a free server and experiences zero waiting time."),
                ("<i>&zeta;&#772;</i> = (<i>&sigma;<sub>&vartheta;</sub></i><sup>2</sup> + <i>&vartheta;&#772;</i><sup>2</sup>)/(2<i>&vartheta;&#772;</i>)", "Mean residual service time in an <i>&#8499;</i>/<i>&#119970;</i>/1 queue, in seconds (s)."),
                ("<i>d</i>(<i>T</i>), <i>&eta;<sub>n</sub></i>", "Total customers served up to time <i>T</i> and waiting time <i>t</i><sub>start,<i>n</i></sub> &minus; <i>t</i><sub>arr,<i>n</i></sub> of the <i>n</i>-th served customer."),
            ])

            if eta_val is not None and not is_unstable and not math.isinf(eta_val):
                if math.isinf(K_val) and service_is_exponential and all_arr_exponential and A0_val < c_val:
                    eps_bar = vartheta_bar / (c_val - A0_val)
                    pc_val = theo.get("p_c", rho_offered)
                    ana_step = (
                        f"<b>Analytical Calculation ({model_tag}, Eq. 1):</b> "
                        f"With <i>A</i><sub>0</sub> = {A0_val:.4f} E, <i>m</i> = {c_val}, <i>&vartheta;&#772;</i> = {vartheta_bar:.4f} s, and Erlang-C probability <i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>) = {pc_val:.4f}: "
                        f"<br>&bull; Average waiting time for a <i>generic</i> customer: <i>&eta;&#772;</i> = {pc_val:.4f} &times; {vartheta_bar:.4f} / ({c_val} &minus; {A0_val:.4f}) = <b>{eta_val:.4f} s</b>. "
                        f"<br>&bull; Average waiting time for a customer that <i>actually joins the queue</i>: <i>&varepsilon;&#772;</i> = <i>&vartheta;&#772;</i> / (<i>m</i> &minus; <i>A</i><sub>0</sub>) = {vartheta_bar:.4f} / ({c_val} &minus; {A0_val:.4f}) = <b>{eps_bar:.4f} s</b>."
                    )
                else:
                    ana_step = (
                        f"<b>Analytical Calculation ({model_tag}, Eqs. 1 &amp; 3):</b> "
                        f"Evaluating the analytical model for <i>&lambda;</i> = {lam_val:.2f} cust/s and <i>&mu;</i> = {mu_val:.2f} cust/s gives: "
                        f"<br><i>&eta;&#772;</i> = <i>A<sub>c</sub></i> / <i>&lambda;<sub>s</sub></i> = <b>{eta_val:.4f} s</b>."
                    )
            else:
                ana_step = (
                    "<b>Analytical Calculation (Reference <i>&#8499;</i>/<i>&#8499;</i>/1 Benchmark at <i>&vartheta;&#772;</i> = 1.00 s, <i>&rho;</i> = 0.80, Eq. 1):</b> "
                    "<br>&bull; Generic customer: <i>&eta;&#772;</i> = <i>&vartheta;&#772;</i> &middot; <i>&rho;</i> / (1 &minus; <i>&rho;</i>) = 1.00 &times; 0.80 / 0.20 = <b>4.0000 s</b>. "
                    "<br>&bull; Customer that joins the queue: <i>&varepsilon;&#772;</i> = <i>&vartheta;&#772;</i> / (1 &minus; <i>&rho;</i>) = 1.00 / 0.20 = <b>5.0000 s</b>."
                )

            if has_sim_data and served_cnt > 0:
                tot_eta = eta_sim * served_cnt
                emp_step = (
                    f"<b>Empirical Simulator Evaluation (Eq. 3, Live Run with <i>d</i>(<i>T</i>) = {served_cnt} served customers):</b> "
                    f"Summing <i>&eta;<sub>n</sub></i> = <i>t</i><sub>start,<i>n</i></sub> &minus; <i>t</i><sub>arr,<i>n</i></sub> over all {served_cnt} completed customers gives "
                    f"&sum; <i>&eta;<sub>n</sub></i> = <b>{tot_eta:.2f} s</b>. Dividing by <i>d</i>(<i>T</i>) yields: "
                    f"<br><i>&eta;&#772;</i><sub>sim</sub> = {tot_eta:.2f} / {served_cnt} = <b>{eta_sim:.4f} s</b>."
                )
            else:
                emp_step = (
                    "<b>Empirical Simulator Evaluation (Eq. 3, Illustrative Sample of <i>d</i>(<i>T</i>) = 3 Customers):</b> "
                    "If the first 3 served customers experience waiting times <i>&eta;</i><sub>1</sub> = 0.00 s, <i>&eta;</i><sub>2</sub> = 0.20 s, and <i>&eta;</i><sub>3</sub> = 0.60 s, then Eq. (3) gives: "
                    "<br><i>&eta;&#772;</i><sub>sim</sub> = (0.00 + 0.20 + 0.60) / 3 = 0.80 / 3 = <b>0.2667 s</b>."
                )

            html = f"""{css}
            <h1>Average Waiting Time in the Queue (<i>&eta;&#772;</i> and <i>&varepsilon;&#772;</i>, GUI: <i>W<sub>q</sub></i>)</h1>
            <div class="meta-line">Active Model: {model_tag} &nbsp;|&nbsp; Course Symbols: <i>&eta;&#772;</i> (Generic Customer) and <i>&varepsilon;&#772;</i> (Queued Customer)</div>

            <h2>1. Definition and Physical Interpretation</h2>
            <p class="def-paragraph">
                <b>Definition.</b> Course notation distinguishes between two waiting-time random variables:
                (i) <b><i>&eta;</i></b> (with mean <b><i>&eta;&#772;</i></b>, labeled <i>W<sub>q</sub></i> in the simulator), which is the
                waiting time in the queue for a <i>generic entering customer</i> (including those that find an idle server and have
                <i>&eta;</i> = 0); and (ii) <b><i>&varepsilon;</i></b> (with mean <b><i>&varepsilon;&#772;</i></b>), which is the waiting time
                for a customer that <i>actually joins the queue</i> (conditioned on <i>k</i> &ge; <i>m</i>).
            </p>

            <h2>2. Mathematical Formulation</h2>
            <p>
                In an <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i> system with unlimited waiting space (<i>A</i><sub>0</sub> &lt; <i>m</i>),
                the unconditional average waiting time <i>&eta;&#772;</i> and conditional average waiting time <i>&varepsilon;&#772;</i> are:
            </p>
            {eq1}
            <p>
                Under a <b>FIFO queueing policy</b>, the PDF and CDF of <i>&eta;</i> (factoring in the Dirac delta impulse <i>&delta;</i>(<i>t</i>) at <i>t</i> = 0) are:
            </p>
            {eq2}
            <p>
                whereas for a customer that actually joins the queue, <i>f<sub>&varepsilon;</sub></i>(<i>t</i>) = (<i>m&mu;</i> &minus; <i>&lambda;</i>)<i>e</i><sup>&minus;(<i>m&mu;</i>&minus;<i>&lambda;</i>)<i>t</i></sup> and <i>F<sub>&varepsilon;</sub></i>(<i>t</i>) = 1 &minus; <i>e</i><sup>&minus;(<i>m&mu;</i>&minus;<i>&lambda;</i>)<i>t</i></sup> (<i>t</i> &gt; 0).
                For a general single-server <i>&#8499;</i>/<i>&#119970;</i>/1 queue and for the discrete-event simulator:
            </p>
            {eq3}
            {params_eq1_eq3}

            <h2>3. Theoretical Properties and System Dimensioning</h2>
            <ul>
                <li><b>System Dimensioning Based on Average Waiting Time:</b> To guarantee <i>&eta;&#772;</i> &le; <i>&eta;</i><sub>0</sub> for a generic customer, the number of servers must satisfy <b><i>m</i> &ge; <i>A</i><sub>0</sub> + <i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>)<i>&vartheta;&#772;</i>/<i>&eta;</i><sub>0</sub></b>. To guarantee <i>&varepsilon;&#772;</i> &le; <i>&varepsilon;</i><sub>0</sub> for queued customers, <b><i>m</i> &ge; <i>A</i><sub>0</sub> + <i>&vartheta;&#772;</i>/<i>&varepsilon;</i><sub>0</sub></b>. Note that average waiting time formulas hold for <i>any</i> work-conserving queueing policy, not necessarily FIFO.</li>
                <li><b>System Dimensioning Based on Waiting Time Distribution (FIFO):</b> Under FIFO, to guarantee Pr(<i>&eta;</i> &le; <i>&eta;</i><sub>0</sub>) &ge; <i>&pi;</i><sub>0</sub>, we require <b><i>m</i> &ge; <i>A</i><sub>0</sub> + (<i>&vartheta;&#772;</i>/<i>&eta;</i><sub>0</sub>) ln[<i>&#8493;</i>(<i>m</i>, <i>A</i><sub>0</sub>)/(1 &minus; <i>&pi;</i><sub>0</sub>)]</b>.</li>
            </ul>

            <h2>4. Worked Numerical Example</h2>
            <div class="example-box">
                <p class="example-title">Example 1 (Analytical and Empirical Evaluation of &eta;&#772; and &varepsilon;&#772;)</p>
                <ol>
                    <li>{ana_step}</li>
                    <li>{emp_step}</li>
                </ol>
            </div>

            <h2>5. Analytical vs. Empirical Benchmark Table</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Formula / Estimator</th><th>Value</th></tr>
                <tr><td>Theoretical Generic Waiting Time</td><td><i>&eta;&#772;</i> (<i>W</i><sub><i>q</i>,theo</sub>)</td><td><i>A<sub>c</sub></i> / <i>&lambda;<sub>s</sub></i> (Eq. 1)</td><td>{eta_theo_str}</td></tr>
                <tr><td>Simulated Generic Waiting Time</td><td><i>&eta;&#772;</i><sub>sim</sub> (<i>W</i><sub><i>q</i>,sim</sub>)</td><td>[1/<i>d</i>(<i>T</i>)] &sum; <i>&eta;<sub>n</sub></i></td><td>{eta_sim:.4f} s</td></tr>
                <tr class="bottom-rule"><td>Absolute Convergence Discrepancy</td><td>|<i>&eta;&#772;</i><sub>sim</sub> &minus; <i>&eta;&#772;</i>|</td><td>Empirical error</td><td>{disc_str}</td></tr>
            </table>
            """
            return title, _format_theory_html(html)

        # ---------------------------------------------------------------
        # Topic 12: Blocking Probability \pi_p (GUI: P_loss)
        # ---------------------------------------------------------------
        elif topic_index == 12:
            pi_p_theo = theo.get("p_loss", 0.0) if theo else None
            pi_p_theo_str = f"{pi_p_theo*100.0:.2f}% ({pi_p_theo:.4f})" if pi_p_theo is not None else "N/A (No Closed Form)"
            pi_p_sim = m_stats.get("p_loss", 0.0)
            arr_tot = m_stats.get("arrived", 0)
            drop_tot = m_stats.get("dropped", 0)
            A0_val = lam_val * vartheta_bar
            rho_offered = A0_val / c_val

            eq1 = latex_eq_row(
                r"\pi_p = P_m = \frac{A_0^m / m!}{\sum_{k=0}^{m} A_0^k / k!} = \mathcal{B}(m, A_0), \qquad \mathcal{B}(m, A_0) = \frac{A_0\,\mathcal{B}(m - 1, A_0)}{m + A_0\,\mathcal{B}(m - 1, A_0)}, \quad \mathcal{B}(0, A_0) = 1",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\pi_p^{(M/M/1/L)} = P_{L+1} = \frac{1 - A_0}{1 - A_0^{L+2}}\,A_0^{L+1} \;\; (A_0 \neq 1), \qquad \pi_p^{(M/M/1/L)} = \frac{1}{L + 2} \;\; (A_0 = 1)",
                eq_num=2,
                zoom_factor=zoom_factor,
            )
            eq3 = latex_eq_row(
                r"\lambda_p = \pi_p \lambda, \qquad A_p = \pi_p A_0, \qquad \hat{\pi}_{p,\mathrm{sim}} = \frac{a_p(T)}{a(T)} = \frac{N_{\mathrm{dropped}}}{N_{\mathrm{arrived}}}",
                eq_num=3,
                zoom_factor=zoom_factor,
            )

            params_eq1_eq3 = where_list([
                ("<i>&pi;<sub>p</sub></i>", "<b>Blocking probability</b> (probability of a customer being rejected upon arrival, labeled <i>P</i><sub>loss</sub> in the simulator)."),
                ("<i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i> = <i>&lambda;</i> / <i>&mu;</i>", "Traffic offered to the system, in Erlangs (E)."),
                ("<i>m</i>", "Number of parallel servers in the system."),
                ("<i>&#8492;</i>(<i>m</i>, <i>A</i><sub>0</sub>)", "<b>Erlang's B formula</b> giving the exact blocking probability in a loss system without waiting space (<i>&#8499;</i>/<i>&#8499;</i>/<i>m</i>/0 and more generally <i>&#8499;</i>/<i>&#119970;</i>/<i>m</i>/0)."),
                ("<i>L</i> (GUI: <i>K</i>)", "Queue waiting space capacity in a single-server <i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i> system (total system capacity is <i>L</i> + 1)."),
                ("<i>P<sub>m</sub></i>, <i>P</i><sub><i>L</i>+1</sub>", "Steady-state probability of the full-system state where all servers and waiting slots are occupied."),
                ("<i>&lambda;<sub>p</sub></i>, <i>A<sub>p</sub></i>", "Average rate of rejected customers (cust/s) and rejected traffic (in E)."),
                ("<i>a</i>(<i>T</i>), <i>a<sub>p</sub></i>(<i>T</i>)", "Cumulative arrivals and cumulative rejected arrivals up to time <i>T</i>."),
            ])

            if pi_p_theo is not None and not math.isinf(K_val):
                p0_v = theo.get("p0", 0.0)
                L_int = int(K_val)
                if c_val == 1:
                    ana_step = (
                        f"<b>Analytical Calculation (<i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i> with <i>L</i> = {L_int}, Eq. 2):</b> "
                        f"With offered traffic <i>A</i><sub>0</sub> = {A0_val:.4f} E and waiting space <i>L</i> = {L_int} (full state <i>k</i> = <i>L</i> + 1 = {L_int + 1}), "
                        f"Eq. (2) gives <i>P</i><sub>0</sub> = {p0_v:.5f} and blocking probability: "
                        f"<br><i>&pi;<sub>p</sub></i> = <i>P</i><sub>{L_int + 1}</sub> = <i>P</i><sub>0</sub><i>A</i><sub>0</sub><sup>{L_int + 1}</sup> = {p0_v:.5f} &times; ({A0_val:.4f})<sup>{L_int + 1}</sup> = <b>{pi_p_theo:.4f}</b> ({pi_p_theo*100:.2f}%)."
                    )
                else:
                    ana_step = (
                        f"<b>Analytical Calculation ({model_tag} with <i>L</i> = {L_int}, Eqs. 1&ndash;2):</b> "
                        f"With <i>A</i><sub>0</sub> = {A0_val:.4f} E, <i>m</i> = {c_val}, and <i>L</i> = {L_int}, the full-system state is <i>k</i> = <i>m</i> + <i>L</i> = {c_val + L_int}, yielding: "
                        f"<br><i>&pi;<sub>p</sub></i> = <i>P</i><sub>{c_val + L_int}</sub> = <b>{pi_p_theo:.4f}</b> ({pi_p_theo*100:.2f}%)."
                    )
            else:
                ana_step = (
                    "<b>Analytical Calculation (Reference <i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i> Benchmark with <i>L</i> = 3, <i>A</i><sub>0</sub> = 0.80 E, Eq. 2):</b> "
                    "When waiting space is unlimited (<i>L</i> = &infin;), <i>&pi;<sub>p</sub></i> = 0. For a finite queue with <i>L</i> = 3 and <i>A</i><sub>0</sub> = 0.80 E, Eq. (2) gives: "
                    "<br><i>P</i><sub>0</sub> = (1 &minus; 0.80) / (1 &minus; 0.80<sup>5</sup>) = 0.2975, and <i>&pi;<sub>p</sub></i> = <i>P</i><sub>4</sub> = 0.2975 &times; 0.80<sup>4</sup> = <b>0.1219</b> (12.19%)."
                )

            if has_sim_data and arr_tot > 0:
                emp_step = (
                    f"<b>Empirical Simulator Evaluation (Eq. 3, Live Run with <i>a</i>(<i>T</i>) = {arr_tot} arrivals):</b> "
                    f"Out of <i>a</i>(<i>T</i>) = {arr_tot} total arrivals, <i>a<sub>p</sub></i>(<i>T</i>) = {drop_tot} found the system full and were rejected: "
                    f"<br><i>&pi;&#770;</i><sub><i>p</i>,sim</sub> = {drop_tot} / {arr_tot} = <b>{pi_p_sim:.4f}</b> ({pi_p_sim*100:.2f}%)."
                )
            else:
                emp_step = (
                    "<b>Empirical Simulator Evaluation (Eq. 3, Illustrative Sample Run):</b> "
                    "If <i>a</i>(<i>T</i>) = 500 customers arrive during interval <i>T</i> and <i>a<sub>p</sub></i>(<i>T</i>) = 18 are rejected because the queue is full, then Eq. (3) yields: "
                    "<br><i>&pi;&#770;</i><sub><i>p</i>,sim</sub> = 18 / 500 = <b>0.0360</b> (3.60%)."
                )

            html = f"""{css}
            <h1>Blocking Probability (<i>&pi;<sub>p</sub></i>, GUI: <i>P</i><sub>loss</sub>)</h1>
            <div class="meta-line">Active Model: {model_tag} &nbsp;|&nbsp; Course Symbol: <i>&pi;<sub>p</sub></i> (Simulator Label: <i>P</i><sub>loss</sub>)</div>

            <h2>1. Definition and Physical Interpretation</h2>
            <p class="def-paragraph">
                <b>Definition.</b> In a queueing system without waiting space (<i>&#8499;</i>/<i>&#8499;</i>/<i>m</i>/0) or with
                limited waiting space (<i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i>), an arriving customer that finds all servers busy
                and no free queue space is rejected and does not enter the system. The <b>blocking probability</b>
                <b><i>&pi;<sub>p</sub></i></b> is the probability that an arriving customer is rejected.
            </p>
            <p>
                <b>Physical Interpretation.</b> By the PASTA property (Poisson Arrivals See Time Averages), for Poisson arrivals
                the blocking probability <i>&pi;<sub>p</sub></i> coincides with the steady-state probability that the system is in the
                full boundary state (<i>P<sub>m</sub></i> for <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i>/0, or <i>P</i><sub><i>L</i>+1</sub> for <i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i>).
            </p>

            <h2>2. Mathematical Formulation</h2>
            <p>
                <b>Real System Without Waiting Space (<i>&#8499;</i>/<i>&#8499;</i>/<i>m</i>/0 &mdash; Erlang's B Formula).</b>
                When <i>L</i> = 0, <i>&pi;<sub>p</sub></i> is given by <b>Erlang's B formula</b> <i>&#8492;</i>(<i>m</i>, <i>A</i><sub>0</sub>),
                which can also be evaluated recursively without factorial overflow:
            </p>
            {eq1}
            <p>
                <b>Single-Server System With Limited Waiting Space (<i>&#8499;</i>/<i>&#8499;</i>/1/<i>L</i>).</b>
                When the queue can hold up to <i>L</i> waiting customers (so max <i>k</i>(<i>t</i>) = <i>L</i> + 1), steady-state probabilities
                are <i>P<sub>k</sub></i> = <i>P</i><sub>0</sub><i>A</i><sub>0</sub><sup><i>k</i></sup> (0 &le; <i>k</i> &le; <i>L</i> + 1), yielding:
            </p>
            {eq2}
            <p>
                The rejected arrival rate <i>&lambda;<sub>p</sub></i>, rejected traffic <i>A<sub>p</sub></i>, and empirical blocking ratio are:
            </p>
            {eq3}
            {params_eq1_eq3}

            <h2>3. Theoretical Properties and Queueing Analysis</h2>
            <ul>
                <li><b>Insensitivity of Erlang's B Formula (<i>&#8499;</i>/<i>&#119970;</i>/<i>m</i>/0):</b> It can be proved that Erlang's B formula <i>&#8492;</i>(<i>m</i>, <i>A</i><sub>0</sub>) does not depend on the probability distribution of the service time <i>&vartheta;</i>, but only on its mean value <i>&vartheta;&#772;</i> (through <i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i>). Thus, <i>&#8492;</i>(<i>m</i>, <i>A</i><sub>0</sub>) is the exact blocking probability of any <i>&#8499;</i>/<i>&#119970;</i>/<i>m</i>/0 loss system.</li>
                <li><b>Sensitivity to Overload in Large Systems:</b> While larger multi-server systems (larger <i>m</i>) achieve higher server utilization <i>&rho;</i> for a fixed blocking probability (trunking efficiency), they are steeper and more sensitive to percentage fluctuations in offered traffic <i>A</i><sub>0</sub>.</li>
            </ul>

            <h2>4. Worked Numerical Example</h2>
            <div class="example-box">
                <p class="example-title">Example 1 (Analytical and Empirical Evaluation of &pi;<sub>p</sub>)</p>
                <ol>
                    <li>{ana_step}</li>
                    <li>{emp_step}</li>
                </ol>
            </div>

            <h2>5. Analytical vs. Empirical Benchmark Table</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Formula / Estimator</th><th>Value</th></tr>
                <tr><td>Theoretical Blocking Probability</td><td><i>&pi;<sub>p</sub></i> (<i>P</i><sub>loss,theo</sub>)</td><td><i>P</i><sub>full</sub> (Eqs. 1&ndash;2)</td><td>{pi_p_theo_str}</td></tr>
                <tr><td>Simulated Blocking Probability</td><td><i>&pi;&#770;</i><sub><i>p</i>,sim</sub> (<i>P</i><sub>loss,sim</sub>)</td><td><i>a<sub>p</sub></i>(<i>T</i>) / <i>a</i>(<i>T</i>)</td><td>{pi_p_sim*100.0:.2f}% ({pi_p_sim:.4f})</td></tr>
                <tr class="bottom-rule"><td>Rejected / Total Arrivals</td><td><i>a<sub>p</sub></i>(<i>T</i>) / <i>a</i>(<i>T</i>)</td><td>Event counters</td><td>{drop_tot:,} / {arr_tot:,} cust</td></tr>
            </table>
            """
            return title, _format_theory_html(html)

        # ---------------------------------------------------------------
        # Topic 13: Little's Law A = \lambda_s \bar{\delta} (GUI: L_diff)
        # ---------------------------------------------------------------
        elif topic_index == 13:
            A_sim = m_stats.get("L", 0.0)
            Ac_sim = m_stats.get("Lq", 0.0)
            delta_sim = m_stats.get("W", 0.0)
            eta_sim = m_stats.get("Wq", 0.0)
            lam_s_sim = m_stats.get("lambda_eff", 0.0)
            littles_A = m_stats.get("littles_L", 0.0)
            littles_Ac = m_stats.get("littles_Lq", 0.0)
            littles_err = m_stats.get("littles_error_L", 0.0)

            eq1 = latex_eq_row(
                r"A = \lambda\,\overline{\delta} \quad (\text{Lossless System}), \qquad A = \lambda_s\,\overline{\delta}, \qquad A_c = \lambda_s\,\overline{\eta}, \qquad A_s = \lambda_s\,\overline{\vartheta}",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\overline{\delta} = \overline{\eta} + \overline{\vartheta} \quad \Longrightarrow \quad A = \lambda_s\left(\overline{\eta} + \overline{\vartheta}\right) = A_c + A_s",
                eq_num=2,
                zoom_factor=zoom_factor,
            )
            eq3 = latex_eq_row(
                r"L_{\mathrm{diff}} = \left| I_{\mathrm{sim}}(T) - \lambda_{s,\mathrm{sim}}\,\overline{\delta}_{\mathrm{sim}} \right| \longrightarrow 0 \quad (T \to \infty)",
                eq_num=3,
                zoom_factor=zoom_factor,
            )

            params_eq1_eq3 = where_list([
                ("<i>A</i> = &langle;<i>k</i>(<i>t</i>)&rangle;", "Average traffic intensity in the whole system (average number of customers in the system, labeled <i>L</i> in the simulator), in Erlangs (E)."),
                ("<i>A<sub>c</sub></i>, <i>A<sub>s</sub></i>", "Average number of customers waiting in the queue (<i>A<sub>c</sub></i>, labeled <i>L<sub>q</sub></i>) and average number of customers being served (<i>A<sub>s</sub></i> = <i>m&rho;</i>), in Erlangs (E)."),
                ("<i>&lambda;</i>, <i>&lambda;<sub>s</sub></i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>&lambda;</i>", "Average arrival rate offered to the system (<i>&lambda;</i>) and average rate of customers entering (admitted to) the system (<i>&lambda;<sub>s</sub></i>, labeled <i>&lambda;</i><sub>eff</sub> in the simulator), in customers per second (cust/s)."),
                ("<i>&delta;&#772;</i>, <i>&eta;&#772;</i>, <i>&vartheta;&#772;</i>", "Average sojourn time in the system (<i>&delta;&#772;</i>, labeled <i>W</i>), average waiting time in the queue (<i>&eta;&#772;</i>, labeled <i>W<sub>q</sub></i>), and average service time (<i>&vartheta;&#772;</i> = 1/<i>&mu;</i>), in seconds (s)."),
                ("<i>L</i><sub>diff</sub>", "Absolute discrepancy between the time-average traffic integral <i>I</i><sub>sim</sub>(<i>T</i>) and the Little's Law product <i>&lambda;</i><sub><i>s</i>,sim</sub><i>&delta;&#772;</i><sub>sim</sub> over finite simulation time <i>T</i>."),
            ])

            if has_sim_data:
                admitted_cnt = m_stats.get("arrived", 0) - m_stats.get("dropped", 0)
                example_body = f"""
                <p>
                    Using the live simulation counters at observation time <i>T</i> = <b>{sim_T:.2f} s</b>:
                </p>
                <ol>
                    <li><b>Admitted Customer Rate (<i>&lambda;<sub>s</sub></i>):</b> With {admitted_cnt} customers entering the system over <i>T</i> = {sim_T:.2f} s:
                        <br><i>&lambda;</i><sub><i>s</i>,sim</sub> = {admitted_cnt} / {sim_T:.2f} = <b>{lam_s_sim:.5f} cust/s</b>.</li>
                    <li><b>Whole-System Little's Law Verification (Eqs. 1 &amp; 3):</b> Multiplying <i>&lambda;</i><sub><i>s</i>,sim</sub> by the average sojourn time <i>&delta;&#772;</i><sub>sim</sub> = {delta_sim:.5f} s gives:
                        <br><i>&lambda;</i><sub><i>s</i>,sim</sub> &middot; <i>&delta;&#772;</i><sub>sim</sub> = {lam_s_sim:.5f} &times; {delta_sim:.5f} = <b>{littles_A:.5f} E</b>.
                        Comparing against the time-average occupancy integral <i>I</i><sub>sim</sub>(<i>T</i>) = <b>{A_sim:.5f} E</b> yields residual:
                        <br><i>L</i><sub>diff</sub> = |{A_sim:.5f} &minus; {littles_A:.5f}| = <b>{littles_err:.5f} E</b>.</li>
                    <li><b>Queue Subsystem Verification (Eq. 1):</b> For the waiting queue alone:
                        <br><i>&lambda;</i><sub><i>s</i>,sim</sub> &middot; <i>&eta;&#772;</i><sub>sim</sub> = {lam_s_sim:.5f} &times; {eta_sim:.5f} = <b>{littles_Ac:.5f} E</b> (compared to <i>A&#770;</i><sub><i>c</i>,sim</sub> = <b>{Ac_sim:.5f} E</b>).</li>
                </ol>
                """
            else:
                example_body = """
                <p>
                    Consider a queueing system observed over <i>T</i> = <b>100.0 s</b> in which <b>80 customers</b> are admitted (<i>&lambda;<sub>s</sub></i> = 0.80 cust/s), each spending an average waiting time <i>&eta;&#772;</i> = <b>1.50 s</b> in the queue and an average service time <i>&vartheta;&#772;</i> = <b>1.00 s</b> in the server (so <i>&delta;&#772;</i> = <i>&eta;&#772;</i> + <i>&vartheta;&#772;</i> = <b>2.50 s</b>):
                </p>
                <ol>
                    <li><b>Queue Subsystem (Eq. 1):</b> <i>A<sub>c</sub></i> = <i>&lambda;<sub>s</sub>&eta;&#772;</i> = 0.80 &times; 1.50 = <b>1.2000 E</b>.</li>
                    <li><b>Server Subsystem (Eq. 1):</b> <i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub>&vartheta;&#772;</i> = 0.80 &times; 1.00 = <b>0.8000 E</b>.</li>
                    <li><b>Whole System (Eqs. 1&ndash;2):</b> <i>A</i> = <i>&lambda;<sub>s</sub>&delta;&#772;</i> = 0.80 &times; 2.50 = <b>2.0000 E</b> = <i>A<sub>c</sub></i> + <i>A<sub>s</sub></i> (with <i>L</i><sub>diff</sub> = <b>0.00000</b>).</li>
                </ol>
                """

            html = f"""{css}
            <h1>Little's Law (<i>A</i> = <i>&lambda;<sub>s</sub>&delta;&#772;</i>, <i>A<sub>c</sub></i> = <i>&lambda;<sub>s</sub>&eta;&#772;</i>, <i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub>&vartheta;&#772;</i>)</h1>
            <div class="meta-line">Active Model: {model_tag} &nbsp;|&nbsp; Course Formula: <i>A</i> = <i>&lambda;<sub>s</sub>&delta;&#772;</i> (Simulator Label: <i>L</i> = <i>&lambda;</i><sub>eff</sub><i>W</i>)</div>

            <h2>1. Definition and Physical Interpretation</h2>
            <p class="def-paragraph">
                <b>Theorem (Little's Law).</b> In any teletraffic system that exhibits a long-run stable behavior (so that the
                average values exist), the average traffic intensity <b><i>A</i></b> in the system is equal to the product of the
                average rate of customers entering the system (<b><i>&lambda;<sub>s</sub></i></b>) and the average sojourn time
                spent by a customer in the system (<b><i>&delta;&#772;</i></b>): <b><i>A</i> = <i>&lambda;<sub>s</sub>&delta;&#772;</i></b>.
            </p>
            <p>
                <b>Universal Validity and Subsystem Application.</b> Little's Law is valid in complete generality and is
                <i>independent</i> of the probability distribution of the arrival process, the distribution of the service process,
                the number of servers <i>m</i>, and the queueing policy (FIFO, LIFO, RC, PRIO). Furthermore, the exact same relation
                applies to <i>any subsystem</i> of the system under observation—specifically the queue alone and the set of servers alone.
            </p>

            <h2>2. Mathematical Formulation</h2>
            <p>
                Applying Little's Law to the entire queueing system, to the queue subsystem, and to the server subsystem yields:
            </p>
            {eq1}
            <p>
                Combining Eq. (1) with the additive decomposition of average sojourn time (<i>&delta;&#772;</i> = <i>&eta;&#772;</i> + <i>&vartheta;&#772;</i>)
                proves the additive decomposition of average traffic:
            </p>
            {eq2}
            <p>
                Over a finite simulation horizon <i>T</i>, the empirical conservation discrepancy <i>L</i><sub>diff</sub> converges to zero as <i>T</i> &rarr; &infin;:
            </p>
            {eq3}
            {params_eq1_eq3}

            <h2>3. Theoretical Properties and Queueing Analysis</h2>
            <ul>
                <li><b>Admission vs. Arrival Rate (<i>&lambda;</i> &ne; <i>&lambda;<sub>s</sub></i> in Loss Systems):</b> When customers can be rejected (<i>&pi;<sub>p</sub></i> &gt; 0), rejected customers do not enter the system and spend zero time inside it. Therefore, Little's Law must be written using the <i>entering (admitted) rate</i> <b><i>&lambda;<sub>s</sub></i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>&lambda;</i></b> rather than the offered arrival rate <i>&lambda;</i>.</li>
            </ul>

            <h2>4. Worked Numerical Example</h2>
            <div class="example-box">
                <p class="example-title">Example 1 (Verification of Little's Law Across System and Subsystems)</p>
                {example_body}
            </div>

            <h2>5. Analytical vs. Empirical Benchmark Table</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Formula / Estimator</th><th>Live Value</th></tr>
                <tr><td>Simulated Average Traffic</td><td><i>I</i><sub>sim</sub>(<i>T</i>) (<i>L</i><sub>sim</sub>)</td><td>(1/<i>T</i>) &int; <i>k</i>(<i>t</i>) d<i>t</i></td><td>{A_sim:.5f} E</td></tr>
                <tr><td>Admitted Customer Rate</td><td><i>&lambda;</i><sub><i>s</i>,sim</sub> (<i>&lambda;</i><sub>eff</sub>)</td><td>[<i>a</i>(<i>T</i>) &minus; <i>a<sub>p</sub></i>(<i>T</i>)] / <i>T</i></td><td>{lam_s_sim:.5f} cust/s</td></tr>
                <tr><td>Simulated Average Sojourn Time</td><td><i>&delta;&#772;</i><sub>sim</sub> (<i>W</i><sub>sim</sub>)</td><td>[1/<i>d</i>(<i>T</i>)] &sum; <i>&delta;<sub>n</sub></i></td><td>{delta_sim:.5f} s</td></tr>
                <tr><td>Little's Law Product</td><td><i>&lambda;</i><sub><i>s</i>,sim</sub><i>&delta;&#772;</i><sub>sim</sub></td><td><i>&lambda;</i><sub><i>s</i>,sim</sub> &middot; <i>&delta;&#772;</i><sub>sim</sub></td><td>{littles_A:.5f} E</td></tr>
                <tr class="bottom-rule"><td>Empirical Discrepancy</td><td><i>L</i><sub>diff</sub></td><td>|<i>I</i><sub>sim</sub>(<i>T</i>) &minus; <i>&lambda;</i><sub><i>s</i>,sim</sub><i>&delta;&#772;</i><sub>sim</sub>|</td><td>{littles_err:.5f} E</td></tr>
            </table>
            """
            return title, _format_theory_html(html)

        # ---------------------------------------------------------------
        # Topic 14: Customer Flow Accounting & Carried Traffic (Served / Arrived)
        # ---------------------------------------------------------------
        else:
            arr_tot = m_stats.get("arrived", 0)
            served_tot = m_stats.get("served", 0)
            dropped_tot = m_stats.get("dropped", 0)
            k_now = (
                engine.total_in_system
                if engine is not None
                else max(0, arr_tot - served_tot - dropped_tot)
            )
            t_sim = max(1e-4, m_stats.get("T", 0.0))
            lam_s_sim = (served_tot / t_sim) if sim_T > 0.01 else 0.0
            pi_p_theo = theo.get("p_loss", 0.0) if theo else 0.0
            theo_lam_s = (
                lam_val * (1.0 - pi_p_theo)
                if (theo and not is_unstable)
                else min(lam_val, c_val * mu_val)
            )

            eq1 = latex_eq_row(
                r"k(t) = k(0) + a(t) - d(t) \;\; (\text{Lossless}), \qquad a(t) = d(t) + k(t) + a_p(t) \;\; (\text{General System},\; k(0) = 0)",
                eq_num=1,
                zoom_factor=zoom_factor,
            )
            eq2 = latex_eq_row(
                r"\lambda = \lim_{t \to \infty} \frac{a(t)}{t}, \qquad \lambda = \lambda_s + \lambda_p, \qquad \lambda_s = (1 - \pi_p)\lambda = \lim_{t \to \infty} \frac{d(t)}{t}, \qquad \lambda_p = \pi_p \lambda",
                eq_num=2,
                zoom_factor=zoom_factor,
            )
            eq3 = latex_eq_row(
                r"A_0 = A_s + A_p, \qquad A_s = \lambda_s\,\overline{\vartheta} = (1 - \pi_p)A_0, \qquad A_p = \lambda_p\,\overline{\vartheta} = \pi_p A_0",
                eq_num=3,
                zoom_factor=zoom_factor,
            )

            params_eq1_eq3 = where_list([
                ("<i>a</i>(<i>t</i>)", "Total number of arrivals to the system up to time <i>t</i> (labeled <i>Arrived</i> in the simulator)."),
                ("<i>d</i>(<i>t</i>)", "Total number of departures (completed services) from the system up to time <i>t</i> (labeled <i>Served</i> in the simulator)."),
                ("<i>a<sub>p</sub></i>(<i>t</i>)", "Total number of customers rejected (lost) up to time <i>t</i> due to the queue being full (labeled <i>Drops</i> in the simulator)."),
                ("<i>k</i>(<i>t</i>)", "Number of customers currently inside the system at time <i>t</i> (with initial state <i>k</i>(0) = 0)."),
                ("<i>&lambda;</i>, <i>&lambda;<sub>s</sub></i>, <i>&lambda;<sub>p</sub></i>", "Average arrival rate (<i>&lambda;</i>), average rate of customers entering/served by the system (<i>&lambda;<sub>s</sub></i>), and average rate of customers rejected by the system (<i>&lambda;<sub>p</sub></i>), in customers per second (cust/s)."),
                ("<i>A</i><sub>0</sub>, <i>A<sub>s</sub></i>, <i>A<sub>p</sub></i>", "Offered traffic (<i>A</i><sub>0</sub> = <i>&lambda;&vartheta;&#772;</i>), carried/served traffic (<i>A<sub>s</sub></i> = <i>&lambda;<sub>s</sub>&vartheta;&#772;</i>), and rejected/lost traffic (<i>A<sub>p</sub></i> = <i>&lambda;<sub>p</sub>&vartheta;&#772;</i>), in Erlangs (E)."),
            ])

            if has_sim_data:
                example_body = f"""
                <p>
                    Evaluating the cumulative counters at simulation time <i>t</i> = <b>{sim_T:.2f} s</b> (with initial occupancy <i>k</i>(0) = 0):
                </p>
                <ol>
                    <li><b>Sample-Path Customer Conservation (Eq. 1):</b> At <i>t</i> = {sim_T:.2f} s, we have <i>d</i>(<i>t</i>) = {served_tot} departures, <i>k</i>(<i>t</i>) = {k_now} customers currently inside the system, and <i>a<sub>p</sub></i>(<i>t</i>) = {dropped_tot} rejected customers:
                        <br><i>d</i>(<i>t</i>) + <i>k</i>(<i>t</i>) + <i>a<sub>p</sub></i>(<i>t</i>) = {served_tot} + {k_now} + {dropped_tot} = <b>{served_tot + k_now + dropped_tot} customers</b> = <i>a</i>(<i>t</i>) ({arr_tot} arrivals).</li>
                    <li><b>Empirical Rate Balance (Eq. 2):</b> Dividing by <i>t</i> = {sim_T:.2f} s gives the empirical departure rate:
                        <br><i>d</i>(<i>t</i>) / <i>t</i> = {served_tot} / {sim_T:.2f} = <b>{lam_s_sim:.4f} cust/s</b> (compared to theoretical <i>&lambda;<sub>s</sub></i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>&lambda;</i> = <b>{theo_lam_s:.4f} cust/s</b>).</li>
                </ol>
                """
            else:
                example_body = f"""
                <p>
                    Consider an observation interval <i>T</i> = <b>100.0 s</b> starting from an empty system <i>k</i>(0) = 0, during which <i>a</i>(<i>T</i>) = <b>82 customers</b> arrive:
                </p>
                <ol>
                    <li><b>Sample-Path Customer Balance (Eq. 1):</b> If <i>a<sub>p</sub></i>(<i>T</i>) = 2 customers are rejected at the buffer entrance and <i>k</i>(<i>T</i>) = 1 customer is still inside the system at <i>t</i> = <i>T</i>, then the number of completed departures is:
                        <br><i>d</i>(<i>T</i>) = <i>a</i>(<i>T</i>) &minus; <i>k</i>(<i>T</i>) &minus; <i>a<sub>p</sub></i>(<i>T</i>) = 82 &minus; 1 &minus; 2 = <b>79 customers</b>.</li>
                    <li><b>Rate and Traffic Decomposition (Eqs. 2&ndash;3):</b> Over <i>T</i> = 100.0 s, the empirical arrival rate is <i>a</i>(<i>T</i>)/<i>T</i> = 0.82 cust/s, split into admitted rate <i>&lambda;<sub>s</sub></i> &approx; 0.80 cust/s and rejected rate <i>&lambda;<sub>p</sub></i> &approx; 0.02 cust/s.</li>
                </ol>
                """

            html = f"""{css}
            <h1>Customer Flow Balance (<i>a</i>(<i>t</i>), <i>d</i>(<i>t</i>), <i>k</i>(<i>t</i>)) and Carried Throughput (<i>&lambda;<sub>s</sub></i>)</h1>
            <div class="meta-line">Active Model: {model_tag} &nbsp;|&nbsp; Course Symbols: <i>d</i>(<i>t</i>) / <i>a</i>(<i>t</i>) and <i>&lambda;</i> = <i>&lambda;<sub>s</sub></i> + <i>&lambda;<sub>p</sub></i></div>

            <h2>1. Definition and Physical Interpretation</h2>
            <p class="def-paragraph">
                <b>Definition.</b> Under the fundamental teletraffic assumptions, customers neither appear inside nor disappear
                from the system: every customer that enters the system must eventually exit, and every customer that exits has
                previously entered. In a lossless system, the number of customers inside the system at time <i>t</i> satisfies
                <b><i>k</i>(<i>t</i>) = <i>k</i>(0) + <i>a</i>(<i>t</i>) &minus; <i>d</i>(<i>t</i>)</b>, where <i>a</i>(<i>t</i>)
                is the total number of arrivals up to time <i>t</i> and <i>d</i>(<i>t</i>) is the total number of departures up to time <i>t</i>.
            </p>
            <p>
                <b>Arrival vs. Admission in Finite-Capacity Queues.</b> When the queue has a finite size, arrival does not coincide
                with admission: an arriving customer that finds the queue full is rejected. Thus, total arrival rate <i>&lambda;</i>
                splits into the rate of customers entering the system (<b><i>&lambda;<sub>s</sub></i></b>) and the rate of customers
                rejected by the system (<b><i>&lambda;<sub>p</sub></i></b>): <b><i>&lambda;</i> = <i>&lambda;<sub>s</sub></i> + <i>&lambda;<sub>p</sub></i></b>.
            </p>

            <h2>2. Mathematical Formulation</h2>
            <p>
                At any instant <i>t</i> &ge; 0, the cumulative counting processes satisfy the exact sample-path conservation identity:
            </p>
            {eq1}
            <p>
                Taking the long-run time-average rates as <i>t</i> &rarr; &infin; (where <i>k</i>(<i>t</i>)/<i>t</i> &rarr; 0 in any stable or finite-capacity system) yields the rate conservation equations:
            </p>
            {eq2}
            <p>
                Multiplying Eq. (2) by the mean service time <i>&vartheta;&#772;</i> = 1/<i>&mu;</i> produces the traffic conservation identity (in Erlangs):
            </p>
            {eq3}
            {params_eq1_eq3}

            <h2>3. Theoretical Properties and Queueing Analysis</h2>
            <ul>
                <li><b>Burke's Theorem for Departure Processes (<i>&#8499;</i>/<i>&#8499;</i>/<i>m</i>):</b> In a stable <i>&#8499;</i>/<i>&#8499;</i>/1 or <i>&#8499;</i>/<i>&#8499;</i>/<i>m</i> system in statistical equilibrium, the departure process <i>d</i>(<i>t</i>) is itself a homogeneous Poisson process with rate equal to the arrival rate <i>&lambda;</i>.</li>
            </ul>

            <h2>4. Worked Numerical Example</h2>
            <div class="example-box">
                <p class="example-title">Example 1 (Customer Flow Balance and Rate Decomposition)</p>
                {example_body}
            </div>

            <h2>5. Analytical vs. Empirical Benchmark Table</h2>
            <table class="book-table">
                <tr><th>Quantity</th><th>Course Symbol (GUI)</th><th>Conservation Relation</th><th>Live Value</th></tr>
                <tr><td>Total Arrivals up to <i>t</i></td><td><i>a</i>(<i>t</i>) (Arrived)</td><td><i>d</i>(<i>t</i>) + <i>k</i>(<i>t</i>) + <i>a<sub>p</sub></i>(<i>t</i>)</td><td>{arr_tot:,} cust</td></tr>
                <tr><td>Total Departures up to <i>t</i></td><td><i>d</i>(<i>t</i>) (Served)</td><td>Completed services</td><td>{served_tot:,} cust</td></tr>
                <tr><td>Customers in System at <i>t</i></td><td><i>k</i>(<i>t</i>) (Occupancy)</td><td>In queue + in servers</td><td>{k_now:,} cust</td></tr>
                <tr><td>Customers Rejected up to <i>t</i></td><td><i>a<sub>p</sub></i>(<i>t</i>) (Drops)</td><td>Rejected at full queue</td><td>{dropped_tot:,} cust</td></tr>
                <tr class="bottom-rule"><td>Simulated / Theoretical Entering Rate</td><td><i>d</i>(<i>t</i>)/<i>t</i> vs. <i>&lambda;<sub>s</sub></i></td><td><i>&lambda;<sub>s</sub></i> = (1 &minus; <i>&pi;<sub>p</sub></i>)<i>&lambda;</i></td><td>{lam_s_sim:.4f} / {theo_lam_s:.4f} cust/s</td></tr>
            </table>
            """
            return title, _format_theory_html(html)


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
            "Erlang (E_r)",
            "Hyperexponential (H₂ - Bursty)",
            "Pareto (Heavy-Tailed)",
            "System Instability & Ergodicity (ρ ≥ 1.0)",
            "Metric Theory: Server Utilization ρ (U)",
            "Metric Theory: Avg Traffic in System A (L)",
            "Metric Theory: Avg Queue Customers A_c (Lq)",
            "Metric Theory: Avg Sojourn Time δ̄ (W)",
            "Metric Theory: Avg Waiting Time η̄ (Wq)",
            "Metric Theory: Blocking Probability π_p (P_loss)",
            "Metric Theory: Little's Law A = λ_s δ̄ (L_diff)",
            "Metric Theory: Customer Flow Balance (Served / Arrived)",
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

        self.combo_topic.currentIndexChanged.connect(self._on_topic_or_role_changed)
        self.combo_role.currentIndexChanged.connect(self._on_topic_or_role_changed)

        if dist_index is not None and 0 <= dist_index <= 14:
            self.combo_topic.setCurrentIndex(dist_index)
        else:
            self.combo_topic.setCurrentIndex(6)
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