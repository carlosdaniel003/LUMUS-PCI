from __future__ import annotations

import inspect
import unittest

from src.platform.display_mask_editor import DisplayMaskEditorWindow
from src.platform.display_production_f3 import DisplayProductionF3Mixin
from src.platform.display_project_config import DisplayProjectConfigWindow
from src.platform.display_project_repository import (
    DISPLAY_PROJECT_CONFIG_FILE,
    DisplayProjectRepository,
)


class DisplayF3Phase2ArchitectureTests(unittest.TestCase):
    def test_fase1_permanece_com_mesmo_contrato(self):
        self.assertEqual(
            (
                "janela_f3",
                "atalho_f3",
                "preview_camera_somente_leitura",
                "ciclo_abertura_fechamento_f3",
            ),
            DisplayProductionF3Mixin.responsabilidades_f3(),
        )

    def test_fase2_declara_apenas_projeto_resolucao_e_mascaras(self):
        self.assertEqual(
            (
                "projeto_display_persistente",
                "resolucao_mestra_display",
                "mascaras_display_persistentes",
            ),
            DisplayProductionF3Mixin.responsabilidades_f3_fase2(),
        )

    def test_repositorio_display_nao_depende_do_config_repository_do_f2(self):
        source = inspect.getsource(__import__(
            "src.platform.display_project_repository",
            fromlist=["DisplayProjectRepository"],
        ))
        self.assertNotIn("from src.infra.config_repository import", source)
        self.assertNotIn("from src.platform.led_project_repository import", source)
        self.assertNotIn("from src.models.led_selection import", source)
        self.assertNotIn("ConfigRepository(", source)
        self.assertNotIn("LedSelection(", source)
        self.assertTrue(issubclass(DisplayProjectRepository, object))

    def test_arquivo_display_nao_e_o_json_principal_do_f2(self):
        normalized = str(DISPLAY_PROJECT_CONFIG_FILE).replace("\\", "/")
        self.assertEqual("data/config/odin_display_projects.json", normalized)
        self.assertNotIn("odin_pci_config.json", normalized)

    def test_editor_visual_display_nao_ler_estado_de_roi_led_do_f2(self):
        source = inspect.getsource(__import__(
            "src.platform.display_mask_editor",
            fromlist=["DisplayMaskEditorWindow"],
        ))
        for forbidden in (
            "leds_selecionados",
            "leds_fixos_configurados",
            "config_repository",
            "operacao_engine",
            "operacao_ativa",
            "LedSelection",
        ):
            self.assertNotIn(forbidden, source)
        self.assertTrue(hasattr(DisplayMaskEditorWindow, "save"))

    def test_configuracao_display_recebe_repositorio_explicito(self):
        signature = inspect.signature(DisplayProjectConfigWindow.__init__)
        self.assertIn("repository", signature.parameters)
        self.assertIn("frame_provider", signature.parameters)
        source = inspect.getsource(DisplayProjectConfigWindow)
        self.assertNotIn("self.config_repository", source)
        self.assertIn("self.repository", source)

    def test_f3_nao_sobrescreve_metodos_de_projeto_led_do_f2(self):
        forbidden = {
            "carregar_leds_fixos",
            "salvar_leds_fixos",
            "_salvar_leds_no_projeto",
            "_sincronizar_projeto_ativo_apos_gestao",
            "preparar_tela_operacao",
            "disparar_inspecao_operacao",
        }
        self.assertTrue(forbidden.isdisjoint(DisplayProductionF3Mixin.__dict__))


if __name__ == "__main__":
    unittest.main()
