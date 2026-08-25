from __future__ import annotations

from dataclasses import dataclass

from src.core.segment_low_light import STATUS_ACESO
from src.platform.f2_automatic_analysis import estados_resultado_operacao


F2_AUTO_REMOVAL_SCORE_REQUIRED = 5
F2_AUTO_REMOVAL_ON_PENALTY = 2


@dataclass
class F2AutomaticCycleState:
    """Controla presença, inspeção e retirada sem depender de um frame perfeito."""

    removal_score_required: int = F2_AUTO_REMOVAL_SCORE_REQUIRED
    on_penalty: int = F2_AUTO_REMOVAL_ON_PENALTY
    waiting_removal: bool = False
    removal_score: int = 0

    def __post_init__(self) -> None:
        self.removal_score_required = max(1, int(self.removal_score_required))
        self.on_penalty = max(1, int(self.on_penalty))

    @staticmethod
    def has_on(states: dict[str, str] | None) -> bool:
        return any(
            str(status).strip().upper() == STATUS_ACESO
            for status in dict(states or {}).values()
        )

    @staticmethod
    def has_low_light(states: dict[str, str] | None) -> bool:
        return any(
            str(status).strip().upper() in {"POUCA_LUZ", "POUCA LUZ"}
            for status in dict(states or {}).values()
        )

    def reset(self) -> None:
        self.waiting_removal = False
        self.removal_score = 0

    def mark_inspected(self) -> None:
        self.waiting_removal = True
        self.removal_score = 0

    def observe_after_result(self, states: dict[str, str] | None) -> bool:
        """Retorna True somente quando a retirada da placa foi confirmada."""
        if not self.waiting_removal:
            return False

        if self.has_on(states):
            # Um reflexo ou oscilação isolada não deve apagar todo o progresso,
            # mas uma placa ainda presente e continuamente acesa impede o rearme.
            self.removal_score = max(0, self.removal_score - self.on_penalty)
            return False

        self.removal_score += 1
        if self.removal_score < self.removal_score_required:
            return False

        self.waiting_removal = False
        self.removal_score = 0
        return True

    def should_trigger(
        self,
        states: dict[str, str] | None,
        can_trigger: bool,
    ) -> bool:
        return bool(
            not self.waiting_removal
            and can_trigger
            and self.has_on(states)
        )

    def visible_states(self, states: dict[str, str] | None) -> dict[str, str]:
        """Suporte vazio fica neutro; placa luminosa mantém feedback das ROIs."""
        current = dict(states or {})
        if self.has_on(current) or self.has_low_light(current):
            return current
        return {}


class F2AutomaticCycleGuardMixin:
    """Ciclo robusto e exclusivo da análise automática da Produção F2."""

    def __init__(self, *args, **kwargs) -> None:
        self._f2_auto_cycle = F2AutomaticCycleState()
        self._f2_auto_last_raw_states: dict[str, str] = {}
        super().__init__(*args, **kwargs)

    def _f2_auto_reset_runtime(self) -> None:
        result = super()._f2_auto_reset_runtime()
        self._f2_auto_cycle.reset()
        self._f2_auto_last_raw_states = {}
        return result

    def _f2_auto_publish_states(self, states: dict[str, str]) -> None:
        visible = self._f2_auto_cycle.visible_states(states)
        self._f2_auto_last_states = visible
        window = getattr(self, "operacao_window", None)
        setter = getattr(window, "set_live_roi_states", None)
        if callable(setter):
            setter(visible, enabled=True)

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

        # A retirada é avaliada antes da publicação visual. Assim que o frame
        # deixa de ter ACESO, o suporte já fica neutro em vez de permanecer
        # vermelho enquanto o debounce confirma a saída da placa.
        self._f2_auto_cycle.observe_after_result(states)
        self._f2_auto_publish_states(states)

        if not self._f2_auto_cycle.should_trigger(
            states,
            can_trigger=self._f2_auto_can_trigger(),
        ):
            return False

        total_before = int(getattr(self, "operacao_total", 0) or 0)
        self.disparar_inspecao_operacao()
        return int(getattr(self, "operacao_total", 0) or 0) > total_before

    def disparar_inspecao_operacao(self) -> None:
        """Qualquer inspeção válida inicia o gate de retirada, inclusive Enter/GPIO."""
        total_before = int(getattr(self, "operacao_total", 0) or 0)
        result = super().disparar_inspecao_operacao()
        if (
            self._f2_auto_enabled()
            and int(getattr(self, "operacao_total", 0) or 0) > total_before
        ):
            self._f2_auto_cycle.mark_inspected()
        return result
