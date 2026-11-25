import math
import unittest

import numpy as np

from telemetry_node.chaos_metrics import generate_lorenz, largest_lyapunov_rosenstein
from telemetry_node.supervisor import (
    Observation, Strategy, rule_based_decision, validate_recommendation,
)


class ChaosMetricTests(unittest.TestCase):
    def test_lorenz_trajectory_is_finite_and_reproducible(self):
        t1, x1 = generate_lorenz(duration=10, dt=0.01, discard=1, noise_std=0.1, seed=9)
        t2, x2 = generate_lorenz(duration=10, dt=0.01, discard=1, noise_std=0.1, seed=9)
        self.assertTrue(np.array_equal(t1, t2))
        self.assertTrue(np.array_equal(x1, x2))
        self.assertTrue(np.isfinite(x1).all())

    def test_lorenz_exponent_is_positive_in_configured_reference_case(self):
        _, states = generate_lorenz(duration=50, dt=0.01, discard=5)
        estimate = largest_lyapunov_rosenstein(states, 0.01)
        self.assertGreater(estimate, 0.0)
        self.assertLess(estimate, 3.0)

    def test_estimator_rejects_too_short_signal(self):
        with self.assertRaises(ValueError):
            largest_lyapunov_rosenstein(np.arange(50), 0.01)


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.observation = Observation(0.2, 2.0, 10.0, 100.0)

    def test_rule_chooses_speed_reduction_on_high_indicator(self):
        decision = rule_based_decision(self.observation, now=100.1)
        self.assertEqual(decision.strategy, Strategy.REDUCE_SPEED)

    def test_stale_state_falls_back_to_hold(self):
        decision = rule_based_decision(self.observation, now=102.0)
        self.assertEqual(decision.strategy, Strategy.HOLD)
        self.assertFalse(decision.accepted)

    def test_valid_and_invalid_recommendations(self):
        valid = validate_recommendation(
            {'strategy': 'reduce_speed', 'timestamp_s': 100.0},
            self.observation, now=100.1,
        )
        self.assertTrue(valid.accepted)
        invalid = validate_recommendation(
            {'strategy': 'motor_command', 'timestamp_s': 100.0},
            self.observation, now=100.1,
        )
        self.assertFalse(invalid.accepted)
        self.assertEqual(invalid.strategy, Strategy.HOLD)


if __name__ == '__main__':
    unittest.main()
