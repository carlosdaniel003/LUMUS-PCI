from __future__ import annotations

import math
import re
import tkinter as tk
from dataclasses import fields
from pathlib import Path
from tkinter import messagebox
from uuid import uuid4

import cv2

from config import CONFIG_DIR
from src.core.feature_extractor import extrair_features_selecao
from src.core.roi_geometry import roi_dentro_imagem
from src.models.led_features import LedFeatures
from src.platform.bulk_roi_editor import copiar_led
from src.platform.reference_capture import (
    _REFERENCIAS,
    _criar_photo_preview,
    _encontrar_corpo_referencias,
    recortar_referencia_roi,
)
from src.platform.reference_project_store import (
    MAX_REFERENCIAS_POR_ESTADO,
    LimiteReferenciasError,
    escrever_configuracao,
    mover_escopo_referencia,
    normalizar_biblioteca_referencias,
    obter_referencias_ativas,
    remover_amostra_referencia,
    salvar_amostra_referencia,
    sincronizar_espelho_legado,
)


_TIPO_STORE = {
    "aceso": "on",
    "apagado": "off",
    "pouca_luz": "low_light",
}

_ATTRS_REFERENCIA = {
    "aceso": (
        "imagem_referencia_acesa",
        "caminho_referencia_acesa",
        "features_referencia_acesa",
        "referencias_acesas_ativas",
    ),
    "apagado": (
        "imagem_referencia_apagada",
        "caminho_referencia_apagada",
        "features_referencia_apagada",
        "referencias_apagadas_ativas",
    ),
    "pouca_luz": (
        "imagem_referencia_pouca_luz",
        "caminho_referencia_pouca_luz",
        "features_referencia_pouca_luz",
        "referencias_pouca_luz_ativas",
    ),
}


def agregar_features_referencias(amostras: list[dict]) -> LedFeatures | None:
    """Cria o centróide das referências ativas sem mudar o classificador legado."""
    objetos = []
    for entrada in amostras or ():
        sample = entrada.get("sample", entrada) if isinstance(entrada, dict) else {}
        features = sample.get("features", {}) if isinstance(sample, dict) else {}
        if isinstance(features, dict) and features:
            objetos.append(LedFeatures.from_dict(features))
    if not objetos:
        return None

    valores = {}
    campos_inteiros = {"area_pixels", "inner_area_pixels", "ring_area_pixels"}
    for campo in fields(LedFeatures):
        nome = campo.name
        numeros = [float(getattr(item, nome, 0.0)) for item in objetos]
        if nome == "h_mean":
            # Hue do OpenCV é circular em 0..179. Média circular evita que
            # vermelho próximo de 0 e 179 gere um valor artificial no centro.
            senos = [math.sin((valor / 180.0) * 2.0 * math.pi) for valor in numeros]
            cossenos = [math.cos((valor / 180.0) * 2.0 * math.pi) for valor in numeros]
            angulo = math.atan2(sum(senos) / len(senos), sum(cossenos) / len(cossenos))
            if angulo < 0:
                angulo += 2.0 * math.pi
            media = (angulo / (2.0 * math.pi)) * 180.0
        else:
            media = sum(numeros) / len(numeros)
        valores[nome] = int(round(media)) if nome in campos_inteiros else float(media)
    return LedFeatures(**valores)


def _slug_arquivo(valor: str | None) -> str:
    texto = re.sub(r"[^A-Za-z0-9_-]+", "_", str(valor or "").strip())
    texto = texto.strip("_")
    return texto.lower() or "sem_projeto"


