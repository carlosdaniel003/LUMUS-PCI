import unittest

from src.platform.project_master_resolution_guard import (
    ProjectMasterResolutionGuardMixin,
)
from src.platform.raspberry_pi3_production_app import RaspberryPi3ProductionApp
from src.platform.project_master_resolution import ProjectMasterResolutionMixin


class FakeBase:
    def __init__(self):
        self.events = []
        self.largura_original = 1920
        self.altura_original = 1080
        self.selected = "PLACA 640"
        self.real_resolution = (640, 480)

    def _selecionar_projeto_led_existente(self, _projetos):
        self.events.append("dialogo_confirmado")
        return self.selected

    def _aplicar_resolucao_mestra_projeto(
        self,
        projeto,
        reiniciar_se_necessario=True,
    ):
        self.events.append(
            ("resolucao_aplicada", projeto, reiniciar_se_necessario)
        )
        return True

    def _obter_resolucao_edicao_atual(self):
        return self.real_resolution

    def _salvar_leds_no_projeto(self, nome_projeto, **_kwargs):
        self.events.append(
            (
                "salvamento_base",
                nome_projeto,
                self.largura_original,
                self.altura_original,
            )
        )
        return True


class GuardFake(ProjectMasterResolutionGuardMixin, FakeBase):
    pass


class ProjectMasterResolutionGuardTests(unittest.TestCase):
    def test_resolucao_e_aplicada_antes_do_gerenciador_receber_projeto(self):
        app = GuardFake()

        escolhido = app._selecionar_projeto_led_existente(["PLACA 640"])

        self.assertEqual("PLACA 640", escolhido)
        self.assertEqual("dialogo_confirmado", app.events[0])
        self.assertEqual(
            ("resolucao_aplicada", "PLACA 640", True),
            app.events[1],
        )

    def test_cancelar_nao_aplica_resolucao(self):
        app = GuardFake()
        app.selected = None

        self.assertIsNone(app._selecionar_projeto_led_existente(["PLACA 640"]))
        self.assertEqual(["dialogo_confirmado"], app.events)

    def test_salvar_reafirma_base_com_resolucao_real(self):
        app = GuardFake()
        app.real_resolution = (640, 480)

        self.assertTrue(app._salvar_leds_no_projeto("PLACA 640"))

        self.assertEqual(640, app.largura_original)
        self.assertEqual(480, app.altura_original)
        self.assertEqual(
            ("salvamento_base", "PLACA 640", 640, 480),
            app.events[-1],
        )

    def test_mro_final_coloca_guard_antes_da_resolucao_mestra(self):
        mro = RaspberryPi3ProductionApp.__mro__
        self.assertIn(ProjectMasterResolutionGuardMixin, mro)
        self.assertIn(ProjectMasterResolutionMixin, mro)
        self.assertLess(
            mro.index(ProjectMasterResolutionGuardMixin),
            mro.index(ProjectMasterResolutionMixin),
        )


if __name__ == "__main__":
    unittest.main()
