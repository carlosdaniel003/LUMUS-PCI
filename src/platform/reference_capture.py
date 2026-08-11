from __future__ import annotations

import base64
import copy
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import cv2

from config import (
    CONFIG_DIR,
    DEFAULT_THRESHOLD_V,
    MAX_RADIUS_PX,
    MIN_RADIUS_PX,
)
from src.core.feature_extractor import (
    extrair_features_referencia_led,
)
from src.models.led_selection import LedSelection
from src.models.reference_sample import ReferenceSample
from src.platform.fullscreen_led_selection import CTRL_MASK
from src.ui.main_window_parts.canvas.roi_shape_canvas import (
    ponto_original_para_canvas,
)


TAG_REFERENCIA_CAPTURA = "referencia_captura_overlay"
MARGEM_RECORTE_REFERENCIA = 1.12

_REFERENCIAS = {
    "aceso": {
        "titulo": "Referência • LED aceso",
        "botao": "Ref. aceso",
        "arquivo": "reference_on.png",
        "config_key": "reference_on",
        "imagem_attr": "imagem_referencia_acesa",
        "caminho_attr": "caminho_referencia_acesa",
        "features_attr": "features_referencia_acesa",
        "cor": "#22C55E",
    },
    "apagado": {
        "titulo": "Referência • LED apagado",
        "botao": "Ref. apagado",
        "arquivo": "reference_off.png",
        "config_key": "reference_off",
        "imagem_attr": "imagem_referencia_apagada",
        "caminho_attr": "caminho_referencia_apagada",
        "features_attr": "features_referencia_apagada",
        "cor": "#38BDF8",
    },
    "pouca_luz": {
        "titulo": "Referência • pouca luz",
        "botao": "Ref. pouca luz",
        "arquivo": "reference_low_light.png",
        "config_key": "reference_low_light",
        "imagem_attr": "imagem_referencia_pouca_luz",
        "caminho_attr": "caminho_referencia_pouca_luz",
        "features_attr": "features_referencia_pouca_luz",
        "cor": "#FBBF24",
    },
}


def raio_recorte_referencia(raio_roi: int) -> int:
    return max(1, int(math.ceil(max(1, int(raio_roi)) * MARGEM_RECORTE_REFERENCIA)))


def recortar_referencia_circular(
    imagem,
    centro_x: int,
    centro_y: int,
    raio_roi: int,
):
    """Recorta um quadrado centrado na ROI circular usada como referência.

    A pequena margem faz com que o raio de 45% aplicado por
    ``extrair_features_referencia_led`` coincida aproximadamente com o raio
    selecionado pelo operador, além de deixar contexto visível na preview.
    """
    if imagem is None or getattr(imagem, "size", 0) == 0:
        return None

    altura, largura = imagem.shape[:2]
    margem = raio_recorte_referencia(raio_roi)
    x1 = int(centro_x) - margem
    y1 = int(centro_y) - margem
    x2 = int(centro_x) + margem + 1
    y2 = int(centro_y) + margem + 1

    if x1 < 0 or y1 < 0 or x2 > largura or y2 > altura:
        return None

    recorte = imagem[y1:y2, x1:x2]
    if recorte is None or getattr(recorte, "size", 0) == 0:
        return None
    return recorte.copy()


def atualizar_configuracao_referencia(
    configuracao: dict | None,
    chave_referencia: str,
    caminho_imagem: str,
    features: dict,
    raio_atual_px: int,
    settings_padrao: dict | None = None,
) -> dict:
    """Atualiza uma referência sem apagar LEDs, settings ou outras refs."""
    dados = copy.deepcopy(configuracao) if isinstance(configuracao, dict) else {}

    dados.setdefault("project", "ODIN")
    dados.setdefault("version", "0.13.0")
    dados.setdefault(
        "inspection_method",
        "single_selected_led_reference_classifier_modular",
    )
    dados.setdefault("threshold_v", DEFAULT_THRESHOLD_V)
    dados.setdefault("fixed_leds", [])
    dados["default_radius_px"] = int(raio_atual_px)

    if not isinstance(dados.get("settings"), dict):
        dados["settings"] = copy.deepcopy(settings_padrao or {})

    dados[str(chave_referencia)] = {
        "image_path": str(caminho_imagem),
        "features": copy.deepcopy(features),
    }
    return dados


