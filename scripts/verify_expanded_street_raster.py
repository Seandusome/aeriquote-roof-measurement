"""Independent raster check for opt-in synthetic Street View PDF fixtures, no providers."""
import json,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
all_layouts='--all-layouts' in sys.argv;root=Path(sys.argv[1]);results=json.loads((root/'results.json').read_text());evidence=[]
for job in results:
 images=[];found=0
 for pdf in job['pdfs']:
  pdf=Path(pdf);pre=pdf.with_suffix('');subprocess.run(['pdftoppm','-scale-to','1100','-png',str(pdf),str(pre)],check=True,stderr=subprocess.DEVNULL)
  pages=sorted(root.glob(pre.name+'-*.png'))
  for p in pages:
   im=Image.open(p).convert('RGB');images.append((p.name,im.copy()))
   if not all_layouts and 'expanded' not in p.name:continue
   a=np.asarray(im).astype(int);blue=(abs(a[:,:,0]-219)<12)&(abs(a[:,:,1]-234)<12)&(abs(a[:,:,2]-254)<12)
   labeled,n=ndimage.label(blue);sizes=np.bincount(labeled.ravel());sizes[0]=0
   if n==0 or max(sizes)<300:continue
   ys,xs=np.where(labeled==sizes.argmax());x0,x1,y0,y1=xs.min(),xs.max(),ys.min(),ys.max();crop=a[y0:y1+1,x0:x1+1];navy=(crop[:,:,0]<45)&(crop[:,:,1]<55)&(crop[:,:,2]<100)
   lab,count=ndimage.label(navy);ss=np.bincount(lab.ravel());ss[0]=0
   if count==0:raise AssertionError('Missing calibration circle '+p.name)
   cy,cx=np.where(lab==ss.argmax());ratio=(cx.max()-cx.min()+1)/(cy.max()-cy.min()+1);assert .90<ratio<1.10,(p.name,'stretched circle',ratio)
   red=(a[:,:,0]>170)&(a[:,:,1]<85)&(a[:,:,2]<85);ry,rx=np.where(red)
   assert len(rx)>20,(p.name,'missing source border')
   expected=next(c for c in job['captureChecks'] if c.get('street'));source_ratio=expected['sourceWidth']/expected['sourceHeight'];border_ratio=(rx.max()-rx.min()+1)/(ry.max()-ry.min()+1);assert abs(border_ratio/source_ratio-1)<.06,(p.name,'cropped or distorted source border',border_ratio,source_ratio)
   evidence.append(dict(pdf=pdf.name,page=p.name,circle_ratio=round(ratio,4),source_ratio=round(source_ratio,4),border_ratio=round(border_ratio,4)));found+=1
  # One contact per actual PDF: every rendered page retained, unmodified originals remain nearby.
  thumbs=[]
  for name,im in images:
   if not name.startswith(pre.name+'-'):continue
   im.thumbnail((700,600));thumbs.append(im)
  if thumbs:
   contact=Image.new('RGB',(sum(i.width for i in thumbs),max(i.height for i in thumbs)+28),'#ccc');draw=ImageDraw.Draw(contact);draw.text((8,6),pdf.name,fill='black');x=0
   for im in thumbs:contact.paste(im,(x,28));x+=im.width
   contact.save(root/(pre.name+'-review.png'))
 assert found==(2 if all_layouts else 1),(job['industry'],job['width'],'must show full Street View once per tested layout')
(root/'raster-checks.json').write_text(json.dumps(evidence,indent=2));print('PASS',len(results),'Single/Expanded PDF pairs' if all_layouts else 'Expanded PDFs','calibration circles proportional, all four source borders retained')
