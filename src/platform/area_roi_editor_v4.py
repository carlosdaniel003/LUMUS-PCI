from __future__ import annotations

from types import SimpleNamespace

from src.platform.area_roi_editor_v3 import AreaRoiEditorV3Mixin
from src.platform.bulk_roi_editor import copiar_led, mover_rois


MOVIMENTO_TECLADO_PX = 1


class AreaRoiEditorV4Mixin(AreaRoiEditorV3Mixin):
    """Move a ROI individual ou o subconjunto selecionado com as setas."""

    DIRECOES = {
        "Left": (-MOVIMENTO_TECLADO_PX, 0, "esquerda"),
        "Right": (MOVIMENTO_TECLADO_PX, 0, "direita"),
        "Up": (0, -MOVIMENTO_TECLADO_PX, "cima"),
        "Down": (0, MOVIMENTO_TECLADO_PX, "baixo"),
        "KP_Left": (-MOVIMENTO_TECLADO_PX, 0, "esquerda"),
        "KP_Right": (MOVIMENTO_TECLADO_PX, 0, "direita"),
        "KP_Up": (0, -MOVIMENTO_TECLADO_PX, "cima"),
        "KP_Down": (0, MOVIMENTO_TECLADO_PX, "baixo"),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._instalar_movimento_roi_teclado()

    def _instalar_movimento_roi_teclado(self) -> None:
        canvas = getattr(getattr(self, "view", None), "canvas", None)
        if canvas is None:
            return

        for sequencia in (
            "<Left>",
            "<Right>",
            "<Up>",
            "<Down>",
            "<KP_Left>",
            "<KP_Right>",
            "<KP_Up>",
            "<KP_Down>",
        ):
            canvas.bind(
                sequencia,
                self._evento_mover_roi_teclado,
                add="+",
            )

    def _evento_preview_teclado(self):
        view = getattr(self, "view", None)
        if view is None:
            return None

        ultima_posicao = getattr(
            view,
            "_lupa_ultima_posicao_canvas",
            None,
        )
        if ultima_posicao is not None:
            return SimpleNamespace(
                x=int(ultima_posicao[0]),
                y=int(ultima_posicao[1]),
            )

        selecionados = self._leds_area_selecionados()
        bbox = self._bbox_leds(selecionados)
        if bbox is None:
            return None

        x1, y1, x2, y2 = bbox
        centro_x = (x1 + x2) / 2.0
        centro_y = (y1 + y2) / 2.0
        return SimpleNamespace(
            x=int(round(self._coordenada_canvas(centro_x, "x"))),
            y=int(round(self._coordenada_canvas(centro_y, "y"))),
        )

    def _atualizar_preview_apos_teclado(self) -> None:
        evento = self._evento_preview_teclado()
        if evento is not None:
            self._atualizar_lupa_dinamica(evento)

    def _evento_mover_roi_teclado(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        if not self._area_roi_ids:
            return None
        if self._area_roi_mode is not None:
            return "break"

        keysym = str(getattr(evento, "keysym", ""))
        direcao = self.DIRECOES.get(keysym)
        if direcao is None:
            return None

        deslocamento_x, deslocamento_y, nome_direcao = direcao
        todos = [copiar_led(led) for led in self._leds_editaveis()]
        ids = set(self._area_roi_ids)
        selecionados = [
            copiar_led(led)
            for led in todos
            if str(led.id) in ids
        ]
        if not selecionados:
            return None

        movidos = mover_rois(
            selecionados,
            deslocamento_x,
            deslocamento_y,
            int(getattr(self, "largura_original", 0) or 0),
            int(getattr(self, "altura_original", 0) or 0),
        )
        houve_movimento = any(
            antes.centro_x != depois.centro_x
            or antes.centro_y != depois.centro_y
            for antes, depois in zip(selecionados, movidos)
        )

        self._area_roi_snapshot_all = todos
        self._substituir_leds_editaveis(
            self._mesclar_transformados(movidos)
        )
        self._atualizar_pos_edicao_roi()
        self._atualizar_preview_apos_teclado()

        quantidade = len(selecionados)
        if houve_movimento:
            self.view.atualizar_status(
                f"{quantidade} ROI(s) movida(s) 1 px para {nome_direcao}. "
                "Continue usando as setas para ajuste fino."
            )
        else:
            self.view.atualizar_status(
                f"Movimento para {nome_direcao} bloqueado pelo limite da imagem."
            )
        return "break"

    def iniciar_selecao_led(self) -> None:
        super().iniciar_selecao_led()
        if self._modo_edicao_roi_ativo():
            self.view.atualizar_status(
                "Seleção ativa. Clique no vazio para adicionar ROI; arraste no vazio "
                "para selecionar uma área; clique numa ROI para editar; use as setas "
                "para mover a seleção pixel a pixel."
            )
