from __future__ import annotations

import unittest

from src.models.led_selection import LedSelection
from src.platform.freeform_live_camera_geometry import (
    FreeformLiveCameraGeometryMixin,
)
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


class _LiveViewFake:
    def __init__(self) -> None:
        self.drawn: list[list[dict]] = []

    def desenhar_canvas(self, leds, _resultados, *args, **kwargs):
        self.drawn.append([led.to_dict() for led in (leds or ())])
        return True


class _LegacyLiveCameraRefreshBase:
    """Reproduz a degradação real do refresh antigo: id/centro/raio apenas."""

    def atualizar_frame_camera(self):
        self.leds_selecionados = [
            LedSelection(
                id=led.id,
                centro_x=led.centro_x,
                centro_y=led.centro_y,
                raio=led.raio,
            )
            for led in self.leds_manuais_camera
        ]
        self.view.desenhar_canvas(self.leds_selecionados, [])
        # As previews auxiliares são geradas depois do primeiro desenho do frame.
        self.preview_auxiliar = [led.to_dict() for led in self.leds_selecionados]
        return "legacy-refresh"


class _LiveCameraGeometryHarness(
    FreeformLiveCameraGeometryMixin,
    _LegacyLiveCameraRefreshBase,
):
    pass


class FreeformProjectRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        instalar_persistencia_segmento_livre()

    def test_refresh_camera_nunca_expoe_segmento_livre_como_circulo(self):
        original = criar_segmento_livre_por_pontos(
            [(40, 30), (130, 30), (130, 75), (40, 75)],
            "SEG_001",
        )
        pontos_originais = list(original.pontos_segmento_livre or ())

        app = object.__new__(_LiveCameraGeometryHarness)
        app.camera_ativa = True
        app.camera_em_pausa_analise = False
        app.selecao_manual_camera_ativa = True
        app.modo_atual = "selecionar_leds_camera"
        app.leds_manuais_camera = [
            copiar_mascara_absoluta_segmento_livre(original)
        ]
        app.leds_selecionados = []
        app.view = _LiveViewFake()
        app.preview_auxiliar = []

        retorno = app.atualizar_frame_camera()

        self.assertEqual("legacy-refresh", retorno)
        self.assertEqual(1, len(app.view.drawn))
        self.assertEqual("segmento", app.view.drawn[0][0].get("tipo_roi"))
        self.assertEqual(
            [[float(x), float(y)] for x, y in pontos_originais],
            app.view.drawn[0][0].get("pontos_segmento_livre"),
        )
        self.assertEqual("segmento", app.preview_auxiliar[0].get("tipo_roi"))
        self.assertTrue(app.leds_selecionados[0].eh_segmento_livre)
        self.assertTrue(app.leds_manuais_camera[0].eh_segmento_livre)
        self.assertEqual(
            pontos_originais,
            list(app.leds_selecionados[0].pontos_segmento_livre or ()),
        )

    def test_refresh_sem_selecao_manual_permanece_no_fluxo_legado(self):
        app = object.__new__(_LiveCameraGeometryHarness)
        app.camera_ativa = True
        app.camera_em_pausa_analise = False
        app.selecao_manual_camera_ativa = False
        app.modo_atual = "tela_ao_vivo"
        app.leds_manuais_camera = []
        app.leds_selecionados = []
        app.view = _LiveViewFake()
        app.preview_auxiliar = []

        self.assertEqual("legacy-refresh", app.atualizar_frame_camera())
        self.assertEqual([[]], app.view.drawn)

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