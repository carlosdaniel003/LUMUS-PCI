from __future__ import annotations

from src.platform.fixed_mask_geometry_guard import copiar_mascaras_absolutas
from src.platform.led_project_repository import normalizar_resolucao_mestra


class ProjectMaskGeometryAnchorMixin:
    """Ancora as ROIs fixas na geometria canônica do projeto.

    A câmera pode iniciar em uma resolução provisória antes de o operador
    carregar um projeto. Essa resolução nunca pode virar a nova base das ROIs.
    Antes de qualquer sincronização por troca de resolução, esta camada relê a
    geometria persistida do projeto e a canonicaliza usando a resolução mestre
    do próprio projeto. A camada de sincronização recebe então uma fonte limpa,
    em vez de uma ROI que já tenha sido escalada para um frame anterior.

    Isso é especialmente importante para segmentos/polígonos livres: centro e
    raio possuem metadados normalizados, mas os vértices locais são geometria em
    pixels. Reusar uma cópia runtime já escalada acumula escala e produz ROI
    esticada/deslocada ao voltar para a resolução original.
    """

    def _project_mask_loaded_name(self) -> str:
        if hasattr(self, "_projeto_led_sessao_carregado"):
            return str(
                getattr(self, "_projeto_led_sessao_carregado", "") or ""
            ).strip()

        nome = str(getattr(self, "projeto_led_ativo", "") or "").strip()
        if nome:
            return nome

        repository = getattr(self, "config_repository", None)
        obter = getattr(repository, "obter_projeto_led_ativo", None)
        if callable(obter):
            try:
                return str(obter() or "").strip()
            except Exception:
                pass
        return ""

    def _project_mask_master_resolution(
        self,
        project: str | None = None,
    ) -> tuple[int, int] | None:
        nome = str(project or self._project_mask_loaded_name() or "").strip()
        if not nome:
            return None

        obter = getattr(self, "_obter_resolucao_mestra_projeto", None)
        if not callable(obter):
            return None
        try:
            resolucao = obter(nome)
        except TypeError:
            try:
                resolucao = obter(projeto=nome)
            except Exception:
                return None
        except Exception:
            return None
        return normalizar_resolucao_mestra(resolucao)

    def _project_mask_read_repository(
        self,
        project: str,
    ):
        repository = getattr(self, "config_repository", None)
        carregar = getattr(repository, "carregar_leds_fixos", None)
        if not callable(carregar):
            return []
        try:
            return copiar_mascaras_absolutas(
                carregar(projeto=project) or ()
            )
        except TypeError:
            try:
                return copiar_mascaras_absolutas(carregar() or ())
            except Exception:
                return []
        except Exception:
            return []

    def _mask_guard_capture(
        self,
        force: bool = False,
        source=None,
        project: str | None = None,
    ) -> None:
        """Canonicaliza projeto pela resolução mestre, nunca pelo frame provisório."""
        lock = getattr(self, "_mask_guard_lock", None)
        if lock is None:
            return super()._mask_guard_capture(
                force=force,
                source=source,
                project=project,
            )

        with lock:
            projeto = str(project or self._project_mask_loaded_name() or "").strip()

            # NeutralProjectStartupMixin mantém a sessão sem projeto no boot.
            # Nesse estado não capture silenciosamente o último projeto salvo.
            if (
                hasattr(self, "_projeto_led_sessao_carregado")
                and not projeto
                and source is None
            ):
                self._mask_guard_project = "__SESSION_EMPTY__"
                self._mask_guard_snapshot = ()
                return

            if not projeto:
                projeto = str(self._mask_guard_active_project())
            if not force and projeto == getattr(self, "_mask_guard_project", ""):
                return

            mascaras = (
                copiar_mascaras_absolutas(source)
                if source is not None
                else self._project_mask_read_repository(projeto)
            )
            if not mascaras and source is None:
                mascaras = copiar_mascaras_absolutas(
                    self._mask_guard_read_repository()
                )

            referencia = (
                self._project_mask_master_resolution(projeto)
                or self._mask_guard_current_resolution()
            )
            canonical = self._mask_guard_canonicalize(
                mascaras,
                referencia,
            )
            self._mask_guard_project = projeto
            self._mask_guard_snapshot = tuple(canonical)

    def _project_mask_anchor_before_resolution_sync(
        self,
        force: bool = False,
    ) -> None:
        project = self._project_mask_loaded_name()
        if not project:
            return

        editing = getattr(self, "_mask_guard_editing", None)
        if callable(editing) and editing():
            # Nunca substitua uma edição ainda não salva.
            return

        frame = getattr(self, "camera_frame_atual", None)
        frame_resolution = None
        if frame is not None and getattr(frame, "size", 0):
            height, width = frame.shape[:2]
            if width > 0 and height > 0:
                frame_resolution = (int(width), int(height))

        resolution_changed = (
            frame_resolution is not None
            and frame_resolution != getattr(self, "_mask_resolution_active", None)
        )
        project_changed = project != getattr(self, "_mask_guard_project", "")
        if not (force or resolution_changed or project_changed):
            return

        persisted = self._project_mask_read_repository(project)
        if not persisted:
            return

        self._mask_guard_capture(
            force=True,
            source=persisted,
            project=project,
        )
        snapshot = copiar_mascaras_absolutas(
            getattr(self, "_mask_guard_snapshot", ())
        )
        if snapshot:
            # ResolutionSynchronizedLedMasksMixin parte deste atributo. Forçar
            # a cópia canônica aqui impede escala acumulativa de um frame para
            # o próximo.
            self.leds_fixos_configurados = snapshot

    def _synchronize_masks_with_current_frame(
        self,
        force: bool = False,
        schedule_operation_prepare: bool = True,
    ) -> None:
        self._project_mask_anchor_before_resolution_sync(force=force)
        return super()._synchronize_masks_with_current_frame(
            force=force,
            schedule_operation_prepare=schedule_operation_prepare,
        )

    def adaptar_leds_fixos_para_frame_camera(self, leds_fixos):
        project = self._project_mask_loaded_name()
        editing = getattr(self, "_mask_guard_editing", None)
        editing_active = bool(callable(editing) and editing())

        if project and not editing_active:
            if project != getattr(self, "_mask_guard_project", ""):
                self._project_mask_anchor_before_resolution_sync(force=True)
            snapshot = copiar_mascaras_absolutas(
                getattr(self, "_mask_guard_snapshot", ())
            )
            if snapshot:
                leds_fixos = snapshot

        return super().adaptar_leds_fixos_para_frame_camera(leds_fixos)

    def carregar_leds_fixos(self) -> None:
        result = super().carregar_leds_fixos()

        project = self._project_mask_loaded_name()
        if project:
            persisted = self._project_mask_read_repository(project)
            if persisted:
                self._mask_guard_capture(
                    force=True,
                    source=persisted,
                    project=project,
                )
                enforce = getattr(self, "_mask_guard_enforce", None)
                if callable(enforce):
                    enforce()
        return result
