from __future__ import annotations

import math
from copy import deepcopy

from config import DEFAULT_RADIUS_PX, MAX_RADIUS_PX, MIN_RADIUS_PX
from src.core.roi_geometry import SEGMENTO_ALTURA_MINIMA, SEGMENTO_LARGURA_MINIMA
from src.platform.display_mask_geometry import (
    DISPLAY_MASK_F2_PARITY_TOOLS,
    TOOL_CIRCLE,
    TOOL_FREEFORM,
    TOOL_MASS,
    TOOL_SEGMENT,
    _bbox,
    _id,
    _move,
    _rotate,
    _rotate_xy,
    _scale,
    _valid,
    bbox_mascara_display,
    criar_poligono_display_por_pontos,
    criar_segmento_display_por_arrasto,
    mascara_display_contem_ponto,
)
from src.ui.main_window_parts.image.selection_zoom import (
    ZOOM_SELECAO_MIN,
    calcular_centro_zoom_ancorado,
    calcular_viewport_zoom_selecao,
    proximo_fator_zoom_selecao,
)

CTRL_MASK = 0x0004
SHIFT_MASK = 0x0001
DRAG_PX = 5
HANDLE_HIT_PX = 14
ROTATE_OFFSET_PX = 34
FREEFORM_CLOSE_PX = 18


