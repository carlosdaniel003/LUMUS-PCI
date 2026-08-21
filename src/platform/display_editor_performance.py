from __future__ import annotations

import base64
import time
import tkinter as tk

import cv2


# Mantém a mesma cadência de lupa já usada no editor F2 e limita apenas eventos
# contínuos. Cliques, soltura, teclado e salvamento continuam síncronos.
DISPLAY_EDITOR_POINTER_INTERVAL_S = 0.040
DISPLAY_EDITOR_DRAG_INTERVAL_S = 1.0 / 60.0


def viewport_render_cache_key(viewport, frame=None) -> tuple:
    """Assinatura do recorte visual; mudanças de ROI não invalidam o fundo."""
    shape = tuple(getattr(frame, "shape", ()) or ())
    return (
        id(frame),
        shape,
        int(viewport.origem_visual_x),
        int(viewport.origem_visual_y),
        int(viewport.fim_visual_x),
        int(viewport.fim_visual_y),
        int(viewport.largura_render),
        int(viewport.altura_render),
        int(viewport.deslocamento_render_x),
        int(viewport.deslocamento_render_y),
    )


def interaction_redraw_due(last_time: float, now: float, interval: float) -> bool:
    return float(now) - float(last_time or 0.0) >= max(0.0, float(interval))


def _photo_from_bgr_fast(image):
    """PhotoImage sem PNG/Base64 no caminho quente, com fallback compatível."""
    if image is None or getattr(image, "size", 0) == 0:
        return None
    try:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        header = f"P6\n{width} {height}\n255\n".encode("ascii")
        return tk.PhotoImage(
            data=header + rgb.tobytes(),
            format="PPM",
        )
    except Exception:
        try:
            ok, buffer = cv2.imencode(
                ".png",
                image,
                [cv2.IMWRITE_PNG_COMPRESSION, 1],
            )
            if not ok:
                return None
            return tk.PhotoImage(data=base64.b64encode(buffer).decode("ascii"))
        except Exception:
            return None


def _throttled_interaction(original, last_attr: str, interval: float):
    """Executa a geometria sempre; apenas pula redraws intermediários demais."""

    def wrapped(self, event):
        now = time.perf_counter()
        last = float(getattr(self, last_attr, 0.0) or 0.0)
        allow_redraw = interaction_redraw_due(last, now, interval)
        if allow_redraw:
            setattr(self, last_attr, now)

        previous = bool(getattr(self, "_odin_editor_suppress_redraw", False))
        self._odin_editor_suppress_redraw = previous or not allow_redraw
        try:
            return original(self, event)
        finally:
            self._odin_editor_suppress_redraw = previous

    return wrapped


def instalar_otimizacao_editor_mascaras_display_f3() -> None:
    import src.platform.display_mask_editor as mask_module

    cls = mask_module.DisplayMaskEditorWindow
    if getattr(cls, "_odin_display_editor_performance", False):
        return

    original_init = cls.__init__
    original_redraw = cls.redraw
    original_motion = cls._motion
    original_drag = cls._drag
    original_drag_pan = cls._drag_pan

    def init(self, *args, **kwargs) -> None:
        self._odin_editor_background_key = None
        self._odin_editor_background_photo = None
        self._odin_editor_suppress_redraw = False
        self._odin_editor_last_motion_s = 0.0
        self._odin_editor_last_drag_s = 0.0
        self._odin_editor_last_pan_s = 0.0
        original_init(self, *args, **kwargs)

    def redraw(self) -> None:
        if bool(getattr(self, "_odin_editor_suppress_redraw", False)):
            return
        return original_redraw(self)

    def background(self, viewport):
        frame = getattr(self, "frame", None)
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        key = viewport_render_cache_key(viewport, frame)
        if (
            key == getattr(self, "_odin_editor_background_key", None)
            and getattr(self, "_odin_editor_background_photo", None) is not None
        ):
            return self._odin_editor_background_photo

        crop = frame[
            viewport.origem_visual_y:viewport.fim_visual_y,
            viewport.origem_visual_x:viewport.fim_visual_x,
        ]
        if getattr(crop, "size", 0) == 0:
            return None
        image = cv2.resize(
            crop,
            (
                max(1, int(viewport.largura_render)),
                max(1, int(viewport.altura_render)),
            ),
            interpolation=(
                cv2.INTER_AREA if viewport.escala < 1.0 else cv2.INTER_LINEAR
            ),
        )
        photo = _photo_from_bgr_fast(image)
        if photo is not None:
            self._odin_editor_background_key = key
            self._odin_editor_background_photo = photo
        return photo

    def draw_magnifier(self) -> None:
        frame = getattr(self, "frame", None)
        pointer_canvas = getattr(self, "pointer_canvas", None)
        pointer_master = getattr(self, "pointer_master", None)
        if (
            frame is None
            or getattr(frame, "size", 0) == 0
            or pointer_canvas is None
            or pointer_master is None
        ):
            return

        x, y = pointer_master
        radius = 28
        x1, x2 = max(0, x - radius), min(self.master_width, x + radius)
        y1, y2 = max(0, y - radius), min(self.master_height, y + radius)
        crop = frame[y1:y2, x1:x2]
        if getattr(crop, "size", 0) == 0:
            return

        size = int(mask_module.MAGNIFIER_SIZE_PX)
        image = cv2.resize(
            crop,
            (size, size),
            interpolation=cv2.INTER_NEAREST,
        )
        self._magnifier = _photo_from_bgr_fast(image)
        if self._magnifier is None:
            return

        canvas_width = max(1, int(self.canvas.winfo_width()))
        left = canvas_width - size - 18
        if pointer_canvas[0] > left - 20:
            left = 18
        top = 42
        self.canvas.create_image(
            left,
            top,
            image=self._magnifier,
            anchor="nw",
        )
        self.canvas.create_rectangle(
            left,
            top,
            left + size,
            top + size,
            outline="#38BDF8",
            width=2,
        )

    cls.__init__ = init
    cls.redraw = redraw
    cls._background = background
    cls._draw_magnifier = draw_magnifier
    cls._motion = _throttled_interaction(
        original_motion,
        "_odin_editor_last_motion_s",
        DISPLAY_EDITOR_POINTER_INTERVAL_S,
    )
    cls._drag = _throttled_interaction(
        original_drag,
        "_odin_editor_last_drag_s",
        DISPLAY_EDITOR_DRAG_INTERVAL_S,
    )
    cls._drag_pan = _throttled_interaction(
        original_drag_pan,
        "_odin_editor_last_pan_s",
        DISPLAY_EDITOR_DRAG_INTERVAL_S,
    )
    cls._odin_display_editor_performance = True


