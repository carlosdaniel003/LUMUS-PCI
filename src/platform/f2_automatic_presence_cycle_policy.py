from __future__ import annotations

from src.core.segment_low_light import STATUS_APAGADO
from src.platform.f2_automatic_analysis import estados_resultado_operacao
from src.platform.f2_board_presence_references import (
    F2_BOARD_PRESENCE_EMPTY,
    F2_BOARD_PRESENCE_PRESENT,
)


F2_AUTO_NEW_BOARD_OFF_FRAMES_REQUIRED = 2


class F2AutomaticPresenceCyclePolicyMixin:
    """Liga o disparo por LED ao ciclo físico de troca da placa.

    A primeira análise automática continua sendo disparada pela evidência já
    validada no F2: pelo menos um LED ACESO. Depois de uma inspeção bem-sucedida,
    porém, a placa fica travada e não pode disparar novamente. O rearme exige a
    sequência física SUPORTE VAZIO -> NOVA PLACA PRESENTE E APAGADA. Só depois
    disso um novo LED ACESO pode iniciar outra análise automática.

    Enter/GPIO continuam independentes: uma ação manual sempre pode solicitar
    uma análise, mesmo quando o ciclo automático está travado.
    """

    def _f2_auto_reset_runtime(self) -> None:
        result = super()._f2_auto_reset_runtime()
        self._f2_auto_waiting_new_board_off = False
        self._f2_auto_new_board_off_frames = 0
        return result

    @staticmethod
    def _f2_auto_all_leds_off(states: dict[str, str] | None) -> bool:
        current = dict(states or {})
        return bool(current) and all(
            str(status).strip().upper() == STATUS_APAGADO
            for status in current.values()
        )

    def _f2_auto_observe_new_board_off(
        self,
        states: dict[str, str],
        presence: str,
    ) -> bool:
        if not bool(getattr(self, "_f2_auto_waiting_new_board_off", False)):
            return False

        new_board_is_off = (
            presence == F2_BOARD_PRESENCE_PRESENT
            and self._f2_auto_all_leds_off(states)
        )
        if not new_board_is_off:
            self._f2_auto_new_board_off_frames = 0
            return False

        self._f2_auto_new_board_off_frames = int(
            getattr(self, "_f2_auto_new_board_off_frames", 0) or 0
        ) + 1
        if (
            self._f2_auto_new_board_off_frames
            < F2_AUTO_NEW_BOARD_OFF_FRAMES_REQUIRED
        ):
            return False

        self._f2_auto_waiting_new_board_off = False
        self._f2_auto_new_board_off_frames = 0
        return True

    def _f2_auto_mark_cycle_inspected(self) -> None:
        """Trava o automático logo após qualquer inspeção F2 bem-sucedida."""
        marker = getattr(self, "_f2_auto_mark_inspected", None)
        if callable(marker):
            marker()
        else:
            self._f2_auto_cycle.mark_inspected()
            self._f2_auto_reference_empty_frames = 0
        self._f2_auto_waiting_new_board_off = False
        self._f2_auto_new_board_off_frames = 0

    def disparar_inspecao_operacao(self) -> None:
        """Mantém Enter livre, mas registra a placa como já analisada."""
        total_before = int(getattr(self, "operacao_total", 0) or 0)
        result = super().disparar_inspecao_operacao()
        successful = int(getattr(self, "operacao_total", 0) or 0) > total_before
        if self._f2_auto_enabled() and successful:
            self._f2_auto_mark_cycle_inspected()
        return result

    def _f2_auto_analyze_current_frame(self) -> bool:
        if not self._f2_auto_enabled():
            return False

        engine = getattr(self, "operacao_engine", None)
        frame = getattr(self, "camera_frame_atual", None)
        if (
            engine is None
            or not engine.ready
            or frame is None
            or getattr(frame, "size", 0) == 0
            or getattr(self, "operacao_processando", False)
            or not self._f2_auto_fresh_analysis_due()
        ):
            return False

        try:
            result = engine.analyze(frame)
        except Exception:
            return False

        states = estados_resultado_operacao(result)
        self._f2_auto_last_raw_states = states
        presence, _scores = self._f2_auto_presence(frame)
        self._f2_auto_last_presence = presence

        if not self._f2_auto_result_hold_active():
            was_waiting_removal = bool(self._f2_auto_cycle.waiting_removal)
            removed = self._f2_auto_observe_removal(frame, presence)
            if (
                was_waiting_removal
                and removed
                and presence == F2_BOARD_PRESENCE_EMPTY
            ):
                # O vazio confirma que a placa anterior saiu, mas ainda não
                # arma o gatilho. Primeiro precisamos ver a próxima placa
                # presente e completamente apagada.
                self._f2_auto_waiting_new_board_off = True
                self._f2_auto_new_board_off_frames = 0

            self._f2_auto_observe_new_board_off(states, presence)

        self._f2_auto_publish_states(states, presence)

        can_trigger = (
            self._f2_auto_can_trigger()
            and not bool(getattr(self, "_f2_auto_waiting_new_board_off", False))
        )
        if not self._f2_auto_cycle.should_trigger(
            states,
            can_trigger=can_trigger,
        ):
            return False

        total_before = int(getattr(self, "operacao_total", 0) or 0)
        self.disparar_inspecao_operacao()
        fired = int(getattr(self, "operacao_total", 0) or 0) > total_before
        if not fired:
            self._f2_auto_cycle.trigger_on_frames = 0
        return fired
