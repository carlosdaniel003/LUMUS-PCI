import base64

import cv2
import tkinter as tk

from src.ui.main_window_parts.image.rotacao_visual_principal import (
    rotacionar_imagem_visual,
)
from src.ui.main_window_parts.image.selection_zoom import (
    calcular_viewport_zoom_selecao,
)


def _codificar_ppm_bgr(imagem_bgr) -> bytes:
    altura, largura = imagem_bgr.shape[:2]
    imagem_rgb = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2RGB)
    cabecalho = f"P6\n{largura} {altura}\n255\n".encode("ascii")
    return cabecalho + imagem_rgb.tobytes()


def _atualizar_photoimage_ppm(self, dados_ppm: bytes) -> bool:
    largura = int(
        getattr(
            self,
            "_imagem_render_largura",
            self.largura_imagem_exibida,
        )
    )
    altura = int(
        getattr(
            self,
            "_imagem_render_altura",
            self.altura_imagem_exibida,
        )
    )
    imagem_existente = getattr(self, "imagem_tk", None)
    mesma_resolucao = (
        imagem_existente is not None
        and getattr(self, "_imagem_tk_largura", None) == largura
        and getattr(self, "_imagem_tk_altura", None) == altura
    )

    try:
        if mesma_resolucao:
            imagem_existente.configure(
                data=dados_ppm,
                format="PPM",
            )
        else:
            self.imagem_tk = tk.PhotoImage(
                data=dados_ppm,
                format="PPM",
            )
            self._imagem_tk_largura = largura
            self._imagem_tk_altura = altura
        return True
    except tk.TclError:
        return False


def atualizar_imagem_principal_redimensionada(self) -> None:
    if self.imagem_canvas_original is None:
        return

    imagem_visual = rotacionar_imagem_visual(
        self.imagem_canvas_original,
        getattr(self, "rotacao_visual_principal", 0),
    )
    altura_visual, largura_visual = imagem_visual.shape[:2]
    largura_disponivel, altura_disponivel = (
        self.obter_tamanho_canvas_principal()
    )

    zoom_ativo = bool(getattr(self, "_selecao_zoom_ativo", False))
    fator_zoom = (
        float(getattr(self, "_selecao_zoom_fator", 1.0) or 1.0)
        if zoom_ativo
        else 1.0
    )
    centro_zoom_x = (
        getattr(self, "_selecao_zoom_centro_visual_x", None)
        if zoom_ativo
        else None
    )
    centro_zoom_y = (
        getattr(self, "_selecao_zoom_centro_visual_y", None)
        if zoom_ativo
        else None
    )

    viewport = calcular_viewport_zoom_selecao(
        largura_visual=largura_visual,
        altura_visual=altura_visual,
        largura_canvas=largura_disponivel,
        altura_canvas=altura_disponivel,
        fator_zoom=fator_zoom,
        centro_visual_x=centro_zoom_x,
        centro_visual_y=centro_zoom_y,
    )

    # Estes três valores continuam representando a imagem virtual completa.
    # Assim os overlays e a conversão Canvas -> imagem original permanecem
    # geometricamente corretos mesmo quando só um recorte é renderizado.
    self.escala_exibicao = float(viewport.escala)
    self.largura_imagem_exibida = int(viewport.largura_virtual)
    self.altura_imagem_exibida = int(viewport.altura_virtual)
    self.deslocamento_imagem_x = int(viewport.deslocamento_virtual_x)
    self.deslocamento_imagem_y = int(viewport.deslocamento_virtual_y)

    recorte = imagem_visual[
        viewport.origem_visual_y:viewport.fim_visual_y,
        viewport.origem_visual_x:viewport.fim_visual_x,
    ]
    if recorte is None or getattr(recorte, "size", 0) == 0:
        return

    self._imagem_render_largura = int(viewport.largura_render)
    self._imagem_render_altura = int(viewport.altura_render)
    self._imagem_render_offset_x = int(viewport.deslocamento_render_x)
    self._imagem_render_offset_y = int(viewport.deslocamento_render_y)

    interpolacao = (
        cv2.INTER_AREA
        if self.escala_exibicao < 1.0
        else cv2.INTER_LINEAR
    )
    self.imagem_exibicao = cv2.resize(
        recorte,
        (
            self._imagem_render_largura,
            self._imagem_render_altura,
        ),
        interpolation=interpolacao,
    )

    dados_ppm = _codificar_ppm_bgr(self.imagem_exibicao)
    if _atualizar_photoimage_ppm(self, dados_ppm):
        return

    sucesso, buffer = cv2.imencode(
        ".png",
        self.imagem_exibicao,
        [cv2.IMWRITE_PNG_COMPRESSION, 1],
    )
    if not sucesso:
        return

    imagem_base64 = base64.b64encode(buffer).decode("ascii")
    self.imagem_tk = tk.PhotoImage(data=imagem_base64)
    self._imagem_tk_largura = self._imagem_render_largura
    self._imagem_tk_altura = self._imagem_render_altura
