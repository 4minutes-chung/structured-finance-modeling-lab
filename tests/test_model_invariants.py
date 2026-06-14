import unittest

from model.validate_cashflows import ModelParams, Scenario, run_scenario, scenario_monotonicity
from model.delinquency_trigger_model import (
    ModelParams as ModelParamsV2,
    ScenarioV2,
    monotonicity_ok,
    run_scenario_v2,
)
from model.scenario_config import DEFAULT_V1_SCENARIOS, DEFAULT_V2_SCENARIOS, load_scenario_bundle


class ScenarioConfigTests(unittest.TestCase):
    def test_default_bundle_has_expected_scenarios(self):
        bundle = load_scenario_bundle(None)

        self.assertEqual([s["name"] for s in bundle["v1_scenarios"]], ["Base", "Mild_Stress", "Severe_Stress"])
        self.assertEqual([s["name"] for s in bundle["v2_scenarios"]], ["Base", "Mild_Stress", "Severe_Stress"])


class V1ModelInvariantTests(unittest.TestCase):
    def test_v1_default_scenarios_are_ordered_and_balanced(self):
        params = ModelParams()
        results = [
            run_scenario(
                params,
                Scenario(
                    name=str(s["name"]),
                    cpr_annual=float(s["cpr_annual"]),
                    cdr_annual=float(s["cdr_annual"]),
                    severity=float(s["severity"]),
                ),
            )
            for s in DEFAULT_V1_SCENARIOS
        ]

        self.assertTrue(scenario_monotonicity(results))
        for result in results:
            metrics = result["metrics"]
            self.assertLessEqual(metrics["principal_diff_max"], 1e-6)
            self.assertLessEqual(metrics["interest_diff_max"], 1e-6)
            self.assertLessEqual(metrics["loss_diff_max"], 1e-6)
            self.assertGreaterEqual(metrics["min_balance_seen"], -1e-6)


class V2ModelInvariantTests(unittest.TestCase):
    def test_v2_default_scenarios_are_ordered_and_balanced(self):
        params = ModelParamsV2()
        results = [
            run_scenario_v2(
                params,
                ScenarioV2(
                    name=str(s["name"]),
                    cpr_annual=float(s["cpr_annual"]),
                    severity=float(s["severity"]),
                    roll_to_30_annual=float(s["roll_to_30_annual"]),
                    default_from_60_annual=float(s["default_from_60_annual"]),
                    cure_30_monthly=float(s["cure_30_monthly"]),
                    roll_30_to_60_monthly=float(s["roll_30_to_60_monthly"]),
                    cure_60_monthly=float(s["cure_60_monthly"]),
                ),
                trigger_loss_threshold=0.03,
                trigger_dq_threshold=0.06,
            )
            for s in DEFAULT_V2_SCENARIOS
        ]

        self.assertTrue(monotonicity_ok(results))
        for result in results:
            metrics = result["metrics"]
            self.assertLessEqual(metrics["principal_diff_max"], 1e-6)
            self.assertLessEqual(metrics["interest_diff_max"], 1e-6)
            self.assertLessEqual(metrics["loss_diff_max"], 1e-6)
            self.assertLessEqual(metrics["pool_roll_diff_max"], 1e-6)
            self.assertGreaterEqual(metrics["min_balance_seen"], -1e-6)


if __name__ == "__main__":
    unittest.main()
