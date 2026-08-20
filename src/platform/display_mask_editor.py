from __future__ import annotations

import base64
import tkinter as tk
from collections.abc import Callable
from copy import deepcopy

import cv2

from src.platform.display_mask_geometry import (
    DISPLAY_MASK_F2_PARITY_TOOLS, TOOL_CIRCLE, TOOL_FREEFORM, TOOL_MASS, TOOL_SEGMENT,
    _id, _segment_points, converter_mascara_legada_para_editor,
    bbox_mascara_display, criar_segmento_display_por_arrasto, mascara_display_contem_ponto,
)
from src.platform.display_mask_editor_interactions import (
    DisplayMaskEditorInteractionMixin,
)
from src.platform.display_project_repository import normalizar_mascaras_display, normalizar_resolucao_display
from src.ui.main_window_parts.image.selection_zoom import ZOOM_SELECAO_MIN

HANDLE_PX=7
MAGNIFIER_SIZE_PX=190

class DisplayMaskEditorWindow(DisplayMaskEditorInteractionMixin):
    """Editor F3 com as ferramentas do ``Selecionar LEDs`` do F2, estado isolado."""
    BG="#020617"; PANEL="#07111F"; MASK="#22D3EE"; SEL="#FBBF24"; ROT="#A78BFA"

    def __init__(self, root, master_resolution, masks, frame=None, on_save: Callable[[list[dict]],None]|None=None):
        res=normalizar_resolucao_display(master_resolution)
        if res is None: raise ValueError("Resolução mestre inválida para o editor Display")
        self.root=root; self.master_width,self.master_height=res; self.on_save=on_save
        self.masks=[converter_mascara_legada_para_editor(m) for m in normalizar_mascaras_display(deepcopy(masks or []))]
        self.frame=None
        if frame is not None and getattr(frame,"size",0)>0:
            self.frame=cv2.resize(frame,(self.master_width,self.master_height),interpolation=cv2.INTER_AREA) if tuple(frame.shape[:2])!=(self.master_height,self.master_width) else frame.copy()
        self.tool=TOOL_SEGMENT; self.selected_ids=set(); self.mode=None; self.handle=None
        self.press_canvas=None; self.press_master=None; self.current_master=None; self.snapshot=[]; self.snapshot_sel=[]; self.snapshot_bbox=None
        self.draft_segment=None; self.freeform=[]; self.freeform_mouse=None
        self.zoom_factor=ZOOM_SELECAO_MIN; self.zoom_cx=None; self.zoom_cy=None; self.pan=False; self.pan_last=None
        self._photo=None; self._magnifier=None; self.pointer_canvas=None; self.pointer_master=None
        self.window=tk.Toplevel(root); self.window.title("ODIN • Projeto Display • Seleção e ajuste de máscaras"); self.window.configure(bg=self.BG)
        self.window.protocol("WM_DELETE_WINDOW",self.close); self._toolbar()
        self.canvas=tk.Canvas(self.window,bg=self.BG,highlightthickness=0,cursor="crosshair",bd=0); self.canvas.pack(fill=tk.BOTH,expand=True)
        self.status=tk.Label(self.window,text="",font=("DejaVu Sans",9,"bold"),fg="#AAB8C8",bg=self.PANEL,anchor="w"); self.status.pack(fill=tk.X,padx=14,pady=(5,8))
        self._bind(); self._maximize(); self.set_tool(TOOL_SEGMENT); self.window.after(60,self.redraw); self.window.after(80,self.canvas.focus_set)

    @property
    def visible(self):
        try: return bool(self.window.winfo_exists())
        except Exception: return False

    def _toolbar(self):
        bar=tk.Frame(self.window,bg=self.PANEL,height=72); bar.pack(fill=tk.X); bar.pack_propagate(False)
        txt=tk.Frame(bar,bg=self.PANEL); txt.pack(side=tk.LEFT,fill=tk.BOTH,expand=True,padx=(18,8),pady=7)
        tk.Label(txt,text="SELEÇÃO E AJUSTE DE MÁSCARAS • PROJETO DISPLAY",font=("DejaVu Sans",12,"bold"),fg="#F9FAFB",bg=self.PANEL,anchor="w").pack(fill=tk.X)
        tk.Label(txt,text="Segmento: arraste • Shift+arraste seleciona área • Ctrl+scroll zoom • botão do meio arrasta • setas movem 1 px",font=("DejaVu Sans",8),fg="#AAB8C8",bg=self.PANEL,anchor="w").pack(fill=tk.X,pady=(2,0))
        tk.Button(bar,text="OK",command=self.save,font=("DejaVu Sans",10,"bold"),bg="#D6A900",fg="#111318",relief="flat",padx=24,pady=8).pack(side=tk.RIGHT,padx=(8,18),pady=12)
        self.zoom_label=tk.Label(bar,text="ZOOM 100%",font=("DejaVu Sans",9,"bold"),fg="#38BDF8",bg=self.PANEL,padx=8,pady=5); self.zoom_label.pack(side=tk.RIGHT,padx=8)
        buttons=tk.Frame(bar,bg=self.PANEL); buttons.pack(side=tk.RIGHT,padx=4); self.tool_buttons={}
        for tool,text in ((TOOL_SEGMENT,"▰ Segmento"),(TOOL_CIRCLE,"● Círculo"),(TOOL_FREEFORM,"✎ Segmento por pontos"),(TOOL_MASS,"▣ Seleção em massa")):
            b=tk.Button(buttons,text=text,command=lambda v=tool:self.set_tool(v),font=("DejaVu Sans",8,"bold"),relief="flat",padx=10,pady=5); b.pack(side=tk.LEFT,padx=2); self.tool_buttons[tool]=b

    def _bind(self):
        for seq,cb in (("<Configure>",lambda e:self.redraw()),("<Button-1>",self._press),("<B1-Motion>",self._drag),("<ButtonRelease-1>",self._release),("<Motion>",self._motion),("<Leave>",self._leave),("<Button-2>",self._start_pan),("<B2-Motion>",self._drag_pan),("<ButtonRelease-2>",self._end_pan),("<Delete>",self._delete_selected),("<BackSpace>",self._delete_selected),("<Escape>",self._escape),("<Control-a>",self._select_all),("<Control-A>",self._select_all),("<Left>",self._move_keyboard),("<Right>",self._move_keyboard),("<Up>",self._move_keyboard),("<Down>",self._move_keyboard),("<Return>",self._finish_freeform),("<KP_Enter>",self._finish_freeform)):
            self.canvas.bind(seq,cb)
        for seq in ("<MouseWheel>","<Button-4>","<Button-5>"): self.canvas.bind(seq,self._wheel,add="+")

    def _maximize(self):
        try: self.window.attributes("-fullscreen",True)
        except Exception: self.window.geometry(f"{max(900,self.root.winfo_screenwidth())}x{max(650,self.root.winfo_screenheight())}+0+0")

    def _background(self,v):
        if self.frame is None:return None
        crop=self.frame[v.origem_visual_y:v.fim_visual_y,v.origem_visual_x:v.fim_visual_x]
        if crop.size==0:return None
        img=cv2.resize(crop,(v.largura_render,v.altura_render),interpolation=cv2.INTER_AREA if v.escala<1 else cv2.INTER_LINEAR)
        ok,b=cv2.imencode(".png",img,[cv2.IMWRITE_PNG_COMPRESSION,1]); return tk.PhotoImage(data=base64.b64encode(b).decode("ascii")) if ok else None
    def _draw_mask(self,m):
        c=self.SEL if _id(m) in self.selected_ids else self.MASK; w=3 if _id(m) in self.selected_ids else 2; kind=m.get("type")
        if kind=="circle":
            x,y=self._to_canvas(m["cx"],m["cy"]); r=m["radius"]*self._vp().escala; self.canvas.create_oval(x-r,y-r,x+r,y+r,outline=c,width=w)
        else:
            pts=_segment_points(m) if kind=="segment" else m.get("points",[]); coords=[]
            for p in pts: coords.extend(self._to_canvas(p[0],p[1]))
            if len(coords)>=6:self.canvas.create_polygon(*coords,fill="",outline=c,width=w)
    def _draw_handles(self):
        hs=self._handles()
        for name,p in hs.items():
            x,y=self._to_canvas(*p); r=HANDLE_PX
            if name=="rotate":
                if "n" in hs:
                    nx,ny=self._to_canvas(*hs["n"]); self.canvas.create_line(nx,ny,x,y,fill=self.ROT,width=2,dash=(3,3))
                self.canvas.create_oval(x-r,y-r,x+r,y+r,fill=self.ROT,outline="#111827")
            else:self.canvas.create_rectangle(x-r,y-r,x+r,y+r,fill="#38BDF8" if name in {"n","e","s","w"} else self.SEL,outline="#111827")
    def _draw_freeform(self):
        if not self.freeform:return
        pts=[self._to_canvas(*p) for p in self.freeform]
        if len(pts)>=2:self.canvas.create_line(*[v for p in pts for v in p],fill="#38BDF8",width=3)
        if self.freeform_mouse:
            self.canvas.create_line(*pts[-1],*self._to_canvas(*self.freeform_mouse),fill="#7DD3FC",width=2,dash=(6,4))
        for i,(x,y) in enumerate(pts):r=7 if i==0 else 4;self.canvas.create_oval(x-r,y-r,x+r,y+r,fill="#FBBF24" if i==0 else "#38BDF8")
    def _draw_magnifier(self):
        if self.frame is None or self.pointer_canvas is None or self.pointer_master is None:return
        x,y=self.pointer_master; r=28; x1,x2=max(0,x-r),min(self.master_width,x+r); y1,y2=max(0,y-r),min(self.master_height,y+r); crop=self.frame[y1:y2,x1:x2]
        if crop.size==0:return
        img=cv2.resize(crop,(MAGNIFIER_SIZE_PX,MAGNIFIER_SIZE_PX),interpolation=cv2.INTER_NEAREST); ok,b=cv2.imencode(".png",img)
        if not ok:return
        self._magnifier=tk.PhotoImage(data=base64.b64encode(b).decode("ascii")); cw=max(1,self.canvas.winfo_width()); lx=cw-MAGNIFIER_SIZE_PX-18
        if self.pointer_canvas[0]>lx-20:lx=18
        ly=42; self.canvas.create_image(lx,ly,image=self._magnifier,anchor="nw"); self.canvas.create_rectangle(lx,ly,lx+MAGNIFIER_SIZE_PX,ly+MAGNIFIER_SIZE_PX,outline="#38BDF8",width=2)
    def redraw(self):
        if not self.visible:return
        self.canvas.delete("all"); v=self._vp(); self._photo=self._background(v)
        if self._photo:self.canvas.create_image(v.deslocamento_render_x,v.deslocamento_render_y,image=self._photo,anchor="nw")
        else:self.canvas.create_rectangle(v.deslocamento_virtual_x,v.deslocamento_virtual_y,v.deslocamento_virtual_x+v.largura_virtual,v.deslocamento_virtual_y+v.altura_virtual,fill="#0B1220",outline="#1E293B")
        for m in self.masks:self._draw_mask(m)
        if self.draft_segment:self._draw_mask(self.draft_segment)
        self._draw_freeform(); self._draw_handles(); self._draw_magnifier(); self.status.configure(text=f"Projeto Display • {len(self.masks)} máscara(s) • {len(self.selected_ids)} selecionada(s) • Zoom {int(round(self.zoom_factor*100))}%")

    def save(self):
        if self.freeform:self._finish_freeform()
        masks=normalizar_mascaras_display(deepcopy(self.masks))
        if self.on_save:self.on_save(masks)
        self.close()
    def close(self):
        try:self.window.destroy()
        except Exception:pass
