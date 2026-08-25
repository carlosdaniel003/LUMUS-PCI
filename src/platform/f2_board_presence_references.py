from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk

import cv2
import numpy as np

from config import CONFIG_DIR
from src.platform.reference_capture import (
    _criar_photo_preview,
    _encontrar_corpo_referencias,
)
from src.platform.reference_project_store import escrever_configuracao


F2_BOARD_PRESENCE_KEY = "board_presence_references"
F2_BOARD_REF_BOARD_ON = "board_on"
F2_BOARD_REF_BOARD_OFF = "board_off"
F2_BOARD_REF_EMPTY = "empty_support"
F2_BOARD_REF_SLOTS = (
    F2_BOARD_REF_BOARD_ON,
    F2_BOARD_REF_BOARD_OFF,
    F2_BOARD_REF_EMPTY,
)

F2_BOARD_PRESENCE_PRESENT = "present"
F2_BOARD_PRESENCE_EMPTY = "empty"
F2_BOARD_PRESENCE_UNKNOWN = "unknown"
F2_BOARD_PRESENCE_UNAVAILABLE = "unavailable"

F2_BOARD_PRESENCE_COMPARE_WIDTH = 160
F2_BOARD_PRESENCE_COMPARE_HEIGHT = 120
F2_BOARD_PRESENCE_MARGIN = 0.025
F2_BOARD_PRESENCE_RATIO = 0.82

_SLOT_UI = {
    F2_BOARD_REF_BOARD_ON: {
        "title": "1. Placa fixa ligada",
        "short": "PLACA LIGADA",
        "color": "#22C55E",
    },
    F2_BOARD_REF_BOARD_OFF: {
        "title": "2. Placa fixa desligada",
        "short": "PLACA DESLIGADA",
        "color": "#F59E0B",
    },
    F2_BOARD_REF_EMPTY: {
        "title": "3. Placa fora do suporte",
        "short": "SUPORTE VAZIO",
        "color": "#60A5FA",
    },
}

_PATCH_PRESERVACAO_INSTALADO = False


def _normalizar_nome_projeto(nome: str | None) -> str:
    return re.sub(r"\s+", " ", str(nome or "").strip()).upper()


def _slug(valor: str | None) -> str:
    texto = re.sub(r"[^A-Za-z0-9_-]+", "_", str(valor or "").strip())
    return texto.strip("_").lower() or "sem_projeto"


def _normalizar_entrada(entrada) -> dict:
    if not isinstance(entrada, dict):
        return {}
    caminho = str(entrada.get("image_path") or "").strip()
    if not caminho:
        return {}
    try:
        width = int(entrada.get("width") or 0)
        height = int(entrada.get("height") or 0)
    except (TypeError, ValueError):
        width = height = 0
    return {
        "image_path": caminho,
        "width": max(0, width),
        "height": max(0, height),
        "updated_at": entrada.get("updated_at"),
    }


def normalizar_referencias_presenca(valor) -> dict[str, dict]:
    origem = valor if isinstance(valor, dict) else {}
    return {
        slot: _normalizar_entrada(origem.get(slot))
        for slot in F2_BOARD_REF_SLOTS
    }


def obter_referencias_presenca_projeto(
    configuracao: dict | None,
    projeto: str | None,
) -> dict[str, dict]:
    dados = configuracao if isinstance(configuracao, dict) else {}
    projetos = dados.get("led_projects", {})
    if not isinstance(projetos, dict):
        return normalizar_referencias_presenca({})
    nome = _normalizar_nome_projeto(projeto)
    projeto_dados = projetos.get(nome, {})
    if not isinstance(projeto_dados, dict):
        return normalizar_referencias_presenca({})
    return normalizar_referencias_presenca(
        projeto_dados.get(F2_BOARD_PRESENCE_KEY)
    )


def definir_referencia_presenca_projeto(
    configuracao: dict | None,
    projeto: str,
    slot: str,
    entrada: dict | None,
) -> dict:
    if slot not in F2_BOARD_REF_SLOTS:
        raise ValueError("slot de presença F2 inválido")
    dados = copy.deepcopy(configuracao) if isinstance(configuracao, dict) else {}
    projetos = dados.get("led_projects", {})
    if not isinstance(projetos, dict):
        projetos = {}
    nome = _normalizar_nome_projeto(projeto)
    if not nome or nome not in projetos or not isinstance(projetos[nome], dict):
        raise ValueError("carregue um projeto de LEDs antes de salvar a referência")

    projeto_dados = dict(projetos[nome])
    referencias = normalizar_referencias_presenca(
        projeto_dados.get(F2_BOARD_PRESENCE_KEY)
    )
    referencias[slot] = _normalizar_entrada(entrada)
    projeto_dados[F2_BOARD_PRESENCE_KEY] = referencias
    projeto_dados["updated_at"] = datetime.now(timezone.utc).isoformat()
    projetos[nome] = projeto_dados
    dados["led_projects"] = projetos
    return dados


