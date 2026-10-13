from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from scipy import ndimage as ndi
OUT=Path('single_agent_resume_2310/slipper_publish/M001/real_foreground_composite');OUT.mkdir(parents=True,exist_ok=True)
src=Path('../task-7/M001_execution/native_crops/Red.jpg')
im=Image.open(src).convert('RGB');a=np.array(im).astype(float)
# Color segmentation finds real red perimeter; hole fill retains original dark lettering.
envelope=Image.new('L',im.size);ImageDraw.Draw(envelope).polygon([(81,17),(105,12),(139,19),(166,30),(189,50),(207,73),(221,98),(239,128),(259,155),(278,181),(295,208),(311,236),(324,262),(337,286),(348,310),(358,336),(367,368),(376,405),(385,447),(392,480),(401,514),(405,538),(401,563),(391,584),(372,600),(349,612),(324,618),(297,616),(271,608),(248,592),(225,575),(202,551),(179,526),(161,499),(143,469),(125,440),(106,408),(88,375),(70,340),(54,305),(39,264),(27,226),(18,189),(11,158),(11,129),(14,100),(28,74),(42,48),(63,31)],fill=255)
envelope=envelope.filter(ImageFilter.MaxFilter(7))
red=(a[:,:,0]>65)&(a[:,:,0]>a[:,:,1]*1.38)&(a[:,:,0]>a[:,:,2]*1.22)&(np.array(envelope)>0)
labels,n=ndi.label(red);sizes=np.bincount(labels.ravel());sizes[0]=0
shoe=ndi.binary_fill_holes(labels==sizes.argmax())
# Bound hand selection to visible source fingers/wrist, without reconstructing hidden parts.
hand=Image.new('L',im.size);d=ImageDraw.Draw(hand)
d.polygon([(31,305),(43,291),(68,277),(80,277),(89,283),(90,294),(85,309),(65,322),(61,334),(103,336),(116,342),(121,350),(119,360),(108,369),(81,380),(86,390),(122,389),(135,396),(137,405),(133,416),(115,428),(94,435),(91,444),(103,458),(135,475),(149,499),(179,531),(193,575),(207,609),(220,629),(294,629),(286,600),(273,564),(236,516),(177,463),(117,438),(68,423),(52,404),(51,388),(42,376),(39,357),(42,344),(34,329)],fill=255)
skin=(np.array(hand)>0)&(a[:,:,0]>a[:,:,1]*1.07)&(a[:,:,0]>a[:,:,2]*1.14)&(a[:,:,0]>45)
skin=ndi.binary_fill_holes(skin)
mask=Image.fromarray(np.maximum(shoe.astype('uint8')*255,skin.astype('uint8')*255))
# At most subpixel-style antialias; foreground RGB is never retouched or regenerated.
mask=mask.filter(ImageFilter.GaussianBlur(.35));mask.save(OUT/'foreground_mask.png')
fg=im.copy();fg.putalpha(mask);fg.save(OUT/'real_foreground.png')
bgpath=OUT/'generated_empty_background.png'
if bgpath.exists():bg=Image.open(bgpath).convert('RGB').resize((700,700),Image.Resampling.LANCZOS)
else:bg=Image.new('RGB',(700,700),(242,242,240))
offset=(135,70);bg.paste(im,offset,mask);bg.save(OUT/'M001_real_composite.png');bg.save(OUT/'M001_real_composite.jpg',quality=96,subsampling=0)
opaque=np.array(mask)==255;actual=np.array(bg)[70:700,135:560];orig=np.array(im)
proof={'source':str(src.resolve()),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'source_size':im.size,'output_size':[700,700],'offset':offset,'foreground_scale':1,'foreground_stretch':False,'foreground_regenerated':False,'opaque_foreground_pixel_equality':bool(np.array_equal(actual[opaque],orig[opaque])),'shoe_full_extent_height_fraction':600/700,'background_generated':bgpath.exists(),'shadow_policy':'Original hand-held product; no invented floor contact shadow','output_sha256':hashlib.sha256((OUT/'M001_real_composite.jpg').read_bytes()).hexdigest(),'qa':'PENDING_VISUAL'}
(OUT/'provenance.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(proof))
