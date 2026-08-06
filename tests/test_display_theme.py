import unittest

from src.platform.display_theme import (
    DISPLAY_BLUE,
    DISPLAY_DARK,
    DISPLAY_DARK_ALT,
    DISPLAY_DARK_CARD,
    DISPLAY_DARK_RAISED,
    DISPLAY_INK,
    DISPLAY_WHITE,
    DISPLAY_YELLOW,
    DISPLAY_YELLOW_DARK,
    DisplayThemeMixin,
    aplicar_tema_arvore,
    instalar_paleta_display,
    mapear_cor_display,
)
from src.platform.raspberry_pi3_production_app import (
    RaspberryPi3ProductionApp,
)
from src.ui.main_window import ODINView
from src.ui.operation_window_raspberry import RaspberryOperationWindow


class FakeWidget:
    def __init__(self, classe="Frame", opcoes=None, filhos=None):
        self._classe = classe
        self._opcoes = dict(opcoes or {})
        self._filhos = list(filhos or ())

    def winfo_class(self):
        return self._classe

    def winfo_children(self):
        return tuple(self._filhos)

    def cget(self, opcao):
        if opcao not in self._opcoes:
            raise KeyError(opcao)
        return self._opcoes[opcao]

    def configure(self, **opcoes):
        self._opcoes.update(opcoes)


class DisplayThemeTests(unittest.TestCase):
    def test_cores_principais_sao_exatamente_as_solicitadas(self):
        self.assertEqual("#F5C518", DISPLAY_YELLOW)
        self.assertEqual("#2596BE", DISPLAY_BLUE)
        self.assertEqual("#0B0D0F", DISPLAY_DARK)

    def test_fundos_sao_escuros_e_detalhes_sao_amarelos(self):
        self.assertEqual(
            DISPLAY_DARK,
            mapear_cor_display("background", "#030712"),
        )
        self.assertEqual(
            DISPLAY_DARK_ALT,
            mapear_cor_display("background", "#07111F"),
        )
        self.assertEqual(
            DISPLAY_DARK_CARD,
            mapear_cor_display("background", "#0B1626"),
        )
        self.assertEqual(
            DISPLAY_YELLOW,
            mapear_cor_display("highlightbackground", "#122033"),
        )
        self.assertEqual(
            DISPLAY_YELLOW,
            mapear_cor_display("foreground", "#38BDF8"),
        )

    def test_nao_substitui_cores_semanticas_ok_e_ng(self):
        self.assertEqual(
            "#16A34A",
            mapear_cor_display("background", "#16A34A"),
        )
        self.assertEqual(
            "#DC2626",
            mapear_cor_display("background", "#DC2626"),
        )

    def test_botao_verde_antigo_recebe_amarelo_com_texto_escuro(self):
        botao = FakeWidget(
            classe="Button",
            opcoes={
                "background": "#16A34A",
                "foreground": "#FFFFFF",
                "activebackground": "#15803D",
                "activeforeground": "#FFFFFF",
                "highlightbackground": "#122033",
                "text": "PRODUÇÃO  F2",
            },
        )

        aplicar_tema_arvore(botao)

        self.assertEqual(DISPLAY_YELLOW, botao._opcoes["background"])
        self.assertEqual(DISPLAY_INK, botao._opcoes["foreground"])
        self.assertEqual(
            DISPLAY_YELLOW_DARK,
            botao._opcoes["activebackground"],
        )

    def test_arvore_tematiza_janela_e_texto_da_legenda(self):
        legenda = FakeWidget(
            classe="Label",
            opcoes={
                "background": "#07111F",
                "foreground": "#2563EB",
                "text": "CÍRCULO AZUL: LED APAGADO",
            },
        )
        raiz = FakeWidget(
            classe="Toplevel",
            opcoes={
                "background": "#020617",
            },
            filhos=[legenda],
        )

        aplicar_tema_arvore(raiz)

        self.assertEqual(DISPLAY_DARK, raiz._opcoes["background"])
        self.assertEqual(DISPLAY_DARK_ALT, legenda._opcoes["background"])
        self.assertEqual(DISPLAY_YELLOW, legenda._opcoes["foreground"])
        self.assertEqual(
            "CÍRCULO AMARELO: LED APAGADO",
            legenda._opcoes["text"],
        )

    def test_instalacao_atualiza_constantes_das_telas(self):
        instalar_paleta_display()

        self.assertEqual(DISPLAY_DARK, ODINView.COR_FUNDO_APP)
        self.assertEqual(DISPLAY_DARK_ALT, ODINView.COR_TOPO)
        self.assertEqual(DISPLAY_DARK_CARD, ODINView.COR_CARD)
        self.assertEqual(DISPLAY_DARK_RAISED, ODINView.COR_CARD_2)
        self.assertEqual(DISPLAY_YELLOW, ODINView.COR_BORDA)
        self.assertEqual(DISPLAY_YELLOW, ODINView.COR_AZUL)
        self.assertEqual(DISPLAY_WHITE, ODINView.COR_TEXTO)
        self.assertEqual(
            DISPLAY_DARK,
            RaspberryOperationWindow.PREVIEW_BACKGROUND,
        )
        self.assertEqual(
            DISPLAY_YELLOW,
            RaspberryOperationWindow.PREVIEW_BORDER,
        )

    def test_perfil_display_inclui_mixin_de_tema(self):
        self.assertIn(DisplayThemeMixin, RaspberryPi3ProductionApp.__mro__)


if __name__ == "__main__":
    unittest.main()
