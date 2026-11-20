import sys,glob
from PIL import Image,ImageDraw,ImageFont
out,lines=sys.argv[1],sys.argv[2:]
S=800;m=28;bw=8;bar=64
im=Image.new('RGB',(S,S),'white');d=ImageDraw.Draw(im)
d.rounded_rectangle([m,m,S-m,S-m],radius=22,fill=(178,178,178),outline='black',width=bw)
d.rectangle([m+bw,m+bar,S-m-bw,S-m-bw],fill='white')
d.line([(m,m+bar),(S-m,m+bar)],fill='black',width=bw)
d.rounded_rectangle([m,m,S-m,S-m],radius=22,outline='black',width=bw)
for i in range(3):
  cx=m+36+i*42;cy=m+bar//2+2;d.ellipse([cx-13,cy-13,cx+13,cy+13],fill='white',outline='black',width=5)
fp=(glob.glob('/usr/share/fonts/**/NotoSansCJK-Black.ttc',recursive=True)+glob.glob('/usr/share/fonts/**/NotoSansCJK-Bold.ttc',recursive=True))[0]
top=m+bar+bw;area=S-m-bw-top;size=140
fits=lambda s:all(d.textlength(l,font=ImageFont.truetype(fp,s,index=1))<=660 for l in lines) and len(lines)*s*1.22<=area-40
while not fits(size):size-=4
f=ImageFont.truetype(fp,size,index=1);lh=size*1.22;y0=top+(area-lh*len(lines))/2+lh/2
for i,l in enumerate(lines):d.text((S/2,y0+i*lh),l,font=f,fill=(255,0,0) if i==len(lines)-1 else (0,0,0),anchor='mm')
im.save(out,quality=92)
