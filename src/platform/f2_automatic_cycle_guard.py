from __future__ import annotations

from dataclasses import dataclass

from src.core.segment_low_light import STATUS_ACESO
from src.platform.f2_automatic_analysis import estados_resultado_operacao


# Fallback quando o GPIO do JIG não está disponível. A análise roda a ~100 ms,
# então a ausência precisa permanecer estável por cerca de 1,2 s.
F2_AUTO_REMOVAL_OFF_FRAMES_REQUIRED = 12
F2_AUTO_TRIGGER_ON_FRAMES_REQUIRED = 2
F2_AUTO_GPIO_RELEASE_FRAMES_REQUIRED = 2

# Alias mantido para testes/código legado que importava o nome antigo.
F2_AUTO_REMOVAL_SCORE_REQUIRED = F2_AUTO_REMOVAL_OFF_FRAMES_REQUIRED


@dataclass
class F2AutomaticCycleState:
    """Controla entrada, inspeção e retirada de uma placa no F2 automático."""

    removal_score_required: int = F2_AUTO_REMOVAL_OFF_FRAMES_REQUIRED
    trigger_on_frames_required: int = F2_AUTO_TRIGGER_ON_FRAMES_REQUIRED
    gpio_release_frames_required: int = F2_AUTO_GPIO_RELEASE_FRAMES_REQUIRED
    waiting_removal: bool = False
    removal_score: int = 0
    trigger_on_frames: int = 0

    def __post_init__(self) -> None:
        self.removal_score_required = max(1, int(self.removal_score_required))
        self.trigger_on_frames_required = max(
            1,
            int(self.trigger_on_frames_required),
        )
        self.gpio_release_frames_required = max(
            1,
            int(self.gpio_release_frames_required),
        )

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
        self.trigger_on_frames = 0

    def mark_inspected(self) -> None:
        self.waiting_removal = True
        self.removal_score = 0
        self.trigger_on_frames = 0

    def _confirm_removal(self) -> bool:
        self.waiting_removal = False
        self.removal_score = 0
        self.trigger_on_frames = 0
        return True

    def observe_after_result(self, states: dict[str, str] | None) -> bool:
        """Fallback visual usado somente quando não existe GPIO confiável."""
        if not self.waiting_removal:
            return False

        if self.has_on(states):
            self.removal_score = 0
            return False

        self.removal_score += 1
        if self.removal_score < self.removal_score_required:
            return False

        return self._confirm_removal()

    def observe_physical_removal(self, board_present: bool) -> bool:
        """Usa o sensor físico do JIG como fonte autoritativa de retirada."""
        if not self.waiting_removal:
            return False

        if bool(board_present):
            self.removal_score = 0
            return False

        self.removal_score += 1
        if self.removal_score < self.gpio_release_frames_required:
            return False

        return self._confirm_removal()

    def should_trigger(
        self,
        states: dict[str, str] | None,
        can_trigger: bool,
    ) -> bool:
        if self.waiting_removal:
            self.trigger_on_frames = 0
            return False

        if not can_trigger:
            return False

        if not self.has_on(states):
            self.trigger_on_frames = 0
            return False

        # A entrada de placa precisa aparecer em dois frames novos. Um único
        # reflexo/transiente nunca equivale ao ENTER automático.
        self.trigger_on_frames += 1
        return self.trigger_on_frames >= self.trigger_on_frames_required

    def visible_states(self, states: dict[str, str] | None) -> dict[str, str]:
        """Suporte vazio fica neutro; placa luminosa mantém feedback das ROIs."""
        current = dict(states or {})
        if self.has_on(current):
            return current
        if self.waiting_removal and self.has_low_light(current):
            return current
        return {}


