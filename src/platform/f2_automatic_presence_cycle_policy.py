from __future__ import annotations

from src.platform.f2_automatic_analysis import estados_resultado_operacao


class F2AutomaticPresenceCyclePolicyMixin:
    """Liga o disparo por LED ao rearme por retirada física da placa.

    A presença da placa não decide quando analisar: isso continua sendo
    determinado exclusivamente pelos LEDs (ao menos um ACESO). Depois de uma
    inspeção, porém, o ciclo permanece travado até o guard confirmar SUPORTE
    VAZIO. Assim, desligar e religar a mesma placa nunca cria uma nova análise
    automática.
    """

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

        # Presença tem uma única função no ciclo automático: confirmar que a
        # placa já analisada realmente saiu do suporte e liberar a próxima.
        if not self._f2_auto_result_hold_active():
            self._f2_auto_observe_removal(frame, presence)
        self._f2_auto_publish_states(states, presence)

        # O disparo continua dependendo somente da evidência funcional já
        # validada no F2: pelo menos um LED ACESO durante frames estáveis.
        # SUPORTE VAZIO/PRESENTE/AMBÍGUO não antecipam nem bloqueiam o gatilho;
        # enquanto waiting_removal=True, o próprio ciclo impede nova análise.
        if not self._f2_auto_cycle.should_trigger(
            states,
            can_trigger=self._f2_auto_can_trigger(),
        ):
            return False

        total_before = int(getattr(self, "operacao_total", 0) or 0)
        self.disparar_inspecao_operacao()
        fired = int(getattr(self, "operacao_total", 0) or 0) > total_before
        if not fired:
            self._f2_auto_cycle.trigger_on_frames = 0
        return fired
