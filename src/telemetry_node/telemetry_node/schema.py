"""JSON schemas used at the ROS/agent integration boundary."""
from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class ChaosMetric:
    timestamp_s: float
    instability: float
    lyapunov_per_s: float
    sample_count: int
    quality: float
    source: str = "imu"

    def to_json(self):
        return json.dumps(asdict(self), separators=(",", ":"))


@dataclass(frozen=True)
class StrategyCommand:
    timestamp_s: float
    strategy: str
    reason: str
    source: str = "supervisory_agent"

    def to_json(self):
        return json.dumps(asdict(self), separators=(",", ":"))
