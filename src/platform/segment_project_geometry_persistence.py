from __future__ import annotations

from src.core.roi_geometry import TIPO_ROI_SEGMENTO, normalizar_tipo_roi
from src.models.led_selection import LedSelection


_PATCH_RESOLUTION_SYNC_INSTALADO = False


def copiar_led_geometria_completa(led: LedSelection) -> LedSelection:
    """Copia uma ROI sem perder geometria nem metadados de resolução."""
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


def copiar_lista_geometria_completa(leds) -> list[LedSelection]:
    return [copiar_led_geometria_completa(led) for led in (leds or ())]


def normalizar_lista_geometria(
    leds,
    largura_base: int | None,
    altura_base: int | None,
) -> list[LedSelection]:
    completos = copiar_lista_geometria_completa(leds)
    if not largura_base or not altura_base:
        return completos
    return [
        led.com_normalizacao(
            largura_base=int(largura_base),
            altura_base=int(altura_base),
        )
        for led in completos
    ]


def restaurar_tipo_roi_apos_adaptacao(
    original: LedSelection,
    adaptado: LedSelection,
) -> LedSelection:
    """Recupera segmentos quando um fallback legado devolve apenas círculo.

    ``LedSelection.adaptar_para_resolucao`` já preserva a geometria completa.
    O tratamento abaixo existe para os caminhos legados de ``ODINApp`` que
    calculam centro/escala e depois recriam uma instância apenas com raio.
    """
    if normalizar_tipo_roi(getattr(original, "tipo_roi", None)) != TIPO_ROI_SEGMENTO:
        return copiar_led_geometria_completa(adaptado)
    if normalizar_tipo_roi(getattr(adaptado, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
        return copiar_led_geometria_completa(adaptado)

    escala = float(getattr(adaptado, "raio", 1) or 1) / max(
        1.0,
        float(getattr(original, "raio", 1) or 1),
    )
    pontos = getattr(original, "pontos_segmento_livre", None)
    pontos_escalados = (
        [
            (float(x) * escala, float(y) * escala)
            for x, y in pontos
        ]
        if pontos
        else None
    )
    largura = getattr(original, "largura", None)
    altura = getattr(original, "altura", None)
    return LedSelection(
        id=str(adaptado.id),
        centro_x=int(adaptado.centro_x),
        centro_y=int(adaptado.centro_y),
        raio=max(1, int(adaptado.raio)),
        centro_x_normalizado=adaptado.centro_x_normalizado,
        centro_y_normalizado=adaptado.centro_y_normalizado,
        raio_normalizado=adaptado.raio_normalizado,
        largura_base=adaptado.largura_base,
        altura_base=adaptado.altura_base,
        tipo_roi=TIPO_ROI_SEGMENTO,
        largura=(
            max(1, int(round(float(largura) * escala)))
            if largura is not None
            else None
        ),
        altura=(
            max(1, int(round(float(altura) * escala)))
            if altura is not None
            else None
        ),
        angulo=float(getattr(original, "angulo", 0.0) or 0.0),
        pontos_segmento_livre=pontos_escalados,
    )


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
        return copiar_led_geometria_completa(led)

    def _reafirmar_geometria_projeto(
        self,
        leds,
        projeto: str | None = None,
        redesenhar: bool = True,
    ) -> list[LedSelection]:
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

    def _restaurar_geometria_manual_camera(self, redesenhar: bool = False) -> bool:
        manuais = copiar_lista_geometria_completa(
            getattr(self, "leds_manuais_camera", ())
        )
        if not manuais:
            return False
        self.leds_selecionados = manuais
        view = getattr(self, "view", None)
        if view is not None:
            try:
                view.selecao_manual_camera_visivel = True
            except Exception:
                pass
        if not redesenhar or view is None:
            return True
        try:
            view.desenhar_canvas(
                self.leds_selecionados,
                getattr(self, "resultados_led_atual", []),
            )
        except Exception:
            pass
        return True

    def atualizar_frame_camera(self) -> None:
        """Impede o refresh da câmera de reduzir segmento livre a círculo."""
        resultado = super().atualizar_frame_camera()
        if (
            bool(getattr(self, "camera_ativa", False))
            and getattr(self, "leds_manuais_camera", None)
            and not bool(getattr(self, "camera_em_pausa_analise", False))
        ):
            self._restaurar_geometria_manual_camera(redesenhar=True)
        return resultado

    def iniciar_selecao_led(self) -> None:
        """Ao reabrir Selecionar LEDs, restaura a geometria completa da ROI."""
        resultado = super().iniciar_selecao_led()
        if (
            bool(getattr(self, "camera_ativa", False))
            and getattr(self, "leds_manuais_camera", None)
        ):
            self._restaurar_geometria_manual_camera(redesenhar=True)
        return resultado

    def analisar_led_selecionado(self, *args, **kwargs):
        """Garante que a análise use o polígono real, não o raio compatível."""
        if (
            bool(getattr(self, "camera_ativa", False))
            and getattr(self, "leds_manuais_camera", None)
        ):
            self._restaurar_geometria_manual_camera(redesenhar=False)
        return super().analisar_led_selecionado(*args, **kwargs)

    def adaptar_leds_fixos_para_frame_camera(self, leds_fixos):
        """Mantém o tipo/contorno mesmo quando o fallback legado reposiciona ROIs."""
        adaptados = list(super().adaptar_leds_fixos_para_frame_camera(leds_fixos) or [])
        origem_por_id = {
            str(getattr(led, "id", "")): led
            for led in (leds_fixos or ())
        }
        resultado = []
        for adaptado in adaptados:
            origem = origem_por_id.get(str(getattr(adaptado, "id", "")))
            if origem is None:
                resultado.append(copiar_led_geometria_completa(adaptado))
                continue
            resultado.append(restaurar_tipo_roi_apos_adaptacao(origem, adaptado))
        return resultado

    def salvar_leds_fixos(self) -> None:
        """Regrava o salvamento legado com a mesma geometria vista no editor."""
        largura = int(getattr(self, "largura_original", 0) or 0)
        altura = int(getattr(self, "altura_original", 0) or 0)
        geometria_antes = normalizar_lista_geometria(
            getattr(self, "leds_selecionados", ()),
            largura if largura > 0 else None,
            altura if altura > 0 else None,
        )
        resultado = super().salvar_leds_fixos()
        if not geometria_antes or not any(
            normalizar_tipo_roi(getattr(led, "tipo_roi", None)) == TIPO_ROI_SEGMENTO
            for led in geometria_antes
        ):
            return resultado

        repository = getattr(self, "config_repository", None)
        salvar = getattr(repository, "salvar_leds_fixos", None)
        if callable(salvar):
            try:
                salvar(
                    copiar_lista_geometria_completa(geometria_antes),
                    largura_base=None,
                    altura_base=None,
                    projeto=getattr(self, "projeto_led_ativo", None),
                )
            except TypeError:
                try:
                    salvar(
                        copiar_lista_geometria_completa(geometria_antes),
                        largura_base=None,
                        altura_base=None,
                    )
                except TypeError:
                    salvar(copiar_lista_geometria_completa(geometria_antes))
        self.leds_fixos_configurados = copiar_lista_geometria_completa(
            geometria_antes
        )
        self.leds_selecionados = copiar_lista_geometria_completa(
            geometria_antes
        )
        return resultado

    def _salvar_leds_no_projeto(
        self,
        nome_projeto: str,
        parent=None,
        confirmar_substituicao: bool = True,
    ) -> bool:
        """Regrava a geometria completa e sua resolução base após o fluxo legado."""
        largura_base = int(getattr(self, "largura_original", 0) or 0)
        altura_base = int(getattr(self, "altura_original", 0) or 0)
        geometria_antes = normalizar_lista_geometria(
            getattr(self, "leds_selecionados", ()),
            largura_base if largura_base > 0 else None,
            altura_base if altura_base > 0 else None,
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

        self._reafirmar_geometria_projeto(
            completos,
            projeto=projeto or None,
            redesenhar=True,
        )
