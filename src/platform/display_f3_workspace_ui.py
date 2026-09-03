from __future__ import annotations

"""Layout desktop consistente para as janelas exclusivas do Display F3.

A camada é intencionalmente aplicada por monkey-patch no bootstrap F3 para não
alterar telas compartilhadas do F2. O objetivo é usar a área disponível sem
simplesmente esticar a antiga composição de 820 px.
"""

from src.platform.display_check_editor import (
    DisplayCheckManagerWindow,
    DisplayCheckMaskEditorWindow,
)
from src.platform.display_mask_editor import DisplayMaskEditorWindow
from src.platform.display_project_config import DisplayProjectConfigWindow
from src.platform.display_reference_learning import DisplayReferenceConfigWindow
from src.platform.display_reference_roi import DisplayReferenceRoiDialog


F3_DESKTOP_MIN_WIDTH = 900
F3_DESKTOP_MIN_HEIGHT = 620
F3_PROJECT_NAV_WIDTH = 300
F3_CHECK_NAV_WIDTH = 380
F3_WORKSPACE_MAX_WIDTH = 1180
F3_EDITOR_REDRAW_DELAY_MS = 70


def maximizar_janela_workspace_f3(window) -> str:
    """Maximiza preservando barra de título; funciona em Windows, X11 e fallback Tk."""
    try:
        window.resizable(True, True)
    except Exception:
        pass
    try:
        window.minsize(F3_DESKTOP_MIN_WIDTH, F3_DESKTOP_MIN_HEIGHT)
    except Exception:
        pass
    try:
        window.update_idletasks()
    except Exception:
        pass

    try:
        window.state("zoomed")
        return "state_zoomed"
    except Exception:
        pass
    try:
        window.attributes("-zoomed", True)
        return "attribute_zoomed"
    except Exception:
        pass
    try:
        width = max(F3_DESKTOP_MIN_WIDTH, int(window.winfo_screenwidth()))
        height = max(F3_DESKTOP_MIN_HEIGHT, int(window.winfo_screenheight()))
        window.geometry(f"{width}x{height}+0+0")
        return "screen_geometry"
    except Exception:
        return "unavailable"


def _reaplicar_maximizacao(owner) -> None:
    window = getattr(owner, "window", None)
    if window is None:
        return
    try:
        owner._display_f3_workspace_window_mode = maximizar_janela_workspace_f3(window)
    except Exception:
        pass


