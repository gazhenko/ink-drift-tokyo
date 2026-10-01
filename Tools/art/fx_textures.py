"""Small FX textures: toon smoke puff (R=shape, G=noise), glow dot, flame, tire tread."""
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
rng=np.random.default_rng(7)
OUT="Game/Assets/InkDrift/Art/Generated/"
N=256
y,x=np.mgrid[0:N,0:N]/(N-1)*2-1
r=np.sqrt(x*x+y*y)
# smoke: clustered blobs -> lumpy cloud shape, falls to 0 at edge
shape=np.zeros((N,N))
for i in range(9):
    cx,cy=rng.uniform(-0.35,0.35,2); rad=rng.uniform(0.28,0.5)
    shape=np.maximum(shape, np.clip(1-np.sqrt((x-cx)**2+(y-cy)**2)/rad,0,1))
shape=gaussian_filter(shape,3)
shape*=np.clip((1-r)*2.2,0,1)
shape=shape/shape.max()
noise=gaussian_filter(rng.random((N,N)),4); noise=(noise-noise.min())/(noise.max()-noise.min())
img=np.zeros((N,N,4),np.uint8)
img[...,0]=(shape*255).astype(np.uint8); img[...,1]=(noise*255).astype(np.uint8); img[...,2]=0; img[...,3]=255
Image.fromarray(img,"RGBA").save(OUT+"smoke_puff.png")
# glow dot
g=np.clip(1-r,0,1)**2.2
Image.fromarray(np.dstack([np.full((N,N),255)]*3+[(g*255)]).astype(np.uint8),"RGBA").save(OUT+"glow_dot.png")
# flame: teardrop along +y (stretched particle aligns with velocity)
fx=x; fy=(y+1)/2
fl=np.clip(1-np.abs(fx)/(0.15+0.55*fy*(1-fy)*2),0,1)*np.clip(1-np.abs(fy-0.45)*1.9,0,1)
fl=gaussian_filter(fl,2)
col=np.dstack([np.full((N,N),255),np.clip(120+fl*135,0,255),np.clip(fl**3*255,0,255),fl*255]).astype(np.uint8)
Image.fromarray(col,"RGBA").save(OUT+"flame.png")
# tread: grayscale grooves along v
t=np.zeros((128,64))
for i in range(64):
    t[:,i]=0.6+0.4*np.sin(i/64*np.pi*6)
for j in range(128):
    if (j//8)%2==0: t[j,:]*=0.85
Image.fromarray((t*255).astype(np.uint8),"L").save(OUT+"tread.png")
print("ok")
