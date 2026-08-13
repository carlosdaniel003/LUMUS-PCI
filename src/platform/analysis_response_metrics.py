from __future__ import annotations

import time


class AnalysisResponseMetricsMixin:
    """Mede do acionamento da análise até o resultado ser renderizado."""

    def __init__(self, *args, **kwargs) -> None:
        self._analise_inicio_perf_counter = None
        super().__init__(*args, **kwargs)

    def _iniciar_medicao_tempo_resposta(self) -> None:
        if self._analise_inicio_perf_counter is None:
            self._analise_inicio_perf_counter = time.perf_counter()

    def _cancelar_medicao_tempo_resposta(self) -> None:
        self._analise_inicio_perf_counter = None

    def _finalizar_medicao_tempo_resposta(self, total_rois: int) -> float | None:
        inicio = self._analise_inicio_perf_counter
        if inicio is None:
            return None

        # Garante que o resultado já tenha sido entregue ao Tkinter antes de
        # encerrar o cronômetro. Assim o número representa a resposta percebida
        # pelo operador, e não somente o tempo interno do classificador.
        try:
            self.root.update_idletasks()
        except Exception:
            pass

        tempo_ms = max(0.0, (time.perf_counter() - inicio) * 1000.0)
        self._analise_inicio_perf_counter = None
        try:
            self.view.atualizar_metricas_desempenho(
                tempo_resposta_ms=tempo_ms,
                rois_analisadas=total_rois,
            )
        except Exception:
            pass
        return tempo_ms

    def analisar_led_selecionado(self):
        iniciou_nesta_chamada = self._analise_inicio_perf_counter is None
        if iniciou_nesta_chamada:
            self._iniciar_medicao_tempo_resposta()

        resultados_antes = getattr(self, "resultados_led_atual", None)
        try:
            retorno = super().analisar_led_selecionado()
        except Exception:
            if iniciou_nesta_chamada:
                self._cancelar_medicao_tempo_resposta()
            raise

        resultados_depois = getattr(self, "resultados_led_atual", None)
        analise_renderizada = bool(
            resultados_depois
            and resultados_depois is not resultados_antes
        )

        if analise_renderizada:
            self._finalizar_medicao_tempo_resposta(len(resultados_depois))
        elif iniciou_nesta_chamada and self._analise_inicio_perf_counter is not None:
            # Chamadas inválidas (sem imagem/ROI/referências, câmera ainda não
            # pronta etc.) não devem deixar um cronômetro pendurado para a
            # próxima análise válida. No fluxo de câmera válido, a chamada
            # recursiva conclui a medição e limpa o marcador antes de chegar aqui.
            self._cancelar_medicao_tempo_resposta()

        return retorno
