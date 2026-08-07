from __future__ import annotations

from src.platform.area_roi_editor import LUPA_TAMANHO_PX
from src.platform.rotated_roi_editor import RotatedAreaRoiEditorMixin
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    normalizar_rotacao_visual,
)


def converter_ponto_preview_lupa(
    x: float,
    y: float,
    tamanho: int,
    rotacao: int,
) -> tuple[float, float]:
    """Projeta um ponto do preview quadrado na mesma rotação da imagem."""
    limite = float(max(1, int(tamanho)))
    px = float(x)
    py = float(y)
    angulo = normalizar_rotacao_visual(rotacao)

    if angulo == 90:
        return limite - py, px
    if angulo == 180:
        return limite - px, limite - py
    if angulo == 270:
        return py, limite - px
    return px, py


def converter_retangulo_preview_lupa(
    esquerda: float,
    topo: float,
    direita: float,
    base: float,
    tamanho: int,
    rotacao: int,
) -> tuple[float, float, float, float]:
    pontos = (
        converter_ponto_preview_lupa(esquerda, topo, tamanho, rotacao),
        converter_ponto_preview_lupa(direita, topo, tamanho, rotacao),
        converter_ponto_preview_lupa(direita, base, tamanho, rotacao),
        converter_ponto_preview_lupa(esquerda, base, tamanho, rotacao),
    )
    xs = [ponto[0] for ponto in pontos]
    ys = [ponto[1] for ponto in pontos]
    return min(xs), min(ys), max(xs), max(ys)


class RotatedPreviewAreaRoiEditorMixin(RotatedAreaRoiEditorMixin):
    """Completa o editor rotacionado fazendo a lupa acompanhar a orientação."""

    def _desenhar_marquee_na_lupa(
        self,
        evento,
        imagem_x: int,
        imagem_y: int,
    ) -> None:
        if (
            self._area_roi_mode != "marquee"
            or self._area_roi_press_image is None
            or self._area_roi_current_image is None
        ):
            return

        imagem = getattr(self.view, "imagem_canvas_original", None)
        if imagem is None or getattr(imagem, "size", 0) == 0:
            return

        altura, largura = imagem.shape[:2]
        raio = max(3, int(getattr(self.view, "raio_atual_px", 3)))
        margem = max(28, raio * 4)
        recorte_x1 = max(0, imagem_x - margem)
        recorte_y1 = max(0, imagem_y - margem)
        recorte_x2 = min(largura, imagem_x + margem)
        recorte_y2 = min(altura, imagem_y + margem)
        if recorte_x2 <= recorte_x1 or recorte_y2 <= recorte_y1:
            return

        sx1, sy1 = self._area_roi_press_image
        sx2, sy2 = self._area_roi_current_image
        esquerda = max(min(sx1, sx2), recorte_x1)
        direita = min(max(sx1, sx2), recorte_x2)
        topo = max(min(sy1, sy2), recorte_y1)
        base = min(max(sy1, sy2), recorte_y2)
        if direita <= esquerda or base <= topo:
            return

        escala_x = LUPA_TAMANHO_PX / max(1, recorte_x2 - recorte_x1)
        escala_y = LUPA_TAMANHO_PX / max(1, recorte_y2 - recorte_y1)

        local_esquerda = (esquerda - recorte_x1) * escala_x
        local_direita = (direita - recorte_x1) * escala_x
        local_topo = (topo - recorte_y1) * escala_y
        local_base = (base - recorte_y1) * escala_y

        rotacao = normalizar_rotacao_visual(
            getattr(self.view, "rotacao_visual_principal", 0)
        )
        rx1, ry1, rx2, ry2 = converter_retangulo_preview_lupa(
            local_esquerda,
            local_topo,
            local_direita,
            local_base,
            LUPA_TAMANHO_PX,
            rotacao,
        )

        largura_canvas, _ = self.view.obter_tamanho_canvas_principal()
        x_lupa = largura_canvas - LUPA_TAMANHO_PX - 18
        y_lupa = 42
        mouse_sobre_lupa = (
            evento.x >= x_lupa - 20
            and evento.x <= x_lupa + LUPA_TAMANHO_PX + 20
            and evento.y >= y_lupa - 40
            and evento.y <= y_lupa + LUPA_TAMANHO_PX + 50
        )
        if mouse_sobre_lupa:
            x_lupa = 18
        x_lupa = max(12, x_lupa)
        y_lupa = max(12, y_lupa)

        self.view.canvas.create_rectangle(
            x_lupa + rx1,
            y_lupa + ry1,
            x_lupa + rx2,
            y_lupa + ry2,
            outline="#38BDF8",
            width=2,
            dash=(5, 3),
            tags=("lupa_canvas",),
        )
        self.view.canvas.tag_raise("lupa_canvas")
