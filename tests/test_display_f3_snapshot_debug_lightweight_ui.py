import inspect
import unittest

import src.platform.display_f3_snapshot_debug_lightweight_ui as debug_ui


class DisplayF3SnapshotDebugLightweightUiTests(unittest.TestCase):
    def test_debug_nao_renderiza_relatorio_completo(self):
        source = inspect.getsource(debug_ui)
        self.assertNotIn("tk.Text(", source)
        self.assertNotIn("Scrollbar(", source)
        self.assertNotIn("text.insert(", source)
        self.assertIn("COPIAR DEBUG", source)
        self.assertIn("_display_f3_manual_snapshot_report", source)

    def test_debug_usa_mesma_maximizacao_do_workspace_f3(self):
        source = inspect.getsource(debug_ui)
        self.assertIn("maximizar_janela_workspace_f3(top)", source)
        self.assertIn("after_idle", source)
        self.assertIn("wraplength", source)
        self.assertIn("<Configure>", source)

    def test_mensagem_explica_o_conteudo_disponivel(self):
        summary = debug_ui.DEBUG_SUMMARY.lower()
        for term in ("estado físico", "scores", "check", "máscaras", "aceso/apagado", "energia"):
            self.assertIn(term, summary)

    def test_modulo_permanece_isolado_do_f2(self):
        source = inspect.getsource(debug_ui).lower()
        self.assertNotIn("f2_", source)


if __name__ == "__main__":
    unittest.main()
