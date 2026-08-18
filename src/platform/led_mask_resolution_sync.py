from __future__ import annotations

from dataclasses import dataclass

from config import MIN_RADIUS_PX
from src.models.led_selection import LedSelection


@dataclass(frozen=True)
class LedMaskAdaptation:
    canonical_leds: tuple[LedSelection, ...]
    adapted_leds: tuple[LedSelection, ...]
    migrated_legacy: bool


def _copy_led(led: LedSelection) -> LedSelection:
    return LedSelection(
        id=str(led.id),
        centro_x=int(led.centro_x),
        centro_y=int(led.centro_y),
        raio=int(led.raio),
        centro_x_normalizado=led.centro_x_normalizado,
        centro_y_normalizado=led.centro_y_normalizado,
        raio_normalizado=led.raio_normalizado,
        largura_base=led.largura_base,
        altura_base=led.altura_base,
        tipo_roi=getattr(led, "tipo_roi", "circulo"),
        largura=getattr(led, "largura", None),
        altura=getattr(led, "altura", None),
        angulo=float(getattr(led, "angulo", 0.0) or 0.0),
        pontos_segmento_livre=(
            list(getattr(led, "pontos_segmento_livre", None) or ()) or None
        ),
    )


def canonicalize_led_mask(
    led: LedSelection,
    reference_width: int,
    reference_height: int,
) -> tuple[LedSelection, bool]:
    """Garante que a máscara tenha uma base independente da resolução atual."""
    if led.possui_coordenadas_normalizadas():
        return _copy_led(led), False

    base_width = max(1, int(led.largura_base or reference_width))
    base_height = max(1, int(led.altura_base or reference_height))
    canonical = _copy_led(led).com_normalizacao(
        largura_base=base_width,
        altura_base=base_height,
    )
    return canonical, True


def adapt_led_masks_to_resolution(
    leds: list[LedSelection] | tuple[LedSelection, ...],
    target_width: int,
    target_height: int,
    reference_width: int | None = None,
    reference_height: int | None = None,
    min_radius: int = MIN_RADIUS_PX,
    max_radius: int | None = None,
) -> LedMaskAdaptation:
    """Adapta máscaras sempre da geometria canônica, sem acumular escala.

    ``max_radius`` é opcional de propósito: MAX_RADIUS_PX pertence ao editor e
    não deve truncar uma máscara já salva quando o stream muda de resolução.
    Uma ROI também não é descartada por chegar perto da borda após uma troca de
    resolução; o frame/máscara final faz o recorte necessário.
    """
    target_width = max(1, int(target_width))
    target_height = max(1, int(target_height))
    reference_width = max(1, int(reference_width or target_width))
    reference_height = max(1, int(reference_height or target_height))
    radius_limit = (
        max(target_width, target_height)
        if max_radius is None
        else max(1, int(max_radius))
    )

    canonical_leds: list[LedSelection] = []
    adapted_leds: list[LedSelection] = []
    migrated_legacy = False

    for led in leds:
        canonical, migrated = canonicalize_led_mask(
            led,
            reference_width=reference_width,
            reference_height=reference_height,
        )
        adapted = canonical.adaptar_para_resolucao(
            largura_destino=target_width,
            altura_destino=target_height,
            raio_minimo=min_radius,
            raio_maximo=radius_limit,
        )

        canonical_leds.append(canonical)
        adapted_leds.append(adapted)
        migrated_legacy = migrated_legacy or migrated

    return LedMaskAdaptation(
        canonical_leds=tuple(canonical_leds),
        adapted_leds=tuple(adapted_leds),
        migrated_legacy=bool(migrated_legacy),
    )


