from __future__ import annotations

import base64
import tkinter as tk
from collections.abc import Callable
from copy import deepcopy
from tkinter import messagebox, simpledialog

import cv2

from src.platform.display_project_repository import (
    DISPLAY_CHECK_STATE_IGNORE,
    DISPLAY_CHECK_STATE_OFF,
    DISPLAY_CHECK_STATE_ON,
    DisplayProjectRepository,
    normalizar_estados_check_display,
    normalizar_mascaras_display,
    normalizar_nome_check_display,
    normalizar_resolucao_display,
)


CHECK_STATE_LABELS = {
    DISPLAY_CHECK_STATE_ON: "ACESO",
    DISPLAY_CHECK_STATE_OFF: "APAGADO",
    DISPLAY_CHECK_STATE_IGNORE: "IGNORAR",
}
CHECK_STATE_COLORS = {
    DISPLAY_CHECK_STATE_ON: "#22C55E",
    DISPLAY_CHECK_STATE_OFF: "#EF4444",
    DISPLAY_CHECK_STATE_IGNORE: "#94A3B8",
}


def proximo_estado_check_display(estado: str | None) -> str:
    atual = str(estado or DISPLAY_CHECK_STATE_IGNORE).strip().lower()
    if atual == DISPLAY_CHECK_STATE_IGNORE:
        return DISPLAY_CHECK_STATE_ON
    if atual == DISPLAY_CHECK_STATE_ON:
        return DISPLAY_CHECK_STATE_OFF
    return DISPLAY_CHECK_STATE_IGNORE


def nome_segmento_display(indice: int) -> str:
    return f"SEG_{int(indice) + 1:02d}"


