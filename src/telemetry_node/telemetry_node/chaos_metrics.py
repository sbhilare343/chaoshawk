"""Offline Lorenz data generation and Rosenstein largest-Lyapunov estimate.

The estimate is an instability indicator. Noise and forcing can produce
positive finite-window values; this module does not classify UAV flight as
chaotic.
"""
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class LorenzParameters:
    sigma: float = 10.0
    rho: float = 28.0
    beta: float = 8.0 / 3.0


def generate_lorenz(duration=40.0, dt=0.01, initial=(1.0, 1.0, 1.0),
                    parameters=LorenzParameters(), discard=5.0, noise_std=0.0,
                    seed=0):
    """Integrate Lorenz equations; return time and XYZ after transient discard."""
    if duration <= 0 or dt <= 0 or discard < 0 or discard >= duration:
        raise ValueError('Require duration > discard >= 0 and dt > 0')
    if noise_std < 0:
        raise ValueError('noise_std must be non-negative')

    def rhs(_time, state):
        x, y, z = state
        return (parameters.sigma * (y - x),
                x * (parameters.rho - z) - y,
                x * y - parameters.beta * z)

    time = np.arange(0.0, duration, dt)
    result = solve_ivp(rhs, (0.0, duration), initial, t_eval=time,
                       rtol=1e-9, atol=1e-12)
    keep = time >= discard
    values = result.y[:, keep].T
    if noise_std:
        values += np.random.default_rng(seed).normal(0, noise_std, values.shape)
    return time[keep], values


def largest_lyapunov_rosenstein(signal, dt, embedding_dimension=6,
                                delay=8, theiler_window=20,
                                fit_start=1, fit_end=30):
    """Estimate largest exponent (1/time unit) from a uniformly sampled signal.

    Uses delay-coordinate embedding, temporally separated nearest neighbors,
    and a linear fit to mean log-divergence over the selected evolution range.
    """
    data = np.asarray(signal, dtype=float)
    if data.ndim == 2:
        data = data[:, 0]
    if data.ndim != 1 or not np.all(np.isfinite(data)):
        raise ValueError('signal must be finite 1D data or a finite 2D array')
    if dt <= 0 or embedding_dimension < 2 or delay < 1 or theiler_window < 0:
        raise ValueError('Invalid sampling or embedding parameters')
    if fit_start < 0 or fit_end <= fit_start:
        raise ValueError('Require 0 <= fit_start < fit_end')
    length = len(data) - (embedding_dimension - 1) * delay - fit_end
    if length < 3:
        raise ValueError('Signal is too short for embedding and fit range')
    embedded = np.column_stack(
        [data[k * delay:k * delay + length] for k in range(embedding_dimension)]
    )
    neighbors = cKDTree(embedded).query(embedded, k=min(len(embedded), 8))[1]
    pairs = []
    for i, candidates in enumerate(neighbors):
        for j in np.atleast_1d(candidates)[1:]:
            if abs(int(j) - i) > theiler_window:
                pairs.append((i, int(j)))
                break
    if len(pairs) < 2:
        raise ValueError('Not enough temporally separated neighbor pairs')
    i, j = np.asarray(pairs).T
    steps = np.arange(fit_end + 1)
    valid = (i[:, None] + steps < len(embedded)) & (j[:, None] + steps < len(embedded))
    distances = np.linalg.norm(
        embedded[np.minimum(i[:, None] + steps, len(embedded) - 1)] -
        embedded[np.minimum(j[:, None] + steps, len(embedded) - 1)], axis=2
    )
    distances[(~valid) | (distances <= 0)] = np.nan
    divergence = np.nanmean(np.log(distances), axis=0)
    fit_steps = np.arange(fit_start, fit_end + 1)
    good = np.isfinite(divergence[fit_steps])
    if good.sum() < 2:
        raise ValueError('Insufficient valid divergence samples in fit range')
    slope = np.polyfit(fit_steps[good] * dt, divergence[fit_steps][good], 1)[0]
    return float(slope)


def analyze_csv(path, dt=None, column='ax', max_irregular_fraction=0.05,
                **estimator_options):
    """Estimate from CSV; infer dt from median positive timestamp intervals.

    Returns (exponent, timing_metadata). Explicit dt overrides timestamp
    inference and is useful for controlled sensitivity experiments.
    """
    import csv
    with open(path, newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows or column not in rows[0]:
        raise ValueError(f'CSV has no usable {column!r} column')
    inferred = None
    irregular_fraction = None
    if dt is None:
        if 'timestamp_us' not in rows[0]:
            raise ValueError('CSV needs timestamp_us when --dt is omitted')
        stamps = np.asarray([float(row['timestamp_us']) for row in rows])
        intervals = np.diff(stamps)
        positive = intervals[intervals > 0]
        if len(positive) < 2:
            raise ValueError('Not enough positive timestamp intervals')
        inferred = float(np.median(positive) / 1e6)
        irregular_fraction = float(np.mean(np.abs(positive - np.median(positive)) >
                                           max(1.0, 0.05 * np.median(positive))))
        dt = inferred
    exponent = largest_lyapunov_rosenstein(
        [float(row[column]) for row in rows], dt, **estimator_options
    )
    if irregular_fraction is not None and irregular_fraction > max_irregular_fraction:
        raise ValueError(
            f'Irregular sampling fraction {irregular_fraction:.3f} exceeds '
            f'{max_irregular_fraction:.3f}; resample uniformly before estimating'
        )
    return exponent, {
        'dt_s': float(dt), 'dt_source': 'explicit' if inferred is None else 'median timestamp interval',
        'median_timestamp_dt_s': inferred,
        'irregular_interval_fraction': irregular_fraction,
    }
