# Queueing System Simulator

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Plotting](https://img.shields.io/badge/Charts-Matplotlib-orange.svg)](https://matplotlib.org/)

An interactive **Discrete-Event Simulation (DES)** platform and analytical laboratory for queueing theory, network performance evaluation, and teletraffic engineering.

It combines an event-driven stochastic simulation engine with a live 2D animated vector canvas, dynamic birth-death Markov chain visualization, real-time Matplotlib telemetry, and an integrated 16-page LaTeX theory library.

---

## Installation & Quick Start

### 0. Get the Code

The repository is public, so no GitHub account or login is needed. Plain `git` is the simplest option:

```bash
git clone https://github.com/raffiditommaso/Queueing-System-Simulator.git
cd Queueing-System-Simulator
```

To update an existing copy to the latest version, run `git pull` inside the folder.

> **`gh repo clone` fails with `HTTP 401: Bad credentials`?** The GitHub CLI is sending a stored token that is expired or revoked (or an invalid `GH_TOKEN` / `GITHUB_TOKEN` environment variable is set). A public repository does not need a token, but `gh` refuses to continue when the one it has is rejected. Use the `git clone` command above, or repair the CLI login with `gh auth login` (and remove any stale `GH_TOKEN` / `GITHUB_TOKEN` variable).

### 1. Requirements

- **Operating System**: Windows 10/11, Linux, or macOS
- **Python**: Version **3.10** or higher, 64-bit (tested up to Python 3.14). Current PyQt6 and Matplotlib releases no longer publish wheels for Python 3.9.

### 2. Install Dependencies

Install the two required external libraries (preferably inside a virtual environment):

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

*(equivalent to `python -m pip install PyQt6 matplotlib`. All other modules used (`heapq`, `math`, `random`, `dataclasses`, `collections`, `hashlib`, `argparse`) are part of the Python Standard Library).*

> **No PDF library is required.** The theory viewer paginates and renders its A4 pages directly with Qt's core text engine, so you do **not** need `PyQt6.QtPdf`, `PyQt6-WebEngine`, `QtPrintSupport`, or any other PDF package. Do not try to install packages such as `PyQt6-QtPdf` (it does not exist on PyPI).

#### Installation troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `pip` tries to *build* PyQt6 from source (`Preparing metadata (pyproject.toml)`, `qmake not found`, `sip-build` errors) | No pre-built wheel matches your Python/OS (Python 3.9 or older, 32-bit Python, outdated `pip`, or an old Linux distribution with glibc < 2.34) | Use 64-bit Python 3.10+, upgrade `pip`, and retry. On old Linux distributions you can pin an older wheel: `python -m pip install "PyQt6<6.10"` |
| `ModuleNotFoundError: No module named 'PyQt6'` right after installing | `pip` installed into a different interpreter than the one running `main.py` | Always use `python -m pip ...` with the same `python` you launch the app with |
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` (Linux) | Missing system X11 libraries | `sudo apt install libxcb-cursor0 libxkbcommon-x11-0` (Debian/Ubuntu) |

### 3. Run the Simulator

#### Interactive GUI Mode (Default)
```bash
python main.py
```

#### Headless CLI Batch Mode
```bash
# Run 100,000 events on an M/M/2/12 queue:
python main.py --cli -m 2 -K 12 --lambda-rate 1.6 --service-rate 1.0 --events 100000

# Or execute via cli.py directly:
python cli.py -m 1 -K 10 --lambda-rate 0.8 --service-rate 1.0 --events 50000
```

---

## Theoretical Foundation & Nomenclature

The simulator strictly implements standard European and Italian university curriculum conventions for teletraffic networks.

### Mathematical Variables & Symbols Reference

| Symbol | Definition | GUI / Table Label | Unit |
| :---: | :--- | :--- | :---: |
| **$\tau$** | Inter-arrival time random variable | Inter-arrival Time | $\text{s}$ |
| **$\bar{\tau}$** | Mean inter-arrival time ($\bar{\tau} = \mathrm{E}[\tau] = 1/\lambda$) | Mean Inter-arrival: $\mathrm{E}[\tau]$ | $\text{s}$ |
| **$\sigma_\tau^2$** | Variance of inter-arrival times | Inter-arrival Variance: $\mathrm{Var}[\tau]$ | $\text{s}^2$ |
| **$\lambda$** | Offered arrival rate ($\lambda = 1/\bar{\tau}$) | Arrival Rate ($\lambda$) | $\text{cust/s}$ |
| **$\vartheta$** | Service duration random variable | Service Duration | $\text{s}$ |
| **$\bar{\vartheta}$** | Mean service time ($\bar{\vartheta} = \mathrm{E}[\vartheta] = 1/\mu$) | Mean Service: $\mathrm{E}[\vartheta]$ | $\text{s}$ |
| **$\sigma_\vartheta^2$** | Variance of service times | Service Variance: $\mathrm{Var}[\vartheta]$ | $\text{s}^2$ |
| **$\mu$** | Individual server processing rate ($\mu = 1/\bar{\vartheta}$) | Service Rate ($\mu$) | $\text{cust/s}$ |
| **$\zeta$** | Residual service duration (forward recurrence time) | Residual Service Time | $\text{s}$ |
| **$\bar{\zeta}$** | Mean residual service time: $\frac{\sigma_\vartheta^2 + \bar{\vartheta}^2}{2\bar{\vartheta}}$ | Mean Residual Service Time | $\text{s}$ |
| **$m$** | Number of parallel identical servers ($1, 2, \dots, \infty$) | Servers ($m$) | &mdash; |
| **$K$** | Queue buffer waiting capacity ($0, 1, \dots, \infty$; parameter $n$) | Queue Buffer Capacity ($K$) | $\text{cust}$ |
| **$N$** | Total system capacity ($N = m + K$) | Total Capacity ($N$) | $\text{cust}$ |
| **$A_0$** | Offered traffic: $A_0 = \lambda \bar{\vartheta} = \lambda / \mu$ | Offered Traffic ($A_0$) | $\text{Erlang (E)}$ |
| **$A_s$** | Carried / served traffic: $A_s = \lambda_s \bar{\vartheta} = (1 - \pi_p) A_0$ | Carried Traffic ($A_s$) | $\text{Erlang (E)}$ |
| **$A_p$** | Lost / rejected traffic: $A_p = \lambda_p \bar{\vartheta} = \pi_p A_0$ | Lost Traffic ($A_p$) | $\text{Erlang (E)}$ |
| **$\rho$** | Server utilization: $\rho = \frac{A_s}{m} = \frac{\lambda_s}{m\mu} \le 1$ | Server Utilization ($\rho$) | &mdash; |
| **$A$** | Time-average customer traffic in system: $\frac{1}{T}\int_0^T k(t)\,dt$ | Avg Traffic in System ($A$) | $\text{E / cust}$ |
| **$A_c$** | Time-average customer backlog in queue: $\frac{1}{T}\int_0^T k_c(t)\,dt$ | Avg Queue Backlog ($A_c$) | $\text{cust}$ |
| **$\delta$** | Sojourn time in the system ($\delta = \eta + \vartheta$) | Total System Delay | $\text{s}$ |
| **$\bar{\delta}$** | Mean sojourn time: $\mathrm{E}[\delta]$ | Avg Sojourn Time ($\bar{\delta}$) | $\text{s}$ |
| **$\eta$** | Waiting time in queue before receiving service | Queue Waiting Time | $\text{s}$ |
| **$\bar{\eta}$** | Mean waiting time across all admitted customers | Avg Waiting Time ($\bar{\eta}$) | $\text{s}$ |
| **$\varepsilon$** | Waiting time conditioned on experiencing queue delay ($\eta > 0$) | Queued Customer Delay | $\text{s}$ |
| **$\bar{\varepsilon}$** | Mean waiting time for queued customers: $\bar{\eta} / \pi_r$ | Queued Mean Wait ($\bar{\varepsilon}$) | $\text{s}$ |
| **$\pi_p$** | Customer blocking / rejection probability | Blocking Probability ($\pi_p$) | &mdash; |
| **$\pi_r$** | Probability of queue delay / congestion (Erlang-C) | Congestion Probability ($\pi_r$) | &mdash; |
| **$\lambda_s$** | Admitted arrival throughput: $\lambda_s = (1 - \pi_p)\lambda$ | Carried Throughput ($\lambda_s$) | $\text{cust/s}$ |
| **$\lambda_p$** | Rejected arrival rate: $\lambda_p = \pi_p \lambda$ | Rejection Rate ($\lambda_p$) | $\text{cust/s}$ |

---

### Core Analytical Identities & Formulas

1. **Little's Law (Conservation of System Traffic)**:
   $$A = \lambda_s \bar{\delta}, \qquad A_c = \lambda_s \bar{\eta}, \qquad A_s = \lambda_s \bar{\vartheta}$$
   The simulator continuously evaluates Little's Law discrepancy telemetry:
   $$L_{\text{diff}} = |A - \lambda_s \bar{\delta}|$$

2. **Sojourn Time Additivity**:
   $$\bar{\delta} = \bar{\eta} + \bar{\vartheta}$$

3. **Traffic Conservation Law**:
   $$A_0 = A_s + A_p \iff \lambda = \lambda_s + \lambda_p$$

4. **Pollaczek-Khinchine Formula ($M/G/1$)**:
   $$\bar{\eta} = \frac{\lambda \mathrm{E}[\vartheta^2]}{2(1 - \rho)} = \frac{\rho \bar{\vartheta}}{1 - \rho} \cdot \left(\frac{1 + C_v^2}{2}\right), \qquad A_c = \lambda \bar{\eta} = \frac{\rho^2}{1 - \rho} \cdot \left(\frac{1 + C_v^2}{2}\right)$$
   where $C_v = \frac{\sigma_\vartheta}{\bar{\vartheta}}$ is the coefficient of variation of the service distribution.

5. **Erlang-B Loss Model ($M/M/m/0$ Pure Loss System)**:
   $$\pi_p = B(m, A_0) = \frac{\frac{A_0^m}{m!}}{\sum_{k=0}^m \frac{A_0^k}{k!}}$$

6. **Erlang-C Delay Model ($M/M/m$ Infinite Buffer System)**:
   $$\pi_r = C(m, A_0) = \frac{\frac{A_0^m}{m!(1 - \rho)}}{\sum_{k=0}^{m-1} \frac{A_0^k}{k!} + \frac{A_0^m}{m!(1 - \rho)}}, \qquad \bar{\eta} = \frac{\pi_r}{m\mu - \lambda}, \qquad \bar{\varepsilon} = \frac{\bar{\vartheta}}{m - A_0}$$

7. **Finite Buffer Delay-Loss System ($M/M/m/K$)**:
   Full state probabilities $p_0, p_1, \dots, p_N$ (where $N = m + K$):
   $$p_k = \begin{cases} p_0 \frac{A_0^k}{k!}, & 0 \le k \le m \\ p_0 \frac{A_0^m}{m!} \left(\frac{A_0}{m}\right)^{k-m}, & m < k \le m + K \end{cases}$$
   $$\pi_p = p_{m+K}, \qquad \pi_r = \sum_{k=m}^{m+K-1} p_k, \qquad \bar{\varepsilon} = \frac{\bar{\eta}}{\pi_r}$$

8. **Ample Server / Infinite Servers ($M/M/\infty$ Pure Delay System)**:
   Poisson state distribution:
   $$p_n = \frac{A_0^n}{n!} e^{-A_0}, \qquad A = A_0, \qquad A_c = 0, \qquad \bar{\eta} = 0, \qquad \rho = 0, \qquad \pi_p = 0$$

9. **Zero Service Rate ($\mu = 0.00$ cust/s & Frozen System)**:
   Infinite service time $\bar{\vartheta} = \infty$. Servers lock on the first $m$ dispatched jobs; the buffer accumulates $K$ customers until reaching total saturation $N = m + K$. Thereafter, admitted throughput drops to zero ($\lambda_s = 0$) and blocking reaches 100% ($\pi_p = 1.00$).

---

### Kendall Notation Format

The platform adheres to the 6-parameter Kendall notation:
$$\mathcal{A} / \mathcal{B} / m / n / p / \mathcal{S}$$
- $\mathcal{A}$: Arrival process ($M$, $D$, $U$, $E_r$, $H_2$, $\text{Pareto}$, or $G$)
- $\mathcal{B}$: Service process ($M$, $D$, $U$, $E_r$, $H_2$, $\text{Pareto}$, or $G$)
- $m$: Number of identical parallel servers ($1, 2, \dots, \infty$)
- $n$: Queue buffer capacity ($K$). Omitted when infinite ($K = \infty$); specified when finite ($M/M/m/0$ for loss, $M/M/1/12$ for finite buffer).
- $p$: Customer population size (omitted when $\infty$).
- $\mathcal{S}$: Queueing discipline ($\text{FIFO}$ or $\text{PRIO}$).

---

### Supported Stochastic Distributions

All 6 distributions are defined in [`core.distributions`](file:///C:/Users/raffy/Desktop/Queueing%20System%20Simulator/core/distributions.py) with exact analytical moments:

| Distribution | Kendall | Parameters | Mean $\mathrm{E}[X]$ | Variance $\mathrm{Var}[X]$ | Coeff. of Variation $C_v$ | Description |
| :--- | :---: | :--- | :---: | :---: | :---: | :--- |
| **Exponential** | $M$ | Rate $\lambda$ or $\mu$ | $1/\text{rate}$ | $1/\text{rate}^2$ | $C_v = 1$ | Memoryless Poisson process; Markovian service. |
| **Deterministic** | $D$ | Duration $d$ | $d$ | $0$ | $C_v = 0$ | Fixed packet sizes; periodic scheduled arrivals. |
| **Uniform** | $U$ | Bounds $[\tau_m, \tau_M]$ | $\frac{\tau_m + \tau_M}{2}$ | $\frac{(\tau_M - \tau_m)^2}{12}$ | $\frac{\tau_M - \tau_m}{\sqrt{3}(\tau_m + \tau_M)}$ | Bounded jitter or uniform job distributions. |
| **Erlang-$k$** | $E_r$ | Stages $k$, Mean | $\text{mean}$ | $\frac{\text{mean}^2}{k}$ | $C_v = \frac{1}{\sqrt{k}} \le 1$ | Sum of $k$ independent exponential stages. |
| **Hyperexponential** | $H_2$ | $p_1, r_1, r_2$ | $\frac{p_1}{r_1} + \frac{1-p_1}{r_2}$ | $\mathrm{E}[X^2] - \mathrm{E}[X]^2$ | $C_v > 1$ | Two-phase mixture modeling bursty packet flows. |
| **Pareto** | $\text{Pareto}$ | Shape $\alpha$, Scale $t_0$ | $\frac{\alpha t_0}{\alpha - 1}$ ($\alpha > 1$) | $\frac{\alpha t_0^2}{(\alpha-1)^2(\alpha-2)}$ ($\alpha > 2$) | $C_v > 1$ | Heavy-tailed self-similar Internet traffic. |

---

## Operating Modes: Exam Mode vs. Practice Mode

The simulator features a security switch located on the top-right header:

```
[ EXAM MODE ] O════════       (Locked by default - Theory, Markov chain, stability & ? hidden)
              ════════O [ PRACTICE ]  (Unlocked via password - All theory tabs visible)
```

### Exam Mode (Default)
- **Active by default** whenever the simulator starts up.
- **Theory tabs and formulas are strictly inaccessible**.
- **The Markov chain state-transition diagram is hidden**, since it reveals the analytical model of the system.
- **The System Stability Status card is hidden**, so the stable / congested / overloaded verdict ($A_0/m$) must be worked out by the student. Unstable configurations are likewise not flagged in the benchmark table (theoretical values show `N/A`), the model notes, or the $P(k)$ chart.
- **All question mark buttons (`?`) are completely hidden from the GUI** across the sidebar distribution selectors, KPI metric cards, and theoretical benchmark table.
- Direct or programmatic calls to open theory documents are locked.

### Practice Mode
- **Unlocked** by clicking the top-right toggle switch (hover displays `"Unlock practice mode"`).
- Prompts for the instructor authorization password (`sudo unlock practice mode`).
- The password is authenticated via constant-time **SHA-256 cryptographic hashing** without being stored in plain text anywhere in the codebase.
- Upon authentication, all contextual `?` buttons appear on the interface, interactive tooltips are enabled, and all 16 theory documentation pages can be opened.
- Clicking the toggle switch again immediately relocks the system to Exam Mode and closes any open theory tabs.

---

## User Interface & Features

### 1. Left Control Sidebar
- **Arrival & Service Distributions**: Choose any of the 6 stochastic distributions with dynamic parameter controls.
- **Arbitrary Parameter Inputs**: Sliders provide smooth immediate control over typical ranges, while companion number input fields allow typing any arbitrary positive value.
- **Infinite Servers ($m = \infty$)**: Checkbox switches the system into an ample-server pure delay model ($M/M/\infty$).
- **Infinite Queue Buffer ($K = \infty$)**: Checkbox sets pure infinite waiting room.
- **Zero Service Rate ($\mu = 0$)**: Dedicated support to model frozen server behavior.
- **Multi-Class Priority Queueing**: Non-preemptive priority dispatching for Class 1 (High, $P_0$), Class 2 (Medium, $P_1$), and Class 3 (Low, $P_2$) with separate Poisson arrival rates.

### 2. Main Simulation & Analytics Tabs
- **Live Simulation Canvas**: 2D vector animation rendering customer arrivals, buffer progression, server halos, progress rings, and dropped customer indicators.
- **Markov Chain State Diagram** *(Practice Mode only)*: Dynamic birth-death transition graph highlighting instantaneous occupancy $k(t)$ and transition rates ($\lambda, k\mu$).
- **Analytics & Histograms**: Real-time Matplotlib charts for system occupancy time series $k(t)$, empirical state distribution $p_n$, waiting time histograms $\eta$, and sojourn times $\delta$.
- **Analytical Model vs. Simulation Benchmark Table**: Real-time validation table comparing measured simulation metrics against exact theoretical values with Little's Law error tracking.

### 3. Embedded 16-Topic LaTeX Theory Textbook
When in Practice Mode, clicking any `?` button opens textbook-style documentation rendered with Computer Modern LaTeX formulas:
1. **Exponential Distribution ($M$)**
2. **Deterministic Distribution ($D$)**
3. **Uniform Distribution ($U$)**
4. **Erlang Distribution ($E_r$)**
5. **Hyperexponential Distribution ($H_2$)**
6. **Pareto Heavy-Tailed Distribution**
7. **Stochastic Stability: Overload ($\rho \ge 1.0$ & Ergodicity)**
8. **Stochastic Stability: Zero Service Rate ($\mu = 0.00$ & Frozen)**
9. **Metric Theory: Server Utilization ($\rho$) and Traffic Definitions ($A_0, A_s, A_p$)**
10. **Metric Theory: Average Traffic in System ($A$, legacy $L$)**
11. **Metric Theory: Average Queue Backlog ($A_c$, legacy $L_q$)**
12. **Metric Theory: Average Sojourn Time ($\bar{\delta}$, legacy $W$)**
13. **Metric Theory: Average Waiting Time ($\bar{\eta}, \bar{\varepsilon}$, legacy $W_q$)**
14. **Metric Theory: Blocking Probability ($\pi_p$, legacy $P_{\text{loss}}$)**
15. **Metric Theory: Little's Law ($A = \lambda_s \bar{\delta}$)**
16. **Metric Theory: Customer Flow Balance ($\lambda_s$, Carried vs. Arrived)**

### 4. Smart Optical Zoom
- Context-sensitive mouse wheel zoom: hovering over the theory document zooms the page document; hovering over the main GUI scales the whole user interface uniformly.
- High-precision gestures: trackpad pinch-to-zoom, `Ctrl + Mouse Wheel`, `Ctrl + +`, `Ctrl + -`, and `Ctrl + 0` to reset.

---

## Headless CLI Command Reference

The command-line runner supports automated experiment execution and headless batch sweeps:

```bash
python main.py --cli [OPTIONS]
# or
python cli.py [OPTIONS]
```

### Available CLI Flags

| Flag | Short | Type | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `--cli` | &mdash; | flag | `False` | Run headlessly in the console without opening the GUI. |
| `--servers` | `-m`, `-c` | `str` | `'1'` | Number of servers ($1, 2, \dots$ or `'inf'`). |
| `--queue` | `-K` | `str` | `'12'` | Queue buffer capacity ($0, 1, \dots$ or `'inf'`). |
| `--events` | &mdash; | `int` | `50000` | Number of discrete events to simulate. |
| `--lambda-rate` | &mdash; | `float` | `0.8` | Offered arrival rate $\lambda$ (cust/s). |
| `--service-rate` | &mdash; | `float` | `1.0` | Server processing rate $\mu$ (cust/s; set to `0.0` for frozen system). |
| `--priority` | &mdash; | flag | `False` | Enable multi-class non-preemptive priority queueing. |
| `--p0-rate` | &mdash; | `float` | `0.3` | Class 1 (High) arrival rate $\lambda_0$. |
| `--p1-rate` | &mdash; | `float` | `0.3` | Class 2 (Medium) arrival rate $\lambda_1$. |
| `--p2-rate` | &mdash; | `float` | `0.2` | Class 3 (Low) arrival rate $\lambda_2$. |
| `--seed` | &mdash; | `int` | `42` | Random number generator seed. |

---

## Architecture & Project Structure

```
Queueing System Simulator/
├── core/                               # Simulation Engine & Analytical Solvers
│   ├── constants.py                    # Colors, priority labels, Unicode formatting
│   ├── distributions.py                # 6 Stochastic distributions with analytical moments
│   ├── entities.py                     # Customer and Server dataclasses
│   ├── engine.py                       # Calendar queue discrete-event simulation engine
│   └── theory.py                       # Analytical solvers (M/M/m, M/M/m/K, M/G/1, Little's Law)
│
├── gui/                                # User Interface & Visualization
│   ├── canvas.py                       # 2D animated vector canvas
│   ├── main_window.py                  # Main window, controls, and KPI benchmarks
│   ├── markov_canvas.py                # Real-time birth-death Markov chain diagram
│   ├── styles.py                       # Catppuccin dark theme styling
│   ├── theory_dialog.py                # LaTeX formula renderer & 16-topic theory library
│   ├── theory_tab.py                   # High-resolution paginated theory document viewer
│   └── widgets.py                      # Sliders, steppers, zoom filters, password dialog
│
├── cli.py                              # Standalone CLI batch runner
├── main.py                             # Main application entry point
├── requirements.txt                    # pip dependencies (PyQt6, matplotlib)
└── README.md                           # Documentation
```
