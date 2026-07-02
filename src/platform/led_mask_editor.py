from __future__ import annotations

import re
from tkinter import messagebox

from src.core.feature_extractor import validar_centro_led
from src.core.visual_renderer import (
    criar_imagem_mascara_visual,
    criar_imagem_roi_debug_ampliado,
)
from src.models.led_selection import LedSelection


class LedMaskEditorMixin:
    """Edição individual e não destrutiva das máscaras de LEDs."""

    EDITABLE_LED_MODES = (
        "configurar_leds_fixos",
        "selecionar_leds_analise",
        "selecionar_leds_camera",
    )
    EDITOR_PREVIEW_INTERVAL_MS = 90

    def inicializar_editor_mascaras_led(self) -> None:
        self._editor_led_id: str | None = None
        self._editor_arrastando = False
        self._editor_posicao_alterada = False
        self._editor_preview_after_id = None

        canvas = getattr(self.view, "canvas", None)
        if canvas is None:
            return

        canvas.configure(takefocus=True)
        canvas.bind("<B1-Motion>", self.evento_arrastar_mascara_led)
        canvas.bind("<ButtonRelease-1>", self.evento_soltar_mascara_led)
        canvas.bind("<Button-3>", self.evento_clique_direito_mascara_led)
        canvas.bind("<Delete>", self.excluir_mascara_led_selecionada)
        canvas.bind("<BackSpace>", self.excluir_mascara_led_selecionada)

    def _editor_esta_ativo(self) -> bool:
        return self.modo_atual in self.EDITABLE_LED_MODES

    def _editor_camera_esta_ativo(self) -> bool:
        return self.modo_atual == "selecionar_leds_camera"

    def _definir_led_em_edicao(self, led_id: str | None) -> None:
        self._editor_led_id = str(led_id) if led_id else None
        self.view.led_em_edicao_id = self._editor_led_id

    def _cancelar_preview_editor_led(self) -> None:
        if self._editor_preview_after_id is None:
            return

        try:
            self.root.after_cancel(self._editor_preview_after_id)
        except Exception:
            pass

        self._editor_preview_after_id = None

    def _limpar_estado_editor_led(self) -> None:
        self._cancelar_preview_editor_led()
        self._editor_arrastando = False
        self._editor_posicao_alterada = False
        self._definir_led_em_edicao(None)

    @staticmethod
    def _copiar_led(led: LedSelection) -> LedSelection:
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
        )

    @staticmethod
    def _numero_id_led(led_id: str) -> int | None:
        correspondencia = re.search(r"(\d+)$", str(led_id))
        if correspondencia is None:
            return None
        try:
            return int(correspondencia.group(1))
        except ValueError:
            return None

    def _chave_ordenacao_led(self, led: LedSelection):
        numero = self._numero_id_led(led.id)
        if numero is None:
            return (1, str(led.id))
        return (0, numero)

    def _proximo_id_led_disponivel(self) -> str:
        numeros_usados = {
            numero
            for numero in (
                self._numero_id_led(led.id)
                for led in self.leds_selecionados
            )
            if numero is not None and numero > 0
        }

        numero = 1
        while numero in numeros_usados:
            numero += 1

        return f"LED_{numero:03d}"

    def _obter_led_por_id(self, led_id: str | None):
        if not led_id:
            return None

        for led in self.leds_selecionados:
            if str(led.id) == str(led_id):
                return led

        return None

    def _obter_led_na_posicao(self, centro_x: int, centro_y: int):
        melhor_led = None
        melhor_distancia_quadrada = None

        for led in self.leds_selecionados:
            delta_x = int(led.centro_x) - int(centro_x)
            delta_y = int(led.centro_y) - int(centro_y)
            distancia_quadrada = delta_x * delta_x + delta_y * delta_y
            limite = max(8, int(led.raio) + 5)

            if distancia_quadrada > limite * limite:
                continue

            if (
                melhor_distancia_quadrada is None
                or distancia_quadrada < melhor_distancia_quadrada
            ):
                melhor_led = led
                melhor_distancia_quadrada = distancia_quadrada

        return melhor_led

    def _converter_evento_para_imagem(self, evento):
        return self.view.converter_canvas_para_imagem_original(
            evento.x,
            evento.y,
        )

    def _sincronizar_editor_camera(self) -> None:
        if not self._editor_camera_esta_ativo():
            return

        self.leds_manuais_camera = [
            self._copiar_led(led)
            for led in self.leds_selecionados
        ]
        self.guias_leds_fixos_visiveis = False
        self.view.selecao_manual_camera_visivel = True

    def _alvos_preview_editor(self) -> list[LedSelection]:
        led_selecionado = self._obter_led_por_id(
            self._editor_led_id
        )

        if led_selecionado is None:
            return list(self.leds_selecionados)

        return [
            led
            for led in self.leds_selecionados
            if str(led.id) != str(led_selecionado.id)
        ] + [led_selecionado]

    def _atualizar_preview_editor_led_leve(self) -> None:
        if self.imagem_original is None or not self._editor_esta_ativo():
            return

        led_selecionado = self._obter_led_por_id(
            self._editor_led_id
        )
        alvos = self._alvos_preview_editor()
        canvas_mascara = getattr(self.view, "canvas_mascara", None)
        canvas_roi_debug = getattr(self.view, "canvas_roi_debug", None)

        if canvas_mascara is not None:
            imagem_mascara = criar_imagem_mascara_visual(
                self.imagem_original,
                alvos,
            )
            self.view.exibir_imagem_em_canvas(
                canvas=canvas_mascara,
                imagem=imagem_mascara,
                chave="mascara",
            )

        if canvas_roi_debug is not None and led_selecionado is not None:
            imagem_roi = criar_imagem_roi_debug_ampliado(
                self.imagem_original,
                led_selecionado,
            )
            self.view.exibir_imagem_em_canvas(
                canvas=canvas_roi_debug,
                imagem=imagem_roi,
                chave="roi_debug",
            )

    def _executar_preview_editor_led_agendado(self) -> None:
        self._editor_preview_after_id = None
        self._atualizar_preview_editor_led_leve()

    def _agendar_preview_editor_led(self) -> None:
        if self._editor_preview_after_id is not None:
            return

        self._editor_preview_after_id = self.root.after(
            self.EDITOR_PREVIEW_INTERVAL_MS,
            self._executar_preview_editor_led_agendado,
        )

    def _redesenhar_editor_led(
        self,
        atualizar_auxiliares: bool = False,
    ) -> None:
        self._sincronizar_editor_camera()
        self.resultados_led_atual = []
        self.view.desenhar_canvas(
            self.leds_selecionados,
            self.resultados_led_atual,
        )
        self.view.atualizar_faixa_resultado()

        if atualizar_auxiliares:
            self.atualizar_renderizacoes_visuais(
                self._alvos_preview_editor()
            )

        self.atualizar_painel_inicial()

    def _carregar_mascaras_salvas_para_imagem(self) -> list[LedSelection]:
        self.leds_fixos_configurados = (
            self.config_repository.carregar_leds_fixos()
        )

        if not self.leds_fixos_configurados:
            return []

        if self.camera_ativa:
            return self.adaptar_leds_fixos_para_frame_camera(
                self.leds_fixos_configurados
            )

        return self.obter_leds_fixos_validos_para_imagem(
            self.leds_fixos_configurados
        )

    def iniciar_selecao_led(self) -> None:
        iniciando_camera = (
            self.camera_ativa
            and not self.selecao_manual_camera_ativa
        )
        iniciando_imagem = (
            not self.camera_ativa
            and self.modo_atual != "selecionar_leds_analise"
        )

        if iniciando_camera and not self.leds_manuais_camera:
            leds_salvos = self._carregar_mascaras_salvas_para_imagem()
            self.leds_manuais_camera = [
                self._copiar_led(led)
                for led in leds_salvos
            ]

        if iniciando_imagem and not self.leds_selecionados:
            self.leds_selecionados = sorted(
                self._carregar_mascaras_salvas_para_imagem(),
                key=self._chave_ordenacao_led,
            )

        super().iniciar_selecao_led()
        self._limpar_estado_editor_led()

        if not self._editor_esta_ativo():
            return

        self.leds_selecionados.sort(key=self._chave_ordenacao_led)
        self._sincronizar_editor_camera()
        self._redesenhar_editor_led(atualizar_auxiliares=True)
        self.view.canvas.focus_set()

        total = len(self.leds_selecionados)
        if total:
            mensagem = (
                f"Seleção ativa com {total} máscaras. Clique em uma máscara "
                "para selecionar, arraste para mover, use botão direito ou "
                "Delete para excluir e clique em uma área vazia para adicionar."
            )
        else:
            mensagem = (
                "Seleção ativa. Clique nos LEDs para criar máscaras. "
                "As máscaras também podem ser movidas ou excluídas individualmente."
            )

        self.view.atualizar_status(mensagem)

    def configurar_leds_fixos(self) -> None:
        if self.camera_ativa:
            self.parar_tela_ao_vivo(manter_imagem=True)

        if self.imagem_original is None:
            messagebox.showwarning(
                "Atenção",
                "Carregue a imagem da PCI antes de configurar LEDs fixos.",
            )
            return

        leds_carregados = self._carregar_mascaras_salvas_para_imagem()
        self.modo_atual = "configurar_leds_fixos"
        self.leds_selecionados = sorted(
            leds_carregados,
            key=self._chave_ordenacao_led,
        )
        self.resultados_led_atual = []
        self._limpar_estado_editor_led()

        self.view.atualizar_estado_selecao_led(True)
        self.view.preparar_imagem_para_exibicao(self.imagem_original)
        self._redesenhar_editor_led(atualizar_auxiliares=True)

        total = len(self.leds_selecionados)
        if total:
            mensagem = (
                f"{total} máscaras carregadas para edição. "
                "Clique em uma máscara para selecionar, arraste para mover, "
                "use botão direito ou Delete para excluir e clique em uma "
                "área vazia para adicionar."
            )
        else:
            mensagem = (
                "Configuração vazia. Clique nos LEDs para criar as máscaras. "
                "Depois use Configurações > Salvar LEDs."
            )

        self.view.atualizar_status(mensagem)
        self.view.canvas.focus_set()

    def salvar_leds_fixos(self) -> None:
        self._cancelar_preview_editor_led()
        if self._editor_esta_ativo():
            self._sincronizar_editor_camera()
            self.leds_selecionados.sort(
                key=self._chave_ordenacao_led
            )

        super().salvar_leds_fixos()
        self._limpar_estado_editor_led()

    def carregar_leds_fixos(self) -> None:
        self._limpar_estado_editor_led()
        super().carregar_leds_fixos()

    def limpar_tela(self) -> None:
        self._limpar_estado_editor_led()
        super().limpar_tela()

    def evento_clique_esquerdo(self, evento) -> None:
        if not self._editor_esta_ativo():
            super().evento_clique_esquerdo(evento)
            return

        self.view.canvas.focus_set()
        coordenadas = self._converter_evento_para_imagem(evento)
        if coordenadas is None:
            return

        centro_x, centro_y = coordenadas
        led_existente = self._obter_led_na_posicao(
            centro_x,
            centro_y,
        )

        if led_existente is not None:
            self._definir_led_em_edicao(led_existente.id)
            self._editor_arrastando = True
            self._editor_posicao_alterada = False
            self._redesenhar_editor_led()
            self._atualizar_preview_editor_led_leve()
            self.view.atualizar_status(
                f"{led_existente.id} selecionado. Arraste para mover ou "
                "use botão direito/Delete para excluir."
            )
            return

        raio = int(self.raio_atual_px)
        if not validar_centro_led(
            centro_x,
            centro_y,
            raio,
            self.largura_original,
            self.altura_original,
        ):
            self.view.atualizar_status(
                "clique ignorado: máscara fora da área válida da imagem."
            )
            return

        novo_led = LedSelection(
            id=self._proximo_id_led_disponivel(),
            centro_x=int(centro_x),
            centro_y=int(centro_y),
            raio=raio,
        )
        self.leds_selecionados.append(novo_led)
        self.leds_selecionados.sort(key=self._chave_ordenacao_led)
        self._definir_led_em_edicao(novo_led.id)
        self._editor_arrastando = False
        self._editor_posicao_alterada = False
        self._redesenhar_editor_led(atualizar_auxiliares=True)
        self.view.atualizar_status(
            f"{novo_led.id} criado. Total: {len(self.leds_selecionados)}. "
            "Arraste para ajustar ou salve a configuração."
        )

    def evento_arrastar_mascara_led(self, evento) -> None:
        if not self._editor_esta_ativo() or not self._editor_arrastando:
            return

        led = self._obter_led_por_id(self._editor_led_id)
        if led is None:
            self._editor_arrastando = False
            return

        coordenadas = self._converter_evento_para_imagem(evento)
        if coordenadas is None:
            return

        centro_x, centro_y = coordenadas
        if not validar_centro_led(
            centro_x,
            centro_y,
            led.raio,
            self.largura_original,
            self.altura_original,
        ):
            return

        if (
            int(led.centro_x) == int(centro_x)
            and int(led.centro_y) == int(centro_y)
        ):
            return

        led.centro_x = int(centro_x)
        led.centro_y = int(centro_y)
        self._editor_posicao_alterada = True
        self._sincronizar_editor_camera()
        self.resultados_led_atual = []
        self.view.desenhar_canvas(
            self.leds_selecionados,
            self.resultados_led_atual,
        )
        self._agendar_preview_editor_led()

    def evento_soltar_mascara_led(self, _evento=None) -> None:
        if not self._editor_esta_ativo() or not self._editor_arrastando:
            return

        self._editor_arrastando = False
        self._cancelar_preview_editor_led()
        led = self._obter_led_por_id(self._editor_led_id)

        if self._editor_posicao_alterada and led is not None:
            self._redesenhar_editor_led(atualizar_auxiliares=True)
            self.view.atualizar_status(
                f"{led.id} movido para X={led.centro_x}, Y={led.centro_y}. "
                "Salve os LEDs para gravar a alteração."
            )

        self._editor_posicao_alterada = False

    def evento_clique_direito_mascara_led(self, evento) -> str:
        if not self._editor_esta_ativo():
            return "break"

        self.view.canvas.focus_set()
        coordenadas = self._converter_evento_para_imagem(evento)
        if coordenadas is None:
            return "break"

        led = self._obter_led_na_posicao(*coordenadas)
        if led is None:
            self.view.atualizar_status(
                "Nenhuma máscara encontrada nessa posição."
            )
            return "break"

        self._definir_led_em_edicao(led.id)
        self.excluir_mascara_led_selecionada()
        return "break"

    def excluir_mascara_led_selecionada(self, _evento=None) -> str:
        if not self._editor_esta_ativo():
            return "break"

        led = self._obter_led_por_id(self._editor_led_id)
        if led is None:
            self.view.atualizar_status(
                "Selecione uma máscara antes de excluir."
            )
            return "break"

        id_excluido = str(led.id)
        self.leds_selecionados = [
            item
            for item in self.leds_selecionados
            if str(item.id) != id_excluido
        ]
        self._limpar_estado_editor_led()
        self._redesenhar_editor_led(atualizar_auxiliares=True)
        self.view.atualizar_status(
            f"{id_excluido} excluído. Total: {len(self.leds_selecionados)}. "
            "O próximo LED criado reutilizará o menor número disponível. "
            "Salve para gravar a alteração."
        )
        return "break"
