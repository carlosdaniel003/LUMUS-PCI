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
    """Mantém círculos e segmentos intactos ao salvar, trocar e carregar projetos."""

    @staticmethod
    def _copiar_led(led: LedSelection) -> LedSelection:
        # Esta definição tem precedência sobre os helpers legados de
        # LedMaskEditorMixin e RaspberryRuntimeFixesMixin no perfil display.
        return copiar_led_geometria_completa(led)

    def _reafirmar_geometria_projeto(
        self,
        leds,
        projeto: str | None = None,
        redesenhar: bool = True,
    ) -> list[LedSelection]:
        """Torna a geometria completa a fonte canônica da memória e do guard."""
        completos = copiar_lista_geometria_completa(leds)
        if not completos:
            return []

        nome_projeto = str(projeto or "").strip()
        if nome_projeto:
            self.projeto_led_ativo = nome_projeto
            atualizar_projeto = getattr(
                self,
                "_atualizar_projeto_led_na_interface",
                None,
            )
            if callable(atualizar_projeto):
                atualizar_projeto()

        self.leds_fixos_configurados = copiar_lista_geometria_completa(completos)
        self.leds_selecionados = copiar_lista_geometria_completa(completos)
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
                    project=nome_projeto or None,
                )
            except TypeError:
                capturar(force=True, source=completos)

        aplicar = getattr(self, "_mask_guard_enforce", None)
        if callable(aplicar):
            try:
                exibicao = copiar_lista_geometria_completa(aplicar())
                if exibicao:
                    self.leds_selecionados = exibicao
            except Exception:
                pass

        if not redesenhar or getattr(self, "imagem_original", None) is None:
            return copiar_lista_geometria_completa(self.leds_selecionados)

        view = getattr(self, "view", None)
        if view is None:
            return copiar_lista_geometria_completa(self.leds_selecionados)

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
            return copiar_lista_geometria_completa(self.leds_selecionados)

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

        return copiar_lista_geometria_completa(self.leds_selecionados)

    def _salvar_leds_no_projeto(
        self,
        nome_projeto: str,
        parent=None,
        confirmar_substituicao: bool = True,
    ) -> bool:
        """Impede o botão 'Salvar LEDs selecionados' de gravar segmentos como círculos.

        O gerenciador legado chama ``super().salvar_leds_fixos()`` a partir de
        ``LedProjectManagerMixin``. Esse caminho chega ao ODIN base, que ainda
        reconstrói cada seleção somente com id/x/y/raio. Em segmentos, isso
        descartava ``tipo_roi/largura/altura/angulo`` antes de o JSON ser salvo.

        Capturamos a geometria correta antes desse caminho e, após a operação
        legada concluir, gravamos novamente o projeto com os objetos completos.
        """
        geometria_antes = copiar_lista_geometria_completa(
            getattr(self, "leds_selecionados", ())
        )

        salvo = super()._salvar_leds_no_projeto(
            nome_projeto,
            parent=parent,
            confirmar_substituicao=confirmar_substituicao,
        )
        if not salvo or not geometria_antes:
            return bool(salvo)

        repository = getattr(self, "config_repository", None)
        salvar = getattr(repository, "salvar_leds_fixos", None)
        if not callable(salvar):
            return bool(salvo)

        try:
            salvar(
                copiar_lista_geometria_completa(geometria_antes),
                largura_base=None,
                altura_base=None,
                projeto=nome_projeto,
            )
        except TypeError:
            try:
                salvar(
                    copiar_lista_geometria_completa(geometria_antes),
                    projeto=nome_projeto,
                )
            except TypeError:
                salvar(copiar_lista_geometria_completa(geometria_antes))

        # Releitura é deliberada: valida o mesmo caminho que será usado quando
        # o operador clicar posteriormente em "Carregar projeto".
        carregar = getattr(repository, "carregar_leds_fixos", None)
        recarregados = []
        if callable(carregar):
            try:
                recarregados = carregar(projeto=nome_projeto)
            except TypeError:
                recarregados = carregar()
            except Exception:
                recarregados = []

        fonte = recarregados or geometria_antes
        self._reafirmar_geometria_projeto(
            fonte,
            projeto=nome_projeto,
            redesenhar=True,
        )
        return True

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

        # O projeto carregado passa a ser a fonte canônica do guard. Isso evita
        # que um snapshot do projeto anterior seja reutilizado durante o mesmo
        # clique em "Carregar projeto".
        self._reafirmar_geometria_projeto(
            completos,
            projeto=projeto or None,
            redesenhar=True,
        )
