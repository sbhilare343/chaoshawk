"""Generate figures and a compact research-paper report from reference runs."""
import json
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages


def _load(path):
    rows = np.genfromtxt(path, delimiter=",", names=True)
    with open(path.replace("_telemetry.csv", "_metadata.json")) as stream:
        metadata = json.load(stream)
    return rows, metadata


def build_report(baseline_csv, supervised_csv, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    baseline, baseline_meta = _load(baseline_csv)
    supervised, supervised_meta = _load(supervised_csv)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    axes[0, 0].plot(baseline["x"], baseline["y"], label="baseline", color="#ef8354")
    axes[0, 0].plot(supervised["x"], supervised["y"], label="supervised", color="#246a73")
    axes[0, 0].set(xlabel="north position (m)", ylabel="east position (m)", title="Horizontal response")
    axes[0, 0].legend()
    axes[0, 1].plot(baseline["time_s"], baseline["instability"], label="baseline", color="#ef8354")
    axes[0, 1].plot(supervised["time_s"], supervised["instability"], label="supervised", color="#246a73")
    axes[0, 1].axhline(.15, color="#8c2f39", linestyle="--", linewidth=1, label="decision gate")
    axes[0, 1].set(xlabel="time (s)", ylabel="indicator", title="Rolling instability")
    axes[0, 1].legend()
    axes[1, 0].plot(baseline["time_s"], baseline["z"], label="baseline", color="#ef8354")
    axes[1, 0].plot(supervised["time_s"], supervised["z"], label="supervised", color="#246a73")
    axes[1, 0].set(xlabel="time (s)", ylabel="altitude surrogate (m)", title="Vertical response")
    axes[1, 0].legend()
    axes[1, 1].plot(supervised["time_s"], supervised["wind_x"], label="wind x")
    axes[1, 1].plot(supervised["time_s"], supervised["wind_y"], label="wind y")
    axes[1, 1].plot(supervised["time_s"], supervised["wind_z"], label="wind z")
    axes[1, 1].set(xlabel="time (s)", ylabel="wind input (m/s)", title="Lorenz-derived disturbance")
    axes[1, 1].legend()
    figure_path = os.path.join(output_dir, "integration_results.png")
    fig.savefig(figure_path, dpi=180)
    plt.close(fig)
    b = baseline_meta["summary"]
    s = supervised_meta["summary"]
    tex_path = os.path.join(output_dir, "uav_chaos_supervisor_report.tex")
    tex = r'''\documentclass[11pt,a4paper]{article}
\usepackage{graphicx,booktabs,geometry,amsmath}
\geometry{margin=25mm}
\title{A Chaos-Metric Supervisory Subsystem for UAV Flight in a Turbulent Wind Field}
\author{UAV Chaos Supervisor Research Workstream}
\date{\today}
\begin{document}
\maketitle
\begin{abstract}
This paper presents a reproducible reference implementation for a UAV supervisory
loop driven by a Lorenz attractor disturbance. A causal rolling instability
indicator is computed from the disturbance/IMU surrogate, and a safety-gated
supervisor selects bounded high-level strategies. The reference backend is used
for validation when PX4, Gazebo, and ROS 2 are unavailable; it is not claimed to
replace rigid-body simulation or flight testing.
\end{abstract}
\section{System architecture}
The workstream separates the Lorenz ODE, telemetry and metric boundary, a
tool-calling-compatible supervisory agent, and bounded strategy execution. An
OpenAI-compatible endpoint is optional. If it is absent or returns an invalid
proposal, the deterministic conservative policy is used. The PX4 adapter is
kept behind the same boundary and is simulation-only by design.
\section{Methods}
The Lorenz equations are $\dot{x}=\sigma(y-x)$, $\dot{y}=x(\rho-z)-y$,
$\dot{z}=xy-\beta z$, with $(\sigma,\rho,\beta)=(10,28,8/3)$. The state is
scaled into a three-axis wind input. The rolling indicator combines local
acceleration energy and jerk roughness and is bounded to $[0,1]$. Strategies
are selected only after freshness, altitude, and threshold gates. The packaged
offline estimator additionally implements a Rosenstein largest-Lyapunov estimate
for uniformly sampled telemetry.
\section{Results}
Table~\ref{tab:results} reports the matched-seed reference comparison. The
supervised run is an integration demonstration, not evidence of aircraft-level
stability or a causal Lyapunov proof.\par
\begin{table}[h]
\centering\begin{tabular}{lrr}\toprule
Metric & Baseline & Supervised\\\midrule
Horizontal RMS error (m) & B_RMS & S_RMS\\
Horizontal maximum error (m) & B_MAX & S_MAX\\
Peak instability indicator & B_PEAK & S_PEAK\\
Mean altitude (m) & B_ALT & S_ALT\\
\bottomrule\end{tabular}
\caption{Reference-backend results.}\label{tab:results}
\end{table}
\begin{figure}[h]\centering\includegraphics[width=0.98\linewidth]{integration_results.png}
\caption{Trajectory, rolling instability, altitude, and applied Lorenz-derived wind.}\end{figure}
\section{Reproducibility and limitations}
Run \texttt{uav-experiment demo --output-dir results/demo} followed by
\texttt{uav-experiment report ...}. All experiments record the seed, mode,
configuration, telemetry, and supervisor events. PX4 SITL/Gazebo validation
requires the documented Ubuntu 24.04/ROS 2 Jazzy toolchain, a working
\texttt{gz-sim-wind-effects-system}, and a verified force-injection plugin.
The current report must not be interpreted as such a validation.
\end{document}
'''.replace("B_RMS", f"{b['horizontal_rms_error_m']:.3f}").replace("S_RMS", f"{s['horizontal_rms_error_m']:.3f}")
    tex = tex.replace("B_MAX", f"{b['horizontal_max_error_m']:.3f}").replace("S_MAX", f"{s['horizontal_max_error_m']:.3f}")
    tex = tex.replace("B_PEAK", f"{b['instability_peak']:.3f}").replace("S_PEAK", f"{s['instability_peak']:.3f}")
    tex = tex.replace("B_ALT", f"{b['altitude_mean_m']:.3f}").replace("S_ALT", f"{s['altitude_mean_m']:.3f}")
    with open(tex_path, "w") as stream:
        stream.write(tex)
    pdf_path = os.path.join(output_dir, "uav_chaos_supervisor_report.pdf")
    with PdfPages(pdf_path) as pdf:
        page = plt.figure(figsize=(8.27, 11.69))
        page.text(0.10, 0.90, "A Chaos-Metric Supervisory Subsystem", fontsize=22,
                  weight="bold", color="#246a73")
        page.text(0.10, 0.86, "for UAV Flight in a Turbulent Wind Field", fontsize=15)
        page.text(0.10, 0.79, "Research report | reproducible reference backend", fontsize=11)
        abstract = ("Abstract\nThis report presents a deterministic reference implementation for a UAV "
                    "supervisory loop driven by a Lorenz attractor disturbance. A rolling "
                    "instability indicator is consumed by a safety-gated strategy boundary. "
                    "The backend supports validation and demonstration when PX4/Gazebo/ROS 2 "
                    "are unavailable; it is not a replacement for flight validation.")
        page.text(0.10, 0.69, abstract, fontsize=11, va="top", wrap=True, linespacing=1.5)
        page.text(0.10, 0.48, "Results", fontsize=15, weight="bold", color="#246a73")
        table = (f"Metric                              Baseline      Supervised\n"
                 f"Horizontal RMS error (m)           {b['horizontal_rms_error_m']:.3f}         {s['horizontal_rms_error_m']:.3f}\n"
                 f"Horizontal maximum error (m)       {b['horizontal_max_error_m']:.3f}         {s['horizontal_max_error_m']:.3f}\n"
                 f"Peak instability indicator          {b['instability_peak']:.3f}         {s['instability_peak']:.3f}\n"
                 f"Mean altitude (m)                   {b['altitude_mean_m']:.3f}         {s['altitude_mean_m']:.3f}")
        page.text(0.10, 0.42, table, family="monospace", fontsize=10, va="top", linespacing=1.8)
        page.text(0.10, 0.20, "Reproducibility: seed=7, dt=0.02 s, Lorenz (10, 28, 8/3).\n"
                  "See the accompanying .tex source for methods, architecture, and limitations.", fontsize=10)
        pdf.savefig(page, bbox_inches="tight")
        plt.close(page)
        image = plt.figure(figsize=(11, 7))
        image.figimage(plt.imread(figure_path))
        image.suptitle("Integration results", fontsize=14)
        pdf.savefig(image, bbox_inches="tight")
        plt.close(image)
    return tex_path, figure_path, pdf_path
