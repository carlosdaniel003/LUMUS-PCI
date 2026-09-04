from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_runtime_contract_fix as contract


class DisplayF3RuntimeContractFixTests(unittest.TestCase):
    def test_blocked_physical_state_still_releases_mask_analysis(self):
        for kind in ("unknown", "off", "empty", "unavailable", "check"):
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
