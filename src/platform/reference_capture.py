from __future__ import annotations

import base64
import copy
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import cv2

from config import (
    CONFIG_DIR,
    DEFAULT_THRESHOLD_V,
    MAX_RADIUS_PX,
    MIN_RADIUS_PX,
)
from src.core.feature_extractor import extrair_features_selecao
from src.core.roi_geometry import (
    TIPO_ROI_CIRCULO,
    bbox_roi,
    normalizar_tipo_roi,
    roi_dentro_imagem,
)
from src.models.led_selection import LedSelection
from src.models.reference_sample import ReferenceSample
from src.platform.bulk_roi_editor import copiar_led


MARGEM_PREVIEW_REFERENCIA = 0.12

_REFERENCIAS = {
    "aceso": {
        "titulo": "Referência • LED aceso",
        "botao": "Ref. aceso",
        "arquivo": "reference_on.png",
        "config_key": "reference_on",
        "imagem_attr": "imagem_referencia_acesa",
        "caminho_attr": "caminho_referencia_acesa",
        "features_attr": "features_referencia_acesa",
        "cor": "#22C55E",
    },
    "apagado": {
        "titulo": "Referência • LED apagado",
        "botao": "Ref. apagado",
        "arquivo": "reference_off.png",
        "config_key": "reference_off",
        "imagem_attr": "imagem_referencia_apagada",
        "caminho_attr": "caminho_referencia_apagada",
        "features_attr": "features_referencia_apagada",
        "cor": "#38BDF8",
    },
    "pouca_luz": {
        "titulo": "Referência • pouca luz",
        "botao": "Ref. pouca luz",
        "arquivo": "reference_low_light.png",
        "config_key": "reference_low_light",
        "imagem_attr": "imagem_referencia_pouca_luz",
        "caminho_attr": "caminho_referencia_pouca_luz",
        "features_attr": "features_referencia_pouca_luz",
        "cor": "#FBBF24",
    },
}


def recortar_referencia_roi(
    imagem,
    roi: LedSelection,
    margem_relativa: float = MARGEM_PREVIEW_REFERENCIA,
):
    """Recorta a região visual da ROI com uma pequena margem de contexto.

    As features não são extraídas deste retângulo. Elas usam a própria ROI
    selecionada (círculo ou segmento), exatamente como na análise normal.
    """
    if imagem is None or getattr(imagem, "size", 0) == 0 or roi is None:
        return None

    altura, largura = imagem.shape[:2]
    if not roi_dentro_imagem(roi, largura, altura):
        return None

    x1, y1, x2, y2 = bbox_roi(roi)
    largura_roi = max(1.0, float(x2) - float(x1))
    altura_roi = max(1.0, float(y2) - float(y1))
    margem = max(
        2,
        int(
            math.ceil(
                max(largura_roi, altura_roi)
                * max(0.0, float(margem_relativa))
            )
        ),
    )

    esquerda = max(0, int(math.floor(float(x1))) - margem)
    topo = max(0, int(math.floor(float(y1))) - margem)
    direita = min(largura, int(math.ceil(float(x2))) + margem + 1)
    base = min(altura, int(math.ceil(float(y2))) + margem + 1)

    if direita <= esquerda or base <= topo:
        return None

    recorte = imagem[topo:base, esquerda:direita]
    if recorte is None or getattr(recorte, "size", 0) == 0:
        return None
    return recorte.copy()


