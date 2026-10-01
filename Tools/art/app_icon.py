"""App icon: ink-black rounded square, magenta/cyan drift slash, big 墨 kanji with comic stroke."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
S=4; N=1024*S
img=Image.new("RGBA",(N,N),(0,0,0,0)); d=ImageDraw.Draw(img)
d.rounded_rectangle([0,0,N-1,N-1],radius=int(N*0.22),fill=(11,11,18,255))
# halftone corner
for y in range(0,N,36*S):
    for x in range(0,N,36*S):
        g=max(0,1-(x+y)/(N*1.1)); r=18*S*np.sqrt(g)*0.8
        if r>1: d.ellipse([x-r,y-r,x+r,y+r],fill=(60,25,90,255))
# drift slashes
for off,col in ((0,(255,45,122,255)),(90*S,(0,229,255,255))):
    d.polygon([(N*0.05,N*0.72+off),(N*0.95,N*0.38+off),(N*0.95,N*0.47+off),(N*0.05,N*0.81+off)],fill=col)
f=ImageFont.truetype("Game/Assets/InkDrift/Art/Fonts/ReggaeOne-Regular.ttf",int(N*0.66))
t=Image.new("RGBA",(N,N),(0,0,0,0)); td=ImageDraw.Draw(t)
td.text((N*0.53,N*0.47),"墨",font=f,fill=(11,11,18,255),anchor="mm",stroke_width=16*S,stroke_fill=(11,11,18,255))
td.text((N*0.5,N*0.45),"墨",font=f,fill=(255,230,0,255),anchor="mm",stroke_width=8*S,stroke_fill=(11,11,18,255))
td.text((N*0.5,N*0.45),"墨",font=f,fill=(255,230,0,255),anchor="mm",stroke_width=3*S,stroke_fill=(255,248,231,255))
td.text((N*0.5,N*0.45),"墨",font=f,fill=(255,230,0,255),anchor="mm")
t=t.rotate(-8,resample=Image.BICUBIC,center=(N/2,N/2))
img.alpha_composite(t)
mask=Image.new("L",(N,N),0); ImageDraw.Draw(mask).rounded_rectangle([0,0,N-1,N-1],radius=int(N*0.22),fill=255)
img.putalpha(Image.fromarray(np.minimum(np.array(img.getchannel("A")),np.array(mask))))
img.resize((1024,1024),Image.LANCZOS).save("Game/Assets/InkDrift/Art/UI/icon.png")
img.resize((256,256),Image.LANCZOS).save("/private/tmp/claude-501/-Users-jemmygazhenko-Documents-GitHub/d9878ad4-1ca4-4036-a91f-0a331a755fa9/scratchpad/icon.png")
print("ok")
