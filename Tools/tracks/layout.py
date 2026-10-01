"""Turtle-style track layouts: S len | R/L angle radius. Two straights flagged adjX/adjZ are solved to close the loop.
Prints solved lengths and renders previews. Mirrors the C# TrackDefs logic."""
import math, sys, json
import numpy as np
from PIL import Image, ImageDraw

TRACKS = {k:[tuple(x) for x in v] for k,v in json.load(open("/Users/jemmygazhenko/Documents/GitHub/ink-drift-tokyo/Tools/tracks/layouts.json")).items()}

def walk(segs, lens_override=None):
    x=z=0.0; h=0.0  # heading deg, 0=+z, right turn positive
    pts=[(x,z)]
    for i,s in enumerate(segs):
        if s[0]=="S":
            L = lens_override.get(i, s[1]) if lens_override else s[1]
            n=max(1,int(L/2))
            for k in range(n):
                x+=math.sin(math.radians(h))*L/n; z+=math.cos(math.radians(h))*L/n; pts.append((x,z))
        else:
            ang=s[1]*(1 if s[0]=="R" else -1); r=s[2]
            arc=abs(math.radians(ang))*r; n=max(2,int(arc/2))
            for k in range(n):
                h+=ang/n
                step=arc/n
                # midpoint heading approx
                x+=math.sin(math.radians(h-ang/n/2))*step; z+=math.cos(math.radians(h-ang/n/2))*step; pts.append((x,z))
    return np.array(pts), h

def solve(segs):
    ia=[i for i,s in enumerate(segs) if len(s)>2 and s[0]=="S" and s[2]=="adjA"][0]
    ib=[i for i,s in enumerate(segs) if len(s)>2 and s[0]=="S" and s[2]=="adjB"][0]
    base,h=walk(segs)
    end=base[-1]
    # numerical jacobian
    def endpos(la,lb):
        p,_=walk(segs,{ia:la,ib:lb}); return p[-1]
    la,lb=segs[ia][1],segs[ib][1]
    for it in range(20):
        e=endpos(la,lb)
        if np.linalg.norm(e)<0.01: break
        J=np.zeros((2,2))
        J[:,0]=(endpos(la+1,lb)-e); J[:,1]=(endpos(la,lb+1)-e)
        d=np.linalg.solve(J,-e); la+=d[0]; lb+=d[1]
    p,h=walk(segs,{ia:la,ib:lb})
    return p,h,{ia:la,ib:lb}

def seglen(p): return float(np.sum(np.linalg.norm(np.diff(p,axis=0),axis=1)))

out={}
for name,segs in TRACKS.items():
    p,h,sol=solve(segs)
    L=seglen(p)
    print(f"{name}: heading_end={h:.1f} closure={np.linalg.norm(p[-1]):.3f} length={L:.0f}m solved={ {k:round(v,1) for k,v in sol.items()} }")
    # self-intersection check (coarse): min distance between non-neighboring samples
    P=p[::3]; md=1e9
    for i in range(len(P)):
        d=np.linalg.norm(P-P[i],axis=1); n=len(P)
        for j in range(len(P)):
            if min(abs(i-j), n-abs(i-j))>12: md=min(md,d[j])
    print(f"   min separation between distant parts: {md:.1f} m; bbox {p.min(0).round()} .. {p.max(0).round()}")
    out[name]={"solved":{str(k):v for k,v in sol.items()}}
    W=900; mn=p.min(0)-40; mx=p.max(0)+40; sc=(W-40)/max(mx-mn)
    img=Image.new("RGB",(W,W),(20,18,40)); d=ImageDraw.Draw(img)
    q=[((x-mn[0])*sc+20, W-((z-mn[1])*sc+20)) for x,z in p]
    d.line(q,fill=(255,45,122),width=6); d.ellipse([q[0][0]-8,q[0][1]-8,q[0][0]+8,q[0][1]+8],fill=(255,230,0))
    d.text((10,10),f"{name} {L:.0f} m",fill=(255,255,255))
    img.save(f"/Users/jemmygazhenko/Documents/GitHub/ink-drift-tokyo/Tools/tracks/{name}.png")
json.dump(out,open("/Users/jemmygazhenko/Documents/GitHub/ink-drift-tokyo/Tools/tracks/solved.json","w"),indent=1)
