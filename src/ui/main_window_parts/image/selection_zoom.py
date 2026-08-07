from __future__ import annotations

import math
from dataclasses import dataclass


ZOOM_SELECAO_MIN = 1.0
ZOOM_SELECAO_MAX = 8.0
ZOOM_SELECAO_PASSO = 1.25


@dataclass(frozen=True)
class SelectionZoomViewport:
    escala: float
    largura_virtual: int
    altura_virtual: int
    deslocamento_virtual_x: int
    deslocamento_virtual_y: int
    origem_visual_x: int
    origem_visual_y: int
    fim_visual_x: int
    fim_visual_y: int
    largura_render: int
    altura_render: int
    deslocamento_render_x: int
    deslocamento_render_y: int


def limitar_fator_zoom_selecao(valor: float) -> float:
    try:
        fator = float(valor)
    except (TypeError, ValueError):
        fator = ZOOM_SELECAO_MIN
    return max(ZOOM_SELECAO_MIN, min(ZOOM_SELECAO_MAX, fator))


def proximo_fator_zoom_selecao(atual: float, direcao: int) -> float:
    atual = limitar_fator_zoom_selecao(atual)
    if int(direcao) > 0:
        novo = atual * ZOOM_SELECAO_PASSO
    elif int(direcao) < 0:
        novo = atual / ZOOM_SELECAO_PASSO
    else:
        novo = atual

    novo = limitar_fator_zoom_selecao(novo)
    if abs(novo - ZOOM_SELECAO_MIN) < 0.02:
        return ZOOM_SELECAO_MIN
    if abs(novo - ZOOM_SELECAO_MAX) < 0.02:
        return ZOOM_SELECAO_MAX
    return novo


def calcular_escala_zoom_selecao(
    largura_visual: int,
    altura_visual: int,
    largura_canvas: int,
    altura_canvas: int,
    fator_zoom: float,
) -> float:
    largura_visual = max(1, int(largura_visual))
    altura_visual = max(1, int(altura_visual))
    largura_canvas = max(1, int(largura_canvas))
    altura_canvas = max(1, int(altura_canvas))
    escala_base = min(
        largura_canvas / float(largura_visual),
        altura_canvas / float(altura_visual),
        1.0,
    )
    return escala_base * limitar_fator_zoom_selecao(fator_zoom)


def _limitar_deslocamento(
    deslocamento: float,
    tamanho_virtual: int,
    tamanho_canvas: int,
) -> int:
    if tamanho_virtual <= tamanho_canvas:
        return int((tamanho_canvas - tamanho_virtual) / 2)
    minimo = tamanho_canvas - tamanho_virtual
    return int(round(max(minimo, min(0.0, deslocamento))))


