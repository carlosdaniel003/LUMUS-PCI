from __future__ import annotations

import math
from copy import deepcopy
from types import SimpleNamespace

from config import DEFAULT_RADIUS_PX, MAX_RADIUS_PX, MIN_RADIUS_PX
from src.core.roi_geometry import (
    SEGMENTO_ALTURA_MINIMA,
    SEGMENTO_ALTURA_PADRAO,
    SEGMENTO_LARGURA_MINIMA,
    SEGMENTO_LARGURA_PADRAO,
    normalizar_angulo_segmento,
    pontos_segmento,
)
from src.platform.display_project_repository import (
    normalizar_mascaras_display,
    normalizar_resolucao_display,
)

TOOL_SEGMENT = "segment"
TOOL_CIRCLE = "circle"
TOOL_FREEFORM = "freeform"
TOOL_MASS = "mass"
DISPLAY_MASK_F2_PARITY_TOOLS = (TOOL_SEGMENT, TOOL_CIRCLE, TOOL_FREEFORM, TOOL_MASS)


def _id(mask: dict) -> str:
    return str(mask.get("id", ""))


def _area(points) -> float:
    pts = [(float(p[0]), float(p[1])) for p in points or []]
    return abs(sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(pts, pts[1:]+pts[:1]))) / 2 if len(pts) >= 3 else 0.0


def criar_segmento_display_por_arrasto(x1, y1, x2, y2, altura_segmento=SEGMENTO_ALTURA_PADRAO, id_mascara="MASK_001") -> dict:
    dx, dy = float(x2)-float(x1), float(y2)-float(y1)
    comprimento = math.hypot(dx, dy)
    if comprimento < SEGMENTO_LARGURA_MINIMA:
        cx, cy, largura, angulo = int(round(x1)), int(round(y1)), SEGMENTO_LARGURA_PADRAO, 0.0
    else:
        cx, cy = int(round((x1+x2)/2)), int(round((y1+y2)/2))
        largura, angulo = max(SEGMENTO_LARGURA_MINIMA, int(round(comprimento))), math.degrees(math.atan2(dy, dx))
    return {"id": str(id_mascara), "type": "segment", "cx": cx, "cy": cy,
            "width": largura, "height": max(SEGMENTO_ALTURA_MINIMA, int(altura_segmento)),
            "angle": normalizar_angulo_segmento(angulo)}


def _segment_points(mask: dict):
    alvo = SimpleNamespace(centro_x=int(mask.get("cx",0)), centro_y=int(mask.get("cy",0)), raio=1,
        tipo_roi="segmento", largura=int(mask.get("width",SEGMENTO_LARGURA_PADRAO)),
        altura=int(mask.get("height",SEGMENTO_ALTURA_PADRAO)), angulo=float(mask.get("angle",0) or 0),
        pontos_segmento_livre=None)
    return [(float(x), float(y)) for x,y in pontos_segmento(alvo)]


def converter_mascara_legada_para_editor(mask: dict) -> dict:
    item = deepcopy(mask)
    if str(item.get("type","")).lower() != "rectangle":
        return item
    x,y,w,h = int(item.get("x",0)), int(item.get("y",0)), max(1,int(item.get("width",1))), max(1,int(item.get("height",1)))
    return {"id": _id(item), "type":"segment", "cx":int(round(x+w/2)), "cy":int(round(y+h/2)),
            "width":w, "height":h, "angle":0.0}


def _inside_poly(points, x, y) -> bool:
    pts=list(points or []); inside=False; j=len(pts)-1
    for i in range(len(pts)):
        xi,yi=map(float,pts[i]); xj,yj=map(float,pts[j])
        if ((yi>y)!=(yj>y)) and x < (xj-xi)*(y-yi)/float((yj-yi) or 1e-9)+xi: inside=not inside
        j=i
    return inside


def mascara_display_contem_ponto(mask: dict, x, y) -> bool:
    kind=str(mask.get("type","")).lower()
    if kind=="circle":
        return (float(x)-float(mask.get("cx",0)))**2+(float(y)-float(mask.get("cy",0)))**2 <= max(1,float(mask.get("radius",1)))**2
    if kind=="segment": return _inside_poly(_segment_points(mask),x,y)
    if kind=="polygon": return _inside_poly(mask.get("points",[]),x,y)
    if kind=="rectangle": return mascara_display_contem_ponto(converter_mascara_legada_para_editor(mask),x,y)
    return False


def bbox_mascara_display(mask: dict):
    kind=str(mask.get("type","")).lower()
    if kind=="circle":
        cx,cy,r=map(float,(mask.get("cx",0),mask.get("cy",0),max(1,mask.get("radius",1))))
        return cx-r,cy-r,cx+r,cy+r
    if kind=="segment": pts=_segment_points(mask)
    elif kind=="polygon": pts=[(float(p[0]),float(p[1])) for p in mask.get("points",[])]
    elif kind=="rectangle": return bbox_mascara_display(converter_mascara_legada_para_editor(mask))
    else: return 0.0,0.0,0.0,0.0
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys)