def _percorrer_widgets(widget):
    try:
        filhos = tuple(widget.winfo_children())
    except Exception:
        filhos = ()
    for filho in filhos:
        yield filho
        yield from _percorrer_widgets(filho)


def _encontrar_corpo_referencias(janela: tk.Toplevel):
    for widget in _percorrer_widgets(janela):
        if not isinstance(widget, tk.Label):
            continue
        try:
            texto = str(widget.cget("text"))
        except Exception:
            continue
        if texto != "Referências fixas":
            continue

        card = widget.master
        frames = [
            filho
            for filho in card.winfo_children()
            if isinstance(filho, tk.Frame)
        ]
        return frames[-1] if frames else None
    return None


def _criar_photo_preview(imagem, largura_max: int = 176, altura_max: int = 108):
    if imagem is None or getattr(imagem, "size", 0) == 0:
        return None

    altura, largura = imagem.shape[:2]
    if largura <= 0 or altura <= 0:
        return None

    escala = min(
        float(largura_max) / float(largura),
        float(altura_max) / float(altura),
    )
    largura_final = max(1, int(round(largura * escala)))
    altura_final = max(1, int(round(altura * escala)))
    interpolacao = cv2.INTER_AREA if escala < 1.0 else cv2.INTER_LINEAR
    reduzida = cv2.resize(
        imagem,
        (largura_final, altura_final),
        interpolation=interpolacao,
    )
    sucesso, buffer = cv2.imencode(".png", reduzida)
    if not sucesso:
        return None
    dados = base64.b64encode(buffer).decode("ascii")
    return tk.PhotoImage(data=dados)