def calcular_viewport_zoom_selecao(
    largura_visual: int,
    altura_visual: int,
    largura_canvas: int,
    altura_canvas: int,
    fator_zoom: float,
    centro_visual_x: float | None = None,
    centro_visual_y: float | None = None,
) -> SelectionZoomViewport:
    """Calcula o zoom virtual e somente o recorte que precisa ser renderizado.

    A imagem completa pode ficar virtualmente muito maior que o Canvas, mas a
    PhotoImage gerada permanece aproximadamente do tamanho da área visível.
    Isso evita multiplicar o consumo de memória em zoom alto no Raspberry Pi.
    """
    largura_visual = max(1, int(largura_visual))
    altura_visual = max(1, int(altura_visual))
    largura_canvas = max(1, int(largura_canvas))
    altura_canvas = max(1, int(altura_canvas))
    fator_zoom = limitar_fator_zoom_selecao(fator_zoom)

    escala = calcular_escala_zoom_selecao(
        largura_visual,
        altura_visual,
        largura_canvas,
        altura_canvas,
        fator_zoom,
    )
    largura_virtual = max(1, int(round(largura_visual * escala)))
    altura_virtual = max(1, int(round(altura_visual * escala)))

    if fator_zoom <= ZOOM_SELECAO_MIN:
        centro_visual_x = largura_visual / 2.0
        centro_visual_y = altura_visual / 2.0
    else:
        if centro_visual_x is None:
            centro_visual_x = largura_visual / 2.0
        if centro_visual_y is None:
            centro_visual_y = altura_visual / 2.0

    centro_visual_x = max(0.0, min(float(largura_visual), float(centro_visual_x)))
    centro_visual_y = max(0.0, min(float(altura_visual), float(centro_visual_y)))

    deslocamento_x = _limitar_deslocamento(
        largura_canvas / 2.0 - centro_visual_x * escala,
        largura_virtual,
        largura_canvas,
    )
    deslocamento_y = _limitar_deslocamento(
        altura_canvas / 2.0 - centro_visual_y * escala,
        altura_virtual,
        altura_canvas,
    )

    margem_visual = 1
    origem_x = max(
        0,
        int(math.floor(max(0.0, -deslocamento_x / escala))) - margem_visual,
    )
    origem_y = max(
        0,
        int(math.floor(max(0.0, -deslocamento_y / escala))) - margem_visual,
    )
    fim_x = min(
        largura_visual,
        int(math.ceil(min(
            float(largura_visual),
            (largura_canvas - deslocamento_x) / escala,
        ))) + margem_visual,
    )
    fim_y = min(
        altura_visual,
        int(math.ceil(min(
            float(altura_visual),
            (altura_canvas - deslocamento_y) / escala,
        ))) + margem_visual,
    )

    fim_x = max(origem_x + 1, fim_x)
    fim_y = max(origem_y + 1, fim_y)

    largura_render = max(1, int(round((fim_x - origem_x) * escala)))
    altura_render = max(1, int(round((fim_y - origem_y) * escala)))
    deslocamento_render_x = int(round(deslocamento_x + origem_x * escala))
    deslocamento_render_y = int(round(deslocamento_y + origem_y * escala))

    return SelectionZoomViewport(
        escala=escala,
        largura_virtual=largura_virtual,
        altura_virtual=altura_virtual,
        deslocamento_virtual_x=deslocamento_x,
        deslocamento_virtual_y=deslocamento_y,
        origem_visual_x=origem_x,
        origem_visual_y=origem_y,
        fim_visual_x=fim_x,
        fim_visual_y=fim_y,
        largura_render=largura_render,
        altura_render=altura_render,
        deslocamento_render_x=deslocamento_render_x,
        deslocamento_render_y=deslocamento_render_y,
    )


def calcular_centro_zoom_ancorado(
    ponteiro_x: float,
    ponteiro_y: float,
    escala_atual: float,
    deslocamento_atual_x: float,
    deslocamento_atual_y: float,
    largura_virtual_atual: int,
    altura_virtual_atual: int,
    nova_escala: float,
    largura_canvas: int,
    altura_canvas: int,
    largura_visual: int,
    altura_visual: int,
    centro_atual_x: float | None = None,
    centro_atual_y: float | None = None,
) -> tuple[float, float]:
    """Mantém sob o cursor o mesmo ponto da imagem durante Ctrl+scroll."""
    largura_visual = max(1, int(largura_visual))
    altura_visual = max(1, int(altura_visual))
    largura_canvas = max(1, int(largura_canvas))
    altura_canvas = max(1, int(altura_canvas))
    escala_atual = max(1e-9, float(escala_atual))
    nova_escala = max(1e-9, float(nova_escala))

    dentro = (
        float(deslocamento_atual_x) <= float(ponteiro_x)
        < float(deslocamento_atual_x) + int(largura_virtual_atual)
        and float(deslocamento_atual_y) <= float(ponteiro_y)
        < float(deslocamento_atual_y) + int(altura_virtual_atual)
    )

    if not dentro:
        return (
            float(centro_atual_x)
            if centro_atual_x is not None
            else largura_visual / 2.0,
            float(centro_atual_y)
            if centro_atual_y is not None
            else altura_visual / 2.0,
        )

    ancora_visual_x = (
        float(ponteiro_x) - float(deslocamento_atual_x)
    ) / escala_atual
    ancora_visual_y = (
        float(ponteiro_y) - float(deslocamento_atual_y)
    ) / escala_atual

    centro_x = ancora_visual_x + (
        largura_canvas / 2.0 - float(ponteiro_x)
    ) / nova_escala
    centro_y = ancora_visual_y + (
        altura_canvas / 2.0 - float(ponteiro_y)
    ) / nova_escala

    return (
        max(0.0, min(float(largura_visual), centro_x)),
        max(0.0, min(float(altura_visual), centro_y)),
    )
