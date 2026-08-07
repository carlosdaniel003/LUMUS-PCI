from __future__ import annotations

import tkinter as tk
from typing import Callable

from src.ui.main_window_parts.image.rotacao_visual_principal import (
    dimensoes_visuais,
)
from src.ui.main_window_parts.image.selection_zoom import (
    ZOOM_SELECAO_MIN,
    calcular_centro_zoom_ancorado,
    calcular_escala_zoom_selecao,
    proximo_fator_zoom_selecao,
)


CTRL_MASK = 0x0004


class FullscreenLedSelectionMixin:
    """Exibe o editor existente em uma janela de tela cheia, sem tocar na câmera."""

    def __init__(self, *args, **kwargs) -> None:
        self._selecao_tela_cheia_window = None
        self._selecao_tela_cheia_canvas = None
        self._selecao_tela_cheia_canvas_original = None
        self._selecao_tela_cheia_fechando = False
        self._botao_tipo_roi_segmento = None
        self._botao_tipo_roi_circulo = None
        self._label_zoom_selecao = None
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

    def _atualizar_indicador_zoom_selecao(self) -> None:
        label = self._label_zoom_selecao
        if label is None:
            return
        fator = float(
            getattr(getattr(self, "view", None), "_selecao_zoom_fator", 1.0)
            or 1.0
        )
        try:
            label.configure(text=f"ZOOM {int(round(fator * 100))}%")
        except Exception:
            pass

    def _ativar_zoom_selecao(self) -> None:
        view = getattr(self, "view", None)
        if view is None:
            return
        view._selecao_zoom_ativo = True
        view._selecao_zoom_fator = ZOOM_SELECAO_MIN
        view._selecao_zoom_centro_visual_x = None
        view._selecao_zoom_centro_visual_y = None
        self._atualizar_indicador_zoom_selecao()

    def _desativar_zoom_selecao(self) -> None:
        view = getattr(self, "view", None)
        if view is None:
            return
        view._selecao_zoom_ativo = False
        view._selecao_zoom_fator = ZOOM_SELECAO_MIN
        view._selecao_zoom_centro_visual_x = None
        view._selecao_zoom_centro_visual_y = None

    @staticmethod
    def _direcao_scroll(evento) -> int:
        delta = int(getattr(evento, "delta", 0) or 0)
        numero = getattr(evento, "num", None)
        if delta > 0 or numero == 4:
            return 1
        if delta < 0 or numero == 5:
            return -1
        return 0

    def _redesenhar_apos_zoom_selecao(self) -> None:
        view = getattr(self, "view", None)
        if view is None:
            return
        limpar_lupa = getattr(view, "limpar_lupa_canvas", None)
        if callable(limpar_lupa):
            try:
                limpar_lupa()
            except Exception:
                pass
        atualizar = getattr(view, "atualizar_imagem_principal_redimensionada", None)
        if callable(atualizar):
            atualizar()
        desenhar = getattr(view, "desenhar_canvas", None)
        if callable(desenhar):
            desenhar(
                getattr(self, "leds_selecionados", []),
                getattr(self, "resultados_led_atual", []),
            )
        overlay = getattr(self, "_desenhar_overlay_editor_roi", None)
        if callable(overlay):
            try:
                overlay()
            except Exception:
                pass

    def _evento_zoom_selecao(self, evento) -> str:
        view = getattr(self, "view", None)
        if view is None or not bool(getattr(view, "_selecao_zoom_ativo", False)):
            return "break"

        direcao = self._direcao_scroll(evento)
        if direcao == 0:
            return "break"

        fator_atual = float(getattr(view, "_selecao_zoom_fator", 1.0) or 1.0)
        novo_fator = proximo_fator_zoom_selecao(fator_atual, direcao)
        if abs(novo_fator - fator_atual) < 1e-9:
            return "break"

        imagem = getattr(view, "imagem_canvas_original", None)
        shape = getattr(imagem, "shape", None)
        if shape is not None and len(shape) >= 2:
            altura_original = int(shape[0])
            largura_original = int(shape[1])
            largura_visual, altura_visual = dimensoes_visuais(
                largura_original,
                altura_original,
                getattr(view, "rotacao_visual_principal", 0),
            )

            obter_tamanho = getattr(view, "obter_tamanho_canvas_principal", None)
            if callable(obter_tamanho):
                largura_canvas, altura_canvas = obter_tamanho()
            else:
                canvas = getattr(view, "canvas", None)
                largura_canvas = int(getattr(canvas, "winfo_width", lambda: 1)())
                altura_canvas = int(getattr(canvas, "winfo_height", lambda: 1)())

            nova_escala = calcular_escala_zoom_selecao(
                largura_visual,
                altura_visual,
                largura_canvas,
                altura_canvas,
                novo_fator,
            )
            centro_atual_x = getattr(
                view,
                "_selecao_zoom_centro_visual_x",
                None,
            )
            centro_atual_y = getattr(
                view,
                "_selecao_zoom_centro_visual_y",
                None,
            )
            centro_x, centro_y = calcular_centro_zoom_ancorado(
                ponteiro_x=float(getattr(evento, "x", largura_canvas / 2.0)),
                ponteiro_y=float(getattr(evento, "y", altura_canvas / 2.0)),
                escala_atual=float(getattr(view, "escala_exibicao", 1.0) or 1.0),
                deslocamento_atual_x=float(getattr(view, "deslocamento_imagem_x", 0)),
                deslocamento_atual_y=float(getattr(view, "deslocamento_imagem_y", 0)),
                largura_virtual_atual=int(
                    getattr(view, "largura_imagem_exibida", largura_canvas) or largura_canvas
                ),
                altura_virtual_atual=int(
                    getattr(view, "altura_imagem_exibida", altura_canvas) or altura_canvas
                ),
                nova_escala=nova_escala,
                largura_canvas=largura_canvas,
                altura_canvas=altura_canvas,
                largura_visual=largura_visual,
                altura_visual=altura_visual,
                centro_atual_x=centro_atual_x,
                centro_atual_y=centro_atual_y,
            )
            if novo_fator <= ZOOM_SELECAO_MIN:
                view._selecao_zoom_centro_visual_x = None
                view._selecao_zoom_centro_visual_y = None
            else:
                view._selecao_zoom_centro_visual_x = centro_x
                view._selecao_zoom_centro_visual_y = centro_y

        view._selecao_zoom_fator = novo_fator
        self._atualizar_indicador_zoom_selecao()
        self._redesenhar_apos_zoom_selecao()

        atualizar_status = getattr(view, "atualizar_status", None)
        if callable(atualizar_status):
            atualizar_status(
                f"Zoom da seleção: {int(round(novo_fator * 100))}%. "
                "Ctrl+scroll ajusta o zoom sem alterar a máscara."
            )
        return "break"

    def _evento_roda_ou_zoom_selecao(self, evento) -> str | None:
        estado = int(getattr(evento, "state", 0) or 0)
        if estado & CTRL_MASK:
            return self._evento_zoom_selecao(evento)
        callback = getattr(self, "_evento_roda_roi", None)
        if callable(callback):
            return callback(evento)
        return None

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
                "Ctrl+scroll aplica zoom • setas movem 1 px"
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

        zoom_frame = tk.Frame(barra, bg="#07111F")
        zoom_frame.pack(side=tk.RIGHT, padx=(8, 4), pady=8)
        tk.Label(
            zoom_frame,
            text="PRECISÃO",
            font=("DejaVu Sans", 7, "bold"),
            fg="#94A3B8",
            bg="#07111F",
        ).pack(side=tk.TOP, anchor="w", pady=(0, 3))
        self._label_zoom_selecao = tk.Label(
            zoom_frame,
            text="ZOOM 100%",
            font=("DejaVu Sans", 9, "bold"),
            fg="#38BDF8",
            bg="#07111F",
            padx=8,
            pady=5,
        )
        self._label_zoom_selecao.pack(side=tk.TOP)

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

        for sequencia in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._vincular_evento(
                canvas,
                sequencia,
                self._evento_roda_ou_zoom_selecao,
                adicionar=True,
            )

        for sequencia, nome_callback in (
            ("<B1-Motion>", "_evento_arrastar_roi"),
            ("<ButtonRelease-1>", "_evento_soltar_roi"),
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
        self._ativar_zoom_selecao()
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
        self._desativar_zoom_selecao()
        self._selecao_tela_cheia_window = None
        self._selecao_tela_cheia_canvas = None
        self._selecao_tela_cheia_canvas_original = None
        self._botao_tipo_roi_segmento = None
        self._botao_tipo_roi_circulo = None
        self._label_zoom_selecao = None
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
