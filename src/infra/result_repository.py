from __future__ import annotations

from datetime import datetime
from pathlib import Path
from queue import Full, Queue
import re
import threading

import cv2

from config import RESULTS_DIR
from src.models.analysis_result import LedAnalysisResult
from src.models.led_selection import LedSelection
from src.models.output_paths import OutputPaths


class ResultRepository:
    """Salva somente fotografias NG sem bloquear a thread da interface."""

    MAX_FOTOS_PENDENTES = 8
    QUALIDADE_JPEG = 90
    COR_NG_BGR = (255, 0, 0)

    def __init__(self) -> None:
        self._fila_fotos_ng: Queue = Queue(
            maxsize=self.MAX_FOTOS_PENDENTES
        )
        self._worker_fotos_ng: threading.Thread | None = None
        self._worker_lock = threading.Lock()
        self.ultimo_erro_salvamento_ng: str | None = None
        self.fotos_ng_descartadas = 0

        # O worker nasce na inicialização e fica bloqueado na fila, sem polling.
        # Assim, o primeiro NG também executa apenas um put_nowait no fluxo crítico.
        self._garantir_worker_fotos_ng()

    @staticmethod
    def _resultado_eh_ng(resultado) -> bool:
        try:
            return int(getattr(resultado, "valor_binario", 1)) == 0
        except (TypeError, ValueError):
            return str(getattr(resultado, "status", "")).upper() != "ACESO"

    @staticmethod
    def _normalizar_nome_arquivo(valor: str, padrao: str) -> str:
        texto = str(valor or "").strip()
        texto = re.sub(r"[^A-Za-z0-9_-]+", "_", texto)
        texto = texto.strip("_")
        return texto[:48] or padrao

    @classmethod
    def criar_visualizacao_ng(cls, imagem_original, resultados_led):
        """Cria uma cópia da placa destacando apenas LEDs NG em azul."""
        imagem = imagem_original.copy()

        for resultado in resultados_led or ():
            if not cls._resultado_eh_ng(resultado):
                continue

            centro_x = int(getattr(resultado, "centro_x", 0))
            centro_y = int(getattr(resultado, "centro_y", 0))
            raio = max(3, int(getattr(resultado, "raio", 3)))
            raio_visual = max(4, int(round(raio * 1.25)))
            led_id = str(getattr(resultado, "id", "LED"))

            camada = imagem.copy()
            cv2.circle(
                camada,
                (centro_x, centro_y),
                raio_visual,
                cls.COR_NG_BGR,
                -1,
            )
            imagem = cv2.addWeighted(
                camada,
                0.22,
                imagem,
                0.78,
                0,
            )
            cv2.circle(
                imagem,
                (centro_x, centro_y),
                raio_visual,
                cls.COR_NG_BGR,
                3,
            )
            cv2.drawMarker(
                imagem,
                (centro_x, centro_y),
                cls.COR_NG_BGR,
                markerType=cv2.MARKER_CROSS,
                markerSize=max(10, int(raio * 1.10)),
                thickness=2,
            )

            texto = f"{led_id} NG"
            escala_fonte = 0.42
            espessura_fonte = 1
            largura_texto, altura_texto = cv2.getTextSize(
                texto,
                cv2.FONT_HERSHEY_SIMPLEX,
                escala_fonte,
                espessura_fonte,
            )[0]
            x_texto = max(4, centro_x - largura_texto // 2)
            y_texto = max(
                altura_texto + 8,
                centro_y - raio_visual - 7,
            )
            cv2.rectangle(
                imagem,
                (x_texto - 4, y_texto - altura_texto - 4),
                (x_texto + largura_texto + 4, y_texto + 4),
                (20, 25, 35),
                -1,
            )
            cv2.putText(
                imagem,
                texto,
                (x_texto, y_texto),
                cv2.FONT_HERSHEY_SIMPLEX,
                escala_fonte,
                cls.COR_NG_BGR,
                espessura_fonte,
                cv2.LINE_AA,
            )

        return imagem

    def _garantir_worker_fotos_ng(self) -> None:
        worker = self._worker_fotos_ng
        if worker is not None and worker.is_alive():
            return

        with self._worker_lock:
            worker = self._worker_fotos_ng
            if worker is not None and worker.is_alive():
                return

            self._worker_fotos_ng = threading.Thread(
                target=self._processar_fila_fotos_ng,
                name="odin-ng-image-writer",
                daemon=True,
            )
            self._worker_fotos_ng.start()

    def _processar_fila_fotos_ng(self) -> None:
        while True:
            tarefa = self._fila_fotos_ng.get()
            caminho, imagem_original, resultados_led = tarefa
            try:
                caminho.parent.mkdir(parents=True, exist_ok=True)
                imagem_ng = self.criar_visualizacao_ng(
                    imagem_original,
                    resultados_led,
                )
                sucesso, buffer = cv2.imencode(
                    ".jpg",
                    imagem_ng,
                    [cv2.IMWRITE_JPEG_QUALITY, self.QUALIDADE_JPEG],
                )
                if not sucesso:
                    raise OSError("OpenCV não codificou a fotografia NG.")

                buffer.tofile(str(caminho))
                self.ultimo_erro_salvamento_ng = None
            except Exception as erro:
                self.ultimo_erro_salvamento_ng = (
                    f"{type(erro).__name__}: {erro}"
                )
            finally:
                self._fila_fotos_ng.task_done()

    def salvar_foto_ng_assincrona(
        self,
        imagem_original,
        resultados_led,
        salvar_resultados_analise: bool,
        origem: str = "desenvolvimento",
        projeto: str = "",
        momento: datetime | None = None,
    ) -> OutputPaths:
        if not salvar_resultados_analise:
            return OutputPaths()
        if imagem_original is None or getattr(imagem_original, "size", 0) == 0:
            return OutputPaths()

        resultados = tuple(resultados_led or ())
        if not any(self._resultado_eh_ng(item) for item in resultados):
            return OutputPaths()

        momento = momento or datetime.now()
        origem_arquivo = self._normalizar_nome_arquivo(
            origem,
            "desenvolvimento",
        )
        projeto_arquivo = self._normalizar_nome_arquivo(
            projeto,
            "sem_projeto",
        )
        timestamp = momento.strftime("%Y%m%d_%H%M%S_%f")
        caminho = (
            RESULTS_DIR
            / "ng"
            / f"ng_{timestamp}_{origem_arquivo}_{projeto_arquivo}.jpg"
        )

        self._garantir_worker_fotos_ng()
        try:
            self._fila_fotos_ng.put_nowait(
                (caminho, imagem_original, resultados)
            )
        except Full:
            self.fotos_ng_descartadas += 1
            self.ultimo_erro_salvamento_ng = (
                "Fila de fotografias NG cheia; captura descartada para "
                "preservar o desempenho da inspeção."
            )
            return OutputPaths()

        return OutputPaths(caminho_resultado_imagem=caminho)

    def salvar_resultado_analise(
        self,
        imagem_original,
        resultado_led: LedAnalysisResult,
        caminho_imagem_atual: str | None,
        caminho_referencia_acesa: str | None,
        caminho_referencia_apagada: str | None,
        features_referencia_acesa,
        features_referencia_apagada,
        led_selecionado: LedSelection,
        salvar_resultados_analise: bool,
    ) -> OutputPaths:
        return self.salvar_resultado_analise_multiplos(
            imagem_original=imagem_original,
            resultados_led=[resultado_led],
            caminho_imagem_atual=caminho_imagem_atual,
            caminho_referencia_acesa=caminho_referencia_acesa,
            caminho_referencia_apagada=caminho_referencia_apagada,
            features_referencia_acesa=features_referencia_acesa,
            features_referencia_apagada=features_referencia_apagada,
            leds_selecionados=[led_selecionado],
            salvar_resultados_analise=salvar_resultados_analise,
        )

    def salvar_resultado_analise_multiplos(
        self,
        imagem_original,
        resultados_led: list[LedAnalysisResult],
        caminho_imagem_atual: str | None,
        caminho_referencia_acesa: str | None,
        caminho_referencia_apagada: str | None,
        features_referencia_acesa,
        features_referencia_apagada,
        leds_selecionados: list[LedSelection],
        salvar_resultados_analise: bool,
    ) -> OutputPaths:
        projeto = "desenvolvimento"
        if caminho_imagem_atual and caminho_imagem_atual != "camera_usb":
            projeto = Path(str(caminho_imagem_atual)).stem

        return self.salvar_foto_ng_assincrona(
            imagem_original=imagem_original,
            resultados_led=resultados_led,
            salvar_resultados_analise=salvar_resultados_analise,
            origem="desenvolvimento",
            projeto=projeto,
        )