def _centralizar_conteudo_canvas(canvas, max_width: int = F3_WORKSPACE_MAX_WIDTH) -> None:
    """Mantém o workspace legível em 1920 px sem criar faixas de 1500 px."""
    if canvas is None:
        return
    try:
        window_items = [item for item in canvas.find_all() if canvas.type(item) == "window"]
    except Exception:
        window_items = []
    if not window_items:
        return
    window_id = window_items[0]

    def fit(event) -> None:
        try:
            available = max(1, int(event.width))
            width = max(680, min(int(max_width), available - 24))
            x = max(12, (available - width) // 2)
            canvas.itemconfigure(window_id, width=width)
            canvas.coords(window_id, x, 0)
        except Exception:
            pass

    try:
        canvas.bind("<Configure>", fit)
    except Exception:
        pass


def aplicar_workspace_projeto_display_f3(owner) -> None:
    """Sidebar estreita + workspace central, sem o grande vazio preto da versão esticada."""
    project_list = getattr(owner, "project_list", None)
    project_state = getattr(owner, "project_state", None)
    if project_list is None or project_state is None:
        return

    list_frame = getattr(project_list, "master", None)
    left = getattr(list_frame, "master", None)
    body = getattr(left, "master", None)

    right = getattr(project_state, "master", None)
    right_canvas = getattr(right, "master", None)
    right_shell = getattr(right_canvas, "master", None)

    if body is not None:
        try:
            body.pack_configure(fill="both", expand=True, padx=24, pady=(0, 14))
        except Exception:
            pass

    if left is not None:
        try:
            left.configure(width=F3_PROJECT_NAV_WIDTH)
            left.pack_configure(side="left", fill="y", expand=False, padx=(0, 14))
            left.pack_propagate(False)
        except Exception:
            pass

    try:
        project_list.configure(
            bg="#07111F",
            font=("Segoe UI", 10, "bold"),
            selectbackground="#164E63",
        )
    except Exception:
        pass

    if right_shell is not None:
        try:
            right_shell.pack_configure(side="right", fill="both", expand=True, padx=0)
            right_shell.pack_propagate(True)
        except Exception:
            pass

    _centralizar_conteudo_canvas(right_canvas)

    try:
        owner.project_title.configure(font=("Segoe UI", 18, "bold"))
        owner.project_state.configure(font=("Segoe UI", 10), wraplength=1040)
    except Exception:
        pass


def aplicar_workspace_checks_display_f3(owner) -> None:
    """Lista de sequência como navegação e detalhe do CHECK usando o restante da tela."""
    check_list = getattr(owner, "check_list", None)
    check_title = getattr(owner, "check_title", None)
    if check_list is None or check_title is None:
        return

    list_frame = getattr(check_list, "master", None)
    left = getattr(list_frame, "master", None)
    body = getattr(left, "master", None)
    right = getattr(check_title, "master", None)

    if body is not None:
        try:
            body.pack_configure(fill="both", expand=True, padx=24, pady=(0, 14))
        except Exception:
            pass
    if left is not None:
        try:
            left.configure(width=F3_CHECK_NAV_WIDTH)
            left.pack_configure(side="left", fill="y", expand=False, padx=(0, 14))
            left.pack_propagate(False)
        except Exception:
            pass
    if right is not None:
        try:
            right.pack_configure(side="right", fill="both", expand=True, padx=0)
            right.pack_propagate(True)
        except Exception:
            pass

        def fit_detail(event) -> None:
            status = getattr(owner, "status", None)
            if status is not None:
                try:
                    status.configure(wraplength=max(360, int(event.width) - 54))
                except Exception:
                    pass

        try:
            right.bind("<Configure>", fit_detail, add="+")
        except Exception:
            pass

    try:
        check_list.configure(bg="#07111F", selectbackground="#164E63")
        check_title.configure(font=("Segoe UI", 18, "bold"))
    except Exception:
        pass


def _instalar_redraw_configuracao_debounced(cls) -> None:
    """Evita tempestade de redraw durante maximização/redimensionamento do canvas."""
    original_init = cls.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        self._display_f3_resize_redraw_after_id = None

        def schedule(_event=None, owner=self):
            previous = getattr(owner, "_display_f3_resize_redraw_after_id", None)
            if previous is not None:
                try:
                    owner.window.after_cancel(previous)
                except Exception:
                    pass
            try:
                owner._display_f3_resize_redraw_after_id = owner.window.after(
                    F3_EDITOR_REDRAW_DELAY_MS,
                    lambda: _finish_resize_redraw(owner),
                )
            except Exception:
                owner._display_f3_resize_redraw_after_id = None

        try:
            canvas.bind("<Configure>", schedule)
        except Exception:
            pass

    cls.__init__ = init


def _finish_resize_redraw(owner) -> None:
    owner._display_f3_resize_redraw_after_id = None
    try:
        owner.redraw()
    except Exception:
        pass


_INSTALLED = False


def instalar_workspace_telas_display_f3() -> None:
    """Aplica fullscreen responsivo a todas as telas de configuração do F3."""
    global _INSTALLED
    if _INSTALLED:
        return

    # Projeto Display: corrige a antiga expansão 310/450 que gerava um vazio enorme.
    original_project_init = DisplayProjectConfigWindow.__init__

    def project_init(self, *args, **kwargs):
        original_project_init(self, *args, **kwargs)
        aplicar_workspace_projeto_display_f3(self)
        _reaplicar_maximizacao(self)
        try:
            self.window.after_idle(lambda owner=self: _reaplicar_maximizacao(owner))
        except Exception:
            pass

    DisplayProjectConfigWindow.__init__ = project_init

    # Gerenciar CHECKS.
    original_manager_init = DisplayCheckManagerWindow.__init__

    def manager_init(self, *args, **kwargs):
        original_manager_init(self, *args, **kwargs)
        aplicar_workspace_checks_display_f3(self)
        _reaplicar_maximizacao(self)
        try:
            self.window.after_idle(lambda owner=self: _reaplicar_maximizacao(owner))
        except Exception:
            pass

    DisplayCheckManagerWindow.__init__ = manager_init

    # Editores visuais: maximização nativa com barra de título, sem fullscreen
    # borderless; o canvas continua usando toda a área restante.
    def maximize_editor(self):
        self._display_f3_workspace_window_mode = maximizar_janela_workspace_f3(self.window)

    DisplayCheckMaskEditorWindow._maximize = maximize_editor
    DisplayMaskEditorWindow._maximize = maximize_editor

    _instalar_redraw_configuracao_debounced(DisplayCheckMaskEditorWindow)
    _instalar_redraw_configuracao_debounced(DisplayMaskEditorWindow)

    # Referências ACESO/APAGADO/POUCA LUZ.
    original_reference_init = DisplayReferenceConfigWindow.__init__

    def reference_init(self, *args, **kwargs):
        original_reference_init(self, *args, **kwargs)
        try:
            self.grid.pack_configure(fill="both", expand=True, padx=28, pady=(0, 14))
        except Exception:
            pass
        _reaplicar_maximizacao(self)
        try:
            self.window.after_idle(lambda owner=self: _reaplicar_maximizacao(owner))
        except Exception:
            pass

    DisplayReferenceConfigWindow.__init__ = reference_init

    # ROI das referências físicas / CHECK: mantém a seleção modal, mas em tela cheia.
    original_roi_init = DisplayReferenceRoiDialog.__init__

    def roi_init(self, *args, **kwargs):
        original_roi_init(self, *args, **kwargs)
        _reaplicar_maximizacao(self)
        try:
            self.window.after_idle(lambda owner=self: _reaplicar_maximizacao(owner))
        except Exception:
            pass

    DisplayReferenceRoiDialog.__init__ = roi_init

    for cls in (
        DisplayProjectConfigWindow,
        DisplayCheckManagerWindow,
        DisplayCheckMaskEditorWindow,
        DisplayMaskEditorWindow,
        DisplayReferenceConfigWindow,
        DisplayReferenceRoiDialog,
    ):
        cls._display_f3_workspace_ui_installed = True

    _INSTALLED = True
