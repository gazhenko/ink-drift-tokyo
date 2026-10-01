"""Japanese road sign faces + slope-protection lattice texture (procedural, OFL fonts)."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
F="Game/Assets/InkDrift/Art/Fonts/"; O="Game/Assets/InkDrift/Generated/Common/"
jp=lambda s: ImageFont.truetype(F+"NotoSansJP-Black.ttf",s)
num=lambda s: ImageFont.truetype(F+"NotoSansJP-Bold.ttf",s)
S=4
def save(img,name,size): img.resize(size,Image.LANCZOS).save(O+name)
# speed limit 40: white disc, red ring, blue numerals
im=Image.new("RGB",(512*S,512*S),(240,240,236)); d=ImageDraw.Draw(im)
d.ellipse([0,0,512*S-1,512*S-1],fill=(205,30,35)); d.ellipse([60*S,60*S,452*S,452*S],fill=(245,245,242))
f=num(250*S); tw=d.textlength("40",font=f); d.text((256*S-tw/2,90*S),"40",font=f,fill=(25,60,160))
save(im,"roadsign_speed40.png",(512,512))
# 止まれ: inverted red triangle (fills 0.80x0.69 bbox)
W,H=512*S,442*S
im=Image.new("RGB",(W,H),(200,25,30)); d=ImageDraw.Draw(im)
d.polygon([(0,0),(W,0),(W//2,H)],fill=(205,28,32),outline=(245,245,242))
d.line([(14*S,10*S),(W-14*S,10*S),(W//2,H-24*S),(14*S,10*S)],fill=(245,245,242),width=14*S)
f=jp(92*S); tw=d.textlength("止まれ",font=f); d.text((W/2-tw/2,38*S),"止まれ",font=f,fill=(250,250,248))
save(im,"roadsign_tomare.png",(512,442))
# curve warning diamond
im=Image.new("RGB",(512*S,512*S),(250,205,20)); d=ImageDraw.Draw(im)
c=256*S; r=250*S
d.polygon([(c,c-r),(c+r,c),(c,c+r),(c-r,c)],fill=(18,18,20)); r2=r-26*S
d.polygon([(c,c-r2),(c+r2,c),(c,c+r2),(c-r2,c)],fill=(252,205,20))
# curve arrow
d.arc([170*S,160*S,420*S,410*S],180,270,fill=(18,18,20),width=40*S)
d.line([(190*S,285*S),(190*S,380*S)],fill=(18,18,20),width=40*S)
d.polygon([(295*S,120*S),(380*S,165*S),(295*S,210*S)],fill=(18,18,20))
save(im,"roadsign_curve.png",(512,512))
# one-way: blue 3:2 with white arrow + text
im=Image.new("RGB",(768*S,512*S),(25,70,170)); d=ImageDraw.Draw(im)
d.rectangle([12*S,12*S,756*S,500*S],outline=(245,245,242),width=12*S)
d.polygon([(110*S,230*S),(520*S,230*S),(520*S,150*S),(680*S,280*S),(520*S,410*S),(520*S,330*S),(110*S,330*S)],fill=(245,245,242))
f=jp(90*S); tw=d.textlength("一方通行",font=f); d.text((384*S-tw/2,30*S),"一方通行",font=f,fill=(245,245,242))
save(im,"roadsign_oneway.png",(768,512))
# slope protection lattice (法面枠): concrete beams with grass panels, 2x2 cells per tile
rng=np.random.default_rng(3); N=1024
grass=(rng.random((N,N))*0.35+0.45)
from scipy.ndimage import gaussian_filter
grass=gaussian_filter(grass,1.2)
img=np.zeros((N,N,3)); img[...,0]=grass*0.42; img[...,1]=grass*0.62; img[...,2]=grass*0.25
conc=0.62+gaussian_filter(rng.random((N,N)),2)*0.25
cell=N//2; bw=56
for k in range(3):
    for a in (k*cell-bw//2,):
        lo,hi=max(0,a),min(N,a+bw)
        if hi>lo:
            img[lo:hi,:,:]=conc[lo:hi,:,None]*np.array([0.95,0.94,0.9]); img[:,lo:hi,:]=conc[:,lo:hi,None]*np.array([0.95,0.94,0.9])
# wrap beams at tile edges
img[N-bw//2:,:,:]=conc[N-bw//2:,:,None]*np.array([0.95,0.94,0.9]); img[:,N-bw//2:,:]=conc[:,N-bw//2:,None]*np.array([0.95,0.94,0.9])
Image.fromarray((np.clip(img,0,1)*255).astype(np.uint8)).save(O+"slope_grid_albedo.png")
print("ok")