def atualizar_configuracao_referencia(
    configuracao: dict | None,
    chave_referencia: str,
    caminho_imagem: str,
    features: dict,
    raio_atual_px: int,
    settings_padrao: dict | None = None,
    roi: dict | None = None,
) -> dict:
    """Atualiza uma referência sem apagar LEDs, settings ou outras refs."""
    dados = copy.deepcopy(configuracao) if isinstance(configuracao, dict) else {}

    dados.setdefault("project", "ODIN")
    dados.setdefault("version", "0.13.0")
    dados.setdefault(
        "inspection_method",
        "single_selected_led_reference_classifier_modular",
    )
    dados.setdefault("threshold_v", DEFAULT_THRESHOLD_V)
    dados.setdefault("fixed_leds", [])
    dados["default_radius_px"] = int(raio_atual_px)

    if not isinstance(dados.get("settings"), dict):
        dados["settings"] = copy.deepcopy(settings_padrao or {})

    referencia = {
        "image_path": str(caminho_imagem),
        "features": copy.deepcopy(features),
    }
    if isinstance(roi, dict):
        referencia["roi"] = copy.deepcopy(roi)
    dados[str(chave_referencia)] = referencia
    return dados


def _percorrer_widgets(widget):
    try:
        filhos = tuple(widget.winfo_children())
    except Exception:
        filhos = ()
    for filho in filhos:
        yield filho
        yield from _percorrer_widgets(filho)


def _encontrar_corpo_referencias(janela: tk.Toplevel):
    for widget in _percorrer_widgets(janela):
        if not isinstance(widget, tk.Label):
            continue
        try:
            texto = str(widget.cget("text"))
        except Exception:
            continue
        if texto != "Referências fixas":
            continue

        card = widget.master
        frames = [
            filho
            for filho in card.winfo_children()
            if isinstance(filho, tk.Frame)
        ]
        return frames[-1] if frames else None
    return None


def _criar_photo_preview(imagem, largura_max: int = 176, altura_max: int = 108):
    if imagem is None or getattr(imagem, "size", 0) == 0:
        return None

    altura, largura = imagem.shape[:2]
    if largura <= 0 or altura <= 0:
        return None

    escala = min(
        float(largura_max) / float(largura),
        float(altura_max) / float(altura),
    )
    largura_final = max(1, int(round(largura * escala)))
    altura_final = max(1, int(round(altura * escala)))
    interpolacao = cv2.INTER_AREA if escala < 1.0 else cv2.INTER_LINEAR
    reduzida = cv2.resize(
        imagem,
        (largura_final, altura_final),
        interpolation=interpolacao,
    )
    sucesso, buffer = cv2.imencode(".png", reduzida)
    if not sucesso:
        return None
    dados = base64.b64encode(buffer).decode("ascii")
    return tk.PhotoImage(data=dados)


