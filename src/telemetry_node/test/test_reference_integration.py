import unittest
from unittest.mock import patch

from telemetry_node.research_pipeline import ExperimentConfig, run_experiment
from telemetry_node.schema import ChaosMetric
from telemetry_node.supervisor_agent import SupervisoryAgent
from telemetry_node.supervisor import Observation, Strategy


class ReferenceIntegrationTests(unittest.TestCase):
    def test_supervised_run_is_reproducible_and_has_events(self):
        config = ExperimentConfig(duration_s=8.0, seed=4, mode="supervised")
        first = run_experiment(config)
        second = run_experiment(config)
        self.assertEqual(first["summary"], second["summary"])
        self.assertGreater(len(first["time"]), 100)
        self.assertTrue(first["summary"]["actions"])

    def test_agent_falls_back_without_network(self):
        observation = Observation(.4, 1.0, 5.0, 100.0)
        decision = SupervisoryAgent(endpoint=None).decide(observation, now=100.1)
        self.assertEqual(decision.strategy, Strategy.REDUCE_SPEED)

    def test_agent_fails_over_from_openai_to_gemini(self):
        observation = Observation(.4, 1.0, 5.0, 100.0)
        agent = SupervisoryAgent(api_key="openai", gemini_api_key="gemini")
        with patch.object(agent, "_remote_proposal", side_effect=OSError("offline")), \
                patch.object(agent, "_gemini_proposal", return_value={
                    "strategy": "reduce_speed", "timestamp_s": 100.0}):
            decision = agent.decide(observation, now=100.1)
        self.assertTrue(decision.accepted)
        self.assertEqual(agent.last_provider, "gemini")

    def test_metric_schema_is_json(self):
        metric = ChaosMetric(1.0, .2, .5, 20, .9)
        self.assertIn('"instability":0.2', metric.to_json())


if __name__ == '__main__':
    unittest.main()
