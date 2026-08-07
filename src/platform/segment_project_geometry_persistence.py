from __future__ import annotations

from src.models.led_selection import LedSelection


_PATCH_RESOLUTION_SYNC_INSTALADO = False


def copiar_led_geometria_completa(led: LedSelection) -> LedSelection:
    """Copia uma ROI sem perder a geometria de segmento.

    Alguns fluxos legados do Raspberry reconstruíam a seleção apenas com
    ``id/x/y/raio``. Para segmentos, o raio é somente uma medida de
    compatibilidade e essa reconstrução fazia a barra reaparecer como círculo.
    """
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
    )


def copiar_lista_geometria_completa(leds) -> list[LedSelection]:
    return [copiar_led_geometria_completa(led) for led in (leds or ())]


def instalar_preservacao_segmentos_resolution_sync() -> None:
    """Corrige os helpers legados de sincronização sem afetar círculos."""
    global _PATCH_RESOLUTION_SYNC_INSTALADO
    if _PATCH_RESOLUTION_SYNC_INSTALADO:
        return

    import src.platform.led_mask_resolution_sync as sync

    def copiar_led_sync(led: LedSelection) -> LedSelection:
        return copiar_led_geometria_completa(led)

    def canonicalize_led_mask_segment_safe(
        led: LedSelection,
        reference_width: int,
        reference_height: int,
    ) -> tuple[LedSelection, bool]:
        if led.possui_coordenadas_normalizadas():
            return copiar_led_geometria_completa(led), False

        base_width = max(1, int(led.largura_base or reference_width))
        base_height = max(1, int(led.altura_base or reference_height))
        canonical = copiar_led_geometria_completa(led).com_normalizacao(
            largura_base=base_width,
            altura_base=base_height,
        )
        return canonical, True

    sync._copy_led = copiar_led_sync
    sync.canonicalize_led_mask = canonicalize_led_mask_segment_safe
    _PATCH_RESOLUTION_SYNC_INSTALADO = True


class SegmentProjectGeometryPersistenceMixin:
    """Mantém círculos e segmentos intactos ao trocar/carregar projetos."""

    @staticmethod
    def _copiar_led(led: LedSelection) -> LedSelection:
        # Esta definição tem precedência sobre os helpers legados de
        # LedMaskEditorMixin e RaspberryRuntimeFixesMixin no perfil display.
        return copiar_led_geometria_completa(led)

    def carregar_leds_fixos(self) -> None:
        """Carrega o projeto e reafirma a geometria completa antes do desenho."""
        super().carregar_leds_fixos()

        repository = getattr(self, "config_repository", None)
        if repository is None:
            return

        obter_ativo = getattr(repository, "obter_projeto_led_ativo", None)
        carregar = getattr(repository, "carregar_leds_fixos", None)
        if not callable(carregar):
            return

        projeto = ""
        if callable(obter_ativo):
            try:
                projeto = str(obter_ativo() or "").strip()
            except Exception:
                projeto = ""

        try:
            carregados = (
                carregar(projeto=projeto)
                if projeto
                else carregar()
            )
        except TypeError:
            carregados = carregar()
        except Exception:
            return

        completos = copiar_lista_geometria_completa(carregados)
        if not completos:
            return

        if projeto:
            self.projeto_led_ativo = projeto
            atualizar_projeto = getattr(
                self,
                "_atualizar_projeto_led_na_interface",
                None,
            )
            if callable(atualizar_projeto):
                atualizar_projeto()

        # O projeto carregado passa a ser a fonte canônica do guard. Isso evita
        # que um snapshot do projeto anterior seja reutilizado durante o mesmo
        # clique em "Carregar projeto".
        self.leds_fixos_configurados = copiar_lista_geometria_completa(completos)
        self.guias_leds_fixos_visiveis = True
        self.selecao_manual_camera_ativa = False
        self.leds_manuais_camera = []
        self.resultados_led_atual = []

        capturar = getattr(self, "_mask_guard_capture", None)
        if callable(capturar):
            try:
                capturar(
                    force=True,
                    source=completos,
                    project=projeto or None,
                )
            except TypeError:
                capturar(force=True, source=completos)

        aplicar = getattr(self, "_mask_guard_enforce", None)
        if callable(aplicar):
            try:
                exibicao = copiar_lista_geometria_completa(aplicar())
            except Exception:
                exibicao = copiar_lista_geometria_completa(completos)
        else:
            exibicao = copiar_lista_geometria_completa(completos)

        if getattr(self, "imagem_original", None) is None:
            return

        self.leds_selecionados = exibicao
        view = getattr(self, "view", None)
        if view is None:
            return

        try:
            view.selecao_manual_camera_visivel = False
            view.atualizar_estado_selecao_led(False)
            view.preparar_imagem_para_exibicao(self.imagem_original)
            view.desenhar_canvas(
                self.leds_selecionados,
                self.resultados_led_atual,
            )
            view.atualizar_faixa_resultado()
        except Exception:
            return

        if bool(getattr(self, "camera_ativa", False)):
            atualizar = getattr(
                self,
                "atualizar_renderizacoes_camera_se_necessario",
                None,
            )
            if callable(atualizar):
                try:
                    atualizar(forcar=True)
                except Exception:
                    pass
        else:
            atualizar = getattr(self, "atualizar_renderizacoes_visuais", None)
            if callable(atualizar):
                try:
                    atualizar(self.leds_selecionados)
                except Exception:
                    pass
