from __future__ import annotations


DISPLAY_F3_RESULT_HOLD_MS = 2000


def obter_feedback_espera_display_f3(snapshot: dict | None):
    """Retorna o último resultado somente enquanto aguarda o primeiro CHECK."""
    data = dict(snapshot or {})
    try:
        current_index = int(data.get("current_index", 0) or 0)
    except (TypeError, ValueError):
        current_index = 0

    completed_ids = tuple(data.get("completed_ids", ()) or ())
    if current_index != 0 or completed_ids:
        return None

    last_result = str(data.get("last_result") or "").strip().upper()
    if last_result == "OK":
        return (
            "OK",
            "Última placa: OK • aguardando H1 da próxima placa",
        )
    if last_result == "NG":
        return (
            "NG",
            "Última placa: NG • aguardando H1 da próxima placa",
        )
    return None


def instalar_feedback_resultado_display_f3() -> None:
    """Replica no F3 a memória visual pós-resultado usada pela Produção F2."""
    from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin
    import src.platform.display_production_f3_window as window_module

    # O mixin automático vem antes do runtime F3 no MRO da aplicação. Definir
    # aqui mantém a alteração exclusiva do F3 e faz o agendamento oficial usar
    # dois segundos sem tocar no fluxo da Produção F2.
    DisplayAutomaticCheckF3Mixin.DISPLAY_F3_RESULT_HOLD_MS = DISPLAY_F3_RESULT_HOLD_MS

    cls = window_module.DisplayProductionF3Window
    if getattr(cls, "_odin_display_result_feedback", False):
        return

    original_set_check_sequence = cls.set_check_sequence

    def set_check_sequence(self, snapshot) -> None:
        original_set_check_sequence(self, snapshot)

        # O frame extra do fluxo de CHECKS não pertence à janela-base F2, então
        # precisa acompanhar explicitamente a cor principal do estado de espera.
        try:
            self.check_flow_frame.configure(bg=self.COLOR_WAITING)
        except Exception:
            pass

        data = dict(snapshot or {})
        checks = list(data.get("checks", []) or [])
        current = data.get("current_check")
        if not checks or not isinstance(current, dict):
            return
        if not bool(getattr(self, "_camera_ready", False)):
            return

        feedback = obter_feedback_espera_display_f3(data)
        if feedback is None:
            return

        result, detail = feedback
        background = (
            self.COLOR_WAITING_AFTER_OK
            if result == "OK"
            else self.COLOR_WAITING_AFTER_NG
        )
        name = str(current.get("name") or current.get("id") or "CHECK")
        self._set_state(
            background=background,
            foreground="#FFFFFF",
            status=f"AGUARDANDO {name}",
            detail=detail,
        )
        try:
            self.check_flow_frame.configure(bg=background)
        except Exception:
            pass
        self.status_label.configure(font=("DejaVu Sans", 28, "bold"))

    cls.set_check_sequence = set_check_sequence
    cls._odin_display_result_feedback = True


instalar_feedback_resultado_display_f3()
