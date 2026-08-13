import tkinter as tk


def __init__(self, root: tk.Tk, callbacks: dict, raio_atual_px: int) -> None:
    self.root = root
    self.callbacks = callbacks
    self.raio_atual_px = raio_atual_px

    self.imagem_tk = None
    self.imagem_exibicao = None
    self.imagens_auxiliares_tk = {}
    self.imagens_auxiliares_originais = {}
    self.imagem_canvas_original = None
    self.ultimo_led_selecionado = None
    self.ultimo_resultado_led_atual = None
    self.escala_exibicao = 1.0
    self.deslocamento_imagem_x = 0
    self.deslocamento_imagem_y = 0
    self.largura_imagem_exibida = 0
    self.altura_imagem_exibida = 0
    self.resolucao_atual = "--"
    self._ultimo_resultado_historico = None
    self._redimensionamento_pendente = None
    self.selecao_led_ativa = False
    self.tela_ao_vivo_ativa = False
    self.botao_selecionar_leds = None
    self.botao_tela_ao_vivo = None
    self.botao_screenshot_principal = None
    self.tela_cheia_ativa = False
    self.relogio_visivel = True
    self.botao_toggle_relogio = None
    self._atualizacao_relogio_pendente = None
    self.logo_tk = None
    self.lupa_tk = None
    self.rotacao_visual_principal = 0
    self.botao_rotacao_principal = None

    self.janela_imagem_tela_cheia = None
    self.canvas_imagem_tela_cheia = None
    self.chave_imagem_tela_cheia = None
    self.imagem_tela_cheia_tk = None
    self._redesenho_imagem_tela_cheia_pendente = None
    self._imagens_tela_cheia_bindings_instalados = False

    self.root.title("ODIN - Observador Digital Inteligente")

    largura_tela = max(800, int(self.root.winfo_screenwidth()))
    altura_tela = max(600, int(self.root.winfo_screenheight()))
    largura_inicial = min(1600, largura_tela)
    altura_inicial = min(900, altura_tela)
    largura_minima = min(1280, largura_tela)
    altura_minima = min(760, altura_tela)

    self.root.geometry(f"{largura_inicial}x{altura_inicial}")
    self.root.minsize(largura_minima, altura_minima)
    self.root.configure(bg=self.COR_FUNDO_APP)

    self.configurar_atalhos_tela()
    self.configurar_estilo_tabela()
    self.criar_layout()

    configurar_fullscreen_imagens = getattr(
        self,
        "configurar_abertura_imagens_tela_cheia",
        None,
    )
    if callable(configurar_fullscreen_imagens):
        configurar_fullscreen_imagens()

    self.iniciar_relogio_sistema()

    self.root.after(120, self.alternar_tela_cheia)
