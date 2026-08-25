from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from src.core.segment_low_light import STATUS_ACESO
from src.platform.f2_automatic_analysis import estados_resultado_operacao


F2_AUTO_TRIGGER_ON_FRAMES_REQUIRED = 2

# A mesma placa fica travada até a câmera enxergar uma mudança estrutural real
# fora das ROIs dos LEDs. Na primeira retirada da sessão, o ODIN aprende como é
# o suporte vazio; nas retiradas seguintes, compara diretamente com essa cena.
F2_AUTO_VISUAL_FIRST_REMOVAL_FRAMES_REQUIRED = 8
F2_AUTO_VISUAL_KNOWN_EMPTY_FRAMES_REQUIRED = 4
F2_AUTO_VISUAL_CHANGE_PIXEL_THRESHOLD = 24
F2_AUTO_VISUAL_CHANGE_FRACTION_REQUIRED = 0.18
F2_AUTO_VISUAL_CHANGE_MEAN_REQUIRED = 12.0
F2_AUTO_VISUAL_STABLE_PIXEL_THRESHOLD = 12
F2_AUTO_VISUAL_STABLE_FRACTION_MAX = 0.08
F2_AUTO_VISUAL_STABLE_MEAN_MAX = 6.0
F2_AUTO_VISUAL_EMPTY_FRACTION_MAX = 0.10
F2_AUTO_VISUAL_EMPTY_MEAN_MAX = 10.0
F2_AUTO_VISUAL_MIN_VALID_PIXELS = 8000
F2_AUTO_VISUAL_ROI_PADDING_PX = 10
F2_AUTO_VISUAL_ZONE_MARGIN_PX = 40

# Alias preservado apenas para código legado que ainda importe o nome antigo.
F2_AUTO_REMOVAL_SCORE_REQUIRED = F2_AUTO_VISUAL_FIRST_REMOVAL_FRAMES_REQUIRED