def instalar_otimizacao_editor_check_display_f3() -> None:
    import src.platform.display_check_editor as check_module

    cls = check_module.DisplayCheckMaskEditorWindow
    if getattr(cls, "_odin_display_check_editor_performance", False):
        return

    original_init = cls.__init__
    original_redraw = cls.redraw
    original_pan = getattr(cls, "_arrastar_pan_check", None)

    def init(self, *args, **kwargs) -> None:
        self._odin_check_background_key = None
        self._odin_check_background_photo = None
        self._odin_editor_suppress_redraw = False
        self._odin_check_last_pan_s = 0.0
        original_init(self, *args, **kwargs)

    def redraw(self) -> None:
        if bool(getattr(self, "_odin_editor_suppress_redraw", False)):
            return
        return original_redraw(self)

    def background_zoom(self, viewport):
        frame = getattr(self, "frame", None)
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        key = viewport_render_cache_key(viewport, frame)
        if (
            key == getattr(self, "_odin_check_background_key", None)
            and getattr(self, "_odin_check_background_photo", None) is not None
        ):
            return self._odin_check_background_photo

        crop = frame[
            viewport.origem_visual_y:viewport.fim_visual_y,
            viewport.origem_visual_x:viewport.fim_visual_x,
        ]
        if getattr(crop, "size", 0) == 0:
            return None
        image = cv2.resize(
            crop,
            (
                max(1, int(viewport.largura_render)),
                max(1, int(viewport.altura_render)),
            ),
            interpolation=(
                cv2.INTER_AREA if viewport.escala < 1.0 else cv2.INTER_LINEAR
            ),
        )
        photo = _photo_from_bgr_fast(image)
        if photo is not None:
            self._odin_check_background_key = key
            self._odin_check_background_photo = photo
        return photo

    def background_plain(self, render_width: int, render_height: int):
        frame = getattr(self, "frame", None)
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        key = (
            id(frame),
            tuple(getattr(frame, "shape", ()) or ()),
            int(render_width),
            int(render_height),
        )
        if (
            key == getattr(self, "_odin_check_background_key", None)
            and getattr(self, "_odin_check_background_photo", None) is not None
        ):
            return self._odin_check_background_photo
        image = cv2.resize(
            frame,
            (max(1, int(render_width)), max(1, int(render_height))),
            interpolation=cv2.INTER_AREA,
        )
        photo = _photo_from_bgr_fast(image)
        if photo is not None:
            self._odin_check_background_key = key
            self._odin_check_background_photo = photo
        return photo

    def update_segment_button(self, index: int) -> None:
        if index < 0 or index >= len(self.masks):
            return
        if index >= len(getattr(self, "_segment_buttons", ())):
            return
        mask = self.masks[index]
        mask_id = str(mask["id"])
        state = self.states.get(
            mask_id,
            check_module.DISPLAY_CHECK_STATE_IGNORE,
        )
        label = check_module.CHECK_STATE_LABELS.get(state, "IGNORAR")
        color = check_module.CHECK_STATE_COLORS.get(state, self.MUTED)
        try:
            self._segment_buttons[index].configure(
                text=f"{check_module.nome_segmento_display(index)}    {label}",
                fg=color,
                activeforeground=color,
            )
        except Exception:
            pass

    def toggle_mask(self, index: int) -> None:
        if index < 0 or index >= len(self.masks):
            return
        mask_id = str(self.masks[index]["id"])
        self.states[mask_id] = check_module.proximo_estado_check_display(
            self.states.get(mask_id)
        )
        update_segment_button(self, index)
        self.redraw()

    def set_all_ignore(self) -> None:
        for mask_id in self.mask_ids:
            self.states[mask_id] = check_module.DISPLAY_CHECK_STATE_IGNORE
        for index in range(len(self.masks)):
            update_segment_button(self, index)
        self.redraw()

    cls.__init__ = init
    cls.redraw = redraw
    cls.toggle_mask = toggle_mask
    cls.set_all_ignore = set_all_ignore
    cls._odin_update_segment_button = update_segment_button
    cls._background_photo = background_plain

    # A classe com zoom é instalada antes desta extensão. Se o método existir,
    # substituímos somente a geração do bitmap de fundo e limitamos o pan.
    if hasattr(cls, "_background_zoom_check"):
        cls._background_zoom_check = background_zoom
    if callable(original_pan):
        cls._arrastar_pan_check = _throttled_interaction(
            original_pan,
            "_odin_check_last_pan_s",
            DISPLAY_EDITOR_DRAG_INTERVAL_S,
        )

    cls._odin_display_check_editor_performance = True


def instalar_otimizacoes_editores_display_f3() -> None:
    instalar_otimizacao_editor_mascaras_display_f3()
    instalar_otimizacao_editor_check_display_f3()


instalar_otimizacoes_editores_display_f3()
