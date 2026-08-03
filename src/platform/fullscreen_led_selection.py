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
        super().__init__(*args, **kwargs)

    def _selecao_tela_cheia_esta_aberta(self) -> bool:
        janela = self._selecao_tela_cheia_window
        if janela is None:
            return False
        try:
            return bool(janela.winfo_exists())
        except Exception:
            return False

    def _criar_interface_selecao_tela_cheia(self):
        janela = tk.Toplevel(self.root)
        janela.title("ODIN • Seleção de LEDs")
        janela.configure(bg="#020617")

        barra = tk.Frame(
            janela,
            bg="#07111F",
            height=58,
            highlightthickness=1,
            highlightbackground="#122033",
        )
        barra.pack(side=tk.TOP, fill=tk.X)
        barra.pack_propagate(False)

        textos = tk.Frame(barra, bg="#07111F")
        textos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=18, pady=7)

        tk.Label(
            textos,
            text="SELEÇÃO E AJUSTE DE LEDs",
            font=("DejaVu Sans", 12, "bold"),
            fg="#F9FAFB",
            bg="#07111F",
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            textos,
            text=(
                "Clique ou selecione por área • arraste para mover • cantos redimensionam • "
                "laterais esticam • setas movem 1 px • a câmera permanece em 1920×1080 @ 20 FPS"
            ),
            font=("DejaVu Sans", 9),
            fg="#CBD5E1",
            bg="#07111F",
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        botao_ok = tk.Button(
            barra,
            text="OK",
            command=self._confirmar_selecao_tela_cheia,
            font=("DejaVu Sans", 11, "bold"),
            bg="#16A34A",
            fg="#FFFFFF",
            activebackground="#15803D",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=28,
            pady=9,
            cursor="hand2",
        )
        botao_ok.pack(side=tk.RIGHT, padx=18, pady=9)

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
    def _vincular_evento(
        canvas,
        sequencia: str,
        callback: Callable | None,
        adicionar: bool = False,
    ) -> None:
        if not callable(callback):
            return
        canvas.bind(
            sequencia,
            callback,
            add="+" if adicionar else None,
        )

    def _configurar_eventos_canvas_tela_cheia(self, canvas) -> None:
        view = self.view

        self._vincular_evento(
            canvas,
            "<Button-1>",
            getattr(self, "evento_clique_esquerdo", None),
        )
        self._vincular_evento(
            canvas,
            "<Configure>",
            getattr(view, "evento_redimensionar_canvas_principal", None),
        )
        self._vincular_evento(
            canvas,
            "<Motion>",
            getattr(view, "atualizar_lupa_canvas", None),
        )
        self._vincular_evento(
            canvas,
            "<Leave>",
            getattr(view, "limpar_lupa_canvas", None),
        )

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
                canvas,
                sequencia,
                getattr(self, nome_callback, None),
                adicionar=True,
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

        # Força um PhotoImage compatível com o tamanho do Canvas de destino.
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
            janela.protocol(
                "WM_DELETE_WINDOW",
                self._confirmar_selecao_tela_cheia,
            )
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
            # Usa exatamente o fluxo existente do botão Selecionar LEDs para
            # sair do modo, preservando máscaras temporárias e todas as regras.
            if self._modo_edicao_roi_ativo():
                super().iniciar_selecao_led()
            self._fechar_interface_selecao_tela_cheia()
        finally:
            self._selecao_tela_cheia_fechando = False

    def iniciar_selecao_led(self) -> None:
        if self._selecao_tela_cheia_esta_aberta():
            self._confirmar_selecao_tela_cheia()
            return

        # O método original continua responsável por validar câmera, ativar o
        # modo correto e preparar as máscaras. A janela é somente outra visão.
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