@dataclass
class F2AutomaticCycleState:
    """Controla entrada, inspeção e liberação de uma placa no F2 automático."""

    trigger_on_frames_required: int = F2_AUTO_TRIGGER_ON_FRAMES_REQUIRED
    waiting_removal: bool = False
    trigger_on_frames: int = 0

    def __post_init__(self) -> None:
        self.trigger_on_frames_required = max(
            1,
            int(self.trigger_on_frames_required),
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
        self.trigger_on_frames = 0

    def mark_inspected(self) -> None:
        self.waiting_removal = True
        self.trigger_on_frames = 0

    def confirm_removal(self) -> bool:
        if not self.waiting_removal:
            return False
        self.waiting_removal = False
        self.trigger_on_frames = 0
        return True

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


class F2VisualBoardRemovalDetector:
    """Detecta retirada física pela cena da câmera, ignorando as áreas dos LEDs.

    Estratégia:
    1. Ao inspecionar, salva uma referência visual da placa atual.
    2. Compara somente a região ao redor da placa e exclui as ROIs dos LEDs.
    3. A primeira retirada exige uma cena bem diferente e estável por vários
       frames; essa cena passa a ser a referência do suporte vazio.
    4. Depois disso, retirar significa voltar de forma estável à referência do
       suporte vazio. Oscilações ACESO/APAGADO não participam do rearme.
    """

    def __init__(
        self,
        first_removal_frames_required: int = (
            F2_AUTO_VISUAL_FIRST_REMOVAL_FRAMES_REQUIRED
        ),
        known_empty_frames_required: int = (
            F2_AUTO_VISUAL_KNOWN_EMPTY_FRAMES_REQUIRED
        ),
    ) -> None:
        self.first_removal_frames_required = max(
            1,
            int(first_removal_frames_required),
        )
        self.known_empty_frames_required = max(
            1,
            int(known_empty_frames_required),
        )
        self.empty_reference: np.ndarray | None = None
        self.board_reference: np.ndarray | None = None
        self.previous_frame: np.ndarray | None = None
        self.valid_mask: np.ndarray | None = None
        self.confirmation_frames = 0

    def reset(self) -> None:
        self.empty_reference = None
        self.board_reference = None
        self.previous_frame = None
        self.valid_mask = None
        self.confirmation_frames = 0

    @staticmethod
    def _prepare_frame(frame) -> np.ndarray | None:
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        try:
            if len(frame.shape) == 2:
                gray = frame
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return cv2.GaussianBlur(gray, (5, 5), 0)
        except Exception:
            return None

    @staticmethod
    def _led_bounds(led) -> tuple[int, int, int, int] | None:
        try:
            cx = int(getattr(led, "centro_x"))
            cy = int(getattr(led, "centro_y"))
            raio = max(1, int(getattr(led, "raio", 1) or 1))
        except Exception:
            return None

        largura = getattr(led, "largura", None)
        altura = getattr(led, "altura", None)
        try:
            half_w = max(raio, int(round(float(largura or 0) / 2.0)))
        except Exception:
            half_w = raio
        try:
            half_h = max(raio, int(round(float(altura or 0) / 2.0)))
        except Exception:
            half_h = raio

        pontos = getattr(led, "pontos_segmento_livre", None)
        if pontos:
            try:
                half_w = max(
                    half_w,
                    int(round(max(abs(float(x)) for x, _y in pontos))),
                )
                half_h = max(
                    half_h,
                    int(round(max(abs(float(y)) for _x, y in pontos))),
                )
            except Exception:
                pass

        return (
            cx - half_w,
            cy - half_h,
            cx + half_w,
            cy + half_h,
        )

    @classmethod
    def _build_valid_mask(cls, shape, leds) -> np.ndarray:
        height, width = int(shape[0]), int(shape[1])
        mask = np.zeros((height, width), dtype=np.uint8)
        bounds = [cls._led_bounds(led) for led in tuple(leds or ())]
        bounds = [item for item in bounds if item is not None]

        if bounds:
            min_x = min(item[0] for item in bounds)
            min_y = min(item[1] for item in bounds)
            max_x = max(item[2] for item in bounds)
            max_y = max(item[3] for item in bounds)
            span_x = max(1, max_x - min_x)
            span_y = max(1, max_y - min_y)
            margin_x = max(
                F2_AUTO_VISUAL_ZONE_MARGIN_PX,
                int(round(span_x * 0.18)),
            )
            margin_y = max(
                F2_AUTO_VISUAL_ZONE_MARGIN_PX,
                int(round(span_y * 0.18)),
            )
            x1 = max(0, min_x - margin_x)
            y1 = max(0, min_y - margin_y)
            x2 = min(width - 1, max_x + margin_x)
            y2 = min(height - 1, max_y + margin_y)
        else:
            x1 = int(round(width * 0.08))
            y1 = int(round(height * 0.08))
            x2 = int(round(width * 0.92))
            y2 = int(round(height * 0.92))

        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, thickness=-1)

        # Exclui generosamente as próprias ROIs para que ligar/desligar LEDs não
        # pareça retirada física da placa.
        for led in tuple(leds or ()):
            item = cls._led_bounds(led)
            if item is None:
                continue
            left, top, right, bottom = item
            left = max(0, left - F2_AUTO_VISUAL_ROI_PADDING_PX)
            top = max(0, top - F2_AUTO_VISUAL_ROI_PADDING_PX)
            right = min(width - 1, right + F2_AUTO_VISUAL_ROI_PADDING_PX)
            bottom = min(height - 1, bottom + F2_AUTO_VISUAL_ROI_PADDING_PX)
            cv2.rectangle(
                mask,
                (left, top),
                (right, bottom),
                0,
                thickness=-1,
            )

        if int(cv2.countNonZero(mask)) >= F2_AUTO_VISUAL_MIN_VALID_PIXELS:
            return mask

        # Fallback conservador se as ROIs ocuparem quase toda a área calculada.
        mask.fill(0)
        cv2.rectangle(
            mask,
            (int(width * 0.05), int(height * 0.05)),
            (int(width * 0.95), int(height * 0.95)),
            255,
            thickness=-1,
        )
        for led in tuple(leds or ()):
            item = cls._led_bounds(led)
            if item is None:
                continue
            left, top, right, bottom = item
            cv2.rectangle(
                mask,
                (
                    max(0, left - F2_AUTO_VISUAL_ROI_PADDING_PX),
                    max(0, top - F2_AUTO_VISUAL_ROI_PADDING_PX),
                ),
                (
                    min(width - 1, right + F2_AUTO_VISUAL_ROI_PADDING_PX),
                    min(height - 1, bottom + F2_AUTO_VISUAL_ROI_PADDING_PX),
                ),
                0,
                thickness=-1,
            )
        return mask

    @staticmethod
    def _difference_metrics(
        current: np.ndarray,
        reference: np.ndarray,
        mask: np.ndarray,
        pixel_threshold: int,
    ) -> tuple[float, float]:
        if current.shape != reference.shape or current.shape != mask.shape:
            return 1.0, 255.0
        valid = mask > 0
        valid_count = int(np.count_nonzero(valid))
        if valid_count < F2_AUTO_VISUAL_MIN_VALID_PIXELS:
            return 1.0, 255.0

        diff = cv2.absdiff(current, reference)
        values = diff[valid]
        changed_fraction = float(
            np.count_nonzero(values >= int(pixel_threshold)) / valid_count
        )
        mean_diff = float(np.mean(values)) if values.size else 255.0
        return changed_fraction, mean_diff

    def capture_board(self, frame, leds) -> bool:
        prepared = self._prepare_frame(frame)
        if prepared is None:
            self.board_reference = None
            self.previous_frame = None
            self.valid_mask = None
            self.confirmation_frames = 0
            return False

        self.board_reference = prepared.copy()
        self.previous_frame = prepared.copy()
        self.valid_mask = self._build_valid_mask(prepared.shape, leds)
        self.confirmation_frames = 0
        return int(cv2.countNonZero(self.valid_mask)) >= (
            F2_AUTO_VISUAL_MIN_VALID_PIXELS
        )

    def _observe_against_known_empty(self, current: np.ndarray) -> bool:
        if self.empty_reference is None or self.valid_mask is None:
            return False
        fraction, mean_diff = self._difference_metrics(
            current,
            self.empty_reference,
            self.valid_mask,
            F2_AUTO_VISUAL_CHANGE_PIXEL_THRESHOLD,
        )
        looks_empty = (
            fraction <= F2_AUTO_VISUAL_EMPTY_FRACTION_MAX
            and mean_diff <= F2_AUTO_VISUAL_EMPTY_MEAN_MAX
        )
        self.confirmation_frames = (
            self.confirmation_frames + 1 if looks_empty else 0
        )
        return self.confirmation_frames >= self.known_empty_frames_required

    def _observe_first_removal(self, current: np.ndarray) -> bool:
        if (
            self.board_reference is None
            or self.previous_frame is None
            or self.valid_mask is None
        ):
            return False

        changed_fraction, changed_mean = self._difference_metrics(
            current,
            self.board_reference,
            self.valid_mask,
            F2_AUTO_VISUAL_CHANGE_PIXEL_THRESHOLD,
        )
        stable_fraction, stable_mean = self._difference_metrics(
            current,
            self.previous_frame,
            self.valid_mask,
            F2_AUTO_VISUAL_STABLE_PIXEL_THRESHOLD,
        )
        self.previous_frame = current.copy()

        scene_left_board = (
            changed_fraction >= F2_AUTO_VISUAL_CHANGE_FRACTION_REQUIRED
            and changed_mean >= F2_AUTO_VISUAL_CHANGE_MEAN_REQUIRED
        )
        scene_is_stable = (
            stable_fraction <= F2_AUTO_VISUAL_STABLE_FRACTION_MAX
            and stable_mean <= F2_AUTO_VISUAL_STABLE_MEAN_MAX
        )

        if scene_left_board and scene_is_stable:
            self.confirmation_frames += 1
        else:
            self.confirmation_frames = 0

        if self.confirmation_frames < self.first_removal_frames_required:
            return False

        # Primeira retirada confirmada: a cena estável e sem a placa passa a ser
        # a referência visual do suporte vazio para o restante da sessão F2.
        self.empty_reference = current.copy()
        return True

    def observe_removal(self, frame) -> bool:
        current = self._prepare_frame(frame)
        if (
            current is None
            or self.board_reference is None
            or self.valid_mask is None
            or current.shape != self.board_reference.shape
        ):
            self.confirmation_frames = 0
            return False

        if self.empty_reference is not None:
            removed = self._observe_against_known_empty(current)
        else:
            removed = self._observe_first_removal(current)

        if not removed:
            return False

        self.board_reference = None
        self.previous_frame = None
        self.confirmation_frames = 0
        return True


