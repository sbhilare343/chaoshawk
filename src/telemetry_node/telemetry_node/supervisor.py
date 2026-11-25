"""Deterministic safe strategy selection and strict recommendation validation.

This module intentionally has no PX4 publisher. A validated strategy is an
advisory result; a future adapter must separately implement and test bounded
setpoint-level actions.
"""
from dataclasses import dataclass
from enum import Enum
import math
import time


class Strategy(str, Enum):
    HOLD = 'hold'
    REDUCE_SPEED = 'reduce_speed'
    RETURN_TO_HOME = 'return_to_home'


@dataclass(frozen=True)
class Observation:
    instability: float
    position_error_m: float
    altitude_m: float
    timestamp_s: float
    vehicle_available: bool = True


@dataclass(frozen=True)
class Decision:
    strategy: Strategy
    reason: str
    accepted: bool


def rule_based_decision(observation, now=None, max_age_s=1.0):
    """Choose conservative high-level intent; fail safely on bad/stale state."""
    now = time.time() if now is None else now
    values = (observation.instability, observation.position_error_m,
              observation.altitude_m, observation.timestamp_s)
    if (not observation.vehicle_available or not all(map(math.isfinite, values))
            or observation.timestamp_s > now
            or now - observation.timestamp_s > max_age_s):
        return Decision(Strategy.HOLD, 'state unavailable, invalid, or stale', False)
    if observation.altitude_m < 1.0:
        return Decision(Strategy.HOLD, 'low altitude safety gate', True)
    if abs(observation.position_error_m) > 8.0:
        return Decision(Strategy.RETURN_TO_HOME, 'position error exceeds 8 m', True)
    if observation.instability > 0.15:
        return Decision(Strategy.REDUCE_SPEED, 'instability indicator exceeds threshold', True)
    return Decision(Strategy.HOLD, 'within configured operating limits', True)


def validate_recommendation(payload, observation, now=None, max_age_s=1.0):
    """Validate a structured LLM proposal; return safe HOLD on any rejection."""
    fallback = Decision(Strategy.HOLD, 'proposal rejected; safe fallback', False)
    try:
        if not isinstance(payload, dict) or set(payload) != {'strategy', 'timestamp_s'}:
            return fallback
        if not isinstance(payload['timestamp_s'], (int, float)):
            return fallback
        stamp = float(payload['timestamp_s'])
        now = time.time() if now is None else now
        if not math.isfinite(stamp) or stamp > now or now - stamp > max_age_s:
            return fallback
        strategy = Strategy(payload['strategy'])
        if not observation.vehicle_available or observation.altitude_m < 1.0:
            return fallback
        if strategy is Strategy.RETURN_TO_HOME and abs(observation.position_error_m) <= 8.0:
            return fallback
        if strategy is Strategy.REDUCE_SPEED and observation.instability <= 0.15:
            return fallback
        return Decision(strategy, 'proposal passed deterministic gates', True)
    except (TypeError, ValueError, KeyError, AttributeError):
        return fallback


def load_strategy_model(model_path):
    """Load a locally trained scikit-learn policy model when explicitly used."""
    import joblib
    return joblib.load(model_path)


def model_recommendation(model, observation, now=None):
    """Use the local classifier, then pass its proposal through safety gates."""
    fallback = Decision(Strategy.HOLD, 'model unavailable or invalid; safe fallback', False)
    try:
        if not observation.vehicle_available:
            return fallback
        features = [[observation.instability, abs(observation.position_error_m),
                     observation.altitude_m]]
        strategy = str(model.predict(features)[0])
        payload = {'strategy': strategy,
                   'timestamp_s': time.time() if now is None else now}
        return validate_recommendation(payload, observation, now=now)
    except Exception:
        return fallback
