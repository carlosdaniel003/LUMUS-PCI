import base64
import time
import tkinter as tk

import cv2
import numpy as np

from src.core.roi_geometry import (
    SEGMENTO_ALTURA_PADRAO,
    SEGMENTO_LARGURA_PADRAO,
    TIPO_ROI_SEGMENTO,
    bbox_roi,
    normalizar_tipo_roi,
    pontos_segmento,
    raio_compatibilidade_segmento,
)
from src.models.led_selection import LedSelection
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    normalizar_rotacao_visual,
    rotacionar_imagem_visual,
)


TAG_LUPA = "lupa_canvas"


def rotacionar_preview_lupa(imagem_bgr, rotacao: int):
    """Aplica à lupa exatamente a mesma orientação visual da imagem principal."""
    if imagem_bgr is None:
        return None
    return rotacionar_imagem_visual(
        imagem_bgr,
        normalizar_rotacao_visual(rotacao),
    )


def _converter_imagem_bgr_para_photoimage(imagem_bgr):
    """Converte uma imagem BGR do OpenCV para PhotoImage."""
    if imagem_bgr is None or imagem_bgr.size == 0:
        return None

    sucesso, buffer = cv2.imencode(".png", imagem_bgr)
    if not sucesso:
        return None

    imagem_base64 = base64.b64encode(buffer).decode("ascii")
    return tk.PhotoImage(data=imagem_base64)


def _normalizar_leds_selecionados_preview(self) -> list:
    leds = getattr(self, "ultimo_led_selecionado", [])
    if leds is None:
        return []
    if isinstance(leds, list):
        return [led for led in leds if led is not None]
    return [leds]


def _obter_numero_led_preview(led) -> str:
    id_led = str(getattr(led, "id", "LED"))
    return id_led.split("_")[-1] if "_" in id_led else id_led


def _obter_controlador_preview(self):
    callbacks = getattr(self, "callbacks", {})
    if not isinstance(callbacks, dict):
        return None
    callback = callbacks.get("evento_clique_esquerdo")
    return getattr(callback, "__self__", None)


def _obter_tipo_roi_edicao_preview(self) -> str:
    controlador = _obter_controlador_preview(self)
    return normalizar_tipo_roi(
        getattr(controlador, "tipo_roi_edicao", None)
    )


def _obter_segmento_criacao_preview(self):
    controlador = _obter_controlador_preview(self)
    candidato = getattr(controlador, "_segmento_criacao_atual", None)
    if (
        candidato is not None
        and normalizar_tipo_roi(getattr(candidato, "tipo_roi", None))
        == TIPO_ROI_SEGMENTO
    ):
        return candidato
    return None


def pontos_segmento_preview_recorte(
    led,
    x1: int,
    y1: int,
    escala_x: float,
    escala_y: float,
) -> np.ndarray:
    """Projeta o polígono real do segmento para coordenadas da preview."""
    pontos_locais = []
    for x, y in pontos_segmento(led):
        pontos_locais.append(
            [
                int(round((float(x) - float(x1)) * float(escala_x))),
                int(round((float(y) - float(y1)) * float(escala_y))),
            ]
        )
    return np.asarray(pontos_locais, dtype=np.int32).reshape((-1, 1, 2))


def _roi_intersecta_recorte(led, x1: int, y1: int, x2: int, y2: int) -> bool:
    bx1, by1, bx2, by2 = bbox_roi(led)
    return not (
        bx2 < x1
        or bx1 >= x2
        or by2 < y1
        or by1 >= y2
    )


def _centro_roi_no_recorte(
    led,
    x1: int,
    y1: int,
    escala_x: float,
    escala_y: float,
) -> tuple[int, int]:
    return (
        int(round((int(getattr(led, "centro_x", 0)) - x1) * escala_x)),
        int(round((int(getattr(led, "centro_y", 0)) - y1) * escala_y)),
    )


