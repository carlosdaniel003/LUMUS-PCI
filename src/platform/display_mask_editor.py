from __future__ import annotations

import base64
import math
import tkinter as tk
from copy import deepcopy
from collections.abc import Callable

import cv2

from src.platform.display_project_repository import (
    normalizar_mascaras_display,
    normalizar_resolucao_display,
)


class DisplayMaskEditorWindow:
    """Editor visual exclusivo das máscaras do Projeto Display.

    A janela mantém sua própria lista de máscaras e usa o frame da câmera apenas
    como imagem de fundo. Nenhum estado de ROI/LED do F2 é lido ou alterado.
    """

    BG = "#020617"
    PANEL = "#07111F"
    BORDER = "#1E293B"
    TEXT = "#F8FAFC"
    MUTED = "#94A3B8"
    MASK = "#22D3EE"
    MASK_SELECTED = "#FACC15"
    DRAFT = "#A78BFA"

    def __init__(
        self,
        root,
        master_resolution,
        masks,
        frame=None,
        on_save: Callable[[list[dict]], None] | None = None,
    ) -> None:
        resolucao = normalizar_resolucao_display(master_resolution)
        if resolucao is None:
            raise ValueError("Resolução mestre inválida para o editor Display")

        self.root = root
        self.master_width, self.master_height = resolucao
        self.masks = normalizar_mascaras_display(deepcopy(masks or []))
        self.frame = None
        if frame is not None and getattr(frame, "size", 0) > 0:
            self.frame = frame.copy()
        self.on_save = on_save

        self.mode = "rectangle"
        self.selected_index: int | None = None
        self.drag_start: tuple[int, int] | None = None
        self.drag_current: tuple[int, int] | None = None
        self.polygon_points: list[list[int]] = []
        self._photo = None
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0

        self.window = tk.Toplevel(root)
        self.window.title("ODIN • Projeto Display • Máscaras")
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
            text="MÁSCARAS DO PROJETO DISPLAY",
            font=("DejaVu Sans", 12, "bold"),
            fg=self.TEXT,
            bg=self.PANEL,
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            texts,
            text=(
                f"Resolução mestre: {self.master_width}x{self.master_height} • "
                "Retângulo/Círculo: arraste • Polígono: clique nos pontos e "
                "feche no primeiro ponto ou pressione Enter • Delete remove"
            ),
            font=("DejaVu Sans", 8),
            fg=self.MUTED,
            bg=self.PANEL,
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        actions = tk.Frame(toolbar, bg=self.PANEL)
        actions.pack(side=tk.RIGHT, padx=(8, 18), pady=8)

        self.mode_buttons: dict[str, tk.Button] = {}
        for mode, text in (
            ("rectangle", "▭ Retângulo"),
            ("circle", "● Círculo"),
            ("polygon", "✎ Polígono"),
        ):
            button = tk.Button(
                actions,
                text=text,
                command=lambda value=mode: self.set_mode(value),
                font=("DejaVu Sans", 8, "bold"),
                relief="flat",
                bd=0,
                padx=10,
                pady=6,
                cursor="hand2",
            )
            button.pack(side=tk.LEFT, padx=3)
            self.mode_buttons[mode] = button

        tk.Button(
            actions,
            text="Limpar",
            command=self.clear_masks,
            font=("DejaVu Sans", 8, "bold"),
            bg="#7F1D1D",
            fg="#FFFFFF",
            activebackground="#991B1B",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(10, 3))

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
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            actions,
            text="SALVAR MÁSCARAS",
            command=self.save,
            font=("DejaVu Sans", 9, "bold"),
            bg="#D6A900",
            fg="#111318",
            activebackground="#F5C518",
            activeforeground="#111318",
            relief="flat",
            bd=0,
            padx=15,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(8, 0))

        self.canvas = tk.Canvas(
            self.window,
            bg=self.BG,
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
        )
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

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
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Delete>", self._delete_selected)
        self.canvas.bind("<BackSpace>", self._delete_selected)
        self.canvas.bind("<Return>", self._finish_polygon)
        self.canvas.bind("<KP_Enter>", self._finish_polygon)
        self.canvas.bind("<Escape>", self._cancel_draft)

        self.set_mode("rectangle")
        self._maximize()
        self.window.after(60, self.redraw)
        self.window.after(80, self.canvas.focus_set)

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

    def set_mode(self, mode: str) -> None:
        if mode not in self.mode_buttons:
            return
        self.mode = mode
        self.drag_start = None
        self.drag_current = None
        self.polygon_points = []
        for key, button in self.mode_buttons.items():
            active = key == mode
            button.configure(
                bg="#D6A900" if active else "#182231",
                fg="#111318" if active else "#DCE5EF",
                activebackground="#F5C518" if active else "#243246",
                activeforeground="#111318" if active else "#FFFFFF",
            )
        self.redraw()

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
        return (
            max(0, min(self.master_width - 1, int(round(x)))),
            max(0, min(self.master_height - 1, int(round(y)))),
        )

    def _to_canvas(self, x: float, y: float) -> tuple[float, float]:
        scale, offset_x, offset_y = self._canvas_geometry()
        return offset_x + float(x) * scale, offset_y + float(y) * scale

    def _next_id(self) -> str:
        used = {str(mask.get("id", "")) for mask in self.masks}
        index = 1
        while f"MASK_{index:03d}" in used:
            index += 1
        return f"MASK_{index:03d}"

    def _on_press(self, event) -> str:
        self.canvas.focus_set()
        point = self._to_master(event.x, event.y)
        if point is None:
            return "break"

        if self.mode == "polygon":
            if self.polygon_points and len(self.polygon_points) >= 3:
                first = self.polygon_points[0]
                tolerance = max(5.0, 14.0 / max(self._scale, 1e-6))
                if math.dist(point, first) <= tolerance:
                    return self._finish_polygon(event)
            self.polygon_points.append([point[0], point[1]])
            self.selected_index = None
            self.redraw()
            return "break"

        hit = self._find_mask(point[0], point[1])
        if hit is not None:
            self.selected_index = hit
            self.drag_start = None
            self.drag_current = None
            self.redraw()
            return "break"

        self.selected_index = None
        self.drag_start = point
        self.drag_current = point
        self.redraw()
        return "break"

    def _on_drag(self, event) -> str:
        if self.mode == "polygon" or self.drag_start is None:
            return "break"
        point = self._to_master(event.x, event.y)
        if point is not None:
            self.drag_current = point
            self.redraw()
        return "break"

    def _on_release(self, event) -> str:
        if self.mode == "polygon" or self.drag_start is None:
            return "break"
        point = self._to_master(event.x, event.y) or self.drag_current
        start = self.drag_start
        self.drag_start = None
        self.drag_current = None
        if point is None:
            self.redraw()
            return "break"

        x1, y1 = start
        x2, y2 = point
        if self.mode == "rectangle":
            left, right = sorted((x1, x2))
            top, bottom = sorted((y1, y2))
            if right - left >= 3 and bottom - top >= 3:
                self.masks.append({
                    "id": self._next_id(),
                    "type": "rectangle",
                    "x": left,
                    "y": top,
                    "width": right - left,
                    "height": bottom - top,
                })
                self.selected_index = len(self.masks) - 1
        elif self.mode == "circle":
            radius = int(round(math.dist((x1, y1), (x2, y2))))
            radius = min(
                radius,
                x1,
                y1,
                self.master_width - 1 - x1,
                self.master_height - 1 - y1,
            )
            if radius >= 3:
                self.masks.append({
                    "id": self._next_id(),
                    "type": "circle",
                    "cx": x1,
                    "cy": y1,
                    "radius": radius,
                })
                self.selected_index = len(self.masks) - 1
        self.masks = normalizar_mascaras_display(self.masks)
        self.redraw()
        return "break"

    def _finish_polygon(self, _event=None) -> str:
        if len(self.polygon_points) >= 3:
            self.masks.append({
                "id": self._next_id(),
                "type": "polygon",
                "points": deepcopy(self.polygon_points),
            })
            self.masks = normalizar_mascaras_display(self.masks)
            self.selected_index = len(self.masks) - 1
        self.polygon_points = []
        self.redraw()
        return "break"

    def _cancel_draft(self, _event=None) -> str:
        self.drag_start = None
        self.drag_current = None
        self.polygon_points = []
        self.redraw()
        return "break"

    def _delete_selected(self, _event=None) -> str:
        if self.selected_index is not None and 0 <= self.selected_index < len(self.masks):
            self.masks.pop(self.selected_index)
        self.selected_index = None
        self.redraw()
        return "break"

    def clear_masks(self) -> None:
        self.masks = []
        self.selected_index = None
        self.drag_start = None
        self.drag_current = None
        self.polygon_points = []
        self.redraw()

    def _find_mask(self, x: int, y: int) -> int | None:
        for index in range(len(self.masks) - 1, -1, -1):
            mask = self.masks[index]
            if self._contains(mask, x, y):
                return index
        return None

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
                tags=("background",),
            )
        else:
            self.canvas.create_rectangle(
                offset_x,
                offset_y,
                offset_x + render_width,
                offset_y + render_height,
                fill="#0B1220",
                outline=self.BORDER,
                width=1,
            )

        for index, mask in enumerate(self.masks):
            self._draw_mask(mask, selected=index == self.selected_index)

        if self.drag_start is not None and self.drag_current is not None:
            self._draw_draft_drag()
        if self.polygon_points:
            self._draw_draft_polygon()

        self.status.configure(
            text=(
                f"Projeto Display • {len(self.masks)} máscara(s) • "
                f"modo {self.mode.upper()}"
            )
        )

    def _draw_mask(self, mask: dict, selected: bool = False) -> None:
        color = self.MASK_SELECTED if selected else self.MASK
        width = 3 if selected else 2
        kind = mask.get("type")
        if kind == "rectangle":
            x1, y1 = self._to_canvas(mask["x"], mask["y"])
            x2, y2 = self._to_canvas(
                int(mask["x"]) + int(mask["width"]),
                int(mask["y"]) + int(mask["height"]),
            )
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=width)
        elif kind == "circle":
            cx, cy = self._to_canvas(mask["cx"], mask["cy"])
            radius = float(mask["radius"]) * self._scale
            self.canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                outline=color,
                width=width,
            )
        elif kind == "polygon":
            coords: list[float] = []
            for point in mask.get("points", []):
                px, py = self._to_canvas(point[0], point[1])
                coords.extend((px, py))
            if len(coords) >= 6:
                self.canvas.create_polygon(
                    *coords,
                    outline=color,
                    fill="",
                    width=width,
                )

    def _draw_draft_drag(self) -> None:
        if self.drag_start is None or self.drag_current is None:
            return
        x1, y1 = self._to_canvas(*self.drag_start)
        x2, y2 = self._to_canvas(*self.drag_current)
        if self.mode == "rectangle":
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.DRAFT, width=2, dash=(5, 3))
        elif self.mode == "circle":
            radius = math.dist((x1, y1), (x2, y2))
            self.canvas.create_oval(
                x1 - radius,
                y1 - radius,
                x1 + radius,
                y1 + radius,
                outline=self.DRAFT,
                width=2,
                dash=(5, 3),
            )

    def _draw_draft_polygon(self) -> None:
        coords: list[float] = []
        for point in self.polygon_points:
            px, py = self._to_canvas(point[0], point[1])
            coords.extend((px, py))
            self.canvas.create_oval(px - 4, py - 4, px + 4, py + 4, outline=self.DRAFT, width=2)
        if len(coords) >= 4:
            self.canvas.create_line(*coords, fill=self.DRAFT, width=2, dash=(5, 3))

    def save(self) -> None:
        if self.polygon_points:
            self._finish_polygon()
        masks = normalizar_mascaras_display(deepcopy(self.masks))
        if self.on_save is not None:
            self.on_save(masks)
        self.close()

    def close(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass
