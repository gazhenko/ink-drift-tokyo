"""Green Japanese expressway gantry signs (4 stacked 2048x512 faces in one 2048x2048 texture)."""
from PIL import Image, ImageDraw, ImageFont
F="Game/Assets/InkDrift/Art/Fonts/"
jp=ImageFont.truetype(F+"NotoSansJP-Bold.ttf",150); en=ImageFont.truetype(F+"NotoSansJP-Bold.ttf",64); num=ImageFont.truetype(F+"ChakraPetch-Bold.ttf",110)
signs=[
 [("銀座","Ginza","C1",False),("羽田","Haneda","1",True)],
 [("新宿","Shinjuku","4",False),("渋谷","Shibuya","3",True)],
 [("箱崎","Hakozaki","9",False),("湾岸線","Wangan","B",True)],
 [("霞が関","Kasumigaseki","C1",False),("池袋","Ikebukuro","5",True)],
]
img=Image.new("RGB",(2048,2048),(0,0,0)); d=ImageDraw.Draw(img)
G=(14,110,64); W=(245,245,240)
for row,pair in enumerate(signs):
    y0=row*512
    d.rectangle([0,y0,2047,y0+511],fill=G)
    d.rectangle([14,y0+14,2033,y0+497],outline=W,width=10)
    for k,(kanji,rom,route,arrowRight) in enumerate(pair):
        x0=60+k*1000
        # route shield
        d.ellipse([x0,y0+70,x0+190,y0+260],fill=W); d.ellipse([x0+12,y0+82,x0+178,y0+248],fill=(30,70,170))
        tw=d.textlength(route,font=num); d.text((x0+95-tw/2,y0+95),route,font=num,fill=W)
        d.text((x0+230,y0+40),kanji,font=jp,fill=W)
        d.text((x0+235,y0+250),rom,font=en,fill=W)
        # arrow
        ax=x0+(760 if k==0 else 690); ay=y0+380
        if arrowRight:
            d.polygon([(ax,ay-40),(ax+120,ay-40),(ax+120,ay-90),(ax+210,ay),(ax+120,ay+90),(ax+120,ay+40),(ax,ay+40)],fill=W)
        else:
            d.polygon([(ax+60,ay+60),(ax+60,ay-60),(ax+10,ay-60),(ax+100,ay-170),(ax+190,ay-60),(ax+140,ay-60),(ax+140,ay+60)],fill=W)
img.save("Game/Assets/InkDrift/Generated/Common/gantry_signs.png")
print("ok")
