from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_runtime_contract_fix as contract


class DisplayF3RuntimeContractFixTests(unittest.TestCase):
    def test_blocked_physical_state_still_releases_mask_analysis(self):
        for kind in ("unknown", "powered", "off", "empty", "unavailable", "check"):
            with self.subTest(kind=kind):
                state = contract.preparar_estado_para_mascaras_ativas_f3(
                    {"kind": kind, "allow_auto": False}
                )
                self.assertTrue(state["allow_auto"])
                self.assertTrue(state[contract.F3_MASK_LIVE_KEY])
                self.assertFalse(state[contract.F3_DECISION_ALLOWED_KEY])

                restored = contract.restaurar_autoridade_fisica_f3(state)
                self.assertFalse(restored["allow_auto"])
                self.assertTrue(restored[contract.F3_MASK_LIVE_KEY])

    def test_source_never_publishes_masks_as_inactive(self):
        source = inspect.getsource(contract)
        self.assertNotIn("MÁSCARAS • INATIVAS", source)
        self.assertIn("máscaras em leitura", source)

    def test_live_mask_confirmation_can_resolve_unknown_current_check(self):
        state = contract._state_from_mask_confirmation(
            {"kind": "unknown", "allow_auto": False},
            {
                "project_name": "DISPLAY A",
                "check_id": "h1",
                "check_name": "H1",
            },
        )
        self.assertEqual("check", state["kind"])
        self.assertEqual("h1", state["check_id"])
        self.assertTrue(state["allow_auto"])
        self.assertTrue(state[contract.F3_DECISION_ALLOWED_KEY])
        self.assertIn("DISPLAY EM H1", state["text"])

    def test_powered_cycle_can_be_resolved_by_current_check_masks(self):
        self.assertTrue(
            contract._state_accepts_mask_confirmation(
                {
                    "kind": "powered",
                    "allow_auto": True,
                    contract.F3_DECISION_ALLOWED_KEY: False,
                }
            )
        )
        state = contract._state_from_mask_confirmation(
            {
                "kind": "powered",
                "allow_auto": True,
                contract.F3_DECISION_ALLOWED_KEY: False,
            },
            {
                "project_name": "TESTE",
                "check_id": "CHECK_004",
                "check_name": "USB",
            },
        )
        self.assertEqual("check", state["kind"])
        self.assertEqual("CHECK_004", state["check_id"])
        self.assertTrue(state[contract.F3_DECISION_ALLOWED_KEY])
        self.assertIn("DISPLAY EM USB", state["text"])

    def test_off_empty_and_unavailable_remain_absolute_for_mask_promotion(self):
        for kind in ("off", "empty", "unavailable", "check"):
            with self.subTest(kind=kind):
                self.assertFalse(
                    contract._state_accepts_mask_confirmation({"kind": kind})
                )

    def test_powered_preview_explains_that_board_is_on_while_waiting_check(self):
        text = contract._blocked_preview_text(
            {"kind": "powered"},
            {"check_name": "USB"},
        )
        self.assertIn("placa ligada", text)
        self.assertIn("aguardando USB", text)

    def test_runtime_uses_same_promotion_rule_before_reset_and_on_register(self):
        source = inspect.getsource(contract._install_masks_always_live_gate)
        self.assertGreaterEqual(source.count("_state_accepts_mask_confirmation(state)"), 2)
        self.assertIn("physical_kind_before_mask_confirmation", source)

    def test_configuration_contract_keeps_on_change_and_explicit_arguments(self):
        contract._install_configuration_constructor_contract()

        from src.platform.display_project_config import DisplayProjectConfigWindow
        from src.platform.display_visual_reference_status import (
            DisplayProjectConfigPresenceWindow,
        )

        base_parameters = inspect.signature(DisplayProjectConfigWindow.__init__).parameters
        presence_parameters = inspect.signature(
            DisplayProjectConfigPresenceWindow.__init__
        ).parameters

        for parameter in (
            "root",
            "repository",
            "frame_provider",
            "on_change",
            "on_close",
        ):
            self.assertIn(parameter, base_parameters)
            self.assertIn(parameter, presence_parameters)

    def test_contract_is_installed_after_final_performance(self):
        from src.platform import display_f3_fast_expected_gate as fast_gate

        source = inspect.getsource(fast_gate.instalar_gate_rapido_check_esperado_display_f3)
        self.assertLess(
            source.index("instalar_performance_final_display_f3()"),
            source.index("instalar_contrato_runtime_display_f3()"),
        )

    def test_contract_has_no_f2_runtime_dependency(self):
        source = inspect.getsource(contract)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)
        self.assertNotIn("operacao_engine", source)


if __name__ == "__main__":
    unittest.main()