class F2AutomaticCycleGuardMixin:
    """Ciclo robusto e exclusivo da análise automática da Produção F2."""

    def __init__(self, *args, **kwargs) -> None:
        self._f2_auto_cycle = F2AutomaticCycleState()
        self._f2_auto_last_raw_states: dict[str, str] = {}
        self._f2_auto_gpio_presence_seen = False
        super().__init__(*args, **kwargs)

    def _f2_auto_reset_runtime(self) -> None:
        result = super()._f2_auto_reset_runtime()
        self._f2_auto_cycle.reset()
        self._f2_auto_last_raw_states = {}
        self._f2_auto_gpio_presence_seen = False
        return result

    def _f2_auto_publish_states(self, states: dict[str, str]) -> None:
        visible = self._f2_auto_cycle.visible_states(states)
        self._f2_auto_last_states = visible
        window = getattr(self, "operacao_window", None)
        setter = getattr(window, "set_live_roi_states", None)
        if callable(setter):
            setter(visible, enabled=True)

    def _f2_auto_result_hold_active(self) -> bool:
        """A tela OK/NG nunca conta como tempo de retirada da placa."""
        return getattr(self, "_operacao_resultado_after_id", None) is not None

    def _f2_auto_gpio_board_present(self) -> bool | None:
        """Retorna presença física do JIG ou None quando o GPIO não é confiável."""
        service = getattr(self, "gpio_trigger_service", None)
        if service is None or not bool(getattr(service, "available", False)):
            return None
        try:
            return bool(service.is_pressed)
        except Exception:
            return None

    def _f2_auto_mark_inspected(self) -> None:
        self._f2_auto_cycle.mark_inspected()
        self._f2_auto_gpio_presence_seen = (
            self._f2_auto_gpio_board_present() is True
        )

    def _f2_auto_observe_removal(self, states: dict[str, str]) -> bool:
        """GPIO é autoritativo; LEDs são apenas fallback sem sensor físico."""
        if not self._f2_auto_cycle.waiting_removal:
            return False

        board_present = self._f2_auto_gpio_board_present()
        if board_present is None:
            return self._f2_auto_cycle.observe_after_result(states)

        if board_present:
            self._f2_auto_gpio_presence_seen = True
            return self._f2_auto_cycle.observe_physical_removal(True)

        # Se o GPIO está disponível mas nunca vimos a placa pressionando o
        # sensor, não interpretamos "solto" como uma retirada. Isso evita que
        # um sensor fora de posição faça a mesma placa ser analisada em loop.
        if not self._f2_auto_gpio_presence_seen:
            self._f2_auto_cycle.removal_score = 0
            return False

        removed = self._f2_auto_cycle.observe_physical_removal(False)
        if removed:
            self._f2_auto_gpio_presence_seen = False
        return removed

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

        # Enquanto existe GPIO disponível no JIG, a retirada física é definida
        # pelo sensor do suporte, não por oscilações ACESO/APAGADO do classificador.
        # A tela OK/NG também nunca conta como tempo de retirada.
        if not self._f2_auto_result_hold_active():
            self._f2_auto_observe_removal(states)
        self._f2_auto_publish_states(states)

        if not self._f2_auto_cycle.should_trigger(
            states,
            can_trigger=self._f2_auto_can_trigger(),
        ):
            return False

        total_before = int(getattr(self, "operacao_total", 0) or 0)
        self.disparar_inspecao_operacao()
        disparou = int(getattr(self, "operacao_total", 0) or 0) > total_before
        if not disparou:
            # Se o disparo oficial recusou por alguma proteção transitória,
            # exige novamente dois frames ACESO em vez de martelar o callback.
            self._f2_auto_cycle.trigger_on_frames = 0
        return disparou

    def disparar_inspecao_operacao(self) -> None:
        """Qualquer inspeção válida inicia o gate de retirada, inclusive Enter/GPIO."""
        total_before = int(getattr(self, "operacao_total", 0) or 0)
        result = super().disparar_inspecao_operacao()
        if (
            self._f2_auto_enabled()
            and int(getattr(self, "operacao_total", 0) or 0) > total_before
        ):
            self._f2_auto_mark_inspected()
        return result
