from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_zero_cost_debug_runtime as module


class _App:
    def _display_auto_is_reference_gate(self, context):
        return bool((context or {}).get("reference_gate"))

    def _display_auto_is_transient_check(self, context):
        return bool((context or {}).get("transient"))


class DisplayF3ZeroCostDebugRuntimeTests(unittest.TestCase):
    def test_extracts_runtime_captured_before_live_debug(self):
        def original_process(owner):
            return owner

        def diagnostic_process(owner):
            return original_process(owner)

        found = module.extrair_runtime_produtivo_antes_do_debug(diagnostic_process)
        self.assertIs(found, original_process)

    def test_only_h1_and_transient_need_operational_probe_with_debug_off(self):
        app = _App()
        self.assertTrue(
            module._contexto_exige_sonda_operacional(
                app,
                {"reference_gate": True},
            )
        )
        self.assertTrue(
            module._contexto_exige_sonda_operacional(
                app,
                {"transient": True},
            )
        )
        self.assertFalse(
            module._contexto_exige_sonda_operacional(
                app,
                {"check_id": "USB"},
            )
        )

    def test_debug_off_runtime_does_not_build_trace_or_copy_analysis(self):
        source = inspect.getsource(module)
        # Verifica chamadas reais, não palavras explicativas em comentários/docstrings.
        self.assertNotIn("deepcopy(", source)
        self.assertNotIn("set_technical_debug_provider(", source)
        self.assertNotIn("_record_live_frame(", source)
        self.assertIn("return runtime_produtivo(self)", source)

    def test_debug_on_keeps_original_diagnostic_runtime(self):
        source = inspect.getsource(module.instalar_runtime_debug_off_custo_zero_display_f3)
        self.assertIn("debug_tecnico_ativo_display_f3", source)
        self.assertIn("return diagnostic_process(self)", source)

    def test_module_isolated_from_f2(self):
        source = inspect.getsource(module)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)


if __name__ == "__main__":
    unittest.main()