def instalar_preservacao_referencias_presenca() -> None:
    """Preserva o novo campo quando o repositório normaliza/renomeia projetos."""
    global _PATCH_PRESERVACAO_INSTALADO
    if _PATCH_PRESERVACAO_INSTALADO:
        return

    import src.platform.led_project_repository as repository_module

    original = repository_module._normalizar_projetos

    def normalizar_com_presenca(configuracao: dict) -> dict:
        preservadas: dict[str, dict] = {}
        origem = configuracao.get("led_projects", {})
        if isinstance(origem, dict):
            for chave, dados in origem.items():
                if not isinstance(dados, dict):
                    continue
                nome = repository_module.normalizar_nome_projeto_led(
                    dados.get("name", chave)
                )
                if nome:
                    preservadas[nome] = normalizar_referencias_presenca(
                        dados.get(F2_BOARD_PRESENCE_KEY)
                    )

        projetos = original(configuracao)
        for nome, referencias in preservadas.items():
            if nome in projetos and isinstance(projetos[nome], dict):
                projetos[nome][F2_BOARD_PRESENCE_KEY] = referencias
        configuracao["led_projects"] = projetos
        return projetos

    repository_module._normalizar_projetos = normalizar_com_presenca
    _PATCH_PRESERVACAO_INSTALADO = True


class F2BoardPresenceClassifier:
    """Classifica a cena inteira como placa presente, suporte vazio ou ambígua."""

    def __init__(self) -> None:
        self._references: dict[str, np.ndarray] = {}

    @staticmethod
    def _prepare(frame) -> np.ndarray | None:
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        try:
            if len(frame.shape) == 2:
                gray = frame
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(
                gray,
                (F2_BOARD_PRESENCE_COMPARE_WIDTH, F2_BOARD_PRESENCE_COMPARE_HEIGHT),
                interpolation=cv2.INTER_AREA,
            )
            blurred = cv2.GaussianBlur(resized, (7, 7), 0)
            return cv2.equalizeHist(blurred)
        except Exception:
            return None

    def configure(self, images: dict[str, np.ndarray]) -> bool:
        prepared: dict[str, np.ndarray] = {}
        for slot in F2_BOARD_REF_SLOTS:
            image = images.get(slot)
            item = self._prepare(image)
            if item is None:
                self._references = {}
                return False
            prepared[slot] = item
        self._references = prepared
        return True

    @property
    def ready(self) -> bool:
        return all(slot in self._references for slot in F2_BOARD_REF_SLOTS)

    @staticmethod
    def _distance(current: np.ndarray, reference: np.ndarray) -> float:
        if current.shape != reference.shape:
            return 1.0
        intensity = float(np.mean(cv2.absdiff(current, reference))) / 255.0
        edges_current = cv2.Canny(current, 55, 145)
        edges_reference = cv2.Canny(reference, 55, 145)
        edge_distance = float(
            np.mean(cv2.absdiff(edges_current, edges_reference))
        ) / 255.0
        return (0.82 * intensity) + (0.18 * edge_distance)

    def classify(self, frame) -> tuple[str, dict[str, float]]:
        if not self.ready:
            return F2_BOARD_PRESENCE_UNAVAILABLE, {}
        current = self._prepare(frame)
        if current is None:
            return F2_BOARD_PRESENCE_UNKNOWN, {}

        distances = {
            slot: self._distance(current, self._references[slot])
            for slot in F2_BOARD_REF_SLOTS
        }
        present_distance = min(
            distances[F2_BOARD_REF_BOARD_ON],
            distances[F2_BOARD_REF_BOARD_OFF],
        )
        empty_distance = distances[F2_BOARD_REF_EMPTY]
        scores = {
            **distances,
            "present": present_distance,
            "empty": empty_distance,
        }

        if (
            empty_distance + F2_BOARD_PRESENCE_MARGIN < present_distance
            or empty_distance <= present_distance * F2_BOARD_PRESENCE_RATIO
        ):
            return F2_BOARD_PRESENCE_EMPTY, scores
        if (
            present_distance + F2_BOARD_PRESENCE_MARGIN < empty_distance
            or present_distance <= empty_distance * F2_BOARD_PRESENCE_RATIO
        ):
            return F2_BOARD_PRESENCE_PRESENT, scores
        return F2_BOARD_PRESENCE_UNKNOWN, scores


