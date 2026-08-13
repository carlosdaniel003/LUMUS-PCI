def atualizar_metricas_desempenho(
    self,
    fps_preview: float | None = None,
    tempo_resposta_ms: float | None = None,
    rois_analisadas: int | None = None,
) -> None:
    if fps_preview is not None and hasattr(self, "label_meta_fps"):
        fps_preview = max(0.0, float(fps_preview))
        self.label_meta_fps.configure(
            text=f"{fps_preview:.1f} FPS"
        )

    if (
        tempo_resposta_ms is not None
        and hasattr(self, "label_meta_tempo")
    ):
        tempo_resposta_ms = max(0.0, float(tempo_resposta_ms))
        self.label_meta_tempo.configure(
            text=f"{tempo_resposta_ms:.0f} ms"
        )

    if (
        rois_analisadas is not None
        and hasattr(self, "label_meta_rois_analisadas")
    ):
        self.label_meta_rois_analisadas.configure(
            text=str(max(0, int(rois_analisadas)))
        )
