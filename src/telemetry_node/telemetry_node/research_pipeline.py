"""Deterministic end-to-end reference experiment for the UAV research loop.

The reference backend is intentionally small and dependency-light. It is used
for repeatable validation and GUI/report generation; PX4/Gazebo remains the
hardware-in-the-loop backend described in the deployment documentation.
"""
from dataclasses import asdict, dataclass
import csv
import json
import os

import numpy as np

from .chaos_metrics import LorenzParameters, generate_lorenz
from .supervisor import Observation, Strategy
from .supervisor_agent import SupervisoryAgent


@dataclass(frozen=True)
class ExperimentConfig:
    duration_s: float = 35.0
    dt_s: float = 0.02
    seed: int = 7
    wind_scale: float = 0.12
    mode: str = "supervised"
    target_altitude_m: float = 5.0


def _rolling_instability(acceleration, dt, window=160):
    """Return a bounded, causal disturbance indicator in [0, 1]."""
    acceleration = np.asarray(acceleration, dtype=float)
    result = np.zeros(len(acceleration))
    for index in range(len(acceleration)):
        sample = acceleration[max(0, index - window + 1):index + 1]
        if len(sample) < 8:
            continue
        jerk = np.diff(sample, axis=0) / dt
        energy = np.mean(np.linalg.norm(sample, axis=1))
        roughness = np.mean(np.linalg.norm(jerk, axis=1))
        result[index] = 1.0 - np.exp(-0.018 * energy - 0.0015 * roughness)
    return result


def run_experiment(config=ExperimentConfig()):
    """Run baseline or supervised reference flight and return arrays/summary."""
    if config.mode not in {"baseline", "supervised"}:
        raise ValueError("mode must be baseline or supervised")
    time, lorenz = generate_lorenz(
        duration=config.duration_s, dt=config.dt_s, discard=0.0,
        parameters=LorenzParameters(), seed=config.seed,
    )
    rng = np.random.default_rng(config.seed)
    n = len(time)
    position = np.zeros((n, 3))
    velocity = np.zeros((n, 3))
    acceleration = np.zeros((n, 3))
    wind = config.wind_scale * lorenz
    actions = []
    agent = SupervisoryAgent()
    instability = _rolling_instability(wind, config.dt_s)
    last_action = Strategy.HOLD.value
    last_decision_time = -float("inf")
    for i in range(1, n):
        observation = Observation(
            float(instability[i]), float(np.linalg.norm(position[i - 1, :2])),
            float(position[i - 1, 2]), float(time[i - 1]), True,
        )
        if config.mode == "supervised":
            if float(time[i - 1]) - last_decision_time >= 1.0:
                decision = agent.decide(observation, now=float(time[i - 1]) + 0.01)
                last_decision_time = float(time[i - 1])
                action = decision.strategy.value
            else:
                action = last_action
        else:
            action = Strategy.HOLD.value
        if action != last_action:
            actions.append({"time_s": float(time[i]), "strategy": action})
            last_action = action
        damping = {"hold": 0.16, "reduce_speed": 0.62,
                   "return_to_home": 0.82}[action]
        commanded = -damping * velocity[i - 1]
        commanded[2] += 0.8 * (config.target_altitude_m - position[i - 1, 2])
        acceleration[i] = commanded + wind[i] + rng.normal(0, 0.012, 3)
        velocity[i] = velocity[i - 1] + config.dt_s * acceleration[i]
        position[i] = position[i - 1] + config.dt_s * velocity[i]
        position[i, 2] = max(0.0, position[i, 2])
    error = np.linalg.norm(position[:, :2], axis=1)
    summary = {
        "mode": config.mode, "samples": n, "duration_s": float(time[-1]),
        "seed": config.seed, "wind_scale": config.wind_scale,
        "instability_peak": float(np.max(instability)),
        "instability_mean": float(np.mean(instability)),
        "horizontal_rms_error_m": float(np.sqrt(np.mean(error ** 2))),
        "horizontal_max_error_m": float(np.max(error)),
        "altitude_mean_m": float(np.mean(position[:, 2])),
        "altitude_std_m": float(np.std(position[:, 2])),
        "actions": actions,
        "agent": "openai_then_gemini_with_deterministic_safety_fallback"
        if agent.api_key and agent.gemini_api_key else
        "openai_with_deterministic_safety_fallback" if agent.api_key else
        "gemini_with_deterministic_safety_fallback" if agent.gemini_api_key else
        "deterministic_fallback_no_llm_credentials",
    }
    return {"time": time, "lorenz": lorenz, "wind": wind,
            "position": position, "velocity": velocity,
            "acceleration": acceleration, "instability": instability,
            "summary": summary}


def save_experiment(result, output_dir, config):
    """Write machine-readable telemetry and metadata for report generation."""
    os.makedirs(output_dir, exist_ok=True)
    telemetry_path = os.path.join(output_dir, f"{config.mode}_telemetry.csv")
    with open(telemetry_path, "w", newline="") as stream:
        fields = ["time_s", "x", "y", "z", "vx", "vy", "vz",
                  "wind_x", "wind_y", "wind_z", "instability"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for i, stamp in enumerate(result["time"]):
            row = {"time_s": stamp, "instability": result["instability"][i]}
            row.update(dict(zip(("x", "y", "z"), result["position"][i])))
            row.update(dict(zip(("vx", "vy", "vz"), result["velocity"][i])))
            row.update(dict(zip(("wind_x", "wind_y", "wind_z"), result["wind"][i])))
            writer.writerow(row)
    metadata = {"config": asdict(config), "summary": result["summary"],
                "telemetry_csv": telemetry_path,
                "backend": "deterministic reference surrogate"}
    metadata_path = os.path.join(output_dir, f"{config.mode}_metadata.json")
    with open(metadata_path, "w") as stream:
        json.dump(metadata, stream, indent=2)
        stream.write("\n")
    return metadata_path
