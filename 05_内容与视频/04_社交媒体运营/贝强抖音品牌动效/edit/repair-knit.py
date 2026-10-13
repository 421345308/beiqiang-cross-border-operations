"""Retouch transient skin-colored slits in generated knit; preserve every frame.

Only enclosed, thin warm-color islands in the lower collar are eligible.
The open shoe mouth, heel, hand and silhouette cannot enter this mask.
Replacement samples existing adjacent knit, without synthesizing a new shoe.
"""
from pathlib import Path
import subprocess, json, hashlib
import numpy as np
from scipy import ndimage as ndi

P=Path(__file__).resolve().parents[1]
FF=Path('C:/Users/spq/Desktop/贝强/08_工具链/02_视频工具/ffmpeg/ffmpeg-9.0-essentials_build/bin/ffmpeg.exe')
src=P/'public/dynamic/donning.mp4'
dst=P/'public/dynamic/donning-clean.mp4'
W,H=1080,1916
reader=subprocess.Popen([str(FF),'-v','error','-i',str(src),'-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
writer=subprocess.Popen([str(FF),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','24','-i','-','-an','-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(dst)],stdin=subprocess.PIPE)
records=[]
i=0
while True:
 raw=reader.stdout.read(W*H*3)
 if not raw:break
 if len(raw)!=W*H*3:raise RuntimeError('incomplete decoded frame')
 frame=np.frombuffer(raw,dtype=np.uint8).reshape(H,W,3).copy()
 # The rectangle stays strictly inside the lower shaft. Boundary-connected
 # skin is excluded, as are broad regions and small texture speckles.
 y0,y1,x0,x1=970,1300,550,950
 crop=frame[y0:y1,x0:x1].copy()
 c=crop.astype(np.float32);r,g,b=c[:,:,0],c[:,:,1],c[:,:,2]
 warm=(r>50)&(g>27)&(r>g*1.18)&(g>b*1.06)
 labels,n=ndi.label(warm)
 mask=np.zeros(warm.shape,bool)
 for k,sl in enumerate(ndi.find_objects(labels),1):
  if sl is None:continue
  yy,xx=sl
  h,w=yy.stop-yy.start,xx.stop-xx.start
  count=int(np.sum(labels[sl]==k))
  if yy.start==0 or yy.stop==warm.shape[0] or xx.start==0 or xx.stop==warm.shape[1]:continue
  if 20<=count<=6500 and w>=18 and w/max(h,1)>=2.5 and h<=40:
   mask|=labels==k
 if mask.any():
  mask=ndi.binary_dilation(mask,iterations=2)
  dark=(np.max(c,axis=2)<58)&(~mask)
  # nearest existing dark-knit sample, with a softened boundary
  _,indices=ndi.distance_transform_edt(~dark,return_indices=True)
  texture=c[indices[0],indices[1]]
  alpha=ndi.gaussian_filter(mask.astype(np.float32),.65)
  alpha[mask]=1
  crop=np.clip(c*(1-alpha[:,:,None])+texture*alpha[:,:,None],0,255).astype(np.uint8)
  frame[y0:y1,x0:x1]=crop
  records.append({'frame':i,'seconds':round(i/24,4),'retouched_pixels':int(mask.sum())})
 writer.stdin.write(frame.tobytes());i+=1
writer.stdin.close()
if reader.wait()!=0 or writer.wait()!=0:raise RuntimeError('media process failed')
report={'source':'public/dynamic/donning.mp4','output':'public/dynamic/donning-clean.mp4',
 'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
 'output_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),
 'frame_count':i,'fps':24,'geometry':'unchanged; 1080x1916; no crop, speed change or removed frame',
 'method':'thin enclosed warm-color island mask; replace with nearest adjacent existing knit sample',
 'roi_xyxy':[550,970,950,1300],'affected_frames':records}
(P/'edit/knit-repair.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'frame_count':i,'affected_count':len(records),'maximum_mask_pixels':max([r['retouched_pixels'] for r in records],default=0)}))
