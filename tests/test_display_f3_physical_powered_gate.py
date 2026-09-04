from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_physical_powered_gate as gate
import src.platform.display_f3_runtime_contract_fix as contract


class DisplayF3PhysicalPoweredGateTests(unittest.TestCase):
    def _context(self):
        return {
            "project_name": "TESTE",
            "check_id": "CHECK_004",
            "check_name": "USB",
        }

    def _analysis(self, powered: int = 13, off: int = 2):
        items = []
        for index in range(powered):
            items.append(
                {
                    "mask_id": f"ON_{index}",
                    "expected": "on",
                    "classified": "on",
                    "confidence": 0.80,
                }
            )
        for index in range(off):
            items.append(
                {
                    "mask_id": f"OFF_{index}",
                    "expected": "on",
                    "classified": "off",
                    "confidence": 0.70,
                }
            )
        return {
            "ready": True,
            "project_name": "TESTE",
            "check_id": "CHECK_004",
            "mask_results": items,
        }

    def test_usb_debug_case_promotes_unknown_to_powered(self):
        state = {
            "kind": "unknown",
            "allow_auto": True,
            contract.F3_DECISION_ALLOWED_KEY: False,
            "reference_scores": {
                "off": 0.5427,
                "empty": 0.2666,
                "check:CHECK_004": 0.1768,
            },
            "board_references_complete": True,
        }
        result = gate.resolver_estado_ligado_f3(
            state,
            context=self._context(),
            analysis=self._analysis(powered=13, off=2),
        )
        self.assertEqual("powered", result["kind"])
        self.assertTrue(result["allow_auto"])
        self.assertTrue(result[contract.F3_DECISION_ALLOWED_KEY])
        self.assertEqual(gate.F3_POWERED_PHYSICAL_KEY, result["physical_state_key"])
        self.assertIn("ANALISANDO USB", result["text"])
        self.assertEqual(13, result["powered_mask_evidence"]["powered_votes"])
        self.assertEqual(2, result["powered_mask_evidence"]["off_votes"])

    def test_empty_support_is_never_overridden(self):
        state = {
            "kind": "empty",
            "allow_auto": False,
            "reference_scores": {"off": 0.30, "empty": 0.90},
        }
        result = gate.resolver_estado_ligado_f3(
            state,
            context=self._context(),
            analysis=self._analysis(powered=15, off=0),
        )
        self.assertEqual("empty", result["kind"])
        self.assertFalse(result["allow_auto"])

    def test_unknown_requires_board_presence_margin(self):
        state = {
            "kind": "unknown",
            "allow_auto": True,
            contract.F3_DECISION_ALLOWED_KEY: False,
            "reference_scores": {"off": 0.42, "empty": 0.39},
        }
        result = gate.resolver_estado_ligado_f3(
            state,
            context=self._context(),
            analysis=self._analysis(powered=15, off=0),
        )
        self.assertEqual("unknown", result["kind"])
        self.assertFalse(result[contract.F3_DECISION_ALLOWED_KEY])

    def test_explicit_off_requires_very_strong_power_evidence(self):
        state = {
            "kind": "off",
            "allow_auto": True,
            contract.F3_DECISION_ALLOWED_KEY: False,
            "reference_scores": {"off": 0.78, "empty": 0.25},
        }
        weak = gate.resolver_estado_ligado_f3(
            state,
            context=self._context(),
            analysis=self._analysis(powered=10, off=5),
        )
        self.assertEqual("off", weak["kind"])

        strong = gate.resolver_estado_ligado_f3(
            state,
            context=self._context(),
            analysis=self._analysis(powered=13, off=2),
        )
        self.assertEqual("powered", strong["kind"])
        self.assertTrue(strong[contract.F3_DECISION_ALLOWED_KEY])

    def test_analysis_from_other_check_does_not_promote(self):
        analysis = self._analysis(powered=15, off=0)
        analysis["check_id"] = "CHECK_001"
        state = {
            "kind": "unknown",
            "allow_auto": True,
            contract.F3_DECISION_ALLOWED_KEY: False,
            "reference_scores": {"off": 0.55, "empty": 0.20},
        }
        result = gate.resolver_estado_ligado_f3(
            state,
            context=self._context(),
            analysis=analysis,
        )
        self.assertEqual("unknown", result["kind"])

    def test_gate_is_installed_after_runtime_contract(self):
        from src.platform import display_f3_fast_expected_gate as fast_gate

        source = inspect.getsource(fast_gate.instalar_gate_rapido_check_esperado_display_f3)
        self.assertLess(
            source.index("instalar_contrato_runtime_display_f3()"),
            source.index("instalar_gate_placa_ligada_display_f3()"),
        )

    def test_module_has_no_f2_dependency(self):
        source = inspect.getsource(gate)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)


if __name__ == "__main__":
    unittest.main()
