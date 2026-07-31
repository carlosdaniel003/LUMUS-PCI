import json
import tempfile
import unittest
from pathlib import Path

from src.infra.config_repository import ConfigRepository
from src.models.led_selection import LedSelection
from src.platform.fixed_mask_geometry_guard import (
    FixedMaskGeometryGuardMixin,
    assinatura_geometria,
    copiar_mascara_absoluta,
    instalar_repositorio_mascaras_absolutas,
)
from src.platform.led_project_repository import (
    instalar_repositorio_projetos_led,
)


class FakeFrame:
    def __init__(self, largura: int, altura: int):
        self.shape = (altura, largura, 3)
        self.size = largura * altura * 3


class FakeRepository:
    def __init__(self):
        self.active = "PLACA A"
        self.active_reads = 0
        self.projects = {
            "PLACA A": [
                LedSelection(
                    "LED_001",
                    900,
                    500,
                    18,
                    centro_x_normalizado=0.10,
                    centro_y_normalizado=0.20,
                    raio_normalizado=0.01,
                    largura_base=640,
                    altura_base=480,
                ),
                LedSelection("LED_002", 1100, 520, 20),
            ],
            "PLACA B": [
                LedSelection("LED_101", 300, 250, 14),
            ],
        }

    def obter_projeto_led_ativo(self):
        self.active_reads += 1
        return self.active

    def carregar_leds_fixos(self):
        return [copiar_mascara_absoluta(led) for led in self.projects[self.active]]

    def salvar_leds_fixos(self, leds, **_kwargs):
        self.projects[self.active] = [copiar_mascara_absoluta(led) for led in leds]
        return {}


class FakeOperationWindow:
    def __init__(self):
        self.previews = []

    def update_preview(self, _frame, leds):
        self.previews.append(assinatura_geometria(leds))


class FakeBaseApp:
    def __init__(self):
        self.config_repository = FakeRepository()
        self.modo_atual = "ocioso"
        self.guias_leds_fixos_visiveis = True
        self.selecao_manual_camera_ativa = False
        self.leds_fixos_configurados = self.config_repository.carregar_leds_fixos()
        self.leds_selecionados = []
        self.leds_manuais_camera = []
        self.operacao_leds_preview = []
        self.resultados_led_atual = []
        self.camera_frame_atual = FakeFrame(1920, 1080)
        self.largura_original = 1920
        self.altura_original = 1080
        self.operacao_ativa = False
        self.operacao_window = FakeOperationWindow()
        self.frame_updates = 0
        self.production_prepares = 0
        self.production_triggers = 0
        self.production_opens = 0

    def atualizar_frame_camera(self):
        self.frame_updates += 1

    def salvar_leds_fixos(self):
        self.leds_fixos_configurados = [
            copiar_mascara_absoluta(led)
            for led in self.leds_selecionados
        ]
        self.config_repository.salvar_leds_fixos(self.leds_fixos_configurados)

    def carregar_leds_fixos(self):
        self.leds_fixos_configurados = self.config_repository.carregar_leds_fixos()

    def carregar_configuracao(self):
        self.carregar_leds_fixos()

    def salvar_configuracoes_sistema(self, *_args, **_kwargs):
        return None

    def abrir_tela_operacao(self):
        self.production_opens += 1

    def preparar_tela_operacao(self):
        self.production_prepares += 1

    def disparar_inspecao_operacao(self):
        self.production_triggers += 1


class GuardedFakeApp(FixedMaskGeometryGuardMixin, FakeBaseApp):
    pass