class ReferenceCaptureMixin:
    """Captura e apresenta referências fixas diretamente da imagem principal."""

    def __init__(self, *args, **kwargs) -> None:
        self.imagem_referencia_pouca_luz = None
        self.caminho_referencia_pouca_luz = None
        self.features_referencia_pouca_luz = None

        self._referencia_captura_tipo = None
        self._referencia_captura_window = None
        self._referencia_captura_canvas = None
        self._referencia_canvas_original = None
        self._referencia_captura_roi = None
        self._referencia_captura_frame = None
        self._referencia_captura_raio = MIN_RADIUS_PX
        self._referencia_captura_estado_anterior = None
        self._referencia_label_zoom = None
        self._referencia_label_instrucao = None
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Carregamento automático e integração com Configurações
    # ------------------------------------------------------------------
    def carregar_referencias_automaticamente_se_necessario(self) -> None:
        super().carregar_referencias_automaticamente_se_necessario()

        for imagem_attr, caminho_attr in (
            ("imagem_referencia_acesa", "caminho_referencia_acesa"),
            ("imagem_referencia_apagada", "caminho_referencia_apagada"),
        ):
            caminho = getattr(self, caminho_attr, None)
            imagem = self.recarregar_imagem_referencia(caminho)
            if imagem is not None:
                setattr(self, imagem_attr, imagem)

        configuracao = self.config_repository.carregar_configuracao_existente_sem_alerta()
        referencia_pouca_luz = ReferenceSample.from_dict(
            configuracao.get("reference_low_light", {})
        )
        self.caminho_referencia_pouca_luz = referencia_pouca_luz.image_path
        self.features_referencia_pouca_luz = referencia_pouca_luz.features
        self.imagem_referencia_pouca_luz = self.recarregar_imagem_referencia(
            self.caminho_referencia_pouca_luz
        )

        if self.imagem_referencia_pouca_luz is not None:
            self.features_referencia_pouca_luz = extrair_features_referencia_led(
                self.imagem_referencia_pouca_luz
            )

    def abrir_configuracoes(self) -> None:
        self.carregar_referencias_automaticamente_se_necessario()
        super().abrir_configuracoes()
        janela = self._encontrar_janela_configuracoes_aberta()
        if janela is not None:
            self._reconstruir_referencias_configuracoes(janela)

    def _encontrar_janela_configuracoes_aberta(self):
        try:
            candidatos = [
                widget
                for widget in self.root.winfo_children()
                if isinstance(widget, tk.Toplevel)
                and widget.winfo_exists()
                and str(widget.title()) == "Configurações - ODIN"
            ]
        except Exception:
            return None
        return candidatos[-1] if candidatos else None

    def _reconstruir_referencias_configuracoes(self, janela: tk.Toplevel) -> None:
        corpo = _encontrar_corpo_referencias(janela)
        if corpo is None:
            return

        for filho in tuple(corpo.winfo_children()):
            try:
                filho.destroy()
            except Exception:
                pass

        tk.Label(
            corpo,
            text=(
                "As referências são carregadas automaticamente. Clique em uma "
                "referência para abrir a imagem principal em tela cheia, selecione "
                "o LED e confirme em OK."
            ),
            font=("Segoe UI", 9),
            fg=self.view.COR_TEXTO_2,
            bg=self.view.COR_CARD_2,
            wraplength=650,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 10))

        grade = tk.Frame(corpo, bg=self.view.COR_CARD_2)
        grade.pack(fill=tk.X, padx=12, pady=(0, 12))
        for coluna in range(3):
            grade.grid_columnconfigure(coluna, weight=1, uniform="refs")

        fotos = []
        for coluna, tipo in enumerate(("aceso", "apagado", "pouca_luz")):
            dados = _REFERENCIAS[tipo]
            imagem = getattr(self, dados["imagem_attr"], None)

            card = tk.Frame(
                grade,
                bg=self.view.COR_CARD,
                highlightthickness=1,
                highlightbackground=self.view.COR_BORDA,
            )
            card.grid(
                row=0,
                column=coluna,
                sticky="nsew",
                padx=(0 if coluna == 0 else 5, 0 if coluna == 2 else 5),
            )

            preview = tk.Frame(
                card,
                bg="#020617",
                width=188,
                height=118,
                highlightthickness=1,
                highlightbackground=self.view.COR_BORDA,
            )
            preview.pack(fill=tk.X, padx=8, pady=(8, 7))
            preview.pack_propagate(False)

            foto = _criar_photo_preview(imagem)
            if foto is None:
                tk.Label(
                    preview,
                    text="Sem referência",
                    font=("Segoe UI", 9, "bold"),
                    fg=self.view.COR_TEXTO_3,
                    bg="#020617",
                ).pack(fill=tk.BOTH, expand=True)
                estado = "Não definida"
                cor_estado = self.view.COR_TEXTO_3
            else:
                fotos.append(foto)
                tk.Label(
                    preview,
                    image=foto,
                    bg="#020617",
                    bd=0,
                ).pack(fill=tk.BOTH, expand=True)
                estado = "Carregada"
                cor_estado = dados["cor"]

            tk.Button(
                card,
                text=dados["botao"],
                command=lambda valor=tipo, janela_config=janela: (
                    self._fechar_configuracoes_e_iniciar_referencia(
                        janela_config,
                        valor,
                    )
                ),
                font=("Segoe UI", 9, "bold"),
                bg=self.view.COR_CARD_2,
                fg=self.view.COR_TEXTO,
                activebackground=self.view.COR_NEUTRO,
                activeforeground=self.view.COR_TEXTO,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                padx=10,
                pady=7,
            ).pack(fill=tk.X, padx=8)

            tk.Label(
                card,
                text=estado,
                font=("Segoe UI", 8, "bold"),
                fg=cor_estado,
                bg=self.view.COR_CARD,
            ).pack(fill=tk.X, padx=8, pady=(5, 8))

        janela._odin_referencias_preview_tk = fotos

        try:
            from src.platform.display_theme import aplicar_tema_arvore

            aplicar_tema_arvore(corpo)
        except Exception:
            pass
        try:
            janela.update_idletasks()
        except Exception:
            pass

    def _fechar_configuracoes_e_iniciar_referencia(
        self,
        janela: tk.Toplevel,
        tipo: str,
    ) -> None:
        try:
            janela.grab_release()
        except Exception:
            pass
        try:
            janela.destroy()
        except Exception:
            pass
        self.root.after(80, lambda: self._abrir_captura_referencia(tipo))

    # ------------------------------------------------------------------
    # Entrada dos três botões de referência
    # ------------------------------------------------------------------
    def carregar_referencia_led_aceso(self) -> None:
        self._abrir_captura_referencia("aceso")

    def carregar_referencia_led_apagado(self) -> None:
        self._abrir_captura_referencia("apagado")

    def carregar_referencia_led_pouca_luz(self) -> None:
        self._abrir_captura_referencia("pouca_luz")

    # ------------------------------------------------------------------
    # Tela cheia de captura
    # ------------------------------------------------------------------
    def _captura_referencia_esta_aberta(self) -> bool:
        janela = self._referencia_captura_window
        if janela is None:
            return False
        try:
            return bool(janela.winfo_exists())
        except Exception:
            return False

    def _abrir_captura_referencia(self, tipo: str) -> None:
        if tipo not in _REFERENCIAS or self._captura_referencia_esta_aberta():
            return

        if getattr(self, "imagem_original", None) is None:
            messagebox.showwarning(
                "Atenção",
                "Ative a câmera ou carregue uma imagem antes de criar a referência.",
            )
            return

        if bool(getattr(self, "camera_ativa", False)) and getattr(
            self,
            "camera_frame_atual",
            None,
        ) is None:
            messagebox.showwarning(
                "Atenção",
                "Aguarde a câmera exibir uma imagem antes de criar a referência.",
            )
            return

        self._referencia_captura_estado_anterior = {
            "modo_atual": getattr(self, "modo_atual", "ocioso"),
            "camera_em_pausa_analise": bool(
                getattr(self, "camera_em_pausa_analise", False)
            ),
            "guias_leds_fixos_visiveis": bool(
                getattr(self, "guias_leds_fixos_visiveis", True)
            ),
            "selecao_manual_camera_ativa": bool(
                getattr(self, "selecao_manual_camera_ativa", False)
            ),
            "selecao_manual_camera_visivel": bool(
                getattr(self.view, "selecao_manual_camera_visivel", False)
            ),
            "selecao_led_ativa": bool(
                getattr(self.view, "selecao_led_ativa", False)
            ),
            "leds_selecionados": copy.deepcopy(
                getattr(self, "leds_selecionados", [])
            ),
            "leds_manuais_camera": copy.deepcopy(
                getattr(self, "leds_manuais_camera", [])
            ),
            "resultados_led_atual": copy.deepcopy(
                getattr(self, "resultados_led_atual", [])
            ),
        }

        self._referencia_captura_tipo = tipo
        self._referencia_captura_roi = None
        self._referencia_captura_frame = None
        self._referencia_captura_raio = min(
            MAX_RADIUS_PX,
            max(MIN_RADIUS_PX, int(getattr(self, "raio_atual_px", 15))),
        )

        self.modo_atual = "capturar_referencia"
        self.guias_leds_fixos_visiveis = False
        self.selecao_manual_camera_ativa = False
        self.leds_selecionados = []
        self.resultados_led_atual = []
        self.view.selecao_manual_camera_visivel = False
        self.view.atualizar_estado_selecao_led(False)

        janela, canvas = self._criar_interface_captura_referencia(tipo)
        self._referencia_captura_window = janela
        self._referencia_captura_canvas = canvas
        self._referencia_canvas_original = self.view.canvas
        self.view.canvas = canvas
        self._ativar_zoom_selecao()
        self._configurar_eventos_captura_referencia(canvas)

        try:
            janela.protocol(
                "WM_DELETE_WINDOW",
                self._cancelar_captura_referencia,
            )
            janela.bind(
                "<Escape>",
                lambda _evento: self._cancelar_captura_referencia(),
            )
            janela.grab_set()
            janela.lift()
            janela.focus_force()
        except Exception:
            pass

        self._redesenhar_referencia_no_canvas_atual()
        try:
            janela.after(20, lambda: janela.attributes("-fullscreen", True))
            janela.after(70, canvas.focus_set)
        except Exception:
            pass

    def _criar_interface_captura_referencia(self, tipo: str):
        dados = _REFERENCIAS[tipo]
        janela = tk.Toplevel(self.root)
        janela.title(dados["titulo"])
        janela.configure(bg="#020617")

        barra = tk.Frame(
            janela,
            bg="#07111F",
            height=70,
            highlightthickness=1,
            highlightbackground="#122033",
        )
        barra.pack(side=tk.TOP, fill=tk.X)
        barra.pack_propagate(False)

        textos = tk.Frame(barra, bg="#07111F")
        textos.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
            padx=(18, 8),
            pady=8,
        )
        tk.Label(
            textos,
            text=dados["titulo"].upper(),
            font=("DejaVu Sans", 12, "bold"),
            fg="#F9FAFB",
            bg="#07111F",
            anchor="w",
        ).pack(fill=tk.X)
        self._referencia_label_instrucao = tk.Label(
            textos,
            text=(
                "Clique no LED • scroll ajusta o recorte • Ctrl+scroll aplica zoom • "
                "rodinha pressionada+arraste move a imagem"
            ),
            font=("DejaVu Sans", 8),
            fg="#AAB8C8",
            bg="#07111F",
            anchor="w",
        )
        self._referencia_label_instrucao.pack(fill=tk.X, pady=(2, 0))

        tk.Button(
            barra,
            text="OK",
            command=self._confirmar_captura_referencia,
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
        ).pack(side=tk.RIGHT, padx=(8, 18), pady=13)

        tk.Button(
            barra,
            text="Cancelar",
            command=self._cancelar_captura_referencia,
            font=("DejaVu Sans", 9, "bold"),
            bg="#182231",
            fg="#DCE5EF",
            activebackground="#243246",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(6, 0), pady=13)

        self._referencia_label_zoom = tk.Label(
            barra,
            text="ZOOM 100%",
            font=("DejaVu Sans", 9, "bold"),
            fg="#38BDF8",
            bg="#07111F",
            padx=10,
        )
        self._referencia_label_zoom.pack(side=tk.RIGHT, padx=(8, 6))

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

    def _configurar_eventos_captura_referencia(self, canvas) -> None:
        canvas.bind("<Button-1>", self._evento_selecionar_referencia)
        canvas.bind(
            "<Configure>",
            self.view.evento_redimensionar_canvas_principal,
        )
        canvas.bind("<Motion>", self._evento_motion_selecao)
        canvas.bind("<Leave>", self.view.limpar_lupa_canvas)
        canvas.bind("<Button-2>", self._evento_iniciar_pan_selecao)
        canvas.bind("<B2-Motion>", self._evento_arrastar_pan_selecao)
        canvas.bind("<ButtonRelease-2>", self._evento_finalizar_pan_selecao)
        for sequencia in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind(sequencia, self._evento_roda_referencia, add="+")

    def _evento_roda_referencia(self, evento) -> str:
        estado = int(getattr(evento, "state", 0) or 0)
        if estado & CTRL_MASK:
            return self._evento_zoom_selecao(evento)

        direcao = self._direcao_scroll(evento)
        if direcao == 0:
            return "break"

        self._referencia_captura_raio = min(
            MAX_RADIUS_PX,
            max(
                MIN_RADIUS_PX,
                int(self._referencia_captura_raio) + direcao,
            ),
        )
        if self._referencia_captura_roi is not None:
            self._referencia_captura_roi.raio = self._referencia_captura_raio
        self._desenhar_overlay_referencia()
        self._atualizar_instrucao_referencia(
            f"Recorte: {self._referencia_captura_raio}px. Clique no LED e confirme em OK."
        )
        return "break"

    def _evento_selecionar_referencia(self, evento) -> str:
        coordenadas = self.view.converter_canvas_para_imagem_original(
            int(getattr(evento, "x", 0)),
            int(getattr(evento, "y", 0)),
        )
        if coordenadas is None:
            self._atualizar_instrucao_referencia(
                "Clique dentro da imagem para selecionar a referência."
            )
            return "break"

        centro_x, centro_y = coordenadas
        raio = int(self._referencia_captura_raio)
        margem = raio_recorte_referencia(raio)
        imagem = getattr(self, "imagem_original", None)
        if imagem is None:
            return "break"
        altura, largura = imagem.shape[:2]

        if (
            centro_x - margem < 0
            or centro_y - margem < 0
            or centro_x + margem >= largura
            or centro_y + margem >= altura
        ):
            self._atualizar_instrucao_referencia(
                "Seleção muito próxima da borda. Escolha um ponto com espaço para o recorte."
            )
            return "break"

        if self._referencia_captura_frame is None:
            self._referencia_captura_frame = imagem.copy()
            if bool(getattr(self, "camera_ativa", False)):
                self.camera_em_pausa_analise = True

        self._referencia_captura_roi = LedSelection(
            id="REF",
            centro_x=int(centro_x),
            centro_y=int(centro_y),
            raio=raio,
            tipo_roi="circulo",
        )
        self._desenhar_overlay_referencia()
        self._atualizar_instrucao_referencia(
            "Referência selecionada e frame congelado. Ajuste o recorte com scroll ou confirme em OK."
        )
        return "break"

    def _atualizar_instrucao_referencia(self, texto: str) -> None:
        label = self._referencia_label_instrucao
        if label is not None:
            try:
                label.configure(text=str(texto))
            except Exception:
                pass

    def _desenhar_overlay_referencia(self) -> None:
        if not self._captura_referencia_esta_aberta():
            return
        canvas = self._referencia_captura_canvas
        roi = self._referencia_captura_roi
        if canvas is None:
            return
        try:
            canvas.delete(TAG_REFERENCIA_CAPTURA)
        except Exception:
            return
        if roi is None:
            return

        centro_x, centro_y = ponto_original_para_canvas(
            self.view,
            roi.centro_x,
            roi.centro_y,
        )
        raio_canvas = max(
            4,
            int(round(roi.raio * float(self.view.escala_exibicao))),
        )
        dados = _REFERENCIAS[self._referencia_captura_tipo]
        cor = dados["cor"]
        canvas.create_oval(
            centro_x - raio_canvas,
            centro_y - raio_canvas,
            centro_x + raio_canvas,
            centro_y + raio_canvas,
            outline=cor,
            width=3,
            tags=(TAG_REFERENCIA_CAPTURA,),
        )
        canvas.create_line(
            centro_x - raio_canvas,
            centro_y,
            centro_x + raio_canvas,
            centro_y,
            fill=cor,
            width=1,
            tags=(TAG_REFERENCIA_CAPTURA,),
        )
        canvas.create_line(
            centro_x,
            centro_y - raio_canvas,
            centro_x,
            centro_y + raio_canvas,
            fill=cor,
            width=1,
            tags=(TAG_REFERENCIA_CAPTURA,),
        )
        canvas.create_text(
            centro_x,
            centro_y - raio_canvas - 14,
            text="REFERÊNCIA",
            fill=cor,
            font=("DejaVu Sans", 8, "bold"),
            tags=(TAG_REFERENCIA_CAPTURA,),
        )
        try:
            canvas.tag_raise(TAG_REFERENCIA_CAPTURA)
        except Exception:
            pass

    def _redesenhar_referencia_no_canvas_atual(self) -> None:
        imagem = getattr(self, "imagem_original", None)
        if imagem is None:
            return
        self.view.imagem_tk = None
        self.view._imagem_tk_largura = None
        self.view._imagem_tk_altura = None
        self.view.preparar_imagem_para_exibicao(imagem)
        self.view.desenhar_canvas([], [])
        self._desenhar_overlay_referencia()

    def _canvas_selecao_atual(self):
        if self._captura_referencia_esta_aberta():
            return self._referencia_captura_canvas
        return super()._canvas_selecao_atual()

    def _atualizar_indicador_zoom_selecao(self) -> None:
        super()._atualizar_indicador_zoom_selecao()
        label = self._referencia_label_zoom
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

    def _redesenhar_apos_zoom_selecao(self) -> None:
        super()._redesenhar_apos_zoom_selecao()
        self._desenhar_overlay_referencia()

    def atualizar_frame_camera(self) -> None:
        super().atualizar_frame_camera()
        if self._captura_referencia_esta_aberta():
            self._desenhar_overlay_referencia()

    # ------------------------------------------------------------------
    # Confirmação, persistência e retorno às Configurações
    # ------------------------------------------------------------------
    def _confirmar_captura_referencia(self) -> None:
        tipo = self._referencia_captura_tipo
        roi = self._referencia_captura_roi
        if tipo not in _REFERENCIAS or roi is None:
            messagebox.showwarning(
                "Atenção",
                "Selecione o LED que será usado como referência antes de clicar em OK.",
            )
            return

        frame = self._referencia_captura_frame
        if frame is None:
            imagem = getattr(self, "imagem_original", None)
            frame = imagem.copy() if imagem is not None else None

        recorte = recortar_referencia_circular(
            frame,
            roi.centro_x,
            roi.centro_y,
            roi.raio,
        )
        if recorte is None:
            messagebox.showerror(
                "Erro",
                "Não foi possível gerar o recorte da referência selecionada.",
            )
            return

        dados = _REFERENCIAS[tipo]
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        caminho = CONFIG_DIR / dados["arquivo"]
        if not cv2.imwrite(str(caminho), recorte):
            messagebox.showerror(
                "Erro",
                "Não foi possível salvar a imagem de referência.",
            )
            return

        features = extrair_features_referencia_led(recorte)
        setattr(self, dados["imagem_attr"], recorte)
        setattr(self, dados["caminho_attr"], str(caminho))
        setattr(self, dados["features_attr"], features)

        try:
            self._persistir_referencia_individual(
                dados["config_key"],
                caminho,
                features,
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro",
                f"A imagem foi recortada, mas a referência não pôde ser registrada: {erro}",
            )
            return

        self._fechar_captura_referencia(
            reabrir_configuracoes=True,
            status=f"{dados['botao']} atualizada e salva automaticamente.",
        )

    def _persistir_referencia_individual(
        self,
        chave_referencia: str,
        caminho: Path,
        features,
    ) -> None:
        existente = self.config_repository.carregar_configuracao_existente_sem_alerta()
        settings_padrao = {
            "save_analysis_results": bool(
                getattr(self, "salvar_resultados_analise", False)
            ),
            "camera": self.config_repository.obter_configuracoes_camera(),
        }
        configuracao = atualizar_configuracao_referencia(
            configuracao=existente,
            chave_referencia=chave_referencia,
            caminho_imagem=str(caminho),
            features=features.to_dict(),
            raio_atual_px=int(getattr(self, "raio_atual_px", MIN_RADIUS_PX)),
            settings_padrao=settings_padrao,
        )
        arquivo = Path(self.config_repository.config_file)
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with open(arquivo, "w", encoding="utf-8") as destino:
            json.dump(
                configuracao,
                destino,
                indent=4,
                ensure_ascii=False,
            )
        self.configuracao_atual = configuracao

    def _cancelar_captura_referencia(self) -> None:
        self._fechar_captura_referencia(
            reabrir_configuracoes=True,
            status="Captura de referência cancelada.",
        )

    def _fechar_captura_referencia(
        self,
        reabrir_configuracoes: bool,
        status: str | None = None,
    ) -> None:
        if not self._captura_referencia_esta_aberta():
            return

        janela = self._referencia_captura_window
        canvas_original = self._referencia_canvas_original
        estado = self._referencia_captura_estado_anterior or {}

        self._evento_finalizar_pan_selecao()
        self._desativar_zoom_selecao()

        if canvas_original is not None:
            self.view.canvas = canvas_original

        try:
            janela.grab_release()
        except Exception:
            pass
        try:
            janela.destroy()
        except Exception:
            pass

        self._referencia_captura_window = None
        self._referencia_captura_canvas = None
        self._referencia_canvas_original = None
        self._referencia_captura_tipo = None
        self._referencia_captura_roi = None
        self._referencia_captura_frame = None
        self._referencia_label_zoom = None
        self._referencia_label_instrucao = None

        self.modo_atual = estado.get("modo_atual", "ocioso")
        self.camera_em_pausa_analise = bool(
            estado.get("camera_em_pausa_analise", False)
        )
        self.guias_leds_fixos_visiveis = bool(
            estado.get("guias_leds_fixos_visiveis", True)
        )
        self.selecao_manual_camera_ativa = bool(
            estado.get("selecao_manual_camera_ativa", False)
        )
        self.leds_selecionados = copy.deepcopy(
            estado.get("leds_selecionados", [])
        )
        self.leds_manuais_camera = copy.deepcopy(
            estado.get("leds_manuais_camera", [])
        )
        self.resultados_led_atual = copy.deepcopy(
            estado.get("resultados_led_atual", [])
        )
        self.view.selecao_manual_camera_visivel = bool(
            estado.get("selecao_manual_camera_visivel", False)
        )
        self.view.atualizar_estado_selecao_led(
            bool(estado.get("selecao_led_ativa", False))
        )
        self._referencia_captura_estado_anterior = None

        if getattr(self, "imagem_original", None) is not None:
            self.view.preparar_imagem_para_exibicao(self.imagem_original)
            self.view.desenhar_canvas(
                self.leds_selecionados,
                self.resultados_led_atual,
            )

        if status:
            self.view.atualizar_status(status)
        self.atualizar_painel_inicial()

        try:
            self.root.focus_force()
        except Exception:
            pass

        if reabrir_configuracoes:
            self.root.after(140, self.abrir_configuracoes)