def _desenhar_forma_roi_no_recorte(
    recorte_ampliado,
    led,
    x1: int,
    y1: int,
    escala_x: float,
    escala_y: float,
    cor,
    espessura: int = 3,
) -> tuple[int, int, int, int]:
    """Desenha círculo ou segmento sem substituir segmento por raio circular."""
    centro_local_x, centro_local_y = _centro_roi_no_recorte(
        led,
        x1,
        y1,
        escala_x,
        escala_y,
    )

    if normalizar_tipo_roi(getattr(led, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
        pontos = pontos_segmento_preview_recorte(
            led,
            x1,
            y1,
            escala_x,
            escala_y,
        )
        cv2.polylines(
            recorte_ampliado,
            [pontos],
            True,
            cor,
            int(espessura),
            cv2.LINE_AA,
        )
        cv2.drawMarker(
            recorte_ampliado,
            (centro_local_x, centro_local_y),
            cor,
            markerType=cv2.MARKER_CROSS,
            markerSize=9,
            thickness=1,
        )
        xs = pontos[:, 0, 0]
        ys = pontos[:, 0, 1]
        return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

    raio = max(1, int(getattr(led, "raio", 1)))
    raio_local = max(
        8,
        int(raio * ((escala_x + escala_y) / 2.0)),
    )
    cv2.circle(
        recorte_ampliado,
        (centro_local_x, centro_local_y),
        raio_local,
        cor,
        int(espessura),
    )
    cv2.circle(
        recorte_ampliado,
        (centro_local_x, centro_local_y),
        4,
        cor,
        -1,
    )
    return (
        centro_local_x - raio_local,
        centro_local_y - raio_local,
        centro_local_x + raio_local,
        centro_local_y + raio_local,
    )


def _desenhar_leds_confirmados_no_recorte(
    self,
    recorte_ampliado,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    escala_x: float,
    escala_y: float,
) -> None:
    """Desenha cada ROI confirmada com sua geometria real antes da rotação."""
    cor_selecionado = (72, 255, 110)

    for led in _normalizar_leds_selecionados_preview(self):
        if not _roi_intersecta_recorte(led, x1, y1, x2, y2):
            continue

        esquerda, topo, _, _ = _desenhar_forma_roi_no_recorte(
            recorte_ampliado,
            led,
            x1,
            y1,
            escala_x,
            escala_y,
            cor_selecionado,
            espessura=3,
        )

        cv2.putText(
            recorte_ampliado,
            _obter_numero_led_preview(led),
            (
                max(2, esquerda),
                max(13, topo - 4),
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            cor_selecionado,
            1,
            cv2.LINE_AA,
        )


def _criar_segmento_mira_preview(self, imagem_x: int, imagem_y: int) -> LedSelection:
    controlador = _obter_controlador_preview(self)
    largura = max(
        8,
        int(getattr(controlador, "segmento_largura_padrao", SEGMENTO_LARGURA_PADRAO)),
    )
    altura = max(
        4,
        int(getattr(controlador, "segmento_altura_padrao", SEGMENTO_ALTURA_PADRAO)),
    )
    return LedSelection(
        id="MIRA",
        centro_x=int(imagem_x),
        centro_y=int(imagem_y),
        raio=raio_compatibilidade_segmento(largura, altura),
        tipo_roi=TIPO_ROI_SEGMENTO,
        largura=largura,
        altura=altura,
        angulo=0.0,
    )


def _obter_confirmacao_lupa(self):
    confirmacao = getattr(self, "_lupa_confirmacao", None)
    if not isinstance(confirmacao, dict):
        return None

    expira_em = float(confirmacao.get("expira_em", 0.0))
    if time.monotonic() > expira_em:
        return None
    return confirmacao


def desenhar_lupa_canvas(
    self,
    canvas_x: int,
    canvas_y: int,
    imagem_x: int,
    imagem_y: int,
) -> None:
    if self.imagem_canvas_original is None:
        self.limpar_lupa_canvas()
        return

    imagem = self.imagem_canvas_original
    altura_imagem, largura_imagem = imagem.shape[:2]

    raio_atual = max(3, int(self.raio_atual_px))
    margem_recorte = max(28, raio_atual * 4)

    x1 = max(0, imagem_x - margem_recorte)
    y1 = max(0, imagem_y - margem_recorte)
    x2 = min(largura_imagem, imagem_x + margem_recorte)
    y2 = min(altura_imagem, imagem_y + margem_recorte)

    if x2 <= x1 or y2 <= y1:
        self.limpar_lupa_canvas()
        return

    recorte = imagem[y1:y2, x1:x2].copy()
    if recorte.size == 0:
        self.limpar_lupa_canvas()
        return

    tamanho_lupa = 190
    recorte_ampliado = cv2.resize(
        recorte,
        (tamanho_lupa, tamanho_lupa),
        interpolation=cv2.INTER_NEAREST,
    )

    largura_recorte = max(1, x2 - x1)
    altura_recorte = max(1, y2 - y1)
    escala_x = tamanho_lupa / largura_recorte
    escala_y = tamanho_lupa / altura_recorte

    centro_lupa_x = int((imagem_x - x1) * escala_x)
    centro_lupa_y = int((imagem_y - y1) * escala_y)
    raio_lupa = max(
        8,
        int(raio_atual * ((escala_x + escala_y) / 2.0)),
    )

    _desenhar_leds_confirmados_no_recorte(
        self=self,
        recorte_ampliado=recorte_ampliado,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        escala_x=escala_x,
        escala_y=escala_y,
    )

    cor_mira = (248, 189, 56)
    cor_linhas = (94, 234, 212)
    cor_centro = (255, 255, 255)
    espessura_mira = 2

    confirmacao = _obter_confirmacao_lupa(self)
    if confirmacao is not None:
        tipo_confirmacao = str(confirmacao.get("tipo", ""))
        centro_confirmado_x = int(confirmacao.get("centro_x", -99999))
        centro_confirmado_y = int(confirmacao.get("centro_y", -99999))
        distancia_confirmacao = (
            (imagem_x - centro_confirmado_x) ** 2
            + (imagem_y - centro_confirmado_y) ** 2
        )

        if distancia_confirmacao <= max(10, raio_atual) ** 2:
            cor_mira = (
                (0, 190, 255)
                if tipo_confirmacao == "duplicado"
                else (72, 255, 110)
            )
            cor_linhas = cor_mira
            espessura_mira = 4

    tipo_mira = _obter_tipo_roi_edicao_preview(self)
    if tipo_mira == TIPO_ROI_SEGMENTO:
        segmento_mira = _obter_segmento_criacao_preview(self)
        if segmento_mira is None:
            segmento_mira = _criar_segmento_mira_preview(
                self,
                imagem_x,
                imagem_y,
            )
        if _roi_intersecta_recorte(segmento_mira, x1, y1, x2, y2):
            _desenhar_forma_roi_no_recorte(
                recorte_ampliado,
                segmento_mira,
                x1,
                y1,
                escala_x,
                escala_y,
                cor_mira,
                espessura=espessura_mira,
            )
        cv2.line(
            recorte_ampliado,
            (centro_lupa_x - 12, centro_lupa_y),
            (centro_lupa_x + 12, centro_lupa_y),
            cor_linhas,
            1,
        )
        cv2.line(
            recorte_ampliado,
            (centro_lupa_x, centro_lupa_y - 12),
            (centro_lupa_x, centro_lupa_y + 12),
            cor_linhas,
            1,
        )
    else:
        cv2.circle(
            recorte_ampliado,
            (centro_lupa_x, centro_lupa_y),
            raio_lupa,
            cor_mira,
            espessura_mira,
        )
        cv2.line(
            recorte_ampliado,
            (centro_lupa_x - raio_lupa - 10, centro_lupa_y),
            (centro_lupa_x + raio_lupa + 10, centro_lupa_y),
            cor_linhas,
            1,
        )
        cv2.line(
            recorte_ampliado,
            (centro_lupa_x, centro_lupa_y - raio_lupa - 10),
            (centro_lupa_x, centro_lupa_y + raio_lupa + 10),
            cor_linhas,
            1,
        )

    cv2.circle(
        recorte_ampliado,
        (centro_lupa_x, centro_lupa_y),
        3,
        cor_centro,
        -1,
    )
    cv2.rectangle(
        recorte_ampliado,
        (0, 0),
        (tamanho_lupa - 1, tamanho_lupa - 1),
        cor_mira,
        2,
    )

    # O recorte, a mira e as marcações são montados no referencial original.
    # Só depois todo o preview é rotacionado. Assim a lupa mostra exatamente a
    # mesma orientação percebida na Imagem Principal sem alterar a câmera, a
    # análise nem as coordenadas reais das ROIs.
    recorte_ampliado = rotacionar_preview_lupa(
        recorte_ampliado,
        getattr(self, "rotacao_visual_principal", 0),
    )

    imagem_tk = _converter_imagem_bgr_para_photoimage(recorte_ampliado)
    if imagem_tk is None:
        self.limpar_lupa_canvas()
        return

    self.lupa_tk = imagem_tk
    self.canvas.delete(TAG_LUPA)

    largura_canvas, _ = self.obter_tamanho_canvas_principal()
    x_lupa = largura_canvas - tamanho_lupa - 18
    y_lupa = 42

    mouse_sobre_lupa = (
        canvas_x >= x_lupa - 20
        and canvas_x <= x_lupa + tamanho_lupa + 20
        and canvas_y >= y_lupa - 40
        and canvas_y <= y_lupa + tamanho_lupa + 50
    )
    if mouse_sobre_lupa:
        x_lupa = 18
        y_lupa = 42

    x_lupa = max(12, x_lupa)
    y_lupa = max(12, y_lupa)

    total_selecionados = len(_normalizar_leds_selecionados_preview(self))
    angulo_visual = normalizar_rotacao_visual(
        getattr(self, "rotacao_visual_principal", 0)
    )
    texto_topo = (
        f"MIRA {angulo_visual}° | {total_selecionados} selecionado(s)"
    )
    cor_fundo_topo = "#07111F"
    cor_texto_topo = self.COR_TEXTO_2
    cor_borda = self.COR_AZUL

    if confirmacao is not None:
        id_confirmacao = str(confirmacao.get("id", "LED"))
        tipo_confirmacao = str(confirmacao.get("tipo", ""))

        if tipo_confirmacao == "duplicado":
            texto_topo = f"! {id_confirmacao} JÁ SELECIONADO | {angulo_visual}°"
            cor_fundo_topo = "#422006"
            cor_texto_topo = "#FDE68A"
            cor_borda = "#F59E0B"
        else:
            texto_topo = (
                f"✓ {id_confirmacao} SELECIONADO | "
                f"{total_selecionados} | {angulo_visual}°"
            )
            cor_fundo_topo = "#052E1A"
            cor_texto_topo = "#86EFAC"
            cor_borda = "#22C55E"

    self.canvas.create_rectangle(
        x_lupa - 6,
        y_lupa - 30,
        x_lupa + tamanho_lupa + 6,
        y_lupa + tamanho_lupa + 8,
        fill="#020617",
        outline=cor_borda,
        width=2,
        tags=(TAG_LUPA,),
    )
    self.canvas.create_rectangle(
        x_lupa - 5,
        y_lupa - 29,
        x_lupa + tamanho_lupa + 5,
        y_lupa - 2,
        fill=cor_fundo_topo,
        outline="",
        tags=(TAG_LUPA,),
    )
    self.canvas.create_text(
        x_lupa,
        y_lupa - 16,
        text=texto_topo,
        fill=cor_texto_topo,
        font=("Segoe UI", 7, "bold"),
        anchor=tk.W,
        tags=(TAG_LUPA,),
    )
    self.canvas.create_image(
        x_lupa,
        y_lupa,
        image=self.lupa_tk,
        anchor=tk.NW,
        tags=(TAG_LUPA,),
    )
    self.canvas.create_rectangle(
        x_lupa,
        y_lupa,
        x_lupa + tamanho_lupa,
        y_lupa + tamanho_lupa,
        outline=cor_borda,
        width=2,
        tags=(TAG_LUPA,),
    )

    self.canvas.tag_raise(TAG_LUPA)
    self._lupa_visivel = True
