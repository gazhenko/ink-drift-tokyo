"""Trailer title cards (1920x1080 RGBA, comic/graffiti style) using the game's OFL fonts + logo."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
F="Game/Assets/InkDrift/Art/Fonts/"; O="Tools/trailer/cards/"
W,H=1920,1080; S=2
INK=(11,11,18); PAPER=(255,248,231); MAG=(255,45,122); CYAN=(0,229,255); YEL=(255,230,0); RED=(255,59,48)
def font(n,s): return ImageFont.truetype(F+n,s*S)
def halftone(img,col,density=0.5,cell=14,angle=45):
    w,h=img.size; d=ImageDraw.Draw(img)
    a=np.radians(angle)
    for y in range(-2*h,3*h,cell*S):
        for x in range(-2*w,3*w,cell*S):
            X=x*np.cos(a)-y*np.sin(a); Y=x*np.sin(a)+y*np.cos(a)
            if 0<=X<w and 0<=Y<h:
                g=Y/h; r=cell*S*0.5*np.sqrt(max(0,density*(1-g)))
                if r>0.6: d.ellipse([X-r,Y-r,X+r,Y+r],fill=col)
def inked_text(img,xy,text,f,fill,stroke=10,shadow=(10,10),anchor="mm"):
    d=ImageDraw.Draw(img)
    sx,sy=shadow
    d.text((xy[0]+sx*S,xy[1]+sy*S),text,font=f,fill=INK,anchor=anchor,stroke_width=stroke*S,stroke_fill=INK)
    d.text(xy,text,font=f,fill=fill,anchor=anchor,stroke_width=stroke*S,stroke_fill=INK)
    d.text(xy,text,font=f,fill=fill,anchor=anchor,stroke_width=int(stroke*0.35)*S,stroke_fill=PAPER)
    d.text(xy,text,font=f,fill=fill,anchor=anchor)
def card(name,lines,bg=None,dots=None):
    img=Image.new("RGBA",(W*S,H*S),(0,0,0,0) if bg is None else bg+(255,))
    if dots: halftone(img,dots,0.55)
    for (txt,fn,size,col,y,rot) in lines:
        layer=Image.new("RGBA",img.size,(0,0,0,0))
        inked_text(layer,(W*S//2,int(y*S)),txt,font(fn,size),col)
        if rot: layer=layer.rotate(rot,resample=Image.BICUBIC,center=(W*S//2,int(y*S)))
        img=Image.alpha_composite(img,layer)
    img.resize((W,H),Image.LANCZOS).save(O+name+".png")
B="Bangers-Regular.ttf"; D="DelaGothicOne-Regular.ttf"; N="NotoSansJP-Black.ttf"
card("c1_tokyo",[("東京",D,300,PAPER,470,-4),("TOKYO.",B,120,MAG,720,-2)],bg=INK,dots=(40,30,70))
card("c2_never_sleeps",[("この街は眠らない",D,120,CYAN,430,-3),("THE CITY NEVER SLEEPS",B,110,PAPER,620,-2)])
card("c3_neither",[("NEITHER DO WE.",B,170,YEL,520,-5)])
card("c4_counts",[("3 TRACKS",B,150,PAPER,330,-3),("5 MACHINES",B,150,CYAN,540,2),("0 GRIP",B,190,MAG,770,-4)])
card("c5_drift",[("ドリフトしろ！",D,190,RED,500,-6),("DRIFT OR DIE",B,100,PAPER,720,-2)])
# end card: logo + platforms + url
logo=Image.open("Game/Assets/InkDrift/Art/UI/logo_inkdrift.png").convert("RGBA")
end=Image.new("RGBA",(W*S,H*S),INK+(255,)); halftone(end,(45,25,70),0.6)
lw=int(W*S*0.78); lh=int(logo.height*lw/logo.width)
end.alpha_composite(logo.resize((lw,lh),Image.LANCZOS),((W*S-lw)//2,int(H*S*0.12)))
d=ImageDraw.Draw(end)
inked_text(end,(W*S//2,int(H*S*0.78)),"FREE DEMO  ·  macOS  ·  Windows  ·  Linux",font(B,64),YEL,stroke=7,shadow=(6,6))
inked_text(end,(W*S//2,int(H*S*0.88)),"github.com/gazhenko/ink-drift-tokyo",font("ChakraPetch-Bold.ttf",46),PAPER,stroke=5,shadow=(4,4))
end.resize((W,H),Image.LANCZOS).save(O+"c9_end.png")
print("ok")
