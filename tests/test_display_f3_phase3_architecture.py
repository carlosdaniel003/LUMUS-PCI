from __future__ import annotations

import inspect
import unittest

from src.platform.display_check_editor import (
    DisplayCheckManagerWindow,
    DisplayCheckMaskEditorWindow,
    proximo_estado_check_display,
)
from src.platform.display_production_f3 import DisplayProductionF3Mixin
from src.platform.display_project_repository import (
    DISPLAY_CHECK_STATE_IGNORE,
    DISPLAY_CHECK_STATE_OFF,
    DISPLAY_CHECK_STATE_ON,
    DisplayProjectRepository,
)


class DisplayF3Phase3ArchitectureTests(unittest.TestCase):
    def test_fase3_declara_checks_sem_adicionar_analise(self):
        self.assertEqual(
            (
                "checks_display_persistentes",
                "ordem_checks_configuravel",
                "estado_mascara_por_check",
                "editor_visual_checks",
            ),
            DisplayProductionF3Mixin.responsabilidades_f3_fase3(),
        )

    def test_ciclo_visual_e_ignore_on_off_ignore(self):
        state = DISPLAY_CHECK_STATE_IGNORE
        state = proximo_estado_check_display(state)
        self.assertEqual(DISPLAY_CHECK_STATE_ON, state)
        state = proximo_estado_check_display(state)
        self.assertEqual(DISPLAY_CHECK_STATE_OFF, state)
        state = proximo_estado_check_display(state)
        self.assertEqual(DISPLAY_CHECK_STATE_IGNORE, state)

    def test_editor_de_checks_nao_importa_motor_roi_ou_estado_f2(self):
        source = inspect.getsource(__import__(
            "src.platform.display_check_editor",
            fromlist=["DisplayCheckManagerWindow"],
        ))
        for forbidden in (
            "OperationEngine",
            "LedSelection",
            "ConfigRepository",
            "operacao_engine",
            "operacao_ativa",
            "leds_fixos_configurados",
            "leds_selecionados",
            "disparar_inspecao_operacao",
            "preparar_tela_operacao",
        ):
            self.assertNotIn(forbidden, source)

    def test_repositorio_de_check_continua_sendo_o_repositorio_display(self):
        signature = inspect.signature(DisplayCheckManagerWindow.__init__)
        self.assertIn("repository", signature.parameters)
        self.assertIn("project_name", signature.parameters)
        self.assertIn("frame_provider", signature.parameters)
        self.assertTrue(issubclass(DisplayProjectRepository, object))

    def test_editor_visual_recebe_mascaras_e_estados_por_argumento(self):
        signature = inspect.signature(DisplayCheckMaskEditorWindow.__init__)
        for parameter in (
            "check",
            "master_resolution",
            "masks",
            "frame",
            "on_save",
        ):
            self.assertIn(parameter, signature.parameters)

    def test_f3_continua_sem_sobrescrever_runtime_do_f2(self):
        forbidden = {
            "abrir_tela_operacao",
            "fechar_tela_operacao",
            "preparar_tela_operacao",
            "disparar_inspecao_operacao",
            "analisar_led_selecionado",
            "iniciar_tela_ao_vivo",
            "parar_tela_ao_vivo",
            "atualizar_frame_camera",
            "_evento_enter_pressionado",
            "_evento_enter_liberado",
        }
        self.assertTrue(forbidden.isdisjoint(DisplayProductionF3Mixin.__dict__))

    def test_fase3_nao_instala_engine_de_analise(self):
        source_runtime = inspect.getsource(__import__(
            "src.platform.display_production_f3",
            fromlist=["DisplayProductionF3Mixin"],
        ))
        source_editor = inspect.getsource(__import__(
            "src.platform.display_check_editor",
            fromlist=["DisplayCheckMaskEditorWindow"],
        ))
        self.assertNotIn("OperationEngine", source_runtime)
        self.assertNotIn("ReferenceLedClassifier", source_runtime)
        self.assertNotIn("OperationEngine", source_editor)
        self.assertNotIn("ReferenceLedClassifier", source_editor)


if __name__ == "__main__":
    unittest.main()
