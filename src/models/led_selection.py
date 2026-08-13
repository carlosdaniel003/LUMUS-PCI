from __future__ import annotations

import math
from dataclasses import dataclass

from src.core.roi_geometry import (
    TIPO_ROI_CIRCULO,
    TIPO_ROI_SEGMENTO,
    dimensoes_segmento,
    normalizar_angulo_segmento,
    normalizar_tipo_roi,
    raio_compatibilidade_segmento,
)


@dataclass
class LedSelection:
    id: str
    centro_x: int
    centro_y: int
    raio: int
    centro_x_normalizado: float | None = None
    centro_y_normalizado: float | None = None
    raio_normalizado: float | None = None
    largura_base: int | None = None
    altura_base: int | None = None
    tipo_roi: str = TIPO_ROI_CIRCULO
    largura: int | None = None
    altura: int | None = None
    angulo: float = 0.0
    pontos_segmento_livre: list[tuple[float, float]] | None = None

    @staticmethod
    def _normalizar_pontos_segmento_livre(pontos) -> list[tuple[float, float]] | None:
        if not isinstance(pontos, (list, tuple)):
            return None
        normalizados: list[tuple[float, float]] = []
        for ponto in pontos:
            if not isinstance(ponto, (list, tuple)) or len(ponto) < 2:
                continue
            try:
                normalizados.append((float(ponto[0]), float(ponto[1])))
            except (TypeError, ValueError):
                continue
        return normalizados if len(normalizados) >= 3 else None

    def __post_init__(self) -> None:
        self.tipo_roi = normalizar_tipo_roi(self.tipo_roi)
        self.centro_x = int(self.centro_x)
        self.centro_y = int(self.centro_y)
        self.raio = max(1, int(self.raio))
        self.angulo = normalizar_angulo_segmento(self.angulo)
        self.pontos_segmento_livre = self._normalizar_pontos_segmento_livre(
            self.pontos_segmento_livre
        )

        if self.tipo_roi == TIPO_ROI_SEGMENTO:
            if self.pontos_segmento_livre:
                xs = [p[0] for p in self.pontos_segmento_livre]
                ys = [p[1] for p in self.pontos_segmento_livre]
                self.largura = max(1, int(math.ceil(max(xs) - min(xs))))
                self.altura = max(1, int(math.ceil(max(ys) - min(ys))))
                self.raio = max(
                    2,
                    int(
                        math.ceil(
                            max(
                                math.hypot(float(x), float(y))
                                for x, y in self.pontos_segmento_livre
                            )
                        )
                    ),
                )
            else:
                largura, altura = dimensoes_segmento(self)
                self.largura = int(largura)
                self.altura = int(altura)
                self.raio = raio_compatibilidade_segmento(largura, altura)
        else:
            self.largura = None
            self.altura = None
            self.angulo = 0.0
            self.pontos_segmento_livre = None

    @classmethod
    def from_dict(cls, dados: dict | None) -> "LedSelection | None":
        if not dados:
            return None

        normalizado = dados.get("normalized", {})
        resolucao_base = dados.get("base_resolution", {})
        if not isinstance(normalizado, dict):
            normalizado = {}
        if not isinstance(resolucao_base, dict):
            resolucao_base = {}

        def obter_float(*nomes):
            for nome in nomes:
                valor = dados.get(nome, normalizado.get(nome))
                if valor is not None:
                    try:
                        return float(valor)
                    except (TypeError, ValueError):
                        return None
            return None

        def obter_int(*nomes):
            for nome in nomes:
                valor = dados.get(nome, resolucao_base.get(nome))
                if valor is not None:
                    try:
                        return int(valor)
                    except (TypeError, ValueError):
                        return None
            return None

        tipo = normalizar_tipo_roi(
            dados.get("tipo_roi", dados.get("shape", dados.get("tipo")))
        )
        largura_segmento = obter_int("largura", "roi_width", "segment_width")
        altura_segmento = obter_int("altura", "roi_height", "segment_height")
        pontos_segmento_livre = cls._normalizar_pontos_segmento_livre(
            dados.get("pontos_segmento_livre", dados.get("segment_points"))
        )

        raio_origem = dados.get("raio")
        if raio_origem is None and tipo == TIPO_ROI_SEGMENTO:
            raio_origem = raio_compatibilidade_segmento(
                largura_segmento or 48,
                altura_segmento or 14,
            )
        if raio_origem is None:
            return None

        return cls(
            id=str(dados.get("id", "LED_SELECIONADO")),
            centro_x=int(dados["centro_x"]),
            centro_y=int(dados["centro_y"]),
            raio=int(raio_origem),
            centro_x_normalizado=obter_float("centro_x_normalizado", "x"),
            centro_y_normalizado=obter_float("centro_y_normalizado", "y"),
            raio_normalizado=obter_float("raio_normalizado", "radius"),
            largura_base=obter_int("largura_base", "width"),
            altura_base=obter_int("altura_base", "height"),
            tipo_roi=tipo,
            largura=largura_segmento,
            altura=altura_segmento,
            angulo=obter_float("angulo", "angle") or 0.0,
            pontos_segmento_livre=pontos_segmento_livre,
        )

    @property
    def eh_segmento(self) -> bool:
        return self.tipo_roi == TIPO_ROI_SEGMENTO

    @property
    def eh_circulo(self) -> bool:
        return self.tipo_roi == TIPO_ROI_CIRCULO

    @property
    def eh_segmento_livre(self) -> bool:
        return self.eh_segmento and bool(self.pontos_segmento_livre)

    def possui_coordenadas_normalizadas(self) -> bool:
        return (
            self.centro_x_normalizado is not None
            and self.centro_y_normalizado is not None
            and self.raio_normalizado is not None
        )

    def com_normalizacao(
        self,
        largura_base: int,
        altura_base: int,
    ) -> "LedSelection":
        largura_base = max(1, int(largura_base))
        altura_base = max(1, int(altura_base))
        return LedSelection(
            id=self.id,
            centro_x=int(self.centro_x),
            centro_y=int(self.centro_y),
            raio=int(self.raio),
            centro_x_normalizado=float(self.centro_x) / largura_base,
            centro_y_normalizado=float(self.centro_y) / altura_base,
            raio_normalizado=float(self.raio) / largura_base,
            largura_base=largura_base,
            altura_base=altura_base,
            tipo_roi=self.tipo_roi,
            largura=self.largura,
            altura=self.altura,
            angulo=self.angulo,
            pontos_segmento_livre=(
                list(self.pontos_segmento_livre)
                if self.pontos_segmento_livre
                else None
            ),
        )

    def adaptar_para_resolucao(
        self,
        largura_destino: int,
        altura_destino: int,
        raio_minimo: int,
        raio_maximo: int,
    ) -> "LedSelection":
        largura_destino = max(1, int(largura_destino))
        altura_destino = max(1, int(altura_destino))

        if self.possui_coordenadas_normalizadas():
            centro_x = int(round(self.centro_x_normalizado * largura_destino))
            centro_y = int(round(self.centro_y_normalizado * altura_destino))
            escala_x = (
                largura_destino / max(1, int(self.largura_base))
                if self.largura_base
                else 1.0
            )
            escala_y = (
                altura_destino / max(1, int(self.altura_base))
                if self.altura_base
                else 1.0
            )
            raio = int(round(self.raio_normalizado * largura_destino))
        elif self.largura_base and self.altura_base:
            escala_x = largura_destino / max(1, int(self.largura_base))
            escala_y = altura_destino / max(1, int(self.altura_base))
            centro_x = int(round(self.centro_x * escala_x))
            centro_y = int(round(self.centro_y * escala_y))
            raio = int(round(self.raio * min(escala_x, escala_y)))
        else:
            escala_x = 1.0
            escala_y = 1.0
            centro_x = int(self.centro_x)
            centro_y = int(self.centro_y)
            raio = int(self.raio)

        pontos_segmento_livre = None
        if self.eh_segmento:
            if self.pontos_segmento_livre:
                pontos_segmento_livre = [
                    (float(x) * escala_x, float(y) * escala_y)
                    for x, y in self.pontos_segmento_livre
                ]
                largura = max(1, int(round((self.largura or 1) * escala_x)))
                altura = max(1, int(round((self.altura or 1) * escala_y)))
            else:
                largura = max(1, int(round((self.largura or 48) * escala_x)))
                altura = max(1, int(round((self.altura or 14) * escala_y)))
                raio = raio_compatibilidade_segmento(largura, altura)
        else:
            largura = None
            altura = None
            raio = min(int(raio_maximo), max(int(raio_minimo), raio))

        return LedSelection(
            id=self.id,
            centro_x=centro_x,
            centro_y=centro_y,
            raio=raio,
            centro_x_normalizado=self.centro_x_normalizado,
            centro_y_normalizado=self.centro_y_normalizado,
            raio_normalizado=self.raio_normalizado,
            largura_base=self.largura_base,
            altura_base=self.altura_base,
            tipo_roi=self.tipo_roi,
            largura=largura,
            altura=altura,
            angulo=self.angulo,
            pontos_segmento_livre=pontos_segmento_livre,
        )

    def to_dict(self) -> dict:
        dados = {
            "id": self.id,
            "centro_x": int(self.centro_x),
            "centro_y": int(self.centro_y),
            "raio": int(self.raio),
        }

        if self.eh_segmento:
            dados.update(
                {
                    "tipo_roi": TIPO_ROI_SEGMENTO,
                    "largura": int(self.largura or 48),
                    "altura": int(self.altura or 14),
                    "angulo": float(self.angulo),
                }
            )
            if self.pontos_segmento_livre:
                dados["pontos_segmento_livre"] = [
                    [float(x), float(y)]
                    for x, y in self.pontos_segmento_livre
                ]

        if self.possui_coordenadas_normalizadas():
            dados["normalized"] = {
                "x": float(self.centro_x_normalizado),
                "y": float(self.centro_y_normalizado),
                "radius": float(self.raio_normalizado),
            }

        if self.largura_base and self.altura_base:
            dados["base_resolution"] = {
                "width": int(self.largura_base),
                "height": int(self.altura_base),
            }
        return dados