def _bbox(masks):
    items=list(masks)
    if not items: return None
    boxes=[bbox_mascara_display(m) for m in items]
    return min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)


def _valid(mask,w,h):
    x1,y1,x2,y2=bbox_mascara_display(mask)
    return x1>=0 and y1>=0 and x2<int(w) and y2<int(h)


def _rotate_xy(x,y,cx,cy,deg):
    a=math.radians(deg); c,s=math.cos(a),math.sin(a); dx,dy=float(x)-cx,float(y)-cy
    return cx+dx*c-dy*s, cy+dx*s+dy*c


def _move(mask,dx,dy):
    m=deepcopy(mask); kind=m.get("type")
    if kind in {"circle","segment"}: m["cx"]=int(round(m["cx"]+dx)); m["cy"]=int(round(m["cy"]+dy))
    elif kind=="polygon": m["points"]=[[int(round(x+dx)),int(round(y+dy))] for x,y in m["points"]]
    return m


def _rotate(mask,cx,cy,deg):
    m=deepcopy(mask); kind=m.get("type")
    if kind in {"circle","segment"}:
        x,y=_rotate_xy(m["cx"],m["cy"],cx,cy,deg); m["cx"],m["cy"]=int(round(x)),int(round(y))
        if kind=="segment": m["angle"]=normalizar_angulo_segmento(float(m.get("angle",0))+deg)
    elif kind=="polygon": m["points"]=[[int(round(x)),int(round(y))] for x,y in (_rotate_xy(p[0],p[1],cx,cy,deg) for p in m["points"])]
    return m


def _scale(mask,cx,cy,sx,sy):
    m=deepcopy(mask); kind=m.get("type")
    if kind in {"circle","segment"}:
        m["cx"]=int(round(cx+(m["cx"]-cx)*sx)); m["cy"]=int(round(cy+(m["cy"]-cy)*sy))
    if kind=="circle": m["radius"]=max(MIN_RADIUS_PX,min(MAX_RADIUS_PX,int(round(m["radius"]*min(abs(sx),abs(sy))))))
    elif kind=="segment":
        m["width"]=max(SEGMENTO_LARGURA_MINIMA,int(round(m["width"]*abs(sx))))
        m["height"]=max(SEGMENTO_ALTURA_MINIMA,int(round(m["height"]*abs(sy))))
    elif kind=="polygon": m["points"]=[[int(round(cx+(x-cx)*sx)),int(round(cy+(y-cy)*sy))] for x,y in m["points"]]
    return m


def instalar_suporte_segmento_mascara_display() -> None:
    """Estende apenas o subsistema Display; nenhum módulo de Produção F2 é alterado."""
    import src.platform.display_project_repository as repo
    if not getattr(repo,"_odin_display_segment_mask_support",False):
        original=repo.normalizar_mascara_display
        def normalizar(mascara: dict, indice: int=1):
            if isinstance(mascara,dict) and str(mascara.get("type",mascara.get("tipo",""))).lower() in {"segment","segmento"}:
                try:
                    mid=str(mascara.get("id") or f"MASK_{indice:03d}"); cx=int(mascara.get("cx",mascara.get("centro_x")))
                    cy=int(mascara.get("cy",mascara.get("centro_y"))); w=int(mascara.get("width",mascara.get("largura")))
                    h=int(mascara.get("height",mascara.get("altura"))); a=normalizar_angulo_segmento(mascara.get("angle",mascara.get("angulo",0)))
                except (TypeError,ValueError): return None
                if w<SEGMENTO_LARGURA_MINIMA or h<SEGMENTO_ALTURA_MINIMA: return None
                return {"id":mid,"type":"segment","cx":cx,"cy":cy,"width":w,"height":h,"angle":a}
            return original(mascara,indice)
        repo.normalizar_mascara_display=normalizar; repo._odin_display_segment_mask_support=True
    try:
        import src.platform.display_check_editor as checks
        cls=checks.DisplayCheckMaskEditorWindow
    except Exception: return
    if getattr(cls,"_odin_display_segment_mask_support",False): return
    old_contains,old_draw=cls._contains,cls._draw_mask
    cls._contains=staticmethod(lambda m,x,y: mascara_display_contem_ponto(m,x,y) if m.get("type")=="segment" else old_contains(m,x,y))
    def draw(self,index,mask):
        if mask.get("type")=="segment":
            temp=deepcopy(mask); temp["type"]="polygon"; temp["points"]=[[int(round(x)),int(round(y))] for x,y in _segment_points(mask)]
            return old_draw(self,index,temp)
        return old_draw(self,index,mask)
    cls._draw_mask=draw; cls._odin_display_segment_mask_support=True


instalar_suporte_segmento_mascara_display()