class FixedMaskGeometryGuardTests(unittest.TestCase):
    ASSINATURA_A = (
        ("LED_001", 900, 500, 18),
        ("LED_002", 1100, 520, 20),
    )

    def test_copia_absoluta_descarta_metadados_normalizados(self):
        origem = LedSelection(
            "LED_001",
            900,
            500,
            18,
            centro_x_normalizado=0.1,
            centro_y_normalizado=0.2,
            raio_normalizado=0.01,
            largura_base=640,
            altura_base=480,
        )

        copia = copiar_mascara_absoluta(origem)

        self.assertEqual((900, 500, 18), (copia.centro_x, copia.centro_y, copia.raio))
        self.assertFalse(copia.possui_coordenadas_normalizadas())
        self.assertIsNone(copia.largura_base)
        self.assertIsNone(copia.altura_base)

    def test_resolucoes_transitorias_nunca_recalculam_mascaras(self):
        app = GuardedFakeApp()

        for largura, altura in (
            (640, 480),
            (1280, 720),
            (1920, 1080),
            (2560, 1440),
            (3840, 2160),
            (1920, 1080),
        ):
            app.camera_frame_atual = FakeFrame(largura, altura)
            app._synchronize_masks_with_current_frame(force=True)
            self.assertEqual(
                self.ASSINATURA_A,
                assinatura_geometria(app.leds_fixos_configurados),
            )

    def test_repeticao_de_frames_nao_produz_deriva_nem_leitura_do_json(self):
        app = GuardedFakeApp()
        leituras_iniciais = app.config_repository.active_reads

        for indice in range(500):
            largura, altura = (
                (640, 480)
                if indice % 2 == 0
                else (1920, 1080)
            )
            app.camera_frame_atual = FakeFrame(largura, altura)
            app.atualizar_frame_camera()

        self.assertEqual(
            self.ASSINATURA_A,
            assinatura_geometria(app.leds_fixos_configurados),
        )
        self.assertEqual(
            self.ASSINATURA_A,
            assinatura_geometria(app.operacao_leds_preview),
        )
        self.assertEqual(
            leituras_iniciais,
            app.config_repository.active_reads,
        )

    def test_mutacao_fora_do_seletor_e_restaurada_antes_da_producao(self):
        app = GuardedFakeApp()
        app.leds_fixos_configurados[0].centro_x += 73
        app.leds_fixos_configurados[1].centro_y -= 41

        app.preparar_tela_operacao()
        app.disparar_inspecao_operacao()

        self.assertEqual(
            self.ASSINATURA_A,
            assinatura_geometria(app.leds_fixos_configurados),
        )
        self.assertGreaterEqual(app._mask_guard_corrections, 1)
        self.assertEqual(1, app.production_prepares)
        self.assertEqual(1, app.production_triggers)

    def test_edicao_so_altera_geometria_permanente_ao_salvar(self):
        app = GuardedFakeApp()
        app.modo_atual = "selecionar_leds_camera"
        app.leds_selecionados = [
            LedSelection("LED_001", 905, 497, 18),
            LedSelection("LED_002", 1105, 517, 20),
        ]

        app._mask_guard_enforce()
        self.assertEqual(
            self.ASSINATURA_A,
            assinatura_geometria(app.leds_fixos_configurados),
        )

        app.salvar_leds_fixos()
        esperado = (
            ("LED_001", 905, 497, 18),
            ("LED_002", 1105, 517, 20),
        )
        self.assertEqual(
            esperado,
            assinatura_geometria(app.leds_fixos_configurados),
        )
        self.assertEqual(
            esperado,
            assinatura_geometria(app.config_repository.projects["PLACA A"]),
        )

    def test_troca_de_projeto_carrega_geometria_exata_antes_da_producao(self):
        app = GuardedFakeApp()
        app.config_repository.active = "PLACA B"

        app.preparar_tela_operacao()

        self.assertEqual(
            (("LED_101", 300, 250, 14),),
            assinatura_geometria(app.leds_fixos_configurados),
        )

    def test_nova_instancia_simula_reinicio_sem_deslocamento(self):
        primeira = GuardedFakeApp()
        primeira.camera_frame_atual = FakeFrame(640, 480)
        primeira._synchronize_masks_with_current_frame(force=True)

        segunda = GuardedFakeApp()
        segunda.camera_frame_atual = FakeFrame(1920, 1080)
        segunda._synchronize_masks_with_current_frame(force=True)

        self.assertEqual(
            assinatura_geometria(primeira.leds_fixos_configurados),
            assinatura_geometria(segunda.leds_fixos_configurados),
        )
        self.assertEqual(
            self.ASSINATURA_A,
            assinatura_geometria(segunda.leds_fixos_configurados),
        )

    def test_preview_de_operacao_recebe_a_mesma_geometria_travada(self):
        app = GuardedFakeApp()
        app.operacao_ativa = True
        app.camera_frame_atual = FakeFrame(1920, 1080)
        app.leds_fixos_configurados[0].centro_x = 1

        app._synchronize_masks_with_current_frame(force=True)

        self.assertTrue(app.operacao_window.previews)
        self.assertEqual(self.ASSINATURA_A, app.operacao_window.previews[-1])

    def test_repositorio_persiste_apenas_pixels_absolutos(self):
        instalar_repositorio_projetos_led()
        instalar_repositorio_mascaras_absolutas()

        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "config.json"
            repository = ConfigRepository(config_file=caminho)
            repository.salvar_leds_fixos(
                [
                    LedSelection(
                        "LED_001",
                        900,
                        500,
                        18,
                        centro_x_normalizado=0.1,
                        centro_y_normalizado=0.2,
                        raio_normalizado=0.01,
                        largura_base=640,
                        altura_base=480,
                    )
                ],
                largura_base=1920,
                altura_base=1080,
                projeto="PLACA TESTE",
            )

            dados = json.loads(caminho.read_text(encoding="utf-8"))
            salvo = dados["led_projects"]["PLACA TESTE"]["fixed_leds"][0]
            carregado = repository.carregar_leds_fixos("PLACA TESTE")[0]

        self.assertEqual(
            {"id": "LED_001", "centro_x": 900, "centro_y": 500, "raio": 18},
            salvo,
        )
        self.assertEqual((900, 500, 18), (
            carregado.centro_x,
            carregado.centro_y,
            carregado.raio,
        ))
        self.assertFalse(carregado.possui_coordenadas_normalizadas())


if __name__ == "__main__":
    unittest.main()
