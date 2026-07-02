from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable


class SelectLista(tk.Frame):
    """Select visual com lista própria, independente do popup nativo do ttk."""

    COR_FUNDO = "#020617"
    COR_FUNDO_ATIVO = "#102033"
    COR_BORDA = "#122033"
    COR_TEXTO = "#F9FAFB"
    COR_TEXTO_SECUNDARIO = "#CBD5E1"
    COR_SELECAO = "#0F3D24"
    COR_SELECAO_TEXTO = "#BBF7D0"

    def __init__(
        self,
        master,
        textvariable: tk.StringVar | None = None,
        values: Iterable[str] = (),
        state: str = "normal",
        width: int = 20,
        font=None,
        style: str | None = None,
        **kwargs,
    ) -> None:
        background = self._obter_cor_parent(master)
        super().__init__(
            master,
            bg=background,
            highlightthickness=1,
            highlightbackground=self.COR_BORDA,
            bd=0,
        )

        self._textvariable = textvariable or tk.StringVar(self)
        self._values = tuple(str(valor) for valor in values)
        self._state = str(state)
        self._width = max(8, int(width))
        self._font = font or ("Segoe UI", 9, "bold")
        self._list_height = max(4, min(10, len(self._values) or 4))
        self._popup: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None

        self._button_value = tk.Button(
            self,
            textvariable=self._textvariable,
            command=self._abrir_lista,
            font=self._font,
            width=self._width,
            anchor="w",
            padx=9,
            pady=6,
            bg=self.COR_FUNDO,
            fg=self.COR_TEXTO,
            activebackground=self.COR_FUNDO_ATIVO,
            activeforeground=self.COR_TEXTO,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self._button_value.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._button_arrow = tk.Button(
            self,
            text="▼",
            command=self._abrir_lista,
            font=("Segoe UI Symbol", 8, "bold"),
            width=3,
            bg=self.COR_FUNDO,
            fg=self.COR_TEXTO_SECUNDARIO,
            activebackground=self.COR_FUNDO_ATIVO,
            activeforeground=self.COR_TEXTO,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=False,
        )
        self._button_arrow.pack(side=tk.RIGHT, fill=tk.Y)

        self._button_value.bind("<Return>", self._abrir_lista_evento)
        self._button_value.bind("<space>", self._abrir_lista_evento)
        self._button_value.bind("<Down>", self._abrir_lista_evento)
        self.bind("<Destroy>", self._ao_destruir, add="+")

        self._aplicar_estado()

    @staticmethod
    def _obter_cor_parent(master) -> str:
        try:
            return str(master.cget("bg"))
        except (tk.TclError, AttributeError):
            return "#0B1626"

    def _abrir_lista_evento(self, _evento=None) -> str:
        self._abrir_lista()
        return "break"

    def _abrir_lista(self) -> None:
        if self._state == "disabled" or not self._values:
            return

        if self._popup is not None and self._popup.winfo_exists():
            self._fechar_lista()
            return

        self.update_idletasks()

        popup = tk.Toplevel(self)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.configure(bg=self.COR_BORDA)
        popup.transient(self.winfo_toplevel())

        largura = max(self.winfo_width(), 180)
        altura_item = 28
        quantidade_visivel = max(
            1,
            min(self._list_height, len(self._values)),
        )
        altura = quantidade_visivel * altura_item + 4
        posicao_x = self.winfo_rootx()
        posicao_y = self.winfo_rooty() + self.winfo_height() + 2

        popup.geometry(
            f"{largura}x{altura}+{posicao_x}+{posicao_y}"
        )

        listbox = tk.Listbox(
            popup,
            exportselection=False,
            selectmode=tk.BROWSE,
            activestyle="none",
            font=self._font,
            bg=self.COR_FUNDO,
            fg=self.COR_TEXTO,
            selectbackground=self.COR_SELECAO,
            selectforeground=self.COR_SELECAO_TEXTO,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.COR_BORDA,
            highlightcolor=self.COR_BORDA,
        )
        listbox.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        for valor in self._values:
            listbox.insert(tk.END, valor)

        valor_atual = self.get()
        if valor_atual in self._values:
            indice = self._values.index(valor_atual)
            listbox.selection_set(indice)
            listbox.activate(indice)
            listbox.see(indice)
        elif self._values:
            listbox.selection_set(0)
            listbox.activate(0)

        listbox.bind("<ButtonRelease-1>", self._selecionar_item)
        listbox.bind("<Return>", self._selecionar_item)
        listbox.bind("<space>", self._selecionar_item)
        listbox.bind("<Escape>", self._fechar_lista_evento)
        listbox.bind(
            "<MouseWheel>",
            lambda evento: listbox.yview_scroll(
                int(-evento.delta / 120),
                "units",
            ),
        )
        popup.bind("<Escape>", self._fechar_lista_evento)
        popup.bind("<FocusOut>", self._fechar_lista_apos_foco)

        self._popup = popup
        self._listbox = listbox

        popup.deiconify()
        popup.lift()
        try:
            popup.attributes("-topmost", True)
            popup.after_idle(
                lambda: popup.attributes("-topmost", False)
            )
        except tk.TclError:
            pass

        listbox.focus_force()

    def _selecionar_item(self, _evento=None) -> str:
        if self._listbox is None:
            return "break"

        selecao = self._listbox.curselection()
        if not selecao:
            return "break"

        valor = str(self._listbox.get(selecao[0]))
        self.set(valor)
        self._fechar_lista()
        self.event_generate("<<ComboboxSelected>>")
        return "break"

    def _fechar_lista_apos_foco(self, _evento=None) -> None:
        popup = self._popup
        if popup is None:
            return

        popup.after(80, self._fechar_se_fora_do_popup)

    def _fechar_se_fora_do_popup(self) -> None:
        popup = self._popup
        if popup is None or not popup.winfo_exists():
            return

        foco = popup.focus_get()
        if foco is not None and str(foco).startswith(str(popup)):
            return

        self._fechar_lista()

    def _fechar_lista_evento(self, _evento=None) -> str:
        self._fechar_lista()
        return "break"

    def _fechar_lista(self) -> None:
        popup = self._popup
        self._popup = None
        self._listbox = None

        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass

    def _ao_destruir(self, evento) -> None:
        if evento.widget is self:
            self._fechar_lista()

    def _aplicar_estado(self) -> None:
        desabilitado = self._state == "disabled"
        estado = tk.DISABLED if desabilitado else tk.NORMAL
        cursor = "arrow" if desabilitado else "hand2"
        cor_texto = "#94A3B8" if desabilitado else self.COR_TEXTO
        cor_seta = "#64748B" if desabilitado else self.COR_TEXTO_SECUNDARIO

        self._button_value.configure(
            state=estado,
            cursor=cursor,
            fg=cor_texto,
        )
        self._button_arrow.configure(
            state=estado,
            cursor=cursor,
            fg=cor_seta,
        )

    def get(self) -> str:
        return str(self._textvariable.get())

    def set(self, value: str) -> None:
        self._textvariable.set(str(value))

    def current(self, index: int | None = None):
        if index is None:
            valor_atual = self.get()
            try:
                return self._values.index(valor_atual)
            except ValueError:
                return -1

        if 0 <= int(index) < len(self._values):
            self.set(self._values[int(index)])
        return None

    def instate(self, statespec) -> bool:
        estados = tuple(statespec or ())
        if "disabled" in estados:
            return self._state == "disabled"
        if "!disabled" in estados:
            return self._state != "disabled"
        if "readonly" in estados:
            return self._state == "readonly"
        return False

    def state(self, statespec=None):
        if statespec is None:
            return (self._state,)

        for estado in statespec:
            if estado == "disabled":
                self._state = "disabled"
            elif estado == "!disabled" and self._state == "disabled":
                self._state = "readonly"
            elif estado == "readonly":
                self._state = "readonly"

        self._aplicar_estado()
        return ()

    def configure(self, cnf=None, **kwargs):
        opcoes = {}
        if isinstance(cnf, dict):
            opcoes.update(cnf)
        opcoes.update(kwargs)

        if not opcoes:
            return super().configure()

        if "state" in opcoes:
            self._state = str(opcoes.pop("state"))
        if "values" in opcoes:
            self._values = tuple(
                str(valor)
                for valor in opcoes.pop("values")
            )
        if "height" in opcoes:
            self._list_height = max(1, int(opcoes.pop("height")))
        if "width" in opcoes:
            self._width = max(8, int(opcoes.pop("width")))
            self._button_value.configure(width=self._width)
        if "font" in opcoes:
            self._font = opcoes.pop("font")
            self._button_value.configure(font=self._font)
        if "cursor" in opcoes:
            cursor = str(opcoes.pop("cursor"))
            self._button_value.configure(cursor=cursor)
            self._button_arrow.configure(cursor=cursor)
        if "takefocus" in opcoes:
            self._button_value.configure(
                takefocus=opcoes.pop("takefocus")
            )
        opcoes.pop("style", None)

        self._aplicar_estado()

        if opcoes:
            return super().configure(**opcoes)
        return None

    config = configure

    def cget(self, key: str):
        if key == "state":
            return self._state
        if key == "values":
            return self._values
        if key == "width":
            return self._width
        if key == "height":
            return self._list_height
        if key == "textvariable":
            return str(self._textvariable)
        return super().cget(key)