class DisplayMaskEditorInteractionMixin:
    def _vp(self):
        return calcular_viewport_zoom_selecao(
            self.master_width,
            self.master_height,
            max(1, self.canvas.winfo_width()),
            max(1, self.canvas.winfo_height()),
            self.zoom_factor,
            self.zoom_cx,
            self.zoom_cy,
        )

    def _to_canvas(self, x, y):
        viewport = self._vp()
        return (
            viewport.deslocamento_virtual_x + float(x) * viewport.escala,
            viewport.deslocamento_virtual_y + float(y) * viewport.escala,
        )

    def _to_master(self, x, y):
        viewport = self._vp()
        mx = (x - viewport.deslocamento_virtual_x) / max(viewport.escala, 1e-9)
        my = (y - viewport.deslocamento_virtual_y) / max(viewport.escala, 1e-9)
        if mx < 0 or my < 0 or mx >= self.master_width or my >= self.master_height:
            return None
        return (
            max(0, min(self.master_width - 1, int(round(mx)))),
            max(0, min(self.master_height - 1, int(round(my)))),
        )

    def _next_id(self):
        used = {_id(mask) for mask in self.masks}
        index = 1
        while f"MASK_{index:03d}" in used:
            index += 1
        return f"MASK_{index:03d}"

    def _selected(self):
        return [
            deepcopy(mask)
            for mask in self.masks
            if _id(mask) in self.selected_ids
        ]

    def _selection_bbox(self):
        return _bbox(self._selected())

    def _hit(self, x, y):
        for mask in reversed(self.masks):
            if mascara_display_contem_ponto(mask, x, y):
                return _id(mask)
        return None

    def set_tool(self, tool):
        if tool not in DISPLAY_MASK_F2_PARITY_TOOLS:
            return
        self.freeform = []
        self.freeform_mouse = None
        self.draft_segment = None
        self.tool = tool
        for key, button in self.tool_buttons.items():
            button.configure(
                bg="#D6A900" if key == tool else "#182231",
                fg="#111318" if key == tool else "#DCE5EF",
            )
        status = getattr(self, "status", None)
        if status is not None and tool == TOOL_MASS:
            try:
                status.configure(
                    text=(
                        "Seleção em massa ativa • arraste no vazio para englobar "
                        "ROIs • depois mova, redimensione, rotacione ou apague o grupo"
                    )
                )
            except Exception:
                pass
        self.redraw()
        self.canvas.focus_set()

    def _handles(self):
        selected = self._selected()
        box = _bbox(selected)
        if not selected or box is None:
            return {}
        if len(selected) == 1 and selected[0].get("type") == "circle":
            return {}
        if len(selected) == 1 and selected[0].get("type") == "segment":
            mask = selected[0]
            cx = float(mask["cx"])
            cy = float(mask["cy"])
            hx = float(mask["width"]) / 2
            hy = float(mask["height"]) / 2
            angle = float(mask.get("angle", 0))
            local = {
                "nw": (-hx, -hy),
                "n": (0, -hy),
                "ne": (hx, -hy),
                "e": (hx, 0),
                "se": (hx, hy),
                "s": (0, hy),
                "sw": (-hx, hy),
                "w": (-hx, 0),
                "rotate": (0, -hy - max(24.0, float(mask["height"]))),
            }
            return {
                key: _rotate_xy(cx + x, cy + y, cx, cy, angle)
                for key, (x, y) in local.items()
            }
        x1, y1, x2, y2 = box
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        handles = {
            "nw": (x1, y1),
            "n": (mx, y1),
            "ne": (x2, y1),
            "e": (x2, my),
            "se": (x2, y2),
            "s": (mx, y2),
            "sw": (x1, y2),
            "w": (x1, my),
        }
        viewport = self._vp()
        handles["rotate"] = (
            mx,
            y1 - ROTATE_OFFSET_PX / max(viewport.escala, 1e-9),
        )
        return handles

    def _hit_handle(self, x, y):
        for name, point in self._handles().items():
            cx, cy = self._to_canvas(*point)
            if abs(x - cx) <= HANDLE_HIT_PX and abs(y - cy) <= HANDLE_HIT_PX:
                return name
        return None

    def _begin(self, mode, point, handle=None):
        self.mode = mode
        self.handle = handle
        self.press_master = point
        self.snapshot = deepcopy(self.masks)
        self.snapshot_sel = self._selected()
        self.snapshot_bbox = _bbox(self.snapshot_sel)

    def _merge(self, changed):
        by_id = {_id(mask): mask for mask in changed}
        self.masks = [
            deepcopy(by_id.get(_id(mask), mask))
            for mask in self.snapshot
        ]

    def _press(self, event):
        self.canvas.focus_set()
        point = self._to_master(event.x, event.y)
        if point is None:
            return "break"
        self.press_canvas = (event.x, event.y)
        self.press_master = point
        self.current_master = point

        if self.tool == TOOL_FREEFORM:
            hit = self._hit(*point)
            if hit and not self.freeform:
                self.selected_ids = {hit}
                self._begin("move", point)
                self.redraw()
                return "break"
            if self.freeform and len(self.freeform) >= 3:
                first_x, first_y = self._to_canvas(*self.freeform[0])
                if math.hypot(event.x - first_x, event.y - first_y) <= FREEFORM_CLOSE_PX:
                    return self._finish_freeform()
            self.freeform.append([point[0], point[1]])
            self.freeform_mouse = point
            self.selected_ids = set()
            self.redraw()
            return "break"

        handle = self._hit_handle(event.x, event.y)
        if handle:
            self._begin(
                "rotate"
                if handle == "rotate"
                else (
                    "scale"
                    if handle in {"nw", "ne", "se", "sw"}
                    else "stretch"
                ),
                point,
                handle,
            )
            return "break"

        hit = self._hit(*point)
        if hit:
            self.selected_ids = (
                {hit} if hit not in self.selected_ids else self.selected_ids
            )
            self._begin("move", point)
            self.redraw()
            return "break"

        self.selected_ids = set()
        self._begin("pending", point)
        return "break"

    def _drag(self, event):
        point = self._to_master(event.x, event.y)
        if point is None or self.press_master is None:
            return "break"
        self.current_master = point
        if (
            self.mode == "pending"
            and self.press_canvas
            and math.hypot(
                event.x - self.press_canvas[0],
                event.y - self.press_canvas[1],
            )
            >= DRAG_PX
        ):
            shift = int(getattr(event, "state", 0)) & SHIFT_MASK
            if self.tool == TOOL_SEGMENT and not shift:
                self.mode = "create_segment"
            elif self.tool == TOOL_CIRCLE and not shift:
                self.mode = "create_circle"
            else:
                # TOOL_MASS entra sempre aqui: a seleção retangular é sua ação
                # primária, sem exigir Shift, igual à ferramenta explícita do F2.
                self.mode = "marquee"

        if self.mode == "create_segment":
            self.draft_segment = criar_segmento_display_por_arrasto(
                *self.press_master,
                *point,
                id_mascara=self._next_id(),
            )
        elif self.mode == "marquee":
            x1, y1 = self.press_master
            left, right = sorted((x1, point[0]))
            top, bottom = sorted((y1, point[1]))
            selected = set()
            for mask in self.snapshot:
                bx1, by1, bx2, by2 = bbox_mascara_display(mask)
                if (
                    bx1 >= left
                    and by1 >= top
                    and bx2 <= right
                    and by2 <= bottom
                ):
                    selected.add(_id(mask))
            self.selected_ids = selected
        elif self.mode in {"move", "scale", "stretch", "rotate"}:
            self._transform(point)
        self.redraw()
        return "break"

    def _transform(self, point):
        if (
            not self.snapshot_sel
            or self.snapshot_bbox is None
            or self.press_master is None
        ):
            return
        x1, y1, x2, y2 = self.snapshot_bbox
        px, py = self.press_master
        if self.mode == "move":
            changed = [
                _move(mask, point[0] - px, point[1] - py)
                for mask in self.snapshot_sel
            ]
        elif self.mode == "rotate":
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            delta = math.degrees(
                math.atan2(point[1] - cy, point[0] - cx)
                - math.atan2(py - cy, px - cx)
            )
            changed = [
                _rotate(mask, cx, cy, delta)
                for mask in self.snapshot_sel
            ]
        else:
            handle = self.handle
            if (
                len(self.snapshot_sel) == 1
                and self.snapshot_sel[0].get("type") == "segment"
            ):
                mask = deepcopy(self.snapshot_sel[0])
                cx = float(mask["cx"])
                cy = float(mask["cy"])
                qx, qy = _rotate_xy(
                    point[0],
                    point[1],
                    cx,
                    cy,
                    -float(mask.get("angle", 0)),
                )
                lx, ly = qx - cx, qy - cy
                if handle in {"e", "w", "ne", "nw", "se", "sw"}:
                    mask["width"] = max(
                        SEGMENTO_LARGURA_MINIMA,
                        int(round(abs(lx) * 2)),
                    )
                if handle in {"n", "s", "ne", "nw", "se", "sw"}:
                    mask["height"] = max(
                        SEGMENTO_ALTURA_MINIMA,
                        int(round(abs(ly) * 2)),
                    )
                changed = [mask]
                if _valid(mask, self.master_width, self.master_height):
                    self._merge(changed)
                return

            opposite = {
                "nw": (x2, y2, x1, y1),
                "ne": (x1, y2, x2, y1),
                "se": (x1, y1, x2, y2),
                "sw": (x2, y1, x1, y2),
            }
            if self.mode == "scale":
                ax, ay, ox, oy = opposite[handle]
                sx = abs(point[0] - ax) / max(1, abs(ox - ax))
                sy = abs(point[1] - ay) / max(1, abs(oy - ay))
                scale = max(0.05, min(sx, sy))
                changed = [
                    _scale(mask, ax, ay, scale, scale)
                    for mask in self.snapshot_sel
                ]
            else:
                if handle == "e":
                    cx, cy = x1, (y1 + y2) / 2
                    sx = max(0.05, (point[0] - x1) / max(1, x2 - x1))
                    sy = 1
                elif handle == "w":
                    cx, cy = x2, (y1 + y2) / 2
                    sx = max(0.05, (x2 - point[0]) / max(1, x2 - x1))
                    sy = 1
                elif handle == "s":
                    cx, cy = (x1 + x2) / 2, y1
                    sx = 1
                    sy = max(0.05, (point[1] - y1) / max(1, y2 - y1))
                else:
                    cx, cy = (x1 + x2) / 2, y2
                    sx = 1
                    sy = max(0.05, (y2 - point[1]) / max(1, y2 - y1))
                changed = [
                    _scale(mask, cx, cy, sx, sy)
                    for mask in self.snapshot_sel
                ]
        if all(
            _valid(mask, self.master_width, self.master_height)
            for mask in changed
        ):
            self._merge(changed)

    def _release(self, event):
        point = self._to_master(event.x, event.y) or self.current_master
        if self.mode == "pending" and point is not None:
            if self.tool == TOOL_CIRCLE:
                mask = {
                    "id": self._next_id(),
                    "type": "circle",
                    "cx": point[0],
                    "cy": point[1],
                    "radius": DEFAULT_RADIUS_PX,
                }
                if _valid(mask, self.master_width, self.master_height):
                    self.masks.append(mask)
                    self.selected_ids = {_id(mask)}
            elif self.tool == TOOL_SEGMENT:
                mask = criar_segmento_display_por_arrasto(
                    *point,
                    *point,
                    id_mascara=self._next_id(),
                )
                if _valid(mask, self.master_width, self.master_height):
                    self.masks.append(mask)
                    self.selected_ids = {_id(mask)}
        elif (
            self.mode == "create_segment"
            and self.draft_segment
            and _valid(
                self.draft_segment,
                self.master_width,
                self.master_height,
            )
        ):
            self.masks.append(self.draft_segment)
            self.selected_ids = {_id(self.draft_segment)}
        elif self.mode == "create_circle" and point is not None:
            radius = int(round(math.dist(self.press_master, point)))
            mask = {
                "id": self._next_id(),
                "type": "circle",
                "cx": self.press_master[0],
                "cy": self.press_master[1],
                "radius": max(MIN_RADIUS_PX, min(MAX_RADIUS_PX, radius)),
            }
            if _valid(mask, self.master_width, self.master_height):
                self.masks.append(mask)
                self.selected_ids = {_id(mask)}
        self.mode = None
        self.handle = None
        self.draft_segment = None
        self.redraw()
        return "break"

    def _motion(self, event):
        self.pointer_canvas = (event.x, event.y)
        self.pointer_master = self._to_master(event.x, event.y)
        if self.freeform and self.pointer_master:
            self.freeform_mouse = self.pointer_master
        self.redraw()
        return None

    def _leave(self, _event=None):
        self.pointer_canvas = None
        self.pointer_master = None
        self.redraw()

    def _finish_freeform(self, _event=None):
        if len(self.freeform) >= 3:
            try:
                mask = criar_poligono_display_por_pontos(
                    self.freeform,
                    id_mascara=self._next_id(),
                )
            except ValueError:
                mask = None
            if (
                mask is not None
                and _valid(mask, self.master_width, self.master_height)
            ):
                self.masks.append(mask)
                self.selected_ids = {_id(mask)}
        self.freeform = []
        self.freeform_mouse = None
        self.redraw()
        return "break"

    def _escape(self, _event=None):
        if self.freeform:
            self.freeform = []
            self.freeform_mouse = None
        else:
            self.selected_ids = set()
        self.mode = None
        self.redraw()
        return "break"

    def _delete_selected(self, _event=None):
        self.masks = [
            mask
            for mask in self.masks
            if _id(mask) not in self.selected_ids
        ]
        self.selected_ids = set()
        self.redraw()
        return "break"

    def _select_all(self, _event=None):
        self.selected_ids = {_id(mask) for mask in self.masks}
        self.redraw()
        return "break"

    def _move_keyboard(self, event):
        dx = {"Left": -1, "Right": 1}.get(getattr(event, "keysym", ""), 0)
        dy = {"Up": -1, "Down": 1}.get(getattr(event, "keysym", ""), 0)
        snapshot = deepcopy(self.masks)
        changed = [
            _move(mask, dx, dy)
            for mask in self._selected()
        ]
        if all(
            _valid(mask, self.master_width, self.master_height)
            for mask in changed
        ):
            by_id = {_id(mask): mask for mask in changed}
            self.masks = [
                by_id.get(_id(mask), mask)
                for mask in snapshot
            ]
        self.redraw()
        return "break"

    @staticmethod
    def _wheel_dir(event):
        delta = int(getattr(event, "delta", 0) or 0)
        number = getattr(event, "num", None)
        if delta > 0 or number == 4:
            return 1
        if delta < 0 or number == 5:
            return -1
        return 0

    def _wheel(self, event):
        direction = self._wheel_dir(event)
        if not direction:
            return "break"
        if int(getattr(event, "state", 0) or 0) & CTRL_MASK:
            old = self.zoom_factor
            new = proximo_fator_zoom_selecao(old, direction)
            if new != old:
                viewport = self._vp()
                self.zoom_cx, self.zoom_cy = calcular_centro_zoom_ancorado(
                    ponteiro_x=event.x,
                    ponteiro_y=event.y,
                    escala_atual=viewport.escala,
                    deslocamento_atual_x=viewport.deslocamento_virtual_x,
                    deslocamento_atual_y=viewport.deslocamento_virtual_y,
                    largura_virtual_atual=viewport.largura_virtual,
                    altura_virtual_atual=viewport.altura_virtual,
                    nova_escala=viewport.escala * (new / old),
                    largura_canvas=max(1, self.canvas.winfo_width()),
                    altura_canvas=max(1, self.canvas.winfo_height()),
                    largura_visual=self.master_width,
                    altura_visual=self.master_height,
                    centro_atual_x=self.zoom_cx,
                    centro_atual_y=self.zoom_cy,
                )
                self.zoom_factor = new
                self.zoom_label.configure(
                    text=f"ZOOM {int(round(new * 100))}%"
                )
            self.redraw()
            return "break"

        changed = []
        for mask in self._selected():
            new_mask = deepcopy(mask)
            if new_mask.get("type") == "circle":
                new_mask["radius"] = max(
                    MIN_RADIUS_PX,
                    min(
                        MAX_RADIUS_PX,
                        int(new_mask["radius"]) + direction,
                    ),
                )
            changed.append(new_mask)
        if changed:
            by_id = {_id(mask): mask for mask in changed}
            self.masks = [
                by_id.get(_id(mask), mask)
                for mask in self.masks
            ]
            self.redraw()
        return "break"

    def _start_pan(self, event):
        if self.zoom_factor <= ZOOM_SELECAO_MIN:
            return "break"
        self.pan = True
        self.pan_last = (event.x, event.y)
        self.canvas.configure(cursor="fleur")
        return "break"

    def _drag_pan(self, event):
        if not self.pan or not self.pan_last:
            return "break"
        viewport = self._vp()
        dx = event.x - self.pan_last[0]
        dy = event.y - self.pan_last[1]
        self.pan_last = (event.x, event.y)
        cx = (
            (self.canvas.winfo_width() / 2 - viewport.deslocamento_virtual_x)
            / viewport.escala
            - dx / viewport.escala
        )
        cy = (
            (self.canvas.winfo_height() / 2 - viewport.deslocamento_virtual_y)
            / viewport.escala
            - dy / viewport.escala
        )
        self.zoom_cx = max(0, min(self.master_width, cx))
        self.zoom_cy = max(0, min(self.master_height, cy))
        self.redraw()
        return "break"

    def _end_pan(self, _event=None):
        self.pan = False
        self.pan_last = None
        self.canvas.configure(cursor="crosshair")
        return "break"