class ReferenceCaptureMixin:
    """Usa o editor real de ROIs para definir as três referências fixas."""

    MODO_CAPTURA_REFERENCIA = "capturar_referencia"

    def __init__(self, *args, **kwargs) -> None:
        self.imagem_referencia_pouca_luz = None
        self.caminho_referencia_pouca_luz = None
        self.features_referencia_pouca_luz = None

        self._referencia_captura_tipo = None
        self._referencia_captura_frame = None
        self._referencia_captura_estado_anterior = None
        self._referencia_salvando = False
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Carregamento automático e integração com Configurações
    # ------------------------------------------------------------------
    def carregar_referencias_automaticamente_se_necessario(self) -> None:
        super().carregar_referencias_automaticamente_se_necessario()

        # Recarrega as imagens somente para as previews. Não recalcula as
        # features, pois elas podem ter vindo de um segmento rotacionado.
        for imagem_attr, caminho_attr in (
            ("imagem_referencia_acesa", "caminho_referencia_acesa"),
            ("imagem_referencia_apagada", "caminho_referencia_apagada"),
        ):
            caminho = getattr(self, caminho_attr, None)
            imagem = self.recarregar_imagem_referencia(caminho)
            if imagem is not None:
                setattr(self, imagem_attr, imagem)

        configuracao = self.config_repository.carregar_configuracao_existente_sem_alerta()
        referencia_pouca_luz = ReferenceSample.from_dict(
            configuracao.get("reference_low_light", {})
        )
        self.caminho_referencia_pouca_luz = referencia_pouca_luz.image_path
        self.features_referencia_pouca_luz = referencia_pouca_luz.features
        self.imagem_referencia_pouca_luz = self.recarregar_imagem_referencia(
            self.caminho_referencia_pouca_luz
        )

    def abrir_configuracoes(self) -> None:
        self.carregar_referencias_automaticamente_se_necessario()
        super().abrir_configuracoes()
        janela = self._encontrar_janela_configuracoes_aberta()
        if janela is not None:
            self._reconstruir_referencias_configuracoes(janela)

    def _encontrar_janela_configuracoes_aberta(self):
        try:
            candidatos = [
                widget
                for widget in self.root.winfo_children()
                if isinstance(widget, tk.Toplevel)
                and widget.winfo_exists()
                and str(widget.title()) == "Configurações - ODIN"
            ]
        except Exception:
            return None
        return candidatos[-1] if candidatos else None

    def _reconstruir_referencias_configuracoes(self, janela: tk.Toplevel) -> None:
        corpo = _encontrar_corpo_referencias(janela)
        if corpo is None:
            return

        for filho in tuple(corpo.winfo_children()):
            try:
                filho.destroy()
            except Exception:
                pass

        tk.Label(
            corpo,
            text=(
                "As referências são carregadas automaticamente. Clique em uma "
                "referência e desenhe exatamente a ROI que será usada como "
                "amostra, com o mesmo editor de Selecionar LEDs."
            ),
            font=("Segoe UI", 9),
            fg=self.view.COR_TEXTO_2,
            bg=self.view.COR_CARD_2,
            wraplength=650,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 10))

        grade = tk.Frame(corpo, bg=self.view.COR_CARD_2)
        grade.pack(fill=tk.X, padx=12, pady=(0, 12))
        for coluna in range(3):
            grade.grid_columnconfigure(coluna, weight=1, uniform="refs")

        fotos = []
        for coluna, tipo in enumerate(("aceso", "apagado", "pouca_luz")):
            dados = _REFERENCIAS[tipo]
            imagem = getattr(self, dados["imagem_attr"], None)

            card = tk.Frame(
                grade,
                bg=self.view.COR_CARD,
                highlightthickness=1,
                highlightbackground=self.view.COR_BORDA,
            )
            card.grid(
                row=0,
                column=coluna,
                sticky="nsew",
                padx=(0 if coluna == 0 else 5, 0 if coluna == 2 else 5),
            )

            preview = tk.Frame(
                card,
                bg="#020617",
                width=188,
                height=118,
                highlightthickness=1,
                highlightbackground=self.view.COR_BORDA,
            )
            preview.pack(fill=tk.X, padx=8, pady=(8, 7))
            preview.pack_propagate(False)

            foto = _criar_photo_preview(imagem)
            if foto is None:
                tk.Label(
                    preview,
                    text="Sem referência",
                    font=("Segoe UI", 9, "bold"),
                    fg=self.view.COR_TEXTO_3,
                    bg="#020617",
                ).pack(fill=tk.BOTH, expand=True)
                estado = "Não definida"
                cor_estado = self.view.COR_TEXTO_3
            else:
                fotos.append(foto)
                tk.Label(
                    preview,
                    image=foto,
                    bg="#020617",
                    bd=0,
                ).pack(fill=tk.BOTH, expand=True)
                estado = "Carregada"
                cor_estado = dados["cor"]

            tk.Button(
                card,
                text=dados["botao"],
                command=lambda valor=tipo, janela_config=janela: (
                    self._fechar_configuracoes_e_iniciar_referencia(
                        janela_config,
                        valor,
                    )
                ),
                font=("Segoe UI", 9, "bold"),
                bg=self.view.COR_CARD_2,
                fg=self.view.COR_TEXTO,
                activebackground=self.view.COR_NEUTRO,
                activeforeground=self.view.COR_TEXTO,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                padx=10,
                pady=7,
            ).pack(fill=tk.X, padx=8)

            tk.Label(
                card,
                text=estado,
                font=("Segoe UI", 8, "bold"),
                fg=cor_estado,
                bg=self.view.COR_CARD,
            ).pack(fill=tk.X, padx=8, pady=(5, 8))

        janela._odin_referencias_preview_tk = fotos

        try:
            from src.platform.display_theme import aplicar_tema_arvore

            aplicar_tema_arvore(corpo)
        except Exception:
            pass
        try:
            janela.update_idletasks()
        except Exception:
            pass

    def _fechar_configuracoes_e_iniciar_referencia(
        self,
        janela: tk.Toplevel,
        tipo: str,
    ) -> None:
        try:
            janela.grab_release()
        except Exception:
            pass
        try:
            janela.destroy()
        except Exception:
            pass
        self.root.after(80, lambda: self._abrir_captura_referencia(tipo))

    def carregar_referencia_led_aceso(self) -> None:
        self._abrir_captura_referencia("aceso")

    def carregar_referencia_led_apagado(self) -> None:
        self._abrir_captura_referencia("apagado")

    def carregar_referencia_led_pouca_luz(self) -> None:
        self._abrir_captura_referencia("pouca_luz")

    # ------------------------------------------------------------------
    # Integração direta com o editor de ROI usado por "Selecionar LEDs"
    # ------------------------------------------------------------------
    def _captura_referencia_ativa(self) -> bool:
        return (
            self._referencia_captura_tipo in _REFERENCIAS
            and str(getattr(self, "modo_atual", ""))
            == self.MODO_CAPTURA_REFERENCIA
        )

    def _modo_edicao_roi_ativo(self) -> bool:
        if self._captura_referencia_ativa():
            return True
        return super()._modo_edicao_roi_ativo()

    def _leds_editaveis(self):
        if self._captura_referencia_ativa():
            return list(getattr(self, "leds_selecionados", []) or ())
        return super()._leds_editaveis()

    def _substituir_leds_editaveis(self, leds) -> None:
        if not self._captura_referencia_ativa():
            super()._substituir_leds_editaveis(leds)
            return

        novos = [copiar_led(led) for led in (leds or ())]
        # Uma referência representa exatamente uma ROI. Se outra for criada,
        # a nova substitui a ROI temporária anterior.
        if len(novos) > 1:
            novos = [novos[-1]]
        self.leds_selecionados = novos
        self.resultados_led_atual = []

    def evento_clique_esquerdo(self, evento):
        if self._captura_referencia_ativa():
            self._congelar_frame_referencia()
        return super().evento_clique_esquerdo(evento)

    def _evento_soltar_roi(self, evento):
        # Segmentos passam integralmente pelo editor normal. O círculo precisa
        # apenas deste adaptador porque o clique legado do app reconhece somente
        # os modos de inspeção; toda edição posterior usa o mesmo editor normal.
        if (
            self._captura_referencia_ativa()
            and normalizar_tipo_roi(
                getattr(self, "tipo_roi_edicao", TIPO_ROI_CIRCULO)
            )
            == TIPO_ROI_CIRCULO
            and getattr(self, "_area_roi_mode", None) == "pending_marquee"
        ):
            self._area_roi_mode = None
            coordenadas = self.view.converter_canvas_para_imagem_original(
                int(getattr(evento, "x", 0)),
                int(getattr(evento, "y", 0)),
            )
            if coordenadas is None:
                return "break"

            centro_x, centro_y = coordenadas
            raio = min(
                MAX_RADIUS_PX,
                max(
                    MIN_RADIUS_PX,
                    int(getattr(self, "raio_atual_px", MIN_RADIUS_PX)),
                ),
            )
            candidato = LedSelection(
                id="REF_CIRCULO",
                centro_x=int(centro_x),
                centro_y=int(centro_y),
                raio=int(raio),
                tipo_roi=TIPO_ROI_CIRCULO,
            )
            if not roi_dentro_imagem(
                candidato,
                int(getattr(self, "largura_original", 0) or 0),
                int(getattr(self, "altura_original", 0) or 0),
            ):
                self.view.atualizar_status(
                    "ROI de referência não criada: a geometria ultrapassa "
                    "os limites da imagem."
                )
                return "break"

            self._substituir_leds_editaveis([candidato])
            selecionar = getattr(self, "_selecionar_ids", None)
            if callable(selecionar):
                selecionar([candidato.id], mensagem=False)
            atualizar_pos = getattr(self, "_atualizar_pos_edicao_roi", None)
            if callable(atualizar_pos):
                atualizar_pos()
            self.view.desenhar_canvas(
                self.leds_selecionados,
                self.resultados_led_atual,
            )
            self.view.atualizar_status(
                "ROI circular da referência criada. Ajuste como em "
                "Selecionar LEDs e clique em OK."
            )
            return "break"

        return super()._evento_soltar_roi(evento)

    def _congelar_frame_referencia(self) -> None:
        if not self._captura_referencia_ativa():
            return
        if self._referencia_captura_frame is not None:
            return

        frame = None
        if bool(getattr(self, "camera_ativa", False)):
            camera_frame = getattr(self, "camera_frame_atual", None)
            if camera_frame is not None:
                frame = camera_frame.copy()
        if frame is None:
            imagem = getattr(self, "imagem_original", None)
            if imagem is not None:
                frame = imagem.copy()
        if frame is None:
            return

        self._referencia_captura_frame = frame
        self.imagem_original = frame.copy()
        self.altura_original, self.largura_original = frame.shape[:2]

        # Enquanto a ROI é desenhada/editada, o frame não muda sob ela.
        if bool(getattr(self, "camera_ativa", False)):
            self.camera_em_pausa_analise = True

    def _abrir_captura_referencia(self, tipo: str) -> None:
        if tipo not in _REFERENCIAS:
            return
        if bool(getattr(self, "_selecao_tela_cheia_esta_aberta", lambda: False)()):
            return

        imagem = getattr(self, "imagem_original", None)
        if imagem is None:
            messagebox.showwarning(
                "Atenção",
                "Ative a câmera ou carregue uma imagem antes de criar a referência.",
            )
            return

        if (
            bool(getattr(self, "camera_ativa", False))
            and getattr(self, "camera_frame_atual", None) is None
        ):
            messagebox.showwarning(
                "Atenção",
                "Aguarde a câmera exibir uma imagem antes de criar a referência.",
            )
            return

        self._referencia_captura_estado_anterior = {
            "modo_atual": getattr(self, "modo_atual", "ocioso"),
            "camera_em_pausa_analise": bool(
                getattr(self, "camera_em_pausa_analise", False)
            ),
            "guias_leds_fixos_visiveis": bool(
                getattr(self, "guias_leds_fixos_visiveis", True)
            ),
            "selecao_manual_camera_ativa": bool(
                getattr(self, "selecao_manual_camera_ativa", False)
            ),
            "selecao_manual_camera_visivel": bool(
                getattr(self.view, "selecao_manual_camera_visivel", False)
            ),
            "selecao_led_ativa": bool(
                getattr(self.view, "selecao_led_ativa", False)
            ),
            "leds_selecionados": copy.deepcopy(
                getattr(self, "leds_selecionados", [])
            ),
            "leds_manuais_camera": copy.deepcopy(
                getattr(self, "leds_manuais_camera", [])
            ),
            "resultados_led_atual": copy.deepcopy(
                getattr(self, "resultados_led_atual", [])
            ),
            "imagem_original": imagem.copy(),
            "caminho_imagem_atual": getattr(self, "caminho_imagem_atual", None),
            "largura_original": int(getattr(self, "largura_original", 0) or 0),
            "altura_original": int(getattr(self, "altura_original", 0) or 0),
            "tipo_roi_edicao": getattr(self, "tipo_roi_edicao", None),
        }

        self._referencia_captura_tipo = tipo
        self._referencia_captura_frame = None
        self._referencia_salvando = False
        self.modo_atual = self.MODO_CAPTURA_REFERENCIA
        self.guias_leds_fixos_visiveis = False
        self.selecao_manual_camera_ativa = False
        self.leds_selecionados = []
        self.resultados_led_atual = []
        self.view.selecao_manual_camera_visivel = False
        self.view.atualizar_estado_selecao_led(True)

        resetar = getattr(self, "_resetar_editor_roi", None)
        if callable(resetar):
            resetar()

        # Reutiliza literalmente a mesma janela, toolbar e bindings de
        # "Selecionar LEDs": Segmento/Círculo, alças, rotação, zoom e pan.
        self._abrir_selecao_tela_cheia()

        janela = getattr(self, "_selecao_tela_cheia_window", None)
        if janela is None:
            self._restaurar_estado_apos_referencia()
            return

        dados = _REFERENCIAS[tipo]
        try:
            janela.title(f"ODIN • {dados['botao']} • Seleção de ROI")
            janela.protocol(
                "WM_DELETE_WINDOW",
                self._cancelar_captura_referencia,
            )
        except Exception:
            pass

        self.view.atualizar_status(
            f"{dados['botao']}: desenhe uma única ROI exatamente como em "
            "Selecionar LEDs e clique em OK."
        )

    def _confirmar_selecao_tela_cheia(self) -> None:
        if not self._captura_referencia_ativa():
            super()._confirmar_selecao_tela_cheia()
            return
        self._confirmar_captura_referencia()

    # ------------------------------------------------------------------
    # Confirmação, persistência e retorno às Configurações
    # ------------------------------------------------------------------
    def _confirmar_captura_referencia(self) -> None:
        if self._referencia_salvando:
            return

        tipo = self._referencia_captura_tipo
        rois = list(getattr(self, "leds_selecionados", []) or ())
        if tipo not in _REFERENCIAS or len(rois) != 1:
            messagebox.showwarning(
                "Atenção",
                "Desenhe exatamente uma ROI que será usada como referência "
                "antes de clicar em OK.",
            )
            return

        self._congelar_frame_referencia()
        frame = self._referencia_captura_frame
        if frame is None:
            messagebox.showerror(
                "Erro",
                "Não foi possível congelar a imagem usada pela referência.",
            )
            return

        roi = copiar_led(rois[0])
        if not roi_dentro_imagem(roi, int(frame.shape[1]), int(frame.shape[0])):
            messagebox.showerror(
                "Erro",
                "A ROI de referência ultrapassa os limites da imagem.",
            )
            return

        recorte = recortar_referencia_roi(frame, roi)
        if recorte is None:
            messagebox.showerror(
                "Erro",
                "Não foi possível gerar a preview da ROI selecionada.",
            )
            return

        # Aqui está a mudança central: as features vêm da mesma geometria
        # exata selecionada pelo editor normal, inclusive segmento/ângulo.
        features = extrair_features_selecao(frame, roi)
        dados = _REFERENCIAS[tipo]
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        caminho = CONFIG_DIR / dados["arquivo"]

        self._referencia_salvando = True
        try:
            if not cv2.imwrite(str(caminho), recorte):
                raise RuntimeError("não foi possível gravar a imagem da referência")

            setattr(self, dados["imagem_attr"], recorte)
            setattr(self, dados["caminho_attr"], str(caminho))
            setattr(self, dados["features_attr"], features)

            self._persistir_referencia_individual(
                dados["config_key"],
                caminho,
                features,
                roi,
            )
        except Exception as erro:
            self._referencia_salvando = False
            messagebox.showerror(
                "Erro",
                f"Não foi possível salvar a referência: {erro}",
            )
            return

        self._encerrar_captura_referencia(
            reabrir_configuracoes=True,
            status=f"{dados['botao']} atualizada e salva automaticamente.",
        )

    def _persistir_referencia_individual(
        self,
        chave_referencia: str,
        caminho: Path,
        features,
        roi: LedSelection,
    ) -> None:
        existente = self.config_repository.carregar_configuracao_existente_sem_alerta()
        settings_padrao = {
            "save_analysis_results": bool(
                getattr(self, "salvar_resultados_analise", False)
            ),
            "camera": self.config_repository.obter_configuracoes_camera(),
        }
        configuracao = atualizar_configuracao_referencia(
            configuracao=existente,
            chave_referencia=chave_referencia,
            caminho_imagem=str(caminho),
            features=features.to_dict(),
            raio_atual_px=int(getattr(self, "raio_atual_px", MIN_RADIUS_PX)),
            settings_padrao=settings_padrao,
            roi=roi.to_dict(),
        )
        arquivo = Path(self.config_repository.config_file)
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with open(arquivo, "w", encoding="utf-8") as destino:
            json.dump(
                configuracao,
                destino,
                indent=4,
                ensure_ascii=False,
            )
        self.configuracao_atual = configuracao

    def _cancelar_captura_referencia(self) -> None:
        if not self._captura_referencia_ativa():
            return
        self._encerrar_captura_referencia(
            reabrir_configuracoes=True,
            status="Captura de referência cancelada.",
        )

    def _encerrar_captura_referencia(
        self,
        reabrir_configuracoes: bool,
        status: str | None = None,
    ) -> None:
        # Fecha a mesma janela de Selecionar LEDs sem executar o comportamento
        # normal do OK, que alternaria o modo de inspeção.
        if bool(getattr(self, "_selecao_tela_cheia_esta_aberta", lambda: False)()):
            super()._fechar_interface_selecao_tela_cheia()

        self._restaurar_estado_apos_referencia()
        self._referencia_salvando = False

        if status:
            self.view.atualizar_status(status)
        self.atualizar_painel_inicial()

        if reabrir_configuracoes:
            self.root.after(140, self.abrir_configuracoes)

    def _restaurar_estado_apos_referencia(self) -> None:
        estado = self._referencia_captura_estado_anterior or {}

        self._referencia_captura_tipo = None
        self._referencia_captura_frame = None
        self._referencia_captura_estado_anterior = None

        self.modo_atual = estado.get("modo_atual", "ocioso")
        self.camera_em_pausa_analise = bool(
            estado.get("camera_em_pausa_analise", False)
        )
        self.guias_leds_fixos_visiveis = bool(
            estado.get("guias_leds_fixos_visiveis", True)
        )
        self.selecao_manual_camera_ativa = bool(
            estado.get("selecao_manual_camera_ativa", False)
        )
        self.leds_selecionados = copy.deepcopy(
            estado.get("leds_selecionados", [])
        )
        self.leds_manuais_camera = copy.deepcopy(
            estado.get("leds_manuais_camera", [])
        )
        self.resultados_led_atual = copy.deepcopy(
            estado.get("resultados_led_atual", [])
        )
        self.view.selecao_manual_camera_visivel = bool(
            estado.get("selecao_manual_camera_visivel", False)
        )
        self.view.atualizar_estado_selecao_led(
            bool(estado.get("selecao_led_ativa", False))
        )

        tipo_anterior = estado.get("tipo_roi_edicao")
        if tipo_anterior is not None:
            self.tipo_roi_edicao = tipo_anterior

        imagem_restaurada = estado.get("imagem_original")
        if (
            bool(getattr(self, "camera_ativa", False))
            and not self.camera_em_pausa_analise
            and getattr(self, "camera_frame_atual", None) is not None
        ):
            imagem_restaurada = self.camera_frame_atual.copy()

        self.imagem_original = imagem_restaurada
        self.caminho_imagem_atual = estado.get(
            "caminho_imagem_atual",
            getattr(self, "caminho_imagem_atual", None),
        )
        self.largura_original = int(estado.get("largura_original", 0) or 0)
        self.altura_original = int(estado.get("altura_original", 0) or 0)

        if self.imagem_original is not None:
            self.altura_original, self.largura_original = self.imagem_original.shape[:2]
            self.view.preparar_imagem_para_exibicao(self.imagem_original)
            self.view.desenhar_canvas(
                self.leds_selecionados,
                self.resultados_led_atual,
            )

        resetar = getattr(self, "_resetar_editor_roi", None)
        if callable(resetar):
            resetar()

        try:
            self.root.focus_force()
        except Exception:
            pass
