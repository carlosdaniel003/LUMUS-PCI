from __future__ import annotations

import unittest

from src.models.led_selection import LedSelection
from src.platform.freeform_segment_persistence import (
    copiar_mascara_absoluta_segmento_livre,
    instalar_persistencia_segmento_livre,
)
from src.platform.freeform_segment_roi import criar_segmento_livre_por_pontos
from src.platform.led_project_manager import LedProjectManagerMixin


class _LabelFake:
    def __init__(self) -> None:
        self.text = ""

    def configure(self, **kwargs) -> None:
        self.text = str(kwargs.get("text", self.text))


class _ViewFake:
    def __init__(self) -> None:
        self.label_meta_placa = _LabelFake()
        self.status = ""

    def atualizar_status(self, texto: str) -> None:
        self.status = str(texto)


class _RepositoryFake:
    def __init__(self) -> None:
        self.active = "TESTE"
        self.data: dict[str, list[dict]] = {"TESTE": []}

    def listar_projetos_led(self):
        return list(self.data.keys())

    def definir_projeto_led_ativo(self, nome: str) -> bool:
        if nome not in self.data:
            return False
        self.active = nome
        return True

    def salvar_leds_fixos(
        self,
        leds,
        largura_base=None,
        altura_base=None,
        projeto=None,
    ):
        nome = str(projeto or self.active)
        self.data[nome] = [led.to_dict() for led in leds]
        return {"fixed_leds": list(self.data[nome])}

    def carregar_leds_fixos(self, projeto=None):
        nome = str(projeto or self.active)
        resultado = []
        for item in self.data.get(nome, []):
            led = LedSelection.from_dict(item)
            if led is not None:
                resultado.append(led)
        return resultado


class _LegacyProjectSaveBase:
    """Simula o salvamento-base de app.py que historicamente guardava só círculo."""

    def salvar_leds_fixos(self) -> None:
        circulos = [
            LedSelection(
                id=led.id,
                centro_x=led.centro_x,
                centro_y=led.centro_y,
                raio=led.raio,
            )
            for led in self.leds_selecionados
        ]
        self.legacy_saved_circle = bool(circulos and circulos[0].eh_circulo)
        self.config_repository.salvar_leds_fixos(
            circulos,
            projeto=self.projeto_led_ativo,
        )
        self.leds_fixos_configurados = circulos


class _ProjectManagerHarness(
    LedProjectManagerMixin,
    _LegacyProjectSaveBase,
):
    pass


class FreeformProjectRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        instalar_persistencia_segmento_livre()

    def test_salvar_e_reabrir_projeto_preserva_segmento_ponto_a_ponto(self):
        original = criar_segmento_livre_por_pontos(
            [(31, 24), (95, 20), (113, 47), (76, 70), (36, 58)],
            "LED_001",
        )
        pontos_originais = list(original.pontos_segmento_livre or ())

        app = object.__new__(_ProjectManagerHarness)
        app.root = object()
        app.view = _ViewFake()
        app.config_repository = _RepositoryFake()
        app.projeto_led_ativo = "TESTE"
        app.largura_original = 1920
        app.altura_original = 1080
        app.leds_selecionados = [
            copiar_mascara_absoluta_segmento_livre(original)
        ]
        app.leds_fixos_configurados = []
        app.legacy_saved_circle = False

        salvo = app._salvar_leds_no_projeto(
            "TESTE",
            confirmar_substituicao=False,
        )

        self.assertTrue(salvo)
        self.assertTrue(app.legacy_saved_circle)

        bruto = app.config_repository.data["TESTE"][0]
        self.assertEqual("segmento", bruto.get("tipo_roi"))
        self.assertEqual(len(pontos_originais), len(bruto.get("pontos_segmento_livre", [])))

        reaberto = app.config_repository.carregar_leds_fixos(
            projeto="TESTE"
        )[0]
        self.assertTrue(reaberto.eh_segmento)
        self.assertTrue(reaberto.eh_segmento_livre)
        self.assertEqual(pontos_originais, list(reaberto.pontos_segmento_livre or ()))
        self.assertEqual(1920, reaberto.largura_base)
        self.assertEqual(1080, reaberto.altura_base)

    def test_projeto_so_com_circulos_continua_no_fluxo_legado(self):
        circulo = LedSelection(
            id="LED_001",
            centro_x=120,
            centro_y=80,
            raio=12,
        )
        app = object.__new__(_ProjectManagerHarness)
        app.root = object()
        app.view = _ViewFake()
        app.config_repository = _RepositoryFake()
        app.projeto_led_ativo = "TESTE"
        app.largura_original = 1920
        app.altura_original = 1080
        app.leds_selecionados = [circulo]
        app.leds_fixos_configurados = []
        app.legacy_saved_circle = False

        self.assertTrue(
            app._salvar_leds_no_projeto(
                "TESTE",
                confirmar_substituicao=False,
            )
        )
        reaberto = app.config_repository.carregar_leds_fixos("TESTE")[0]
        self.assertTrue(reaberto.eh_circulo)
        self.assertIsNone(reaberto.pontos_segmento_livre)


if __name__ == "__main__":
    unittest.main()