class F2AutomaticCycleGuardMixin:
    """Ciclo visual robusto e exclusivo da análise automática da Produção F2."""

    def __init__(self, *args, **kwargs) -> None:
        self._f2_auto_cycle = F2AutomaticCycleState()
        self._f2_auto_visual_removal = F2VisualBoardRemovalDetector()
        self._f2_auto_last_raw_states: dict[str, str] = {}
        super().__init__(*args, **kwargs)

    def _f2_auto_reset_runtime(self) -> None:
        result = super()._f2_auto_reset_runtime()
        self._f2_auto_cycle.reset()
        self._f2_auto_visual_removal.reset()
        self._f2_auto_last_raw_states = {}
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

    def _f2_auto_mark_inspected(self) -> None:
        self._f2_auto_cycle.mark_inspected()
        self._f2_auto_visual_removal.capture_board(
            getattr(self, "camera_frame_atual", None),
            getattr(self, "operacao_leds_preview", ()),
        )

    def _f2_auto_observe_removal(self) -> bool:
        if not self._f2_auto_cycle.waiting_removal:
            return False
        removed = self._f2_auto_visual_removal.observe_removal(
            getattr(self, "camera_frame_atual", None)
        )
        if not removed:
            return False
        return self._f2_auto_cycle.confirm_removal()

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

        # O rearme é visual e usa somente a estrutura da cena fora das ROIs.
        # Oscilações ACESO/APAGADO não conseguem liberar a mesma placa.
        if not self._f2_auto_result_hold_active():
            self._f2_auto_observe_removal()
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
        """Qualquer inspeção válida inicia o gate visual de retirada."""
        total_before = int(getattr(self, "operacao_total", 0) or 0)
        result = super().disparar_inspecao_operacao()
        if (
            self._f2_auto_enabled()
            and int(getattr(self, "operacao_total", 0) or 0) > total_before
        ):
            self._f2_auto_mark_inspected()
        return result