class DisplayCheckManagerWindow:
    """CRUD e ordenação dos CHECKS pertencentes a um Projeto Display."""

    BG = "#07111F"
    PANEL = "#0B1728"
    BORDER = "#253247"
    TEXT = "#F8FAFC"
    MUTED = "#94A3B8"

    def __init__(
        self,
        root,
        repository: DisplayProjectRepository,
        project_name: str,
        frame_provider: Callable[[], object | None],
        on_change: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.repository = repository
        self.project_name = str(project_name)
        self.frame_provider = frame_provider
        self.on_change = on_change
        self.on_close = on_close
        self.check_editor: DisplayCheckMaskEditorWindow | None = None
        self._check_ids: list[str] = []

        self.window = tk.Toplevel(root)
        self.window.title(f"ODIN • CHECKS • {self.project_name}")
        self.window.configure(bg=self.BG)
        self.window.resizable(False, False)
        self.window.transient(root)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        width = 860
        height = 610
        try:
            x = root.winfo_rootx() + max(0, (root.winfo_width() - width) // 2)
            y = root.winfo_rooty() + max(0, (root.winfo_height() - height) // 2)
        except Exception:
            x = y = 0
        self.window.geometry(f"{width}x{height}+{x}+{y}")

        tk.Label(
            self.window,
            text="CHECKS DO DISPLAY",
            font=("Segoe UI", 17, "bold"),
            fg=self.TEXT,
            bg=self.BG,
        ).pack(anchor="w", padx=22, pady=(18, 3))
        tk.Label(
            self.window,
            text=(
                f"Projeto: {self.project_name} • a ordem abaixo será a ordem "
                "operacional do F3 nas próximas fases."
            ),
            font=("Segoe UI", 9),
            fg=self.MUTED,
            bg=self.BG,
        ).pack(anchor="w", padx=22, pady=(0, 12))

        body = tk.Frame(self.window, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=22, pady=(0, 12))

        left = tk.Frame(
            body,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
            width=420,
        )
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left.pack_propagate(False)

        tk.Label(
            left,
            text="ORDEM DOS CHECKS",
            font=("Segoe UI", 9, "bold"),
            fg=self.MUTED,
            bg=self.PANEL,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(12, 6))

        list_frame = tk.Frame(left, bg=self.PANEL)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.check_list = tk.Listbox(
            list_frame,
            exportselection=False,
            font=("Segoe UI", 11, "bold"),
            bg="#020617",
            fg=self.TEXT,
            selectbackground="#0E7490",
            selectforeground="#FFFFFF",
            activestyle="none",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        self.check_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.configure(command=self.check_list.yview)
        self.check_list.bind("<<ListboxSelect>>", lambda _event: self._update_detail())
        self.check_list.bind("<Double-Button-1>", lambda _event: self.edit_selected())

        actions = tk.Frame(left, bg=self.PANEL)
        actions.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._button(actions, "Adicionar", self.add_check).pack(side=tk.LEFT, padx=(0, 4))
        self._button(actions, "Renomear", self.rename_selected).pack(side=tk.LEFT, padx=4)
        self._button(actions, "Remover", self.remove_selected, danger=True).pack(side=tk.LEFT, padx=4)
        self._button(actions, "↑", lambda: self.move_selected(-1)).pack(side=tk.LEFT, padx=(10, 3))
        self._button(actions, "↓", lambda: self.move_selected(1)).pack(side=tk.LEFT, padx=3)

        right = tk.Frame(
            body,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
            width=390,
        )
        right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(12, 0))
        right.pack_propagate(False)

        self.check_title = tk.Label(
            right,
            text="SEM CHECK",
            font=("Segoe UI", 16, "bold"),
            fg=self.TEXT,
            bg=self.PANEL,
            anchor="w",
        )
        self.check_title.pack(fill=tk.X, padx=16, pady=(18, 4))

        self.check_order = tk.Label(
            right,
            text="",
            font=("Segoe UI", 9),
            fg=self.MUTED,
            bg=self.PANEL,
            anchor="w",
        )
        self.check_order.pack(fill=tk.X, padx=16, pady=(0, 18))

        summary_box = tk.Frame(right, bg="#0F1B2C")
        summary_box.pack(fill=tk.X, padx=16, pady=(0, 12))
        tk.Label(
            summary_box,
            text="ESTADO DAS MÁSCARAS",
            font=("Segoe UI", 9, "bold"),
            fg=self.MUTED,
            bg="#0F1B2C",
        ).pack(anchor="w", padx=12, pady=(11, 6))
        self.state_summary = tk.Label(
            summary_box,
            text="ACESO: 0\nAPAGADO: 0\nIGNORAR: 0",
            font=("Segoe UI", 11, "bold"),
            fg=self.TEXT,
            bg="#0F1B2C",
            justify=tk.LEFT,
            anchor="w",
        )
        self.state_summary.pack(fill=tk.X, padx=12, pady=(0, 10))
        tk.Label(
            summary_box,
            text=(
                "No editor visual, cada clique em um segmento alterna:\n"
                "IGNORAR → ACESO → APAGADO → IGNORAR"
            ),
            font=("Segoe UI", 9),
            fg=self.MUTED,
            bg="#0F1B2C",
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 12))

        self.edit_button = self._button(
            right,
            "EDITAR CHECK PELAS MÁSCARAS",
            self.edit_selected,
            primary=True,
        )
        self.edit_button.pack(fill=tk.X, padx=16, pady=(0, 12))

        self.status = tk.Label(
            right,
            text="",
            font=("Segoe UI", 9),
            fg=self.MUTED,
            bg=self.PANEL,
            justify=tk.LEFT,
            wraplength=350,
            anchor="w",
        )
        self.status.pack(fill=tk.X, padx=16, pady=(0, 12))

        tk.Button(
            self.window,
            text="Fechar",
            command=self.close,
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#FFFFFF",
            activebackground="#475569",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            padx=18,
            pady=8,
            cursor="hand2",
        ).pack(anchor="e", padx=22, pady=(0, 16))

        self.refresh()
        self.window.lift()
        self.window.focus_force()

    def _button(self, parent, text, command, primary: bool = False, danger: bool = False):
        bg = "#0E7490" if primary else "#1E293B"
        active = "#0891B2" if primary else "#334155"
        if danger:
            bg = "#7F1D1D"
            active = "#991B1B"
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 8, "bold"),
            bg=bg,
            fg="#FFFFFF",
            activebackground=active,
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=7,
            cursor="hand2",
        )

    @property
    def visible(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except Exception:
            return False

    def _selected_index(self) -> int | None:
        selection = self.check_list.curselection()
        if not selection:
            return None
        index = int(selection[0])
        if index < 0 or index >= len(self._check_ids):
            return None
        return index

    def _selected_id(self) -> str | None:
        index = self._selected_index()
        return self._check_ids[index] if index is not None else None

    def _notify_change(self) -> None:
        if self.on_change is not None:
            self.on_change()

    def refresh(self, prefer_id: str | None = None) -> None:
        checks = self.repository.listar_checks(self.project_name)
        self.check_list.delete(0, tk.END)
        self._check_ids = []
        selected_index = None
        prefer = str(prefer_id or "").upper()
        for index, check in enumerate(checks):
            check_id = str(check.get("id", ""))
            self._check_ids.append(check_id)
            self.check_list.insert(tk.END, f"{index + 1}.  {check.get('name', 'CHECK')}")
            if check_id.upper() == prefer:
                selected_index = index
        if selected_index is None and checks:
            selected_index = 0
        if selected_index is not None:
            self.check_list.selection_set(selected_index)
            self.check_list.see(selected_index)
        self._update_detail()
        self.status.configure(
            text=f"{len(checks)} CHECK(s) configurado(s) no Projeto Display."
        )

    def _update_detail(self) -> None:
        check_id = self._selected_id()
        if not check_id:
            self.check_title.configure(text="SEM CHECK")
            self.check_order.configure(text="Adicione um CHECK para continuar.")
            self.state_summary.configure(text="ACESO: 0\nAPAGADO: 0\nIGNORAR: 0")
            return
        check = self.repository.carregar_check(self.project_name, check_id)
        if check is None:
            return
        index = self._selected_index()
        states = check.get("mask_states", {})
        counts = {
            DISPLAY_CHECK_STATE_ON: 0,
            DISPLAY_CHECK_STATE_OFF: 0,
            DISPLAY_CHECK_STATE_IGNORE: 0,
        }
        for state in states.values():
            counts[str(state)] = counts.get(str(state), 0) + 1
        self.check_title.configure(text=str(check.get("name", "CHECK")))
        self.check_order.configure(
            text=f"Posição na sequência: {(index or 0) + 1} • ID interno: {check_id}"
        )
        self.state_summary.configure(
            text=(
                f"ACESO: {counts[DISPLAY_CHECK_STATE_ON]}\n"
                f"APAGADO: {counts[DISPLAY_CHECK_STATE_OFF]}\n"
                f"IGNORAR: {counts[DISPLAY_CHECK_STATE_IGNORE]}"
            )
        )

    def add_check(self) -> None:
        name = simpledialog.askstring(
            "Adicionar CHECK",
            "Nome do novo CHECK:",
            parent=self.window,
        )
        name = normalizar_nome_check_display(name)
        if not name:
            return
        check_id = self.repository.adicionar_check(self.project_name, name)
        if not check_id:
            messagebox.showwarning(
                "CHECK não criado",
                "Use um nome válido e diferente dos CHECKS existentes.",
                parent=self.window,
            )
            return
        self.refresh(check_id)
        self._notify_change()

    def rename_selected(self) -> None:
        check_id = self._selected_id()
        if not check_id:
            return
        check = self.repository.carregar_check(self.project_name, check_id)
        if check is None:
            return
        name = simpledialog.askstring(
            "Renomear CHECK",
            "Novo nome:",
            initialvalue=str(check.get("name", "")),
            parent=self.window,
        )
        if not name:
            return
        if not self.repository.renomear_check(self.project_name, check_id, name):
            messagebox.showwarning(
                "Não foi possível renomear",
                "Verifique se já existe outro CHECK com esse nome.",
                parent=self.window,
            )
            return
        self.refresh(check_id)
        self._notify_change()

    def remove_selected(self) -> None:
        check_id = self._selected_id()
        if not check_id:
            return
        check = self.repository.carregar_check(self.project_name, check_id)
        if check is None:
            return
        if not messagebox.askyesno(
            "Remover CHECK",
            f"Remover o CHECK {check.get('name', check_id)}?",
            parent=self.window,
        ):
            return
        if self.repository.remover_check(self.project_name, check_id):
            self.refresh()
            self._notify_change()

    def move_selected(self, direction: int) -> None:
        check_id = self._selected_id()
        if not check_id:
            return
        if self.repository.mover_check(self.project_name, check_id, direction):
            self.refresh(check_id)
            self._notify_change()

    def edit_selected(self) -> None:
        check_id = self._selected_id()
        if not check_id:
            return
        project = self.repository.carregar_projeto(self.project_name)
        check = self.repository.carregar_check(self.project_name, check_id)
        if project is None or check is None:
            return
        masks = project.get("masks", [])
        if not masks:
            messagebox.showwarning(
                "Sem máscaras",
                "Crie as máscaras do Projeto Display antes de editar os CHECKS.",
                parent=self.window,
            )
            return
        resolution = normalizar_resolucao_display(project.get("master_resolution"))
        if resolution is None:
            messagebox.showwarning(
                "Sem resolução mestre",
                "Defina a resolução mestre do Projeto Display primeiro.",
                parent=self.window,
            )
            return
        try:
            frame = self.frame_provider()
        except Exception:
            frame = None

        def save_states(states: dict[str, str]) -> None:
            if self.repository.salvar_estados_check(
                self.project_name,
                check_id,
                states,
            ):
                self.refresh(check_id)
                self._notify_change()

        self.check_editor = DisplayCheckMaskEditorWindow(
            root=self.root,
            project_name=self.project_name,
            check=check,
            master_resolution=resolution,
            masks=masks,
            frame=frame,
            on_save=save_states,
        )

    def close(self) -> None:
        editor = self.check_editor
        if editor is not None and editor.visible:
            editor.close()
        self.check_editor = None
        try:
            self.window.destroy()
        except Exception:
            pass
        if self.on_close is not None:
            self.on_close()


class DisplayCheckMaskEditorWindow:
    """Editor visual de expectativa ON/OFF/IGNORE por máscara do CHECK."""

    BG = "#020617"
    PANEL = "#07111F"
    BORDER = "#1E293B"
    TEXT = "#F8FAFC"
    MUTED = "#94A3B8"

    def __init__(
        self,
        root,
        project_name: str,
        check: dict,
        master_resolution,
        masks,
        frame=None,
        on_save: Callable[[dict[str, str]], None] | None = None,
    ) -> None:
        resolution = normalizar_resolucao_display(master_resolution)
        if resolution is None:
            raise ValueError("Resolução mestre inválida para o editor de CHECK")
        self.root = root
        self.project_name = str(project_name)
        self.check = deepcopy(check)
        self.check_name = str(check.get("name", "CHECK"))
        self.master_width, self.master_height = resolution
        self.masks = normalizar_mascaras_display(deepcopy(masks or []))
        self.mask_ids = [str(mask["id"]) for mask in self.masks]
        self.states = normalizar_estados_check_display(
            check.get("mask_states", {}),
            self.mask_ids,
        )
        self.frame = None
        if frame is not None and getattr(frame, "size", 0) > 0:
            self.frame = frame.copy()
        self.on_save = on_save
        self._photo = None
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._segment_buttons: list[tk.Button] = []

        self.window = tk.Toplevel(root)
        self.window.title(f"ODIN • CHECK {self.check_name}")
        self.window.configure(bg=self.BG)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        toolbar = tk.Frame(
            self.window,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        toolbar.pack(side=tk.TOP, fill=tk.X)
        texts = tk.Frame(toolbar, bg=self.PANEL)
        texts.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=18, pady=9)
        tk.Label(
            texts,
            text=f"CHECK • {self.check_name}",
            font=("DejaVu Sans", 13, "bold"),
            fg=self.TEXT,
            bg=self.PANEL,
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            texts,
            text=(
                f"{self.project_name} • {self.master_width}x{self.master_height} • "
                "clique em uma máscara para alternar ACESO → APAGADO → IGNORAR"
            ),
            font=("DejaVu Sans", 8),
            fg=self.MUTED,
            bg=self.PANEL,
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        actions = tk.Frame(toolbar, bg=self.PANEL)
        actions.pack(side=tk.RIGHT, padx=(8, 18), pady=8)
        tk.Button(
            actions,
            text="Todos IGNORAR",
            command=self.set_all_ignore,
            font=("DejaVu Sans", 8, "bold"),
            bg="#334155",
            fg="#FFFFFF",
            activebackground="#475569",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=11,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=3)
        tk.Button(
            actions,
            text="Cancelar",
            command=self.close,
            font=("DejaVu Sans", 8, "bold"),
            bg="#334155",
            fg="#FFFFFF",
            activebackground="#475569",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=11,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=3)
        tk.Button(
            actions,
            text="SALVAR CHECK",
            command=self.save,
            font=("DejaVu Sans", 9, "bold"),
            bg="#D6A900",
            fg="#111318",
            activebackground="#F5C518",
            activeforeground="#111318",
            relief="flat",
            padx=15,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(8, 0))

        body = tk.Frame(self.window, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(
            body,
            bg=self.BG,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        side = tk.Frame(
            body,
            width=310,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        side.pack(side=tk.RIGHT, fill=tk.Y)
        side.pack_propagate(False)
        tk.Label(
            side,
            text="SEGMENTOS",
            font=("DejaVu Sans", 11, "bold"),
            fg=self.TEXT,
            bg=self.PANEL,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(12, 3))
        tk.Label(
            side,
            text="Clique na lista ou diretamente na máscara.",
            font=("DejaVu Sans", 8),
            fg=self.MUTED,
            bg=self.PANEL,
            anchor="w",
        ).pack(fill=tk.X, padx=12, pady=(0, 8))

        list_box = tk.Frame(side, bg=self.PANEL)
        list_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.list_canvas = tk.Canvas(
            list_box,
            bg=self.PANEL,
            highlightthickness=0,
            bd=0,
        )
        scrollbar = tk.Scrollbar(
            list_box,
            orient=tk.VERTICAL,
            command=self.list_canvas.yview,
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        self.segment_frame = tk.Frame(self.list_canvas, bg=self.PANEL)
        self._segment_window_id = self.list_canvas.create_window(
            (0, 0),
            window=self.segment_frame,
            anchor=tk.NW,
        )
        self.segment_frame.bind(
            "<Configure>",
            lambda _event: self.list_canvas.configure(
                scrollregion=self.list_canvas.bbox("all")
            ),
        )
        self.list_canvas.bind(
            "<Configure>",
            lambda event: self.list_canvas.itemconfigure(
                self._segment_window_id,
                width=max(1, int(event.width)),
            ),
        )

        self.status = tk.Label(
            self.window,
            text="",
            font=("DejaVu Sans", 9, "bold"),
            fg=self.MUTED,
            bg=self.PANEL,
            anchor="w",
        )
        self.status.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(5, 8))

        self.canvas.bind("<Configure>", lambda _event: self.redraw())
        self.canvas.bind("<Button-1>", self._on_click)
        self.window.bind("<Escape>", lambda _event: self.close())

        self._maximize()
        self._refresh_segment_buttons()
        self.window.after(60, self.redraw)

    def _maximize(self) -> None:
        try:
            self.window.attributes("-fullscreen", True)
        except Exception:
            width = max(900, int(self.root.winfo_screenwidth()))
            height = max(650, int(self.root.winfo_screenheight()))
            self.window.geometry(f"{width}x{height}+0+0")

    @property
    def visible(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except Exception:
            return False

    def _canvas_geometry(self) -> tuple[float, float, float]:
        width = max(1, int(self.canvas.winfo_width()))
        height = max(1, int(self.canvas.winfo_height()))
        scale = min(
            width / float(self.master_width),
            height / float(self.master_height),
        )
        render_width = self.master_width * scale
        render_height = self.master_height * scale
        return scale, (width - render_width) / 2.0, (height - render_height) / 2.0

    def _to_master(self, canvas_x: float, canvas_y: float) -> tuple[int, int] | None:
        scale, offset_x, offset_y = self._canvas_geometry()
        if scale <= 0:
            return None
        x = (float(canvas_x) - offset_x) / scale
        y = (float(canvas_y) - offset_y) / scale
        if x < 0 or y < 0 or x > self.master_width or y > self.master_height:
            return None
        return int(round(x)), int(round(y))

    def _to_canvas(self, x: float, y: float) -> tuple[float, float]:
        scale, offset_x, offset_y = self._canvas_geometry()
        return offset_x + float(x) * scale, offset_y + float(y) * scale

    @staticmethod
    def _contains(mask: dict, x: int, y: int) -> bool:
        kind = mask.get("type")
        if kind == "rectangle":
            return (
                int(mask["x"]) <= x <= int(mask["x"]) + int(mask["width"])
                and int(mask["y"]) <= y <= int(mask["y"]) + int(mask["height"])
            )
        if kind == "circle":
            dx = x - int(mask["cx"])
            dy = y - int(mask["cy"])
            return dx * dx + dy * dy <= int(mask["radius"]) ** 2
        if kind == "polygon":
            points = mask.get("points", [])
            inside = False
            j = len(points) - 1
            for i in range(len(points)):
                xi, yi = points[i]
                xj, yj = points[j]
                if ((yi > y) != (yj > y)) and (
                    x < (xj - xi) * (y - yi) / float((yj - yi) or 1e-9) + xi
                ):
                    inside = not inside
                j = i
            return inside
        return False

    def _find_mask(self, x: int, y: int) -> int | None:
        for index in range(len(self.masks) - 1, -1, -1):
            if self._contains(self.masks[index], x, y):
                return index
        return None

    def _on_click(self, event) -> str:
        point = self._to_master(event.x, event.y)
        if point is None:
            return "break"
        index = self._find_mask(*point)
        if index is not None:
            self.toggle_mask(index)
        return "break"

    def toggle_mask(self, index: int) -> None:
        if index < 0 or index >= len(self.masks):
            return
        mask_id = str(self.masks[index]["id"])
        self.states[mask_id] = proximo_estado_check_display(
            self.states.get(mask_id)
        )
        self._refresh_segment_buttons()
        self.redraw()

    def set_all_ignore(self) -> None:
        for mask_id in self.mask_ids:
            self.states[mask_id] = DISPLAY_CHECK_STATE_IGNORE
        self._refresh_segment_buttons()
        self.redraw()

    def _refresh_segment_buttons(self) -> None:
        for button in self._segment_buttons:
            try:
                button.destroy()
            except Exception:
                pass
        self._segment_buttons = []
        for index, mask in enumerate(self.masks):
            mask_id = str(mask["id"])
            state = self.states.get(mask_id, DISPLAY_CHECK_STATE_IGNORE)
            label = CHECK_STATE_LABELS.get(state, "IGNORAR")
            color = CHECK_STATE_COLORS.get(state, self.MUTED)
            button = tk.Button(
                self.segment_frame,
                text=f"{nome_segmento_display(index)}    {label}",
                command=lambda i=index: self.toggle_mask(i),
                font=("DejaVu Sans", 9, "bold"),
                bg="#0F1B2C",
                fg=color,
                activebackground="#17243A",
                activeforeground=color,
                relief="flat",
                bd=0,
                anchor="w",
                padx=10,
                pady=7,
                cursor="hand2",
            )
            button.pack(fill=tk.X, pady=2)
            self._segment_buttons.append(button)

    def _background_photo(self, render_width: int, render_height: int):
        if self.frame is None:
            return None
        try:
            resized = cv2.resize(
                self.frame,
                (max(1, render_width), max(1, render_height)),
                interpolation=cv2.INTER_AREA,
            )
            ok, buffer = cv2.imencode(
                ".png",
                resized,
                [cv2.IMWRITE_PNG_COMPRESSION, 1],
            )
            if not ok:
                return None
            return tk.PhotoImage(data=base64.b64encode(buffer).decode("ascii"))
        except Exception:
            return None

    def redraw(self) -> None:
        if not self.visible:
            return
        self.canvas.delete("all")
        scale, offset_x, offset_y = self._canvas_geometry()
        self._scale = scale
        self._offset_x = offset_x
        self._offset_y = offset_y
        render_width = max(1, int(round(self.master_width * scale)))
        render_height = max(1, int(round(self.master_height * scale)))
        self._photo = self._background_photo(render_width, render_height)
        if self._photo is not None:
            self.canvas.create_image(
                offset_x,
                offset_y,
                image=self._photo,
                anchor=tk.NW,
            )
        else:
            self.canvas.create_rectangle(
                offset_x,
                offset_y,
                offset_x + render_width,
                offset_y + render_height,
                fill="#0B1220",
                outline=self.BORDER,
            )

        for index, mask in enumerate(self.masks):
            self._draw_mask(index, mask)

        counts = {
            state: sum(1 for value in self.states.values() if value == state)
            for state in (
                DISPLAY_CHECK_STATE_ON,
                DISPLAY_CHECK_STATE_OFF,
                DISPLAY_CHECK_STATE_IGNORE,
            )
        }
        self.status.configure(
            text=(
                f"{self.check_name} • ACESO {counts[DISPLAY_CHECK_STATE_ON]} • "
                f"APAGADO {counts[DISPLAY_CHECK_STATE_OFF]} • "
                f"IGNORAR {counts[DISPLAY_CHECK_STATE_IGNORE]}"
            )
        )

    def _draw_mask(self, index: int, mask: dict) -> None:
        mask_id = str(mask["id"])
        state = self.states.get(mask_id, DISPLAY_CHECK_STATE_IGNORE)
        color = CHECK_STATE_COLORS.get(state, self.MUTED)
        kind = mask.get("type")
        label_x = label_y = 0.0
        if kind == "rectangle":
            x1, y1 = self._to_canvas(mask["x"], mask["y"])
            x2, y2 = self._to_canvas(
                int(mask["x"]) + int(mask["width"]),
                int(mask["y"]) + int(mask["height"]),
            )
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=3)
            label_x, label_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        elif kind == "circle":
            cx, cy = self._to_canvas(mask["cx"], mask["cy"])
            radius = float(mask["radius"]) * self._scale
            self.canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                outline=color,
                width=3,
            )
            label_x, label_y = cx, cy
        elif kind == "polygon":
            coords: list[float] = []
            xs: list[float] = []
            ys: list[float] = []
            for point in mask.get("points", []):
                px, py = self._to_canvas(point[0], point[1])
                coords.extend((px, py))
                xs.append(px)
                ys.append(py)
            if len(coords) >= 6:
                self.canvas.create_polygon(
                    *coords,
                    outline=color,
                    fill="",
                    width=3,
                )
                label_x = sum(xs) / len(xs)
                label_y = sum(ys) / len(ys)
        self.canvas.create_text(
            label_x,
            label_y,
            text=f"{nome_segmento_display(index)}\n{CHECK_STATE_LABELS.get(state, 'IGNORAR')}",
            fill=color,
            font=("DejaVu Sans", 8, "bold"),
            justify=tk.CENTER,
        )

    def save(self) -> None:
        states = normalizar_estados_check_display(self.states, self.mask_ids)
        if self.on_save is not None:
            self.on_save(deepcopy(states))
        self.close()

    def close(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass
