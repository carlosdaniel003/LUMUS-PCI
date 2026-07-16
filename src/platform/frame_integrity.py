from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class FrameIntegrityResult:
    valido: bool
    motivo: str = ""
    grupos_horizontais: int = 0
    pico_relativo: float = 0.0
    media_movimento: float = 0.0
    variacao_brilho: float = 0.0


class FrameIntegrityValidator:
    """Validação barata para descartar frames com bandas horizontais corrompidas.

    A análise trabalha em uma miniatura em tons de cinza e compara o frame atual
    apenas com o último frame aceito. Isso mantém o custo baixo no Raspberry Pi 3
    e evita classificar movimento global normal como corrupção horizontal.
    """

    MAX_WIDTH = 320
    LIMIAR_PIXEL_DIFERENTE = 25
    FRACAO_LARGURA_MINIMA = 0.18
    MEDIA_LINHA_MINIMA = 12.0
    MEDIA_BANDA_MINIMA = 16.0
    PICO_RELATIVO_MINIMO = 3.2
    GRUPOS_MINIMOS = 2
    COBERTURA_VERTICAL_MAXIMA = 0.35

    def __init__(self) -> None:
        self._ultimo_cinza: np.ndarray | None = None

    def reset(self) -> None:
        self._ultimo_cinza = None

    @classmethod
    def _preparar_cinza(cls, frame) -> np.ndarray | None:
        if frame is None or getattr(frame, "size", 0) == 0:
            return None

        try:
            if len(frame.shape) == 2:
                cinza = frame
            elif len(frame.shape) == 3 and frame.shape[2] == 3:
                cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            elif len(frame.shape) == 3 and frame.shape[2] == 4:
                cinza = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
            else:
                return None
        except Exception:
            return None

        altura, largura = cinza.shape[:2]
        if altura < 16 or largura < 16:
            return None

        if largura > cls.MAX_WIDTH:
            escala = cls.MAX_WIDTH / float(largura)
            nova_altura = max(16, int(round(altura * escala)))
            cinza = cv2.resize(
                cinza,
                (cls.MAX_WIDTH, nova_altura),
                interpolation=cv2.INTER_AREA,
            )

        return cv2.GaussianBlur(cinza, (3, 3), 0)

    @staticmethod
    def _contar_grupos(mascara: np.ndarray) -> int:
        grupos = 0
        dentro = False
        for valor in mascara.astype(bool):
            if valor and not dentro:
                grupos += 1
                dentro = True
            elif not valor:
                dentro = False
        return grupos

    @staticmethod
    def _parece_translacao_global(
        anterior: np.ndarray,
        atual: np.ndarray,
        media_diferenca: float,
    ) -> bool:
        """Distingue movimento da placa de blocos realmente corrompidos."""
        try:
            (deslocamento_x, deslocamento_y), resposta = cv2.phaseCorrelate(
                anterior.astype(np.float32),
                atual.astype(np.float32),
            )
        except Exception:
            return False

        deslocamento_relevante = (
            abs(float(deslocamento_x)) >= 0.8
            or abs(float(deslocamento_y)) >= 0.8
        )
        if not deslocamento_relevante or float(resposta) < 0.35:
            return False

        matriz = np.float32(
            [
                [1.0, 0.0, -float(deslocamento_x)],
                [0.0, 1.0, -float(deslocamento_y)],
            ]
        )
        alinhado = cv2.warpAffine(
            atual,
            matriz,
            (atual.shape[1], atual.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        residuo = float(cv2.absdiff(anterior, alinhado).mean())
        return residuo <= max(2.5, float(media_diferenca) * 0.35)

    def avaliar(self, frame) -> FrameIntegrityResult:
        atual = self._preparar_cinza(frame)
        if atual is None:
            return FrameIntegrityResult(False, "frame_invalido")

        anterior = self._ultimo_cinza
        if anterior is None or anterior.shape != atual.shape:
            self._ultimo_cinza = atual
            return FrameIntegrityResult(True, "primeiro_frame")

        diferenca = cv2.absdiff(atual, anterior)
        medias_linha = diferenca.mean(axis=1)
        fracoes_linha = (
            diferenca >= self.LIMIAR_PIXEL_DIFERENTE
        ).mean(axis=1)

        mediana = float(np.median(medias_linha))
        desvio_absoluto = float(
            np.median(np.abs(medias_linha - mediana))
        )
        limiar_adaptativo = max(
            self.MEDIA_LINHA_MINIMA,
            mediana + max(6.0, 4.0 * desvio_absoluto),
        )

        linhas_fortes = (
            (medias_linha >= limiar_adaptativo)
            & (
                (fracoes_linha >= self.FRACAO_LARGURA_MINIMA)
                | (medias_linha >= self.MEDIA_BANDA_MINIMA)
            )
        )

        # Ignora duas linhas nas bordas, onde redimensionamento/rotação pode gerar
        # pequenas diferenças sem relevância para a inspeção.
        if linhas_fortes.size >= 4:
            linhas_fortes[:2] = False
            linhas_fortes[-2:] = False

        grupos = self._contar_grupos(linhas_fortes)
        cobertura = float(np.count_nonzero(linhas_fortes)) / max(
            1,
            linhas_fortes.size,
        )
        pico = float(np.max(medias_linha)) if medias_linha.size else 0.0
        pico_relativo = pico / max(1.0, mediana)
        media_movimento = float(diferenca.mean())
        variacao_brilho = abs(float(atual.mean()) - float(anterior.mean()))

        corrompido = (
            grupos >= self.GRUPOS_MINIMOS
            and cobertura <= self.COBERTURA_VERTICAL_MAXIMA
            and pico_relativo >= self.PICO_RELATIVO_MINIMO
        )

        if corrompido and self._parece_translacao_global(
            anterior,
            atual,
            media_movimento,
        ):
            corrompido = False

        if corrompido:
            # Não aprende com o frame rejeitado. Assim, uma sequência de quadros
            # corrompidos continua sendo comparada com o último frame íntegro.
            return FrameIntegrityResult(
                False,
                "bandas_horizontais",
                grupos_horizontais=grupos,
                pico_relativo=round(pico_relativo, 3),
                media_movimento=round(media_movimento, 3),
                variacao_brilho=round(variacao_brilho, 3),
            )

        self._ultimo_cinza = atual
        return FrameIntegrityResult(
            True,
            "ok",
            grupos_horizontais=grupos,
            pico_relativo=round(pico_relativo, 3),
            media_movimento=round(media_movimento, 3),
            variacao_brilho=round(variacao_brilho, 3),
        )
