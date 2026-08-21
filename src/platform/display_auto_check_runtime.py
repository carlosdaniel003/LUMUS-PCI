from __future__ import annotations

from src.platform.display_auto_check_analyzer import DisplayAutomaticCheckAnalyzer


class DisplayAutomaticCheckF3Mixin:
    """Liga a análise automática somente ao loop de preview da Produção Display."""

    DISPLAY_AUTO_OK_STABLE_FRAMES = 3
    DISPLAY_AUTO_NG_STABLE_FRAMES = 6
    DISPLAY_AUTO_TRANSITION_FRAMES = 4

    def __init__(self, *args, **kwargs) -> None:
        self._display_auto_analyzer = None
        self._display_auto_signature = None
        self._display_auto_last_decision = None
        self._display_auto_stable_frames = 0
        self._display_auto_transition_frames = self.DISPLAY_AUTO_TRANSITION_FRAMES
        self._display_auto_last_frame_token = None
        self._display_auto_last_analysis = None
        super().__init__(*args, **kwargs)
        self._rebuild_display_auto_analyzer()

    def _rebuild_display_auto_analyzer(self) -> None:
        repository = getattr(self, "display_project_repository", None)
        self._display_auto_analyzer = (
            DisplayAutomaticCheckAnalyzer(repository)
            if repository is not None
            else None
        )
        self._reset_display_auto_stability()

    def _reset_display_auto_stability(self, transition: bool = True) -> None:
        self._display_auto_signature = None
        self._display_auto_last_decision = None
        self._display_auto_stable_frames = 0
        self._display_auto_last_frame_token = None
        self._display_auto_last_analysis = None
        self._display_auto_transition_frames = (
            self.DISPLAY_AUTO_TRANSITION_FRAMES if transition else 0
        )

    def _display_auto_frame_token(self, frame):
        camera_token = getattr(self, "camera_ultimo_frame_id", None)
        if isinstance(camera_token, int) and camera_token >= 0:
            return ("camera", int(camera_token))
        return ("object", id(frame))

    def _display_auto_set_preview_status(self, text: str, color: str) -> None:
        window = getattr(self, "display_f3_window", None)
        if window is None:
            return
        try:
            window.set_preview_status(str(text), str(color))
        except Exception:
            pass

    def _display_auto_configuration_open(self) -> bool:
        window = getattr(self, "_display_project_config_window", None)
        if window is None:
            return False
        try:
            return bool(window.visible)
        except Exception:
            return False

    @staticmethod
    def _display_auto_reason_text(reason: str) -> str:
        messages = {
            "camera_sem_frame": "Aguardando imagem da câmera",
            "camera_sem_frame_visual": "Aguardando imagem visual válida",
            "projeto_display_inexistente": "Selecione um Projeto Display",
            "check_display_inexistente": "CHECK atual não encontrado",
            "resolucao_mestra_ausente": "Defina a resolução mestre",
            "check_sem_mascaras_ativas": "CHECK sem máscaras ACESO/APAGADO",
            "aprendizado_incompleto": (
                "Configure aprendizado ACESO, APAGADO e POUCA LUZ"
            ),
            "mascara_visual_nao_encontrada": "Máscara do CHECK não encontrada",
            "mascara_invalida": "Máscara inválida para análise",
            "mascara_fora_do_frame": "Máscara fora da imagem",
        }
        return messages.get(str(reason), str(reason).replace("_", " "))

    def _display_auto_current_context(self):
        runtime = getattr(self, "display_check_runtime", None)
        repository = getattr(self, "display_project_repository", None)
        if runtime is None or repository is None:
            return None

        snapshot = runtime.snapshot()
        current = snapshot.get("current_check")
        if not isinstance(current, dict):
            return None

        project_name = repository.obter_projeto_ativo()
        if not project_name:
            return None

        check_id = str(current.get("id") or "")
        if not check_id:
            return None

        return {
            "project_name": str(project_name),
            "check_id": check_id,
            "check_name": str(current.get("name") or check_id),
        }

    def _process_display_auto_check(self) -> None:
        if not bool(getattr(self, "display_f3_ativo", False)):
            return

        if getattr(self, "display_f3_result_after_id", None) is not None:
            self._reset_display_auto_stability()
            return

        if self._display_auto_configuration_open():
            self._reset_display_auto_stability(transition=False)
            self._display_auto_set_preview_status(
                "AUTO PAUSADO • configuração do Display aberta",
                "#FDE68A",
            )
            return

        frame = getattr(self, "camera_frame_atual", None)
        if frame is None or getattr(frame, "size", 0) == 0:
            self._reset_display_auto_stability()
            return

        frame_token = self._display_auto_frame_token(frame)
        if frame_token == self._display_auto_last_frame_token:
            return
        self._display_auto_last_frame_token = frame_token

        context = self._display_auto_current_context()
        if context is None:
            self._reset_display_auto_stability()
            return

        signature = (
            context["project_name"],
            context["check_id"],
        )
        if signature != self._display_auto_signature:
            self._display_auto_signature = signature
            self._display_auto_last_decision = None
            self._display_auto_stable_frames = 0
            self._display_auto_transition_frames = self.DISPLAY_AUTO_TRANSITION_FRAMES

        if self._display_auto_transition_frames > 0:
            self._display_auto_transition_frames -= 1
            self._display_auto_set_preview_status(
                (
                    f"AUTO • {context['check_name']} • estabilizando "
                    f"{self.DISPLAY_AUTO_TRANSITION_FRAMES - self._display_auto_transition_frames}"
                    f"/{self.DISPLAY_AUTO_TRANSITION_FRAMES}"
                ),
                "#FDE68A",
            )
            return

        analyzer = self._display_auto_analyzer
        repository = getattr(self, "display_project_repository", None)
        if analyzer is None or getattr(analyzer, "repository", None) is not repository:
            self._rebuild_display_auto_analyzer()
            analyzer = self._display_auto_analyzer
        if analyzer is None:
            return

        analysis = analyzer.analyze(
            frame=frame,
            project_name=context["project_name"],
            check_id=context["check_id"],
            visual_rotation=self._obter_rotacao_visual_display_f3(),
        )
        self._display_auto_last_analysis = analysis

        if not bool(analysis.get("ready")):
            self._display_auto_last_decision = None
            self._display_auto_stable_frames = 0
            self._display_auto_set_preview_status(
                "AUTO INDISPONÍVEL • "
                + self._display_auto_reason_text(analysis.get("reason", "")),
                "#FCA5A5",
            )
            return

        approved = bool(analysis.get("approved"))
        if approved == self._display_auto_last_decision:
            self._display_auto_stable_frames += 1
        else:
            self._display_auto_last_decision = approved
            self._display_auto_stable_frames = 1

        required = (
            self.DISPLAY_AUTO_OK_STABLE_FRAMES
            if approved
            else self.DISPLAY_AUTO_NG_STABLE_FRAMES
        )
        matched = int(analysis.get("matched_mask_count", 0) or 0)
        total = int(analysis.get("active_mask_count", 0) or 0)
        self._display_auto_set_preview_status(
            (
                f"AUTO • {context['check_name']} • {matched}/{total} conforme • "
                f"{self._display_auto_stable_frames}/{required}"
            ),
            "#86EFAC" if approved else "#FCA5A5",
        )

        if self._display_auto_stable_frames < required:
            return

        self._display_auto_stable_frames = 0
        self._display_auto_last_decision = None
        event = self.registrar_resultado_check_display_f3(approved)
        event_type = str(event.get("event", ""))
        if event_type == "check_advanced":
            self._display_auto_signature = None
            self._display_auto_transition_frames = self.DISPLAY_AUTO_TRANSITION_FRAMES
        else:
            self._reset_display_auto_stability()

    def _atualizar_preview_display_f3(self) -> None:
        super()._atualizar_preview_display_f3()
        self._process_display_auto_check()
