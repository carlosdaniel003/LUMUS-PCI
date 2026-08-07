from __future__ import annotations

import tkinter as tk
from typing import Callable


class FullscreenLedSelectionMixin:
    """Exibe o editor existente em uma janela de tela cheia, sem tocar na câmera."""

    def __init__(self, *args, **kwargs) -> None:
        self._selecao_tela_cheia_window = None
        self._selecao_tela_cheia_canvas = None
        self._selecao_tela_cheia_canvas_original = None
        self._selecao_tela_cheia_fechando = False
        self._botao_tipo_roi_segmento = None
        self._botao_tipo_roi_circulo = None
        super().__init__(*args, **kwargs)

    def _selecao_tela_cheia_esta_aberta(self) -> bool:
        janela = self._selecao_tela_cheia_window
        if janela is None:
            return False
        try:
            return bool(janela.winfo_exists())
        except Exception:
            return False

    def _atualizar_botoes_tipo_roi(self) -> None:
        tipo = str(getattr(self, "tipo_roi_edicao", "segmento"))
        for botao, valor in (
            (self._botao_tipo_roi_segmento, "segmento"),
            (self._botao_tipo_roi_circulo, "circulo"),
        ):
            if botao is None:
                continue
            ativo = tipo == valor
            try:
                botao.configure(
                    bg="#D6A900" if ativo else "#182231",
                    fg="#111318" if ativo else "#DCE5EF",
                    activebackground="#F5C518" if ativo else "#243246",
                    activeforeground="#111318" if ativo else "#FFFFFF",
                )
            except Exception:
                pass

    def _selecionar_tipo_roi_toolbar(self, tipo: str) -> None:
        definir = getattr(self, "definir_tipo_roi_edicao", None)
        if callable(definir):
            definir(tipo)
        else:
            self.tipo_roi_edicao = str(tipo)
            self._atualizar_botoes_tipo_roi()
        canvas = self._selecao_tela_cheia_canvas
        if canvas is not None:
            try:
                canvas.focus_set()
            except Exception:
                pass

    def _criar_interface_selecao_tela_cheia(self):
        janela = tk.Toplevel(self.root)
        janela.title("ODIN • Seleção de ROIs")
        janela.configure(bg="#020617")

        barra = tk.Frame(
            janela,
            bg="#07111F",
            height=66,
            highlightthickness=1,
            highlightbackground="#122033",
        )
        barra.pack(side=tk.TOP, fill=tk.X)
        barra.pack_propagate(False)

        textos = tk.Frame(barra, bg="#07111F")
        textos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(18, 8), pady=7)

        tk.Label(
            textos,
            text="SELEÇÃO E AJUSTE DE ROIs",
            font=("DejaVu Sans", 12, "bold"),
            fg="#F9FAFB",
            bg="#07111F",
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            textos,
            text=(
                "Segmento: arraste para criar • Shift+arraste seleciona área • "
                "alças ajustam largura/altura/ângulo • setas movem 1 px"
            ),
            font=("DejaVu Sans", 8),
            fg="#AAB8C8",
            bg="#07111F",
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        botao_ok = tk.Button(
            barra,
            text="OK",
            command=self._confirmar_selecao_tela_cheia,
            font=("DejaVu Sans", 10, "bold"),
            bg="#D6A900",
            fg="#111318",
            activebackground="#F5C518",
            activeforeground="#111318",
            relief="flat",
            bd=0,
            padx=24,
            pady=8,
            cursor="hand2",
        )
        botao_ok.pack(side=tk.RIGHT, padx=(8, 18), pady=12)

        seletor = tk.Frame(barra, bg="#07111F")
        seletor.pack(side=tk.RIGHT, padx=(8, 4), pady=8)
        tk.Label(
            seletor,
            text="FORMA DA ROI",
            font=("DejaVu Sans", 7, "bold"),
            fg="#94A3B8",
            bg="#07111F",
        ).pack(side=tk.TOP, anchor="w", pady=(0, 3))
        botoes = tk.Frame(seletor, bg="#07111F")
        botoes.pack(side=tk.TOP)

        self._botao_tipo_roi_segmento = tk.Button(
            botoes,
            text="▰ Segmento",
            command=lambda: self._selecionar_tipo_roi_toolbar("segmento"),
            font=("DejaVu Sans", 8, "bold"),
            relief="flat",
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
        )
        self._botao_tipo_roi_segmento.pack(side=tk.LEFT, padx=(0, 4))

        self._botao_tipo_roi_circulo = tk.Button(
            botoes,
            text="● Círculo",
            command=lambda: self._selecionar_tipo_roi_toolbar("circulo"),
            font=("DejaVu Sans", 8, "bold"),
            relief="flat",
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
        )
        self._botao_tipo_roi_circulo.pack(side=tk.LEFT)
        self._atualizar_botoes_tipo_roi()

        canvas = tk.Canvas(
            janela,
            bg="#020617",
            highlightthickness=0,
            cursor="crosshair",
            bd=0,
            width=1,
            height=1,
        )
        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        return janela, canvas

    @staticmethod
    def _vincular_evento(canvas, sequencia: str, callback: Callable | None, adicionar: bool = False) -> None:
        if callable(callback):
            canvas.bind(sequencia, callback, add="+" if adicionar else None)

    def _configurar_eventos_canvas_tela_cheia(self, canvas) -> None:
        view = self.view
        self._vincular_evento(canvas, "<Button-1>", getattr(self, "evento_clique_esquerdo", None))
        self._vincular_evento(canvas, "<Configure>", getattr(view, "evento_redimensionar_canvas_principal", None))
        self._vincular_evento(canvas, "<Motion>", getattr(view, "atualizar_lupa_canvas", None))
        self._vincular_evento(canvas, "<Leave>", getattr(view, "limpar_lupa_canvas", None))

        for sequencia, nome_callback in (
            ("<B1-Motion>", "_evento_arrastar_roi"),
            ("<ButtonRelease-1>", "_evento_soltar_roi"),
            ("<MouseWheel>", "_evento_roda_roi"),
            ("<Button-4>", "_evento_roda_roi"),
            ("<Button-5>", "_evento_roda_roi"),
            ("<Delete>", "_evento_apagar_roi"),
            ("<BackSpace>", "_evento_apagar_roi"),
            ("<Escape>", "_evento_cancelar_selecao_roi"),
            ("<Control-a>", "_evento_selecionar_todas_rois"),
            ("<Control-A>", "_evento_selecionar_todas_rois"),
            ("<Left>", "_evento_mover_roi_teclado"),
            ("<Right>", "_evento_mover_roi_teclado"),
            ("<Up>", "_evento_mover_roi_teclado"),
            ("<Down>", "_evento_mover_roi_teclado"),
        ):
            self._vincular_evento(
                canvas, sequencia, getattr(self, nome_callback, None), adicionar=True
            )

        capturar = getattr(self, "capturar_frame_camera_para_analise", None)
        if callable(capturar):
            self._vincular_evento(canvas, "<Return>", capturar, adicionar=True)
            self._vincular_evento(canvas, "<KP_Enter>", capturar, adicionar=True)

    def _cancelar_redesenho_pendente_selecao(self) -> None:
        view = getattr(self, "view", None)
        if view is None:
            return
        pendente = getattr(view, "_redimensionamento_pendente", None)
        if pendente is None:
            return
        try:
            self.root.after_cancel(pendente)
        except Exception:
            pass
        view._redimensionamento_pendente = None

    def _redesenhar_selecao_no_canvas_atual(self) -> None:
        view = getattr(self, "view", None)
        imagem = getattr(self, "imagem_original", None)
        if view is None or imagem is None:
            return
        view.imagem_tk = None
        view._imagem_tk_largura = None
        view._imagem_tk_altura = None
        view._lupa_ultimo_tempo_s = 0.0
        view._lupa_ultima_posicao_canvas = None
        view.preparar_imagem_para_exibicao(imagem)
        view.desenhar_canvas(
            getattr(self, "leds_selecionados", []),
            getattr(self, "resultados_led_atual", []),
        )

    def _ativar_fullscreen_nativo(self) -> None:
        janela = self._selecao_tela_cheia_window
        if janela is None:
            return
        try:
            janela.attributes("-fullscreen", True)
        except Exception:
            largura = max(800, int(self.root.winfo_screenwidth()))
            altura = max(600, int(self.root.winfo_screenheight()))
            try:
                janela.geometry(f"{largura}x{altura}+0+0")
            except Exception:
                pass

    def _abrir_selecao_tela_cheia(self) -> None:
        if self._selecao_tela_cheia_esta_aberta():
            return
        janela, canvas = self._criar_interface_selecao_tela_cheia()
        self._selecao_tela_cheia_window = janela
        self._selecao_tela_cheia_canvas = canvas
        self._selecao_tela_cheia_canvas_original = self.view.canvas
        self._cancelar_redesenho_pendente_selecao()
        self.view.canvas = canvas
        self._configurar_eventos_canvas_tela_cheia(canvas)
        try:
            janela.protocol("WM_DELETE_WINDOW", self._confirmar_selecao_tela_cheia)
        except Exception:
            pass
        try:
            janela.grab_set()
        except Exception:
            pass
        try:
            janela.lift()
            janela.focus_force()
        except Exception:
            pass
        try:
            janela.after(20, self._ativar_fullscreen_nativo)
            janela.after(60, self._redesenhar_selecao_no_canvas_atual)
            janela.after(80, canvas.focus_set)
        except Exception:
            self._ativar_fullscreen_nativo()
            self._redesenhar_selecao_no_canvas_atual()
            try:
                canvas.focus_set()
            except Exception:
                pass

    def _fechar_interface_selecao_tela_cheia(self) -> None:
        janela = self._selecao_tela_cheia_window
        canvas_original = self._selecao_tela_cheia_canvas_original
        self._cancelar_redesenho_pendente_selecao()
        if canvas_original is not None:
            self.view.canvas = canvas_original
        self._selecao_tela_cheia_window = None
        self._selecao_tela_cheia_canvas = None
        self._selecao_tela_cheia_canvas_original = None
        self._botao_tipo_roi_segmento = None
        self._botao_tipo_roi_circulo = None
        if janela is not None:
            try:
                janela.grab_release()
            except Exception:
                pass
            try:
                janela.destroy()
            except Exception:
                pass
        self._redesenhar_selecao_no_canvas_atual()
        if canvas_original is not None:
            try:
                canvas_original.focus_set()
            except Exception:
                pass

    def _confirmar_selecao_tela_cheia(self) -> None:
        if self._selecao_tela_cheia_fechando:
            return
        self._selecao_tela_cheia_fechando = True
        try:
            if self._modo_edicao_roi_ativo():
                super().iniciar_selecao_led()
            self._fechar_interface_selecao_tela_cheia()
        finally:
            self._selecao_tela_cheia_fechando = False

    def iniciar_selecao_led(self) -> None:
        if self._selecao_tela_cheia_esta_aberta():
            self._confirmar_selecao_tela_cheia()
            return
        super().iniciar_selecao_led()
        if self._modo_edicao_roi_ativo():
            self._abrir_selecao_tela_cheia()

    def parar_tela_ao_vivo(self, *args, **kwargs) -> None:
        if self._selecao_tela_cheia_esta_aberta():
            self._fechar_interface_selecao_tela_cheia()
        super().parar_tela_ao_vivo(*args, **kwargs)

    def limpar_tela(self) -> None:
        if self._selecao_tela_cheia_esta_aberta():
            self._fechar_interface_selecao_tela_cheia()
        super().limpar_tela()
