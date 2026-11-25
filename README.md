# Chaoshawk: UAV Chaos-Metric Supervisor

This repository contains the reproducible research artifacts for:

**A Safety-Gated Chaos-Metric Supervisor for UAVs in Lorenz-Derived
Disturbances**

The project studies a supervisory layer for UAVs. It estimates a bounded
instability indicator from acceleration-like telemetry and selects one of three
high-level strategies: `hold`, `reduce_speed`, or `return_to_home`. Optional
LLM proposals are treated as untrusted suggestions and must pass deterministic
freshness, altitude, availability, and threshold gates.

## Contents

- [`paper/research_paper.pdf`](paper/research_paper.pdf): compiled three-page,
  two-column research paper.
- [`paper/research_paper.tex`](paper/research_paper.tex): LaTeX source.
- [`paper/integration_results.png`](paper/integration_results.png): figure used
  in the paper.
- [`src/telemetry_node/`](src/telemetry_node/): minimal Python research
  package used to generate the reference experiment and report.
- [`requirements.txt`](requirements.txt): Python dependencies.

The repository intentionally excludes PX4/Gazebo build directories, simulator
binaries, ROS install/log directories, caches, raw runtime recordings, and API
credentials.

## Installation

Python 3.10 or newer is recommended. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The offline tools do not require ROS 2, PX4, Gazebo, or an LLM API key.

## Reproduce The Results

Run the matched baseline and supervised reference experiment:

```bash
PYTHONPATH=src/telemetry_node \
python3 -m telemetry_node.experiment_cli \
  demo --duration 35 --seed 7 --output-dir results/demo
```

Generate a figure, metadata report, and dependency-free report artifacts:

```bash
PYTHONPATH=src/telemetry_node \
python3 -m telemetry_node.experiment_cli \
  report results/demo/baseline_telemetry.csv \
  results/demo/supervised_telemetry.csv --output-dir results/report
```

The experiment uses the Lorenz parameters $(\sigma,\rho,\beta)=(10,28,8/3)$,
time step `0.02 s`, wind scale `0.12`, target altitude `5 m`, and seed `7`.
Each run writes telemetry CSV files and JSON metadata. The supervised run
changes to `return_to_home` at approximately `4.78 s`.

## Reported Results

| Metric | Baseline | Supervised |
|---|---:|---:|
| Horizontal RMS error | 72.206 m | 21.839 m |
| Horizontal maximum error | 99.972 m | 29.432 m |
| Peak instability indicator | 0.0895 | 0.0895 |
| Mean altitude | 8.605 m | 8.701 m |

The supervised reference run reduces horizontal RMS error by approximately
69.8% and maximum error by approximately 70.6% under identical forcing. This
is a deterministic integration demonstration, not a statistical evaluation.

## Tests

Run the offline research tests with:

```bash
PYTHONPATH=src/telemetry_node \
python3 -m unittest \
  discover -s src/telemetry_node/test -p 'test_*.py' -v
```

The tests cover Lorenz reproducibility, the finite-window Lyapunov estimator,
sampling validation, safety gates, structured-proposal validation, provider
fallback, and the reference integration loop.

## Compile The Paper

With a LaTeX installation containing `IEEEtran`, `amsmath`, `amsfonts`,
`booktabs`, `graphicx`, `url`, and `xcolor`:

```bash
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory=paper paper/research_paper.tex
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory=paper paper/research_paper.tex
```

The figure must remain beside the LaTeX source because the source includes
`integration_results.png` by filename.

## Additional Tools

The CLI also supports the following reproducible operations:

```bash
PYTHONPATH=src/telemetry_node python3 -m telemetry_node.experiment_cli lorenz \
  --duration 50 --dt 0.01 --noise-std 0.1 --seed 42 --output-dir results

PYTHONPATH=src/telemetry_node python3 -m telemetry_node.experiment_cli wind \
  --duration 40 --dt 0.01 --scale 0.2 --seed 42 --output-dir results

PYTHONPATH=src/telemetry_node python3 -m telemetry_node.experiment_cli estimate \
  path/to/imu.csv --column ax --output-dir results

PYTHONPATH=src/telemetry_node python3 -m telemetry_node.experiment_cli evaluate \
  path/to/vehicle_odometry.csv --reference-x 0 --reference-y 0 \
  --output-dir results
```

The Lyapunov estimate requires uniformly sampled data. When timestamps are
present, the estimator infers the median interval and rejects excessive timing
irregularity. A positive finite-window estimate is an instability indicator; it
does not prove that a UAV is chaotic.

## Scope And Limitations

The reported backend is a deterministic surrogate with a damped point-mass
update. It is not a validated PX4 flight, rigid-body simulation, aerodynamic
model, or physical flight test. The repository does not claim that an LLM
improves safety or that the metric predicts real aircraft instability.

Before live or physical use, the PX4/Gazebo path requires independent
verification of force injection, NED/FRD frame conventions, offboard and arming
state transitions, geofencing, watchdog behavior, failsafe behavior, and manual
override. Keep all credentials in environment variables and never commit API
keys.

## Citation

If you use the artifacts, cite the accompanying paper and identify the exact
seed, duration, time step, and backend used for the reported experiment.
