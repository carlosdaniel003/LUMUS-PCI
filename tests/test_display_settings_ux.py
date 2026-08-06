import inspect
import unittest

import src.platform.display_settings_ux as modulo
from src.platform.display_settings_ux import (
    calcular_unidades_rolagem,
    instalar_ux_configuracoes_display,
    rolar_canvas,
)
from src.ui.main_window import ODINView


class FakeEvent:
    def __init__(self, delta=0, num=None):
        self.delta = delta
        self.num = num
        self.state = 0


class FakeCanvas:
    def __init__(self, inicio=0.2, fim=0.8):
        self.inicio = float(inicio)
        self.fim = float(fim)
        self.chamadas = []

    def yview(self):
        return self.inicio, self.fim

    def yview_scroll(self, unidades, modo):
        self.chamadas.append((unidades, modo))


class DisplaySettingsUxTests(unittest.TestCase):
    def test_roda_windows_converte_direcao_e_tres_unidades(self):
        self.assertEqual(-3, calcular_unidades_rolagem(FakeEvent(delta=120)))
        self.assertEqual(3, calcular_unidades_rolagem(FakeEvent(delta=-120)))
        self.assertEqual(-6, calcular_unidades_rolagem(FakeEvent(delta=240)))

    def test_roda_linux_converte_botoes_quatro_e_cinco(self):
        self.assertEqual(-3, calcular_unidades_rolagem(FakeEvent(num=4)))
        self.assertEqual(3, calcular_unidades_rolagem(FakeEvent(num=5)))

    def test_evento_sem_delta_nao_rola(self):
        self.assertEqual(0, calcular_unidades_rolagem(FakeEvent()))

    def test_canvas_rola_quando_existe_conteudo_na_direcao(self):
        canvas = FakeCanvas(inicio=0.2, fim=0.8)

        self.assertTrue(rolar_canvas(canvas, 3))
        self.assertEqual([(3, "units")], canvas.chamadas)

    def test_canvas_nao_ultrapassa_inicio_ou_fim(self):
        topo = FakeCanvas(inicio=0.0, fim=0.5)
        fim = FakeCanvas(inicio=0.5, fim=1.0)

        self.assertFalse(rolar_canvas(topo, -3))
        self.assertFalse(rolar_canvas(fim, 3))
        self.assertEqual([], topo.chamadas)
        self.assertEqual([], fim.chamadas)

    def test_modulo_de_navegacao_nao_muda_geometria(self):
        codigo = inspect.getsource(modulo)
        self.assertNotIn("pack_configure", codigo)
        self.assertNotIn(".grid(", codigo)
        self.assertNotIn("pack_forget", codigo)
        self.assertNotIn("DisplayThemeMixin", codigo)

    def test_instalador_da_janela_e_idempotente(self):
        original = ODINView.abrir_janela_configuracoes
        try:
            instalar_ux_configuracoes_display()
            primeira = ODINView.abrir_janela_configuracoes
            instalar_ux_configuracoes_display()
            segunda = ODINView.abrir_janela_configuracoes

            self.assertIs(primeira, segunda)
            self.assertTrue(
                getattr(
                    primeira,
                    "_odin_display_settings_ux_instalado",
                    False,
                )
            )
            self.assertIs(original, getattr(primeira, "_odin_original"))
        finally:
            ODINView.abrir_janela_configuracoes = original


if __name__ == "__main__":
    unittest.main()
