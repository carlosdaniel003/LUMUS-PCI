from __future__ import annotations

from threading import RLock
from typing import Iterable

from src.infra.config_repository import ConfigRepository
from src.models.led_selection import LedSelection


_PATCH_REPOSITORIO_INSTALADO = False
MODOS_EDICAO_MASCARA = {
    "selecionar_leds_analise",
    "configurar_leds_fixos",
    "selecionar_leds_camera",
}


def copiar_mascara_absoluta(led: LedSelection) -> LedSelection:
    """Copia somente a geometria em pixels, descartando escalas normalizadas."""
    return LedSelection(
        id=str(led.id),
        centro_x=int(led.centro_x),
        centro_y=int(led.centro_y),
        raio=int(led.raio),
    )


def copiar_mascaras_absolutas(
    leds: Iterable[LedSelection] | None,
) -> list[LedSelection]:
    return [
        copiar_mascara_absoluta(led)
        for led in (leds or ())
    ]


def assinatura_geometria(
    leds: Iterable[LedSelection] | None,
) -> tuple[tuple[str, int, int, int], ...]:
    return tuple(
        (
            str(led.id),
            int(led.centro_x),
            int(led.centro_y),
            int(led.raio),
        )
        for led in (leds or ())
    )


def instalar_repositorio_mascaras_absolutas() -> None:
    """
    Faz o perfil Raspberry salvar e carregar somente coordenadas absolutas.

    O patch deve ser instalado depois do repositório de projetos, para que cada
    projeto continue independente. Os argumentos de resolução são aceitos por
    compatibilidade, mas deliberadamente ignorados.
    """
    global _PATCH_REPOSITORIO_INSTALADO

    if _PATCH_REPOSITORIO_INSTALADO:
        return

    salvar_original = ConfigRepository.salvar_leds_fixos
    carregar_original = ConfigRepository.carregar_leds_fixos

    def salvar_leds_fixos_absolutos(
        self: ConfigRepository,
        leds_fixos: list[LedSelection],
        largura_base: int | None = None,
        altura_base: int | None = None,
        projeto: str | None = None,
    ) -> dict:
        del largura_base, altura_base
        absolutos = copiar_mascaras_absolutas(leds_fixos)

        try:
            return salvar_original(
                self,
                absolutos,
                largura_base=None,
                altura_base=None,
                projeto=projeto,
            )
        except TypeError:
            return salvar_original(
                self,
                absolutos,
                largura_base=None,
                altura_base=None,
            )

    def carregar_leds_fixos_absolutos(
        self: ConfigRepository,
        projeto: str | None = None,
    ) -> list[LedSelection]:
        try:
            carregados = carregar_original(self, projeto=projeto)
        except TypeError:
            carregados = carregar_original(self)
        return copiar_mascaras_absolutas(carregados)

    ConfigRepository.salvar_leds_fixos = salvar_leds_fixos_absolutos
    ConfigRepository.carregar_leds_fixos = carregar_leds_fixos_absolutos
    _PATCH_REPOSITORIO_INSTALADO = True


