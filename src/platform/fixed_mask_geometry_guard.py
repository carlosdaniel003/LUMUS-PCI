from __future__ import annotations

from threading import RLock
from typing import Iterable

from config import MIN_RADIUS_PX
from src.core.roi_geometry import TIPO_ROI_SEGMENTO, normalizar_tipo_roi
from src.infra.config_repository import ConfigRepository
from src.models.led_selection import LedSelection


_PATCH_REPOSITORIO_INSTALADO = False
MODOS_EDICAO_MASCARA = {
    "selecionar_leds_analise",
    "configurar_leds_fixos",
    "selecionar_leds_camera",
}


def copiar_mascara_absoluta(led: LedSelection) -> LedSelection:
    """Copia a geometria completa.

    O nome é mantido por compatibilidade histórica. Diferente do guard antigo,
    a cópia preserva também a resolução base e as coordenadas normalizadas;
    esses metadados são o que impede deslocamento quando o stream muda de
    resolução.
    """
    return LedSelection(
        id=str(led.id),
        centro_x=int(led.centro_x),
        centro_y=int(led.centro_y),
        raio=int(led.raio),
        centro_x_normalizado=getattr(led, "centro_x_normalizado", None),
        centro_y_normalizado=getattr(led, "centro_y_normalizado", None),
        raio_normalizado=getattr(led, "raio_normalizado", None),
        largura_base=getattr(led, "largura_base", None),
        altura_base=getattr(led, "altura_base", None),
        tipo_roi=getattr(led, "tipo_roi", "circulo"),
        largura=getattr(led, "largura", None),
        altura=getattr(led, "altura", None),
        angulo=float(getattr(led, "angulo", 0.0) or 0.0),
        pontos_segmento_livre=(
            list(getattr(led, "pontos_segmento_livre", None) or ()) or None
        ),
    )


def copiar_mascaras_absolutas(
    leds: Iterable[LedSelection] | None,
) -> list[LedSelection]:
    return [copiar_mascara_absoluta(led) for led in (leds or ())]


def assinatura_geometria(
    leds: Iterable[LedSelection] | None,
) -> tuple[tuple, ...]:
    """Assinatura em pixels usada apenas para detectar mutações indevidas."""
    assinatura = []
    for led in leds or ():
        tipo = normalizar_tipo_roi(getattr(led, "tipo_roi", None))
        if tipo == TIPO_ROI_SEGMENTO:
            pontos = tuple(
                (round(float(x), 4), round(float(y), 4))
                for x, y in (
                    getattr(led, "pontos_segmento_livre", None) or ()
                )
            )
            assinatura.append(
                (
                    str(led.id),
                    TIPO_ROI_SEGMENTO,
                    int(led.centro_x),
                    int(led.centro_y),
                    int(led.raio),
                    None if getattr(led, "largura", None) is None else int(led.largura),
                    None if getattr(led, "altura", None) is None else int(led.altura),
                    round(float(getattr(led, "angulo", 0.0) or 0.0), 6),
                    pontos,
                )
            )
        else:
            assinatura.append(
                (
                    str(led.id),
                    int(led.centro_x),
                    int(led.centro_y),
                    int(led.raio),
                )
            )
    return tuple(assinatura)


def instalar_repositorio_mascaras_absolutas() -> None:
    """Preserva a geometria canônica no repositório.

    O nome do instalador é legado. Antes ele removia os metadados normalizados e
    fixava as máscaras em pixels. Agora mantém esses metadados e, quando recebe
    a resolução base do editor, normaliza antes de salvar.
    """
    global _PATCH_REPOSITORIO_INSTALADO
    if _PATCH_REPOSITORIO_INSTALADO:
        return

    salvar_original = ConfigRepository.salvar_leds_fixos
    carregar_original = ConfigRepository.carregar_leds_fixos

    def salvar_leds_fixos_resolucao_segura(
        self: ConfigRepository,
        leds_fixos: list[LedSelection],
        largura_base: int | None = None,
        altura_base: int | None = None,
        projeto: str | None = None,
    ) -> dict:
        preparados = []
        for led in leds_fixos or ():
            copia = copiar_mascara_absoluta(led)
            if largura_base and altura_base:
                copia = copia.com_normalizacao(
                    largura_base=int(largura_base),
                    altura_base=int(altura_base),
                )
            preparados.append(copia)

        # Não pedimos ao wrapper inferior para normalizar novamente. A lista já
        # contém exatamente a base canônica que deve ser persistida.
        try:
            return salvar_original(
                self,
                preparados,
                largura_base=None,
                altura_base=None,
                projeto=projeto,
            )
        except TypeError:
            return salvar_original(
                self,
                preparados,
                largura_base=None,
                altura_base=None,
            )

    def carregar_leds_fixos_resolucao_segura(
        self: ConfigRepository,
        projeto: str | None = None,
    ) -> list[LedSelection]:
        try:
            carregados = carregar_original(self, projeto=projeto)
        except TypeError:
            carregados = carregar_original(self)
        return copiar_mascaras_absolutas(carregados)

    ConfigRepository.salvar_leds_fixos = salvar_leds_fixos_resolucao_segura
    ConfigRepository.carregar_leds_fixos = carregar_leds_fixos_resolucao_segura
    _PATCH_REPOSITORIO_INSTALADO = True