class F2BoardPresenceReferenceController:
    """Persistência, preview e classificação das 3 referências completas do F2."""

    def __init__(self, app) -> None:
        instalar_preservacao_referencias_presenca()
        self.app = app
        self.classifier = F2BoardPresenceClassifier()
        self._cache_project = ""
        self._cache_signature = None
        self._cache_ready = False
        self._cache_master_resolution: tuple[int, int] | None = None

    def invalidate(self) -> None:
        self._cache_project = ""
        self._cache_signature = None
        self._cache_ready = False
        self._cache_master_resolution = None
        self.classifier = F2BoardPresenceClassifier()

    def project_name(self) -> str:
        getter = getattr(self.app, "_projeto_referencia_ativo", None)
        if callable(getter):
            try:
                return _normalizar_nome_projeto(getter())
            except Exception:
                pass
        repository = getattr(self.app, "config_repository", None)
        getter = getattr(repository, "obter_projeto_led_ativo", None)
        if callable(getter):
            try:
                return _normalizar_nome_projeto(getter())
            except Exception:
                pass
        return _normalizar_nome_projeto(getattr(self.app, "projeto_led_ativo", ""))

    def master_resolution(self, projeto: str | None = None) -> tuple[int, int] | None:
        repository = getattr(self.app, "config_repository", None)
        getter = getattr(repository, "obter_resolucao_mestra_projeto_led", None)
        if not callable(getter):
            return None
        try:
            resolution = getter(projeto or self.project_name())
        except Exception:
            return None
        if not resolution or len(resolution) < 2:
            return None
        try:
            return max(1, int(resolution[0])), max(1, int(resolution[1]))
        except (TypeError, ValueError):
            return None

    def _entries(self, projeto: str) -> dict[str, dict]:
        repository = getattr(self.app, "config_repository", None)
        if repository is None:
            return normalizar_referencias_presenca({})
        config = repository.carregar_configuracao_existente_sem_alerta()
        return obter_referencias_presenca_projeto(config, projeto)

    @staticmethod
    def _signature(entries: dict[str, dict], resolution) -> tuple:
        return (
            resolution,
            tuple(
                (
                    slot,
                    entries.get(slot, {}).get("image_path"),
                    entries.get(slot, {}).get("updated_at"),
                )
                for slot in F2_BOARD_REF_SLOTS
            ),
        )

    def _ensure_classifier(self) -> bool:
        projeto = self.project_name()
        if not projeto:
            self.invalidate()
            return False
        resolution = self.master_resolution(projeto)
        entries = self._entries(projeto)
        signature = self._signature(entries, resolution)
        if (
            projeto == self._cache_project
            and signature == self._cache_signature
        ):
            return self._cache_ready

        images: dict[str, np.ndarray] = {}
        ready = resolution is not None
        for slot in F2_BOARD_REF_SLOTS:
            entry = entries.get(slot, {})
            path = str(entry.get("image_path") or "").strip()
            image = cv2.imread(path) if path else None
            if image is None:
                ready = False
                continue
            height, width = image.shape[:2]
            if resolution is not None and (width, height) != resolution:
                ready = False
                continue
            images[slot] = image

        self.classifier = F2BoardPresenceClassifier()
        if ready:
            ready = self.classifier.configure(images)
        self._cache_project = projeto
        self._cache_signature = signature
        self._cache_ready = bool(ready)
        self._cache_master_resolution = resolution
        return self._cache_ready

    @property
    def ready(self) -> bool:
        return self._ensure_classifier()

    def classify(self, frame) -> tuple[str, dict[str, float]]:
        if not self._ensure_classifier():
            return F2_BOARD_PRESENCE_UNAVAILABLE, {}
        resolution = self._cache_master_resolution
        if resolution is not None:
            try:
                height, width = frame.shape[:2]
            except Exception:
                return F2_BOARD_PRESENCE_UNKNOWN, {}
            if (int(width), int(height)) != resolution:
                return F2_BOARD_PRESENCE_UNKNOWN, {}
        return self.classifier.classify(frame)

    def _managed_path(self, projeto: str, slot: str) -> Path:
        directory = Path(CONFIG_DIR) / "f2_board_presence" / _slug(projeto)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{slot}.png"

    def _validate_image(
        self,
        image,
        parent,
    ) -> tuple[bool, tuple[int, int] | None]:
        if image is None or getattr(image, "size", 0) == 0:
            messagebox.showwarning(
                "Imagem inválida",
                "Não foi possível ler a imagem selecionada.",
                parent=parent,
            )
            return False, None
        resolution = self.master_resolution()
        if resolution is None:
            messagebox.showwarning(
                "Resolução do projeto",
                "O projeto ativo ainda não possui resolução mestre definida.",
                parent=parent,
            )
            return False, None
        height, width = image.shape[:2]
        if (int(width), int(height)) != resolution:
            messagebox.showwarning(
                "Resolução incompatível",
                (
                    f"O projeto usa {resolution[0]}x{resolution[1]}, mas a imagem possui "
                    f"{width}x{height}. Use uma imagem completa na mesma resolução do projeto."
                ),
                parent=parent,
            )
            return False, resolution
        return True, resolution

    def _save_image(self, slot: str, image, parent) -> bool:
        projeto = self.project_name()
        if not projeto:
            messagebox.showwarning(
                "Projeto necessário",
                "Carregue um projeto de LEDs antes de salvar estas referências.",
                parent=parent,
            )
            return False
        valid, resolution = self._validate_image(image, parent)
        if not valid or resolution is None:
            return False

        path = self._managed_path(projeto, slot)
        if not cv2.imwrite(str(path), image):
            messagebox.showerror(
                "Falha ao salvar",
                "Não foi possível salvar a referência completa do F2.",
                parent=parent,
            )
            return False

        repository = self.app.config_repository
        config = repository.carregar_configuracao_existente_sem_alerta()
        config = definir_referencia_presenca_projeto(
            config,
            projeto,
            slot,
            {
                "image_path": str(path),
                "width": resolution[0],
                "height": resolution[1],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        escrever_configuracao(repository, config)
        self.invalidate()
        atualizar = getattr(self.app.view, "atualizar_status", None)
        if callable(atualizar):
            atualizar(f"Referência F2 '{_SLOT_UI[slot]['short']}' salva no projeto {projeto}.")
        return True

    def capture_current(self, slot: str, window) -> None:
        frame = getattr(self.app, "camera_frame_atual", None)
        if frame is None or getattr(frame, "size", 0) == 0:
            messagebox.showwarning(
                "Câmera sem imagem",
                "A câmera ainda não possui um frame válido para capturar.",
                parent=window,
            )
            return
        if self._save_image(slot, frame.copy(), window):
            self.render_settings(window)

    def load_file(self, slot: str, window) -> None:
        path = filedialog.askopenfilename(
            parent=window,
            title=f"Selecionar {_SLOT_UI[slot]['title']}",
            filetypes=[
                ("Imagens", "*.png *.jpg *.jpeg *.bmp"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not path:
            return
        image = cv2.imread(path)
        if self._save_image(slot, image, window):
            self.render_settings(window)

    def remove(self, slot: str, window) -> None:
        projeto = self.project_name()
        if not projeto:
            return
        entries = self._entries(projeto)
        entry = entries.get(slot, {})
        if not entry:
            return
        if not messagebox.askyesno(
            "Remover referência",
            f"Remover '{_SLOT_UI[slot]['title']}' do projeto {projeto}?",
            parent=window,
        ):
            return
        repository = self.app.config_repository
        config = repository.carregar_configuracao_existente_sem_alerta()
        config = definir_referencia_presenca_projeto(
            config,
            projeto,
            slot,
            None,
        )
        escrever_configuracao(repository, config)
        path = str(entry.get("image_path") or "")
        try:
            managed_root = (Path(CONFIG_DIR) / "f2_board_presence").resolve()
            candidate = Path(path).resolve()
            if managed_root in candidate.parents and candidate.exists():
                candidate.unlink()
        except Exception:
            pass
        self.invalidate()
        self.render_settings(window)

    def render_settings(self, window) -> None:
        if window is None:
            return
        body = _encontrar_corpo_referencias(window)
        if body is None:
            return

        previous = getattr(window, "_odin_f2_board_presence_container", None)
        if previous is not None:
            try:
                previous.destroy()
            except Exception:
                pass

        view = self.app.view
        container = tk.Frame(body, bg=view.COR_CARD_2)
        container.pack(fill=tk.X, padx=12, pady=(2, 12))
        window._odin_f2_board_presence_container = container

        tk.Frame(container, bg="#172033", height=1).pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            container,
            text="Presença da placa — F2 automático",
            font=("Segoe UI", 10, "bold"),
            fg=view.COR_TEXTO,
            bg=view.COR_CARD_2,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))

        projeto = self.project_name()
        resolution = self.master_resolution(projeto) if projeto else None
        resolution_text = (
            f"{resolution[0]}x{resolution[1]}"
            if resolution is not None
            else "resolução mestre não definida"
        )
        tk.Label(
            container,
            text=(
                f"Projeto ativo: {projeto or 'SEM PROJETO'} • {resolution_text}. "
                "Salve três imagens completas da câmera: placa ligada, placa desligada e suporte vazio. "
                "Estas imagens pertencem somente a este projeto LED e são usadas para decidir presença/retirada da placa."
            ),
            font=("Segoe UI", 8),
            fg=view.COR_TEXTO_2,
            bg=view.COR_CARD_2,
            wraplength=690,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 9))

        entries = self._entries(projeto) if projeto else normalizar_referencias_presenca({})
        grid = tk.Frame(container, bg=view.COR_CARD_2)
        grid.pack(fill=tk.X)
        for column in range(3):
            grid.grid_columnconfigure(column, weight=1, uniform="f2_board_refs")

        photos = []
        for column, slot in enumerate(F2_BOARD_REF_SLOTS):
            ui = _SLOT_UI[slot]
            entry = entries.get(slot, {})
            card = tk.Frame(
                grid,
                bg=view.COR_CARD,
                highlightthickness=1,
                highlightbackground=view.COR_BORDA,
            )
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 5, 0 if column == 2 else 5),
            )
            tk.Label(
                card,
                text=ui["title"],
                font=("Segoe UI", 8, "bold"),
                fg=ui["color"],
                bg=view.COR_CARD,
                anchor="w",
            ).pack(fill=tk.X, padx=7, pady=(7, 4))

            preview = tk.Frame(card, bg="#020617", height=112)
            preview.pack(fill=tk.X, padx=7)
            preview.pack_propagate(False)
            image = cv2.imread(str(entry.get("image_path") or "")) if entry else None
            photo = _criar_photo_preview(image, largura_max=180, altura_max=104)
            if photo is not None:
                photos.append(photo)
                tk.Label(preview, image=photo, bg="#020617", bd=0).pack(
                    fill=tk.BOTH,
                    expand=True,
                )
            else:
                tk.Label(
                    preview,
                    text="SEM IMAGEM",
                    font=("Segoe UI", 8, "bold"),
                    fg=view.COR_TEXTO_3,
                    bg="#020617",
                ).pack(fill=tk.BOTH, expand=True)

            state = tk.NORMAL if projeto and resolution is not None else tk.DISABLED
            actions = tk.Frame(card, bg=view.COR_CARD)
            actions.pack(fill=tk.X, padx=7, pady=6)
            tk.Button(
                actions,
                text="Capturar câmera",
                state=state,
                command=lambda s=slot, w=window: self.capture_current(s, w),
                font=("Segoe UI", 7, "bold"),
                bg=view.COR_CARD_2,
                fg=view.COR_TEXTO,
                disabledforeground=view.COR_TEXTO_3,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                padx=5,
                pady=4,
            ).pack(fill=tk.X)
            tk.Button(
                actions,
                text="Carregar imagem",
                state=state,
                command=lambda s=slot, w=window: self.load_file(s, w),
                font=("Segoe UI", 7),
                bg=view.COR_CARD_2,
                fg=view.COR_TEXTO_2,
                disabledforeground=view.COR_TEXTO_3,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                padx=5,
                pady=3,
            ).pack(fill=tk.X, pady=(3, 0))
            if entry:
                tk.Button(
                    actions,
                    text="Remover",
                    command=lambda s=slot, w=window: self.remove(s, w),
                    font=("Segoe UI", 7),
                    bg=view.COR_CARD,
                    fg="#FCA5A5",
                    relief=tk.FLAT,
                    bd=0,
                    cursor="hand2",
                    padx=5,
                    pady=3,
                ).pack(fill=tk.X, pady=(3, 0))

        window._odin_f2_board_presence_preview_tk = photos
        ready = self._ensure_classifier()
        tk.Label(
            container,
            text=(
                "Status: 3/3 referências prontas para identificação visual."
                if ready
                else "Status: complete os 3 slots para ativar a identificação visual por projeto."
            ),
            font=("Segoe UI", 8, "bold"),
            fg="#86EFAC" if ready else "#FBBF24",
            bg=view.COR_CARD_2,
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 0))

        try:
            window.update_idletasks()
        except Exception:
            pass