class FixedMaskGeometryGuardMixin:
    """Impede qualquer transformação automática das máscaras de produção."""

    def __init__(self, *args, **kwargs) -> None:
        self._mask_guard_lock = RLock()
        self._mask_guard_project = ""
        self._mask_guard_snapshot: tuple[LedSelection, ...] = ()
        self._mask_guard_corrections = 0
        super().__init__(*args, **kwargs)
        self._mask_guard_capture(force=True)
        self._mask_guard_enforce()

    def _mask_guard_active_project(self) -> str:
        repository = getattr(self, "config_repository", None)
        obter_ativo = getattr(repository, "obter_projeto_led_ativo", None)
        if callable(obter_ativo):
            try:
                projeto = str(obter_ativo() or "").strip()
                if projeto:
                    return projeto
            except Exception:
                pass
        return "__DEFAULT__"

    def _mask_guard_read_repository(self) -> list[LedSelection]:
        repository = getattr(self, "config_repository", None)
        carregar = getattr(repository, "carregar_leds_fixos", None)
        if callable(carregar):
            try:
                return copiar_mascaras_absolutas(carregar() or ())
            except Exception:
                pass
        return copiar_mascaras_absolutas(
            getattr(self, "leds_fixos_configurados", ())
        )

    def _mask_guard_capture(
        self,
        force: bool = False,
        source: Iterable[LedSelection] | None = None,
        project: str | None = None,
    ) -> None:
        with self._mask_guard_lock:
            projeto = str(project or self._mask_guard_active_project())
            if not force and projeto == self._mask_guard_project:
                return

            mascaras = (
                copiar_mascaras_absolutas(source)
                if source is not None
                else self._mask_guard_read_repository()
            )
            self._mask_guard_project = projeto
            self._mask_guard_snapshot = tuple(mascaras)

    def _mask_guard_refresh_project(self) -> None:
        """Consulta o projeto somente em eventos de carga/produção, nunca por frame."""
        projeto = self._mask_guard_active_project()
        if projeto != self._mask_guard_project:
            self._mask_guard_capture(force=True, project=projeto)

    def _mask_guard_snapshot_copy(self) -> list[LedSelection]:
        return copiar_mascaras_absolutas(self._mask_guard_snapshot)

    def _mask_guard_editing(self) -> bool:
        return str(getattr(self, "modo_atual", "")) in MODOS_EDICAO_MASCARA

    def _mask_guard_enforce(self) -> list[LedSelection]:
        """Restaura a última geometria salva sem efetuar escala ou arredondamento."""
        with self._mask_guard_lock:
            if not self._mask_guard_project:
                self._mask_guard_capture(force=True)

            esperado = self._mask_guard_snapshot_copy()
            atual = getattr(self, "leds_fixos_configurados", ())
            if assinatura_geometria(atual) != assinatura_geometria(esperado):
                self._mask_guard_corrections += 1

            self.leds_fixos_configurados = copiar_mascaras_absolutas(esperado)
            self.operacao_leds_preview = copiar_mascaras_absolutas(esperado)

            selecao_manual = bool(
                getattr(self, "selecao_manual_camera_ativa", False)
            )
            guias_visiveis = bool(
                getattr(self, "guias_leds_fixos_visiveis", False)
            )
            if (
                not self._mask_guard_editing()
                and not selecao_manual
                and guias_visiveis
            ):
                self.leds_selecionados = copiar_mascaras_absolutas(esperado)

            return copiar_mascaras_absolutas(esperado)

    # O perfil usa câmera fixa em 1920x1080. Nenhuma resolução, transitória ou
    # reportada pelo driver, tem autorização para recalcular a geometria.
    def adaptar_leds_fixos_para_frame_camera(self, leds_fixos):
        del leds_fixos
        return self._mask_guard_enforce()

    def obter_leds_fixos_validos_para_imagem(self, leds_fixos):
        del leds_fixos
        return self._mask_guard_enforce()

    def _normalize_manual_masks(self, leds, reference_resolution):
        del reference_resolution
        return copiar_mascaras_absolutas(leds)

    def _synchronize_masks_with_current_frame(
        self,
        force: bool = False,
        schedule_operation_prepare: bool = True,
    ) -> None:
        del force, schedule_operation_prepare
        frame = getattr(self, "camera_frame_atual", None)
        if frame is not None and getattr(frame, "size", 0):
            altura, largura = frame.shape[:2]
            self.largura_original = int(largura)
            self.altura_original = int(altura)

        mascaras = self._mask_guard_enforce()
        janela = getattr(self, "operacao_window", None)
        if bool(getattr(self, "operacao_ativa", False)) and janela is not None:
            atualizar = getattr(janela, "update_preview", None)
            if callable(atualizar) and frame is not None:
                atualizar(frame, copiar_mascaras_absolutas(mascaras))

    def atualizar_frame_camera(self) -> None:
        super().atualizar_frame_camera()
        self._mask_guard_enforce()

    def salvar_leds_fixos(self) -> None:
        # Este é o único ponto que autoriza uma nova geometria permanente.
        super().salvar_leds_fixos()
        salvas = self._mask_guard_read_repository()
        self._mask_guard_capture(force=True, source=salvas)
        self._mask_guard_enforce()

    def carregar_leds_fixos(self) -> None:
        super().carregar_leds_fixos()
        self._mask_guard_capture(force=True)
        self._mask_guard_enforce()

    def carregar_configuracao(self) -> None:
        super().carregar_configuracao()
        self._mask_guard_capture(force=True)
        self._mask_guard_enforce()

    def salvar_configuracoes_sistema(self, *args, **kwargs) -> None:
        super().salvar_configuracoes_sistema(*args, **kwargs)
        self._mask_guard_enforce()

    def abrir_tela_operacao(self) -> None:
        self._mask_guard_refresh_project()
        self._mask_guard_enforce()
        super().abrir_tela_operacao()

    def preparar_tela_operacao(self) -> None:
        self._mask_guard_refresh_project()
        self._mask_guard_enforce()
        super().preparar_tela_operacao()
        self._mask_guard_enforce()

    def disparar_inspecao_operacao(self) -> None:
        self._mask_guard_refresh_project()
        self._mask_guard_enforce()
        super().disparar_inspecao_operacao()