class FixedMaskGeometryGuardMixin:
    """Protege a geometria relativa e adapta somente quando a resolução muda."""

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

    def _mask_guard_current_resolution(self) -> tuple[int, int] | None:
        for frame in (
            getattr(self, "camera_frame_atual", None),
            getattr(self, "imagem_original", None),
        ):
            if frame is None or not getattr(frame, "size", 0):
                continue
            altura, largura = frame.shape[:2]
            if largura > 0 and altura > 0:
                return int(largura), int(altura)

        largura = int(getattr(self, "largura_original", 0) or 0)
        altura = int(getattr(self, "altura_original", 0) or 0)
        if largura > 0 and altura > 0:
            return largura, altura

        for led in self._mask_guard_snapshot:
            if led.largura_base and led.altura_base:
                return int(led.largura_base), int(led.altura_base)
        return None

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

    @staticmethod
    def _mask_guard_canonicalize(
        leds: Iterable[LedSelection] | None,
        reference_resolution: tuple[int, int] | None,
    ) -> list[LedSelection]:
        from src.platform import led_mask_resolution_sync as sync

        resultado = []
        referencia = reference_resolution
        for led in leds or ():
            copia = copiar_mascara_absoluta(led)
            if copia.possui_coordenadas_normalizadas():
                resultado.append(copia)
                continue

            if referencia is None:
                if copia.largura_base and copia.altura_base:
                    referencia = (
                        int(copia.largura_base),
                        int(copia.altura_base),
                    )
                else:
                    resultado.append(copia)
                    continue

            canonical, _migrated = sync.canonicalize_led_mask(
                copia,
                reference_width=int(referencia[0]),
                reference_height=int(referencia[1]),
            )
            resultado.append(canonical)
        return resultado

    @staticmethod
    def _mask_guard_adapt(
        leds: Iterable[LedSelection] | None,
        target_resolution: tuple[int, int] | None,
    ) -> list[LedSelection]:
        if target_resolution is None:
            return copiar_mascaras_absolutas(leds)

        largura, altura = target_resolution
        resultado = []
        for led in leds or ():
            copia = copiar_mascara_absoluta(led)
            if not copia.possui_coordenadas_normalizadas():
                resultado.append(copia)
                continue
            resultado.append(
                copia.adaptar_para_resolucao(
                    largura_destino=int(largura),
                    altura_destino=int(altura),
                    raio_minimo=MIN_RADIUS_PX,
                    raio_maximo=max(int(largura), int(altura)),
                )
            )
        return resultado

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
            canonical = self._mask_guard_canonicalize(
                mascaras,
                self._mask_guard_current_resolution(),
            )
            self._mask_guard_project = projeto
            self._mask_guard_snapshot = tuple(canonical)

    def _mask_guard_refresh_project(self) -> None:
        projeto = self._mask_guard_active_project()
        if projeto != self._mask_guard_project:
            self._mask_guard_capture(force=True, project=projeto)

    def _mask_guard_snapshot_copy(self) -> list[LedSelection]:
        return copiar_mascaras_absolutas(self._mask_guard_snapshot)

    def _mask_guard_editing(self) -> bool:
        return str(getattr(self, "modo_atual", "")) in MODOS_EDICAO_MASCARA

    def _mask_guard_enforce(self) -> list[LedSelection]:
        with self._mask_guard_lock:
            if not self._mask_guard_project:
                self._mask_guard_capture(force=True)

            esperado = self._mask_guard_adapt(
                self._mask_guard_snapshot,
                self._mask_guard_current_resolution(),
            )
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

    def adaptar_leds_fixos_para_frame_camera(self, leds_fixos):
        resolucao = self._mask_guard_current_resolution()
        canonical = self._mask_guard_canonicalize(leds_fixos, resolucao)
        return self._mask_guard_adapt(canonical, resolucao)

    def obter_leds_fixos_validos_para_imagem(self, leds_fixos):
        return self.adaptar_leds_fixos_para_frame_camera(leds_fixos)

    def _normalize_manual_masks(self, leds, reference_resolution):
        return super()._normalize_manual_masks(leds, reference_resolution)

    def _synchronize_masks_with_current_frame(
        self,
        force: bool = False,
        schedule_operation_prepare: bool = True,
    ) -> None:
        # A sincronização real é responsabilidade da camada normalizada. O
        # guard entra depois apenas para garantir que nenhuma outra rotina tenha
        # alterado a geometria relativa.
        super()._synchronize_masks_with_current_frame(
            force=force,
            schedule_operation_prepare=schedule_operation_prepare,
        )
        self._mask_guard_enforce()

    def atualizar_frame_camera(self) -> None:
        super().atualizar_frame_camera()
        self._mask_guard_enforce()

    def salvar_leds_fixos(self) -> None:
        super().salvar_leds_fixos()
        salvas = self._mask_guard_read_repository()
        self._mask_guard_capture(force=True, source=salvas)

        # Garante que o JSON novo já contenha a base normalizada, inclusive para
        # segmentos que passaram por caminhos legados de persistência.
        repository = getattr(self, "config_repository", None)
        salvar = getattr(repository, "salvar_leds_fixos", None)
        if callable(salvar) and self._mask_guard_snapshot:
            projeto = self._mask_guard_active_project()
            try:
                if projeto != "__DEFAULT__":
                    salvar(list(self._mask_guard_snapshot), projeto=projeto)
                else:
                    salvar(list(self._mask_guard_snapshot))
            except TypeError:
                salvar(list(self._mask_guard_snapshot))
            except Exception:
                pass
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
        self._synchronize_masks_with_current_frame(
            force=True,
            schedule_operation_prepare=False,
        )
        super().preparar_tela_operacao()
        self._mask_guard_enforce()

    def disparar_inspecao_operacao(self) -> None:
        self._mask_guard_refresh_project()
        self._synchronize_masks_with_current_frame(
            force=True,
            schedule_operation_prepare=False,
        )
        super().disparar_inspecao_operacao()
