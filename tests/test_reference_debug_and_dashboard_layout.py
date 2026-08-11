import inspect
import unittest
from types import SimpleNamespace

from src.core.debug_formatter import formatar_resultado_textual_multiplos
from src.models.led_features import LedFeatures
from src.platform.reference_debug_context import criar_contexto_debug_referencias
from src.ui.main_window_parts.layout.criar_area_dashboard import criar_area_dashboard
from src.ui.main_window_parts.panels.criar_painel_central import criar_painel_central
from src.ui.main_window_parts.panels.criar_painel_direito import criar_painel_direito
from src.ui.main_window_parts.panels.criar_tabela_inferior import criar_tabela_inferior


class FakeApp:
    def __init__(self):
        self.projeto_led_ativo = "DISPLAY-7SEG"
        self.features_referencia_acesa = LedFeatures(
            v_mean=250.0,
            v_max=255.0,
            v_std=12.0,
            s_mean=18.0,
            h_mean=1.0,
            glow_score=240.0,
            percent_hot_250=0.88,
        )
        self.features_referencia_apagada = LedFeatures(
            v_mean=28.0,
            v_max=60.0,
            v_std=4.0,
            s_mean=20.0,
            h_mean=2.0,
            glow_score=12.0,
            percent_hot_250=0.0,
        )
        self.features_referencia_pouca_luz = None
        self._referencias_ativas_por_tipo = {
            "aceso": [
                {
                    "scope": "global",
                    "index": 0,
                    "sample": {
                        "id": "acesa-global-001",
                        "image_path": "/tmp/ref_on_global.png",
                        "roi": {
                            "tipo_roi": "segmento",
                            "centro_x": 100,
                            "centro_y": 120,
                            "largura": 90,
                            "altura": 18,
                            "angulo": -3.5,
                        },
                        "features": self.features_referencia_acesa.to_dict(),
                    },
                },
                {
                    "scope": "project",
                    "index": 0,
                    "sample": {
                        "id": "acesa-projeto-002",
                        "image_path": "/tmp/ref_on_project.png",
                        "roi": {
                            "tipo_roi": "circulo",
                            "centro_x": 200,
                            "centro_y": 220,
                            "raio": 14,
                        },
                        "features": self.features_referencia_acesa.to_dict(),
                    },
                },
            ],
            "apagado": [
                {
                    "scope": "project",
                    "index": 0,
                    "sample": {
                        "id": "apagada-projeto-001",
                        "image_path": "/tmp/ref_off.png",
                        "features": self.features_referencia_apagada.to_dict(),
                    },
                }
            ],
            "pouca_luz": [],
        }

    def _projeto_referencia_ativo(self):
        return self.projeto_led_ativo


class ReferenceDebugContextTests(unittest.TestCase):
    def test_contexto_identifica_projeto_escopos_e_geometria(self):
        contexto = criar_contexto_debug_referencias(FakeApp())

        self.assertEqual("DISPLAY-7SEG", contexto["projeto"])
        self.assertEqual(2, contexto["grupos"]["aceso"]["total"])
        self.assertEqual(1, contexto["grupos"]["aceso"]["globais"])
        self.assertEqual(1, contexto["grupos"]["aceso"]["projeto"])
        self.assertEqual(
            "segmento",
            contexto["grupos"]["aceso"]["amostras"][0]["roi"]["tipo"],
        )
        self.assertEqual(
            "ref_on_global.png",
            contexto["grupos"]["aceso"]["amostras"][0]["arquivo"],
        )
        self.assertEqual(
            250.0,
            contexto["grupos"]["aceso"]["agregado"]["v_mean"],
        )
        self.assertFalse(contexto["pouca_luz_habilitada"])

    def test_debug_textual_exibe_referencias_que_participaram_da_analise(self):
        contexto = criar_contexto_debug_referencias(FakeApp())
        texto = formatar_resultado_textual_multiplos(
            [],
            SimpleNamespace(caminho_resultado_imagem=None),
            contexto_referencias=contexto,
        )

        self.assertIn("REFERÊNCIAS ATIVAS DA ANÁLISE", texto)
        self.assertIn("Projeto de Carregar LEDs: DISPLAY-7SEG", texto)
        self.assertIn("ACESO: 2/3 ativas | GLOBAL=1 | PROJETO=1", texto)
        self.assertIn("#1 GLOBAL", texto)
        self.assertIn("ROI segmento", texto)
        self.assertIn("perfil agregado: v_mean=250.0", texto)
        self.assertIn("POUCA LUZ: 0/3 ativas", texto)
        self.assertIn("POUCA_LUZ está DESABILITADO", texto)
        self.assertIn(
            "Resultados ACESO/APAGADO não podem ser sobrescritos para POUCA_LUZ",
            texto,
        )


class DashboardLayoutTests(unittest.TestCase):
    def test_topo_contem_somente_principal_e_resultado(self):
        area = inspect.getsource(criar_area_dashboard)
        central = inspect.getsource(criar_painel_central)

        self.assertIn("grid_columnconfigure(0, weight=7)", area)
        self.assertIn("grid_columnconfigure(1, weight=3)", area)
        self.assertNotIn("grid_columnconfigure(2", area)
        self.assertNotIn("canvas_mapa_intensidade", central)
        self.assertIn('"RESULTADO GERAL"', central)

    def test_faixa_inferior_tem_seis_paineis_na_ordem_solicitada(self):
        fonte = inspect.getsource(criar_painel_direito)
        titulos = [
            '"Imagem de teste • Canal V"',
            '"Mapa de intensidade"',
            '"Máscara / ROI"',
            '"ROI ampliado"',
            '"Debug técnico"',
            '"Log produção"',
        ]
        posicoes = [fonte.index(titulo) for titulo in titulos]
        self.assertEqual(posicoes, sorted(posicoes))
        self.assertIn("for coluna in range(6)", fonte)
        self.assertIn("column=5", fonte)

    def test_historico_ocupa_as_duas_colunas_do_novo_grid(self):
        fonte = inspect.getsource(criar_tabela_inferior)
        self.assertIn("columnspan=2", fonte)


if __name__ == "__main__":
    unittest.main()