class ProjectReferenceSetsMixin:
    """Liga até três referências por estado ao mesmo projeto de Carregar LEDs."""

    def __init__(self, *args, **kwargs) -> None:
        self._referencias_ativas_por_tipo = {
            "aceso": [],
            "apagado": [],
            "pouca_luz": [],
        }
        self._referencia_captura_alvo = None
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Projeto ativo e carregamento das referências
    # ------------------------------------------------------------------
    def _projeto_referencia_ativo(self) -> str:
        repository = getattr(self, "config_repository", None)
        obter = getattr(repository, "obter_projeto_led_ativo", None)
        if callable(obter):
            try:
                return str(obter() or "").strip()
            except Exception:
                pass
        return str(getattr(self, "projeto_led_ativo", "") or "").strip()

    def carregar_referencias_automaticamente_se_necessario(self) -> None:
        self._carregar_referencias_contexto_ativo(persistir_migracao=True)

    def _carregar_referencias_contexto_ativo(
        self,
        persistir_migracao: bool = True,
    ) -> None:
        repository = getattr(self, "config_repository", None)
        if repository is None:
            return

        original = repository.carregar_configuracao_existente_sem_alerta()
        configuracao, _ = normalizar_biblioteca_referencias(original)
        projeto = self._projeto_referencia_ativo()
        configuracao = sincronizar_espelho_legado(configuracao, projeto)

        if persistir_migracao and configuracao != original:
            escrever_configuracao(repository, configuracao)

        self.configuracao_atual = configuracao
        for tipo, store_tipo in _TIPO_STORE.items():
            entradas = obter_referencias_ativas(
                configuracao,
                projeto,
                store_tipo,
            )
            self._referencias_ativas_por_tipo[tipo] = entradas

            imagem_attr, caminho_attr, features_attr, lista_attr = _ATTRS_REFERENCIA[tipo]
            setattr(self, lista_attr, entradas)
            features_agregadas = agregar_features_referencias(entradas)
            setattr(self, features_attr, features_agregadas)

            caminho = None
            imagem = None
            for entrada in entradas:
                sample = entrada.get("sample", {})
                caminho_teste = sample.get("image_path")
                if caminho is None and caminho_teste:
                    caminho = str(caminho_teste)
                if imagem is None and caminho_teste:
                    imagem = self.recarregar_imagem_referencia(caminho_teste)
            setattr(self, caminho_attr, caminho)
            setattr(self, imagem_attr, imagem)

    def referencias_disponiveis(self) -> bool:
        return (
            getattr(self, "features_referencia_acesa", None) is not None
            and getattr(self, "features_referencia_apagada", None) is not None
        )

    def carregar_leds_fixos(self) -> None:
        resultado = super().carregar_leds_fixos()
        self._carregar_referencias_contexto_ativo(persistir_migracao=True)
        return resultado

    def _sincronizar_projeto_ativo_apos_gestao(self, *args, **kwargs):
        resultado = super()._sincronizar_projeto_ativo_apos_gestao(*args, **kwargs)
        self._carregar_referencias_contexto_ativo(persistir_migracao=True)
        return resultado

    # ------------------------------------------------------------------
    # Configurações: três slots por estado, sem seletor de projeto próprio
    # ------------------------------------------------------------------
    def abrir_configuracoes(self) -> None:
        self._carregar_referencias_contexto_ativo(persistir_migracao=True)
        super().abrir_configuracoes()
        janela = self._encontrar_janela_configuracoes_aberta()
        if janela is not None:
            self._reconstruir_referencias_configuracoes(janela)

    def _reconstruir_referencias_configuracoes(self, janela: tk.Toplevel) -> None:
        corpo = _encontrar_corpo_referencias(janela)
        if corpo is None:
            return

        for filho in tuple(corpo.winfo_children()):
            try:
                filho.destroy()
            except Exception:
                pass

        projeto = self._projeto_referencia_ativo()
        projeto_texto = projeto or "SEM PROJETO"

        tk.Label(
            corpo,
            text=f"Projeto ativo: {projeto_texto}",
            font=("Segoe UI", 10, "bold"),
            fg=self.view.COR_TEXTO,
            bg=self.view.COR_CARD_2,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 3))

        tk.Label(
            corpo,
            text=(
                "As referências pertencem ao mesmo projeto de Carregar LEDs. "
                "Para mudar o projeto das referências, mude o projeto em Carregar LEDs. "
                "Cada estado aceita até 3 amostras ativas. Uma amostra GLOBAL "
                "serve automaticamente para todos os projetos."
            ),
            font=("Segoe UI", 9),
            fg=self.view.COR_TEXTO_2,
            bg=self.view.COR_CARD_2,
            wraplength=690,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 10))

        grade = tk.Frame(corpo, bg=self.view.COR_CARD_2)
        grade.pack(fill=tk.X, padx=12, pady=(0, 12))
        for coluna in range(3):
            grade.grid_columnconfigure(coluna, weight=1, uniform="refs_multi")

        fotos = []
        for coluna, tipo in enumerate(("aceso", "apagado", "pouca_luz")):
            dados = _REFERENCIAS[tipo]
            entradas = list(self._referencias_ativas_por_tipo.get(tipo, []))
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

            tk.Label(
                card,
                text=f"{dados['botao']}  {len(entradas)}/{MAX_REFERENCIAS_POR_ESTADO}",
                font=("Segoe UI", 9, "bold"),
                fg=dados["cor"],
                bg=self.view.COR_CARD,
                anchor="w",
            ).pack(fill=tk.X, padx=8, pady=(8, 5))

            for posicao, entrada in enumerate(entradas, start=1):
                sample = entrada.get("sample", {})
                scope = entrada.get("scope", "project")
                indice = int(entrada.get("index", posicao - 1))
                caminho = sample.get("image_path")
                imagem = self.recarregar_imagem_referencia(caminho)

                slot = tk.Frame(
                    card,
                    bg=self.view.COR_CARD_2,
                    highlightthickness=1,
                    highlightbackground=self.view.COR_BORDA,
                )
                slot.pack(fill=tk.X, padx=8, pady=(0, 7))

                cab = tk.Frame(slot, bg=self.view.COR_CARD_2)
                cab.pack(fill=tk.X, padx=5, pady=(4, 2))
                tk.Label(
                    cab,
                    text=f"#{posicao}",
                    font=("Segoe UI", 8, "bold"),
                    fg=self.view.COR_TEXTO_2,
                    bg=self.view.COR_CARD_2,
                ).pack(side=tk.LEFT)
                tk.Label(
                    cab,
                    text="GLOBAL" if scope == "global" else "PROJETO",
                    font=("Segoe UI", 7, "bold"),
                    fg=dados["cor"] if scope == "global" else self.view.COR_TEXTO_3,
                    bg=self.view.COR_CARD_2,
                ).pack(side=tk.RIGHT)

                preview = tk.Frame(
                    slot,
                    bg="#020617",
                    height=62,
                    highlightthickness=0,
                )
                preview.pack(fill=tk.X, padx=5)
                preview.pack_propagate(False)
                foto = _criar_photo_preview(imagem, largura_max=150, altura_max=54)
                if foto is not None:
                    fotos.append(foto)
                    tk.Label(preview, image=foto, bg="#020617", bd=0).pack(
                        fill=tk.BOTH, expand=True
                    )
                else:
                    tk.Label(
                        preview,
                        text="Preview indisponível",
                        font=("Segoe UI", 7),
                        fg=self.view.COR_TEXTO_3,
                        bg="#020617",
                    ).pack(fill=tk.BOTH, expand=True)

                acoes = tk.Frame(slot, bg=self.view.COR_CARD_2)
                acoes.pack(fill=tk.X, padx=5, pady=4)
                tk.Button(
                    acoes,
                    text="Editar",
                    command=lambda t=tipo, s=scope, i=indice, j=janela: (
                        self._fechar_configuracoes_e_capturar_slot(j, t, s, i)
                    ),
                    font=("Segoe UI", 7, "bold"),
                    bg=self.view.COR_CARD,
                    fg=self.view.COR_TEXTO,
                    relief=tk.FLAT,
                    bd=0,
                    cursor="hand2",
                    padx=5,
                    pady=3,
                ).pack(side=tk.LEFT)
                tk.Button(
                    acoes,
                    text="Tudo: SIM" if scope == "global" else "Tudo: NÃO",
                    command=lambda t=tipo, s=scope, i=indice, j=janela: (
                        self._alternar_escopo_referencia(j, t, s, i)
                    ),
                    font=("Segoe UI", 7, "bold"),
                    bg=self.view.COR_CARD,
                    fg=dados["cor"] if scope == "global" else self.view.COR_TEXTO_3,
                    relief=tk.FLAT,
                    bd=0,
                    cursor="hand2",
                    padx=5,
                    pady=3,
                ).pack(side=tk.LEFT, padx=3)
                tk.Button(
                    acoes,
                    text="×",
                    command=lambda t=tipo, s=scope, i=indice, j=janela: (
                        self._remover_referencia_slot(j, t, s, i)
                    ),
                    font=("Segoe UI", 8, "bold"),
                    bg=self.view.COR_CARD,
                    fg="#FCA5A5",
                    relief=tk.FLAT,
                    bd=0,
                    cursor="hand2",
                    padx=6,
                    pady=3,
                ).pack(side=tk.RIGHT)

            if len(entradas) < MAX_REFERENCIAS_POR_ESTADO:
                botoes_add = tk.Frame(card, bg=self.view.COR_CARD)
                botoes_add.pack(fill=tk.X, padx=8, pady=(0, 8))
                estado_projeto = tk.NORMAL if projeto else tk.DISABLED
                tk.Button(
                    botoes_add,
                    text="+ Projeto",
                    state=estado_projeto,
                    command=lambda t=tipo, j=janela: (
                        self._fechar_configuracoes_e_capturar_slot(j, t, "project", None)
                    ),
                    font=("Segoe UI", 7, "bold"),
                    bg=self.view.COR_CARD_2,
                    fg=self.view.COR_TEXTO,
                    disabledforeground=self.view.COR_TEXTO_3,
                    relief=tk.FLAT,
                    bd=0,
                    cursor="hand2",
                    padx=5,
                    pady=4,
                ).pack(side=tk.LEFT, fill=tk.X, expand=True)
                tk.Button(
                    botoes_add,
                    text="+ Global",
                    command=lambda t=tipo, j=janela: (
                        self._fechar_configuracoes_e_capturar_slot(j, t, "global", None)
                    ),
                    font=("Segoe UI", 7, "bold"),
                    bg=self.view.COR_CARD_2,
                    fg=dados["cor"],
                    relief=tk.FLAT,
                    bd=0,
                    cursor="hand2",
                    padx=5,
                    pady=4,
                ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

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

    def _fechar_configuracoes_e_capturar_slot(
        self,
        janela: tk.Toplevel,
        tipo: str,
        scope: str,
        index: int | None,
    ) -> None:
        try:
            janela.grab_release()
        except Exception:
            pass
        try:
            janela.destroy()
        except Exception:
            pass
        self.root.after(
            80,
            lambda: self._abrir_captura_referencia(tipo, scope=scope, index=index),
        )

    def _alternar_escopo_referencia(
        self,
        janela: tk.Toplevel,
        tipo: str,
        scope: str,
        index: int,
    ) -> None:
        projeto = self._projeto_referencia_ativo()
        if scope == "global" and not projeto:
            messagebox.showwarning(
                "Projeto necessário",
                "Carregue um projeto de LEDs antes de transformar a referência global em referência de projeto.",
                parent=janela,
            )
            return
        repository = self.config_repository
        configuracao = repository.carregar_configuracao_existente_sem_alerta()
        try:
            configuracao = mover_escopo_referencia(
                configuracao,
                projeto,
                _TIPO_STORE[tipo],
                scope,
                index,
            )
        except (LimiteReferenciasError, ValueError, IndexError) as erro:
            messagebox.showwarning("Limite de referências", str(erro), parent=janela)
            return

        configuracao = sincronizar_espelho_legado(configuracao, projeto)
        escrever_configuracao(repository, configuracao)
        self._carregar_referencias_contexto_ativo(persistir_migracao=False)
        self._reconstruir_referencias_configuracoes(janela)
        self.view.atualizar_status(
            "Referência agora serve para todos os projetos."
            if scope != "global"
            else f"Referência agora pertence somente ao projeto {projeto}."
        )

    def _remover_referencia_slot(
        self,
        janela: tk.Toplevel,
        tipo: str,
        scope: str,
        index: int,
    ) -> None:
        dados = _REFERENCIAS[tipo]
        if not messagebox.askyesno(
            "Remover referência",
            f"Remover esta amostra de {dados['botao']}?",
            parent=janela,
        ):
            return

        projeto = self._projeto_referencia_ativo()
        repository = self.config_repository
        configuracao = repository.carregar_configuracao_existente_sem_alerta()
        configuracao, removida = remover_amostra_referencia(
            configuracao,
            projeto,
            _TIPO_STORE[tipo],
            scope,
            index,
        )
        if removida is None:
            return
        configuracao = sincronizar_espelho_legado(configuracao, projeto)
        escrever_configuracao(repository, configuracao)
        self._carregar_referencias_contexto_ativo(persistir_migracao=False)
        self._reconstruir_referencias_configuracoes(janela)
        self.view.atualizar_status(f"{dados['botao']} removida.")

    # ------------------------------------------------------------------
    # Captura: reutiliza o editor normal, mas salva no slot correto
    # ------------------------------------------------------------------
    def _abrir_captura_referencia(
        self,
        tipo: str,
        scope: str | None = None,
        index: int | None = None,
    ) -> None:
        if scope is None:
            scope = "project" if self._projeto_referencia_ativo() else "global"
        self._referencia_captura_alvo = {
            "scope": "global" if scope == "global" else "project",
            "index": index,
        }
        super()._abrir_captura_referencia(tipo)

        janela = getattr(self, "_selecao_tela_cheia_window", None)
        if janela is not None and tipo in _REFERENCIAS:
            destino = "GLOBAL" if self._referencia_captura_alvo["scope"] == "global" else self._projeto_referencia_ativo()
            try:
                janela.title(
                    f"ODIN • {_REFERENCIAS[tipo]['botao']} • {destino} • Seleção de ROI"
                )
            except Exception:
                pass

    def _amostra_alvo_existente(self, tipo: str, scope: str, index: int | None):
        if index is None:
            return None
        for entrada in self._referencias_ativas_por_tipo.get(tipo, []):
            if entrada.get("scope") == scope and int(entrada.get("index", -1)) == int(index):
                return entrada.get("sample")
        return None

    def _confirmar_captura_referencia(self) -> None:
        if getattr(self, "_referencia_salvando", False):
            return

        tipo = getattr(self, "_referencia_captura_tipo", None)
        rois = list(getattr(self, "leds_selecionados", []) or ())
        if tipo not in _REFERENCIAS or len(rois) != 1:
            messagebox.showwarning(
                "Atenção",
                "Desenhe exatamente uma ROI de referência antes de clicar em OK.",
            )
            return

        self._congelar_frame_referencia()
        frame = getattr(self, "_referencia_captura_frame", None)
        if frame is None:
            messagebox.showerror("Erro", "Não foi possível congelar a imagem usada pela referência.")
            return

        roi = copiar_led(rois[0])
        if not roi_dentro_imagem(roi, int(frame.shape[1]), int(frame.shape[0])):
            messagebox.showerror("Erro", "A ROI de referência ultrapassa os limites da imagem.")
            return

        recorte = recortar_referencia_roi(frame, roi)
        if recorte is None:
            messagebox.showerror("Erro", "Não foi possível gerar a preview da ROI selecionada.")
            return

        alvo = dict(self._referencia_captura_alvo or {})
        scope = "global" if alvo.get("scope") == "global" else "project"
        index = alvo.get("index")
        projeto = self._projeto_referencia_ativo()
        if scope == "project" and not projeto:
            messagebox.showwarning(
                "Projeto necessário",
                "Carregue ou crie um projeto em Carregar LEDs antes de salvar uma referência de projeto.",
            )
            return

        existente = self._amostra_alvo_existente(tipo, scope, index)
        id_amostra = str((existente or {}).get("id") or uuid4().hex)
        caminho_existente = str((existente or {}).get("image_path") or "")
        if caminho_existente:
            caminho = Path(caminho_existente)
        else:
            destino_slug = "global" if scope == "global" else _slug_arquivo(projeto)
            caminho = CONFIG_DIR / (
                f"reference_{destino_slug}_{_TIPO_STORE[tipo]}_{id_amostra[:10]}.png"
            )

        features = extrair_features_selecao(frame, roi)
        amostra = {
            "id": id_amostra,
            "image_path": str(caminho),
            "features": features.to_dict(),
            "roi": roi.to_dict(),
        }

        repository = self.config_repository
        configuracao = repository.carregar_configuracao_existente_sem_alerta()
        try:
            configuracao = salvar_amostra_referencia(
                configuracao,
                projeto,
                _TIPO_STORE[tipo],
                amostra,
                scope=scope,
                index=index,
            )
        except (LimiteReferenciasError, ValueError, IndexError) as erro:
            messagebox.showwarning("Limite de referências", str(erro))
            return

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._referencia_salvando = True
        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(caminho), recorte):
                raise RuntimeError("não foi possível gravar a imagem da referência")
            configuracao = sincronizar_espelho_legado(configuracao, projeto)
            escrever_configuracao(repository, configuracao)
            self.configuracao_atual = configuracao
            self._carregar_referencias_contexto_ativo(persistir_migracao=False)
        except Exception as erro:
            self._referencia_salvando = False
            messagebox.showerror("Erro", f"Não foi possível salvar a referência: {erro}")
            return

        total = len(self._referencias_ativas_por_tipo.get(tipo, []))
        escopo_texto = "global" if scope == "global" else f"do projeto {projeto}"
        self._encerrar_captura_referencia(
            reabrir_configuracoes=True,
            status=(
                f"{_REFERENCIAS[tipo]['botao']} salva como referência {escopo_texto}. "
                f"Ativas: {total}/{MAX_REFERENCIAS_POR_ESTADO}."
            ),
        )

    def _restaurar_estado_apos_referencia(self) -> None:
        super()._restaurar_estado_apos_referencia()
        self._referencia_captura_alvo = None
