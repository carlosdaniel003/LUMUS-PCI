from __future__ import annotations

import math
from copy import deepcopy

from config import DEFAULT_RADIUS_PX, MAX_RADIUS_PX, MIN_RADIUS_PX
from src.core.roi_geometry import SEGMENTO_ALTURA_MINIMA, SEGMENTO_LARGURA_MINIMA
from src.platform.display_mask_geometry import (
    DISPLAY_MASK_F2_PARITY_TOOLS, TOOL_CIRCLE, TOOL_FREEFORM, TOOL_MASS, TOOL_SEGMENT,
    _area, _bbox, _id, _move, _rotate, _rotate_xy, _scale, _valid,
    bbox_mascara_display, criar_segmento_display_por_arrasto, mascara_display_contem_ponto,
)
from src.ui.main_window_parts.image.selection_zoom import (
    ZOOM_SELECAO_MIN, calcular_centro_zoom_ancorado, calcular_viewport_zoom_selecao,
    proximo_fator_zoom_selecao,
)

CTRL_MASK=0x0004
SHIFT_MASK=0x0001
DRAG_PX=5
HANDLE_HIT_PX=14
ROTATE_OFFSET_PX=34
FREEFORM_CLOSE_PX=18


class DisplayMaskEditorInteractionMixin:
    def _vp(self): return calcular_viewport_zoom_selecao(self.master_width,self.master_height,max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height()),self.zoom_factor,self.zoom_cx,self.zoom_cy)
    def _to_canvas(self,x,y):
        v=self._vp(); return v.deslocamento_virtual_x+float(x)*v.escala, v.deslocamento_virtual_y+float(y)*v.escala
    def _to_master(self,x,y):
        v=self._vp(); mx=(x-v.deslocamento_virtual_x)/max(v.escala,1e-9); my=(y-v.deslocamento_virtual_y)/max(v.escala,1e-9)
        if mx<0 or my<0 or mx>=self.master_width or my>=self.master_height: return None
        return max(0,min(self.master_width-1,int(round(mx)))),max(0,min(self.master_height-1,int(round(my))))
    def _next_id(self):
        used={_id(m) for m in self.masks}; i=1
        while f"MASK_{i:03d}" in used: i+=1
        return f"MASK_{i:03d}"
    def _selected(self): return [deepcopy(m) for m in self.masks if _id(m) in self.selected_ids]
    def _selection_bbox(self): return _bbox(self._selected())
    def _hit(self,x,y):
        for m in reversed(self.masks):
            if mascara_display_contem_ponto(m,x,y): return _id(m)
        return None

    def set_tool(self,tool):
        if tool not in DISPLAY_MASK_F2_PARITY_TOOLS: return
        self.freeform=[]; self.freeform_mouse=None; self.draft_segment=None; self.tool=tool
        for k,b in self.tool_buttons.items(): b.configure(bg="#D6A900" if k==tool else "#182231",fg="#111318" if k==tool else "#DCE5EF")
        self.redraw(); self.canvas.focus_set()

    def _handles(self):
        sel=self._selected(); box=_bbox(sel)
        if not sel or box is None: return {}
        if len(sel)==1 and sel[0].get("type")=="circle": return {}
        if len(sel)==1 and sel[0].get("type")=="segment":
            m=sel[0]; cx,cy=float(m["cx"]),float(m["cy"]); hx,hy=float(m["width"])/2,float(m["height"])/2; a=float(m.get("angle",0))
            local={"nw":(-hx,-hy),"n":(0,-hy),"ne":(hx,-hy),"e":(hx,0),"se":(hx,hy),"s":(0,hy),"sw":(-hx,hy),"w":(-hx,0),"rotate":(0,-hy-max(24.0,float(m["height"])))}
            return {k:_rotate_xy(cx+x,cy+y,cx,cy,a) for k,(x,y) in local.items()}
        x1,y1,x2,y2=box; mx,my=(x1+x2)/2,(y1+y2)/2
        handles={"nw":(x1,y1),"n":(mx,y1),"ne":(x2,y1),"e":(x2,my),"se":(x2,y2),"s":(mx,y2),"sw":(x1,y2),"w":(x1,my)}
        v=self._vp(); handles["rotate"]=(mx,y1-ROTATE_OFFSET_PX/max(v.escala,1e-9)); return handles
    def _hit_handle(self,x,y):
        for name,p in self._handles().items():
            cx,cy=self._to_canvas(*p)
            if abs(x-cx)<=HANDLE_HIT_PX and abs(y-cy)<=HANDLE_HIT_PX: return name
        return None

    def _begin(self,mode,point,handle=None):
        self.mode=mode; self.handle=handle; self.press_master=point; self.snapshot=deepcopy(self.masks); self.snapshot_sel=self._selected(); self.snapshot_bbox=_bbox(self.snapshot_sel)
    def _merge(self,changed):
        by={_id(m):m for m in changed}; self.masks=[deepcopy(by.get(_id(m),m)) for m in self.snapshot]

    def _press(self,e):
        self.canvas.focus_set(); p=self._to_master(e.x,e.y)
        if p is None:return "break"
        self.press_canvas=(e.x,e.y); self.press_master=p; self.current_master=p
        if self.tool==TOOL_FREEFORM:
            hit=self._hit(*p)
            if hit and not self.freeform: self.selected_ids={hit}; self._begin("move",p); self.redraw(); return "break"
            if self.freeform and len(self.freeform)>=3:
                fx,fy=self._to_canvas(*self.freeform[0])
                if math.hypot(e.x-fx,e.y-fy)<=FREEFORM_CLOSE_PX:return self._finish_freeform()
            self.freeform.append([p[0],p[1]]); self.freeform_mouse=p; self.selected_ids=set(); self.redraw(); return "break"
        handle=self._hit_handle(e.x,e.y)
        if handle: self._begin("rotate" if handle=="rotate" else ("scale" if handle in {"nw","ne","se","sw"} else "stretch"),p,handle); return "break"
        hit=self._hit(*p)
        if hit: self.selected_ids={hit} if hit not in self.selected_ids else self.selected_ids; self._begin("move",p); self.redraw(); return "break"
        self.selected_ids=set(); self._begin("pending",p); return "break"

    def _drag(self,e):
        p=self._to_master(e.x,e.y)
        if p is None or self.press_master is None:return "break"
        self.current_master=p
        if self.mode=="pending" and self.press_canvas and math.hypot(e.x-self.press_canvas[0],e.y-self.press_canvas[1])>=DRAG_PX:
            if self.tool==TOOL_SEGMENT and not (int(getattr(e,"state",0))&SHIFT_MASK): self.mode="create_segment"
            elif self.tool==TOOL_CIRCLE and not (int(getattr(e,"state",0))&SHIFT_MASK): self.mode="create_circle"
            else:self.mode="marquee"
        if self.mode=="create_segment": self.draft_segment=criar_segmento_display_por_arrasto(*self.press_master,*p,id_mascara=self._next_id())
        elif self.mode=="marquee":
            x1,y1=self.press_master; l,r=sorted((x1,p[0])); t,b=sorted((y1,p[1])); self.selected_ids={_id(m) for m in self.snapshot if (lambda q:q[0]>=l and q[1]>=t and q[2]<=r and q[3]<=b)(bbox_mascara_display(m))}
        elif self.mode in {"move","scale","stretch","rotate"}: self._transform(p)
        self.redraw(); return "break"

    def _transform(self,p):
        if not self.snapshot_sel or self.snapshot_bbox is None or self.press_master is None:return
        x1,y1,x2,y2=self.snapshot_bbox; px,py=self.press_master
        if self.mode=="move": changed=[_move(m,p[0]-px,p[1]-py) for m in self.snapshot_sel]
        elif self.mode=="rotate":
            cx,cy=(x1+x2)/2,(y1+y2)/2; d=math.degrees(math.atan2(p[1]-cy,p[0]-cx)-math.atan2(py-cy,px-cx)); changed=[_rotate(m,cx,cy,d) for m in self.snapshot_sel]
        else:
            h=self.handle
            if len(self.snapshot_sel)==1 and self.snapshot_sel[0].get("type")=="segment":
                m=deepcopy(self.snapshot_sel[0]); cx,cy=float(m["cx"]),float(m["cy"]); qx,qy=_rotate_xy(p[0],p[1],cx,cy,-float(m.get("angle",0))); lx,ly=qx-cx,qy-cy
                if h in {"e","w","ne","nw","se","sw"}: m["width"]=max(SEGMENTO_LARGURA_MINIMA,int(round(abs(lx)*2)))
                if h in {"n","s","ne","nw","se","sw"}: m["height"]=max(SEGMENTO_ALTURA_MINIMA,int(round(abs(ly)*2)))
                changed=[m]
                if _valid(m,self.master_width,self.master_height): self._merge(changed)
                return
            opp={"nw":(x2,y2,x1,y1),"ne":(x1,y2,x2,y1),"se":(x1,y1,x2,y2),"sw":(x2,y1,x1,y2)}
            if self.mode=="scale":
                ax,ay,ox,oy=opp[h]; sx=abs(p[0]-ax)/max(1,abs(ox-ax)); sy=abs(p[1]-ay)/max(1,abs(oy-ay)); s=max(.05,min(sx,sy)); changed=[_scale(m,ax,ay,s,s) for m in self.snapshot_sel]
            else:
                if h=="e": cx,cy=x1,(y1+y2)/2; sx=max(.05,(p[0]-x1)/max(1,x2-x1)); sy=1
                elif h=="w": cx,cy=x2,(y1+y2)/2; sx=max(.05,(x2-p[0])/max(1,x2-x1)); sy=1
                elif h=="s": cx,cy=(x1+x2)/2,y1; sx=1; sy=max(.05,(p[1]-y1)/max(1,y2-y1))
                else: cx,cy=(x1+x2)/2,y2; sx=1; sy=max(.05,(y2-p[1])/max(1,y2-y1))
                changed=[_scale(m,cx,cy,sx,sy) for m in self.snapshot_sel]
        if all(_valid(m,self.master_width,self.master_height) for m in changed): self._merge(changed)

    def _release(self,e):
        p=self._to_master(e.x,e.y) or self.current_master
        if self.mode=="pending" and p is not None:
            if self.tool==TOOL_CIRCLE:
                m={"id":self._next_id(),"type":"circle","cx":p[0],"cy":p[1],"radius":DEFAULT_RADIUS_PX}
                if _valid(m,self.master_width,self.master_height): self.masks.append(m); self.selected_ids={_id(m)}
            elif self.tool==TOOL_SEGMENT:
                m=criar_segmento_display_por_arrasto(*p,*p,id_mascara=self._next_id())
                if _valid(m,self.master_width,self.master_height): self.masks.append(m); self.selected_ids={_id(m)}
        elif self.mode=="create_segment" and self.draft_segment and _valid(self.draft_segment,self.master_width,self.master_height): self.masks.append(self.draft_segment); self.selected_ids={_id(self.draft_segment)}
        elif self.mode=="create_circle" and p is not None:
            r=int(round(math.dist(self.press_master,p))); m={"id":self._next_id(),"type":"circle","cx":self.press_master[0],"cy":self.press_master[1],"radius":max(MIN_RADIUS_PX,min(MAX_RADIUS_PX,r))}
            if _valid(m,self.master_width,self.master_height): self.masks.append(m); self.selected_ids={_id(m)}
        self.mode=None; self.handle=None; self.draft_segment=None; self.redraw(); return "break"

    def _motion(self,e):
        self.pointer_canvas=(e.x,e.y); self.pointer_master=self._to_master(e.x,e.y)
        if self.freeform and self.pointer_master:self.freeform_mouse=self.pointer_master
        self.redraw(); return None
    def _leave(self,e=None): self.pointer_canvas=None; self.pointer_master=None; self.redraw()
    def _finish_freeform(self,e=None):
        if len(self.freeform)>=3 and _area(self.freeform)>=4:
            m={"id":self._next_id(),"type":"polygon","points":deepcopy(self.freeform)}
            if _valid(m,self.master_width,self.master_height): self.masks.append(m); self.selected_ids={_id(m)}
        self.freeform=[]; self.freeform_mouse=None; self.redraw(); return "break"
    def _escape(self,e=None):
        if self.freeform:self.freeform=[]; self.freeform_mouse=None
        else:self.selected_ids=set()
        self.mode=None; self.redraw(); return "break"
    def _delete_selected(self,e=None): self.masks=[m for m in self.masks if _id(m) not in self.selected_ids]; self.selected_ids=set(); self.redraw(); return "break"
    def _select_all(self,e=None): self.selected_ids={_id(m) for m in self.masks}; self.redraw(); return "break"
    def _move_keyboard(self,e):
        dx={"Left":-1,"Right":1}.get(getattr(e,"keysym",""),0); dy={"Up":-1,"Down":1}.get(getattr(e,"keysym",""),0)
        snap=deepcopy(self.masks); changed=[_move(m,dx,dy) for m in self._selected()]
        if all(_valid(m,self.master_width,self.master_height) for m in changed):
            by={_id(m):m for m in changed}; self.masks=[by.get(_id(m),m) for m in snap]
        self.redraw(); return "break"

    @staticmethod
    def _wheel_dir(e):
        d=int(getattr(e,"delta",0) or 0); n=getattr(e,"num",None); return 1 if d>0 or n==4 else (-1 if d<0 or n==5 else 0)
    def _wheel(self,e):
        d=self._wheel_dir(e)
        if not d:return "break"
        if int(getattr(e,"state",0) or 0)&CTRL_MASK:
            old=self.zoom_factor; new=proximo_fator_zoom_selecao(old,d)
            if new!=old:
                v=self._vp(); self.zoom_cx,self.zoom_cy=calcular_centro_zoom_ancorado(ponteiro_x=e.x,ponteiro_y=e.y,escala_atual=v.escala,deslocamento_atual_x=v.deslocamento_virtual_x,deslocamento_atual_y=v.deslocamento_virtual_y,largura_virtual_atual=v.largura_virtual,altura_virtual_atual=v.altura_virtual,nova_escala=v.escala*(new/old),largura_canvas=max(1,self.canvas.winfo_width()),altura_canvas=max(1,self.canvas.winfo_height()),largura_visual=self.master_width,altura_visual=self.master_height,centro_atual_x=self.zoom_cx,centro_atual_y=self.zoom_cy)
                self.zoom_factor=new; self.zoom_label.configure(text=f"ZOOM {int(round(new*100))}%")
            self.redraw(); return "break"
        changed=[]
        for m in self._selected():
            n=deepcopy(m)
            if n.get("type")=="circle": n["radius"]=max(MIN_RADIUS_PX,min(MAX_RADIUS_PX,int(n["radius"])+d))
            changed.append(n)
        if changed:
            by={_id(m):m for m in changed}; self.masks=[by.get(_id(m),m) for m in self.masks]; self.redraw()
        return "break"

    def _start_pan(self,e):
        if self.zoom_factor<=ZOOM_SELECAO_MIN:return "break"
        self.pan=True; self.pan_last=(e.x,e.y); self.canvas.configure(cursor="fleur"); return "break"
    def _drag_pan(self,e):
        if not self.pan or not self.pan_last:return "break"
        v=self._vp(); dx,dy=e.x-self.pan_last[0],e.y-self.pan_last[1]; self.pan_last=(e.x,e.y)
        cx=(self.canvas.winfo_width()/2-v.deslocamento_virtual_x)/v.escala-dx/v.escala; cy=(self.canvas.winfo_height()/2-v.deslocamento_virtual_y)/v.escala-dy/v.escala
        self.zoom_cx=max(0,min(self.master_width,cx)); self.zoom_cy=max(0,min(self.master_height,cy)); self.redraw(); return "break"
    def _end_pan(self,e=None): self.pan=False; self.pan_last=None; self.canvas.configure(cursor="crosshair"); return "break"