class ResolutionSynchronizedLedMasksMixin:
    """Mantém as máscaras na mesma posição relativa em qualquer resolução."""

    def __init__(self, *args, **kwargs) -> None:
        self._mask_resolution_active: tuple[int, int] | None = None
        self._mask_legacy_migrated_projects: set[str] = set()
        self._mask_resolution_syncing = False
        super().__init__(*args, **kwargs)

    @staticmethod
    def _frame_resolution(frame) -> tuple[int, int] | None:
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        height, width = frame.shape[:2]
        if width <= 0 or height <= 0:
            return None
        return int(width), int(height)

    def _active_mask_project(self) -> tuple[str, object | None]:
        repository = getattr(self, "config_repository", None)
        project = "__DEFAULT__"
        get_active = getattr(repository, "obter_projeto_led_ativo", None)
        if callable(get_active):
            try:
                active = str(get_active() or "").strip()
                if active:
                    project = active
            except Exception:
                pass
        return project, repository

    def _persist_migrated_masks(
        self,
        canonical_leds: tuple[LedSelection, ...],
    ) -> None:
        if not canonical_leds:
            return

        project, repository = self._active_mask_project()
        if project in self._mask_legacy_migrated_projects:
            return

        save = getattr(repository, "salvar_leds_fixos", None)
        if not callable(save):
            return

        try:
            if project != "__DEFAULT__":
                save(list(canonical_leds), projeto=project)
            else:
                save(list(canonical_leds))
        except TypeError:
            try:
                save(list(canonical_leds))
            except Exception:
                return
        except Exception:
            return

        self._mask_legacy_migrated_projects.add(project)

    def _adapt_masks(
        self,
        leds,
        target_width: int,
        target_height: int,
        reference_resolution: tuple[int, int] | None = None,
        persist_legacy: bool = False,
    ) -> list[LedSelection]:
        reference_width, reference_height = (
            reference_resolution
            if reference_resolution is not None
            else (target_width, target_height)
        )
        adaptation = adapt_led_masks_to_resolution(
            leds=tuple(leds or ()),
            target_width=target_width,
            target_height=target_height,
            reference_width=reference_width,
            reference_height=reference_height,
        )

        if persist_legacy and adaptation.migrated_legacy:
            self._persist_migrated_masks(adaptation.canonical_leds)
            self.leds_fixos_configurados = list(adaptation.canonical_leds)

        return list(adaptation.adapted_leds)

    def adaptar_leds_fixos_para_frame_camera(self, leds_fixos):
        width = int(getattr(self, "largura_original", 0) or 0)
        height = int(getattr(self, "altura_original", 0) or 0)
        if width <= 0 or height <= 0:
            return []

        previous = self._mask_resolution_active or (width, height)
        return self._adapt_masks(
            leds=leds_fixos,
            target_width=width,
            target_height=height,
            reference_resolution=previous,
            persist_legacy=True,
        )

    def obter_leds_fixos_validos_para_imagem(self, leds_fixos):
        return self.adaptar_leds_fixos_para_frame_camera(leds_fixos)

    def _normalize_manual_masks(
        self,
        leds,
        reference_resolution: tuple[int, int],
    ) -> list[LedSelection]:
        width, height = reference_resolution
        adaptation = adapt_led_masks_to_resolution(
            leds=tuple(leds or ()),
            target_width=width,
            target_height=height,
            reference_width=width,
            reference_height=height,
        )
        return list(adaptation.adapted_leds)

    def _synchronize_masks_with_current_frame(
        self,
        force: bool = False,
        schedule_operation_prepare: bool = True,
    ) -> None:
        if self._mask_resolution_syncing:
            return

        frame = getattr(self, "camera_frame_atual", None)
        resolution = self._frame_resolution(frame)
        if resolution is None:
            return
        if not force and resolution == self._mask_resolution_active:
            return

        self._mask_resolution_syncing = True
        try:
            previous_resolution = self._mask_resolution_active or resolution
            width, height = resolution
            self._mask_resolution_active = resolution
            self.largura_original = width
            self.altura_original = height

            fixed = list(getattr(self, "leds_fixos_configurados", []) or [])
            if not fixed:
                repository = getattr(self, "config_repository", None)
                load = getattr(repository, "carregar_leds_fixos", None)
                if callable(load):
                    try:
                        fixed = list(load() or [])
                    except Exception:
                        fixed = []

            adapted_fixed = self._adapt_masks(
                leds=fixed,
                target_width=width,
                target_height=height,
                reference_resolution=previous_resolution,
                persist_legacy=True,
            )

            manual = list(getattr(self, "leds_manuais_camera", []) or [])
            adapted_manual = self._adapt_masks(
                leds=manual,
                target_width=width,
                target_height=height,
                reference_resolution=previous_resolution,
                persist_legacy=False,
            )
            self.leds_manuais_camera = adapted_manual

            manual_active = bool(
                getattr(self, "selecao_manual_camera_ativa", False)
            )
            fixed_visible = bool(
                getattr(self, "guias_leds_fixos_visiveis", False)
            )
            if manual_active or (manual and not fixed_visible):
                self.leds_selecionados = adapted_manual
            elif fixed_visible:
                self.leds_selecionados = adapted_fixed

            self.operacao_leds_preview = adapted_fixed

            operation_engine = getattr(self, "operacao_engine", None)
            engine_resolution = (
                int(getattr(operation_engine, "_frame_width", 0) or 0),
                int(getattr(operation_engine, "_frame_height", 0) or 0),
            )
            if engine_resolution not in ((0, 0), resolution):
                invalidate = getattr(operation_engine, "invalidate", None)
                if callable(invalidate):
                    invalidate()

            operation_active = bool(getattr(self, "operacao_ativa", False))
            operation_window = getattr(self, "operacao_window", None)
            if operation_active and operation_window is not None:
                update_preview = getattr(operation_window, "update_preview", None)
                if callable(update_preview):
                    update_preview(frame, adapted_fixed)

                if (
                    schedule_operation_prepare
                    and not bool(getattr(self, "operacao_processando", False))
                ):
                    pending_id = getattr(
                        self,
                        "_operacao_preparo_after_id",
                        None,
                    )
                    if pending_id is not None:
                        try:
                            self.root.after_cancel(pending_id)
                        except Exception:
                            pass
                        self._operacao_preparo_after_id = None
                    schedule = getattr(self, "_agendar_preparo_operacao", None)
                    if callable(schedule):
                        schedule(20)

            if not operation_active:
                view = getattr(self, "view", None)
                draw = getattr(view, "desenhar_canvas", None)
                if callable(draw) and getattr(self, "imagem_original", None) is not None:
                    draw(
                        getattr(self, "leds_selecionados", []),
                        getattr(self, "resultados_led_atual", []),
                    )
        finally:
            self._mask_resolution_syncing = False

    def atualizar_frame_camera(self) -> None:
        super().atualizar_frame_camera()
        self._synchronize_masks_with_current_frame()

    def preparar_tela_operacao(self) -> None:
        self._synchronize_masks_with_current_frame(
            force=True,
            schedule_operation_prepare=False,
        )
        super().preparar_tela_operacao()

    def disparar_inspecao_operacao(self) -> None:
        self._synchronize_masks_with_current_frame(
            force=True,
            schedule_operation_prepare=False,
        )
        super().disparar_inspecao_operacao()

    def selecionar_led_para_analise(self, canvas_x: int, canvas_y: int) -> None:
        super().selecionar_led_para_analise(canvas_x, canvas_y)
        if not bool(getattr(self, "camera_ativa", False)):
            return

        resolution = self._frame_resolution(
            getattr(self, "camera_frame_atual", None)
        )
        if resolution is None:
            return

        self.leds_manuais_camera = self._normalize_manual_masks(
            getattr(self, "leds_manuais_camera", []),
            resolution,
        )
        if bool(getattr(self, "selecao_manual_camera_ativa", False)):
            self.leds_selecionados = list(self.leds_manuais_camera)
