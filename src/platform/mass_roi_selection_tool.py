from __future__ import annotations

import math
import tkinter as tk

from src.core.roi_geometry import normalizar_angulo_segmento, roi_dentro_imagem
from src.platform.freeform_segment_roi import copiar_led_com_segmento_livre


SHIFT_MASK = 0x0001
GROUP_ROTATE_HANDLE_OFFSET_CANVAS_PX = 34
GROUP_ROTATE_HANDLE_RADIUS_PX = 7


class MassRoiSelectionToolMixin:
    """Expõe a seleção retangular existente como ferramenta explícita da toolbar."""

    def __init__(self, *args, **kwargs) -> None:
        self._selecao_massa_ferramenta_ativa = False
        self._botao_selecao_massa = None
        super().__init__(*args, **kwargs)

    def _modo_selecao_massa_ativo(self) -> bool:
        return bool(self._selecao_massa_ferramenta_ativa)

    @staticmethod
    def _estilizar_botao_ferramenta(botao, ativo: bool) -> None:
        if botao is None:
            return
        try:
            botao.configure(
                bg="#D6A900" if ativo else "#182231",
                fg="#111318" if ativo else "#DCE5EF",
                activebackground="#F5C518" if ativo else "#243246",
                activeforeground="#111318" if ativo else "#FFFFFF",
            )
        except Exception:
            pass

    def _atualizar_botoes_tipo_roi(self) -> None:
        super()._atualizar_botoes_tipo_roi()
        massa = self._modo_selecao_massa_ativo()

        if massa:
            self._estilizar_botao_ferramenta(
                getattr(self, "_botao_tipo_roi_segmento", None),
                False,
            )
            self._estilizar_botao_ferramenta(
                getattr(self, "_botao_tipo_roi_circulo", None),
                False,
            )

        self._estilizar_botao_ferramenta(
            self._botao_selecao_massa,
            massa,
        )

    def _selecionar_tipo_roi_toolbar(self, tipo: str) -> None:
        self._selecao_massa_ferramenta_ativa = False
        retorno = super()._selecionar_tipo_roi_toolbar(tipo)
        self._atualizar_botoes_tipo_roi()
        return retorno

    def _selecionar_modo_selecao_massa_toolbar(self) -> None:
        cancelar_livre = getattr(self, "_cancelar_rascunho_segmento_livre", None)
        if callable(cancelar_livre):
            cancelar_livre(mensagem=False)
        if hasattr(self, "_segmento_livre_ativo"):
            self._segmento_livre_ativo = False

        self._selecao_massa_ferramenta_ativa = True
        self._atualizar_botoes_tipo_roi()
        self.view.atualizar_status(
            "Seleção em massa ativa. Clique e arraste no vazio para englobar ROIs. "
            "Depois mova o grupo, use as setas, Delete, as alças de tamanho ou a "
            "alça violeta para rotacionar."
        )
        canvas = getattr(self, "_selecao_tela_cheia_canvas", None)
        if canvas is not None:
            try:
                canvas.focus_set()
            except Exception:
                pass

    def _criar_interface_selecao_tela_cheia(self):
        janela, canvas = super()._criar_interface_selecao_tela_cheia()
        botao_circulo = getattr(self, "_botao_tipo_roi_circulo", None)
        parent = getattr(botao_circulo, "master", None)
        if parent is not None:
            self._botao_selecao_massa = tk.Button(
                parent,
                text="▣ Seleção em massa",
                command=self._selecionar_modo_selecao_massa_toolbar,
                font=("DejaVu Sans", 8, "bold"),
                relief="flat",
                bd=0,
                padx=10,
                pady=5,
                cursor="hand2",
            )
            self._botao_selecao_massa.pack(
                side=tk.LEFT,
                padx=(4, 0),
            )
        self._atualizar_botoes_tipo_roi()
        return janela, canvas

    def evento_clique_esquerdo(self, evento) -> str | None:
        if not self._modo_selecao_massa_ativo():
            return super().evento_clique_esquerdo(evento)

        # O editor de segmento usa Shift como sinal de que o arraste no vazio
        # deve continuar sendo marquee em vez de virar criação de segmento.
        # A ferramenta explícita reaproveita exatamente esse caminho existente,
        # sem exigir que o operador segure Shift.
        estado_original = int(getattr(evento, "state", 0) or 0)
        alterado = False
        try:
            evento.state = estado_original | SHIFT_MASK
            alterado = True
        except Exception:
            pass
        try:
            return super().evento_clique_esquerdo(evento)
        finally:
            if alterado:
                try:
                    evento.state = estado_original
                except Exception:
                    pass

    def _evento_soltar_roi(self, evento) -> str | None:
        modo_antes = getattr(self, "_area_roi_mode", None)
        quantidade_antes = len(getattr(self, "_area_roi_ids", set()) or set())

        if self._modo_selecao_massa_ativo() and modo_antes == "pending_marquee":
            # Clique simples em espaço vazio, estando na ferramenta de seleção,
            # apenas limpa a seleção. Não deixa o editor legado criar outra ROI.
            self._area_roi_mode = None
            self._area_roi_current_image = None
            self._area_roi_ids = set()
            sincronizar = getattr(self, "_sincronizar_preview_area", None)
            if callable(sincronizar):
                sincronizar()
            self.view.desenhar_canvas(
                self.leds_selecionados,
                self.resultados_led_atual,
            )
            self.view.atualizar_status(
                "Seleção em massa ativa. Arraste uma área para englobar as ROIs desejadas."
            )
            return "break"

        retorno = super()._evento_soltar_roi(evento)

        if self._modo_selecao_massa_ativo() and modo_antes == "marquee":
            quantidade = len(getattr(self, "_area_roi_ids", set()) or set())
            if quantidade:
                self.view.atualizar_status(
                    f"Seleção em massa: {quantidade} ROI(s). Arraste para mover; setas movem "
                    "1 px; Delete apaga; alças redimensionam/esticam; a alça violeta rotaciona."
                )
        elif modo_antes == "rotate" and quantidade_antes > 1:
            self.view.atualizar_status(
                f"Rotação em massa concluída para {quantidade_antes} ROI(s)."
            )
        return retorno

    def _handles_canvas(self):
        handles = dict(super()._handles_canvas() or {})
        selecionados = list(getattr(self, "_area_roi_ids", set()) or set())
        if len(selecionados) < 2:
            return handles

        bbox = getattr(self, "_bbox_area_selecionada", lambda: None)()
        if bbox is None:
            return handles
        x1, y1, x2, _y2 = bbox
        escala = max(
            1e-9,
            float(getattr(self.view, "escala_exibicao", 1.0) or 1.0),
        )
        offset_imagem = GROUP_ROTATE_HANDLE_OFFSET_CANVAS_PX / escala
        ponto = ((float(x1) + float(x2)) / 2.0, float(y1) - offset_imagem)
        converter = getattr(self, "_ponto_canvas_rotacionado", None)
        if callable(converter):
            handles["rotate"] = converter(*ponto)
        else:
            handles["rotate"] = (
                float(getattr(self.view, "deslocamento_imagem_x", 0.0))
                + ponto[0] * escala,
                float(getattr(self.view, "deslocamento_imagem_y", 0.0))
                + ponto[1] * escala,
            )
        return handles

    def _desenhar_overlay_editor_roi(self) -> None:
        super()._desenhar_overlay_editor_roi()
        ids = set(getattr(self, "_area_roi_ids", set()) or set())
        if len(ids) < 2 or getattr(self, "_area_roi_mode", None) == "marquee":
            return
        canvas = getattr(getattr(self, "view", None), "canvas", None)
        if canvas is None:
            return
        handles = self._handles_canvas()
        rotate = handles.get("rotate")
        norte = handles.get("n")
        if rotate is None:
            return
        try:
            if norte is not None:
                canvas.create_line(
                    norte[0],
                    norte[1],
                    rotate[0],
                    rotate[1],
                    fill="#A78BFA",
                    width=2,
                    dash=(3, 3),
                    tags="roi_bulk_editor",
                )
            r = GROUP_ROTATE_HANDLE_RADIUS_PX
            canvas.create_oval(
                rotate[0] - r,
                rotate[1] - r,
                rotate[0] + r,
                rotate[1] + r,
                fill="#A78BFA",
                outline="#111827",
                width=1,
                tags="roi_bulk_editor",
            )
        except tk.TclError:
            pass

    def _transformar_handle(self, imagem_x: int, imagem_y: int):
        origem = list(getattr(self, "_area_roi_snapshot_selected", []) or [])
        if (
            getattr(self, "_area_roi_mode", None) != "rotate"
            or len(origem) < 2
        ):
            return super()._transformar_handle(imagem_x, imagem_y)

        bbox = getattr(self, "_area_roi_bbox_snapshot", None)
        press = getattr(self, "_area_roi_press_image", None)
        if bbox is None or press is None:
            return origem

        x1, y1, x2, y2 = bbox
        centro_x = (float(x1) + float(x2)) / 2.0
        centro_y = (float(y1) + float(y2)) / 2.0
        angulo_inicial = math.atan2(float(press[1]) - centro_y, float(press[0]) - centro_x)
        angulo_atual = math.atan2(float(imagem_y) - centro_y, float(imagem_x) - centro_x)
        delta_rad = angulo_atual - angulo_inicial
        delta_graus = math.degrees(delta_rad)
        cos_a = math.cos(delta_rad)
        sin_a = math.sin(delta_rad)

        resultado = []
        for original in origem:
            led = copiar_led_com_segmento_livre(original)
            dx = float(original.centro_x) - centro_x
            dy = float(original.centro_y) - centro_y
            led.centro_x = int(round(centro_x + dx * cos_a - dy * sin_a))
            led.centro_y = int(round(centro_y + dx * sin_a + dy * cos_a))
            if bool(getattr(led, "eh_segmento", False)):
                led.angulo = normalizar_angulo_segmento(
                    float(getattr(original, "angulo", 0.0) or 0.0) + delta_graus
                )
            resultado.append(led)

        largura = int(getattr(self, "largura_original", 0) or 0)
        altura = int(getattr(self, "altura_original", 0) or 0)
        if all(roi_dentro_imagem(led, largura, altura) for led in resultado):
            return resultado
        return [copiar_led_com_segmento_livre(led) for led in origem]

    def _fechar_interface_selecao_tela_cheia(self) -> None:
        self._selecao_massa_ferramenta_ativa = False
        super()._fechar_interface_selecao_tela_cheia()
        self._botao_selecao_massa = None
