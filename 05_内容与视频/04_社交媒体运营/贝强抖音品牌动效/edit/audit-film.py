"""Verify the rendered stream and actual source-frame usage; write QA samples."""
import sys,importlib.util,json,hashlib,subprocess
from pathlib import Path
import numpy as np

P=Path(__file__).resolve().parents[1]
helper=Path('E:/C盘迁移/Codex/.codex/skills/video-use/helpers')
sys.path.insert(0,str(helper))
spec=importlib.util.spec_from_file_location('videoqa',helper/'video_qa.py')
qa=importlib.util.module_from_spec(spec);spec.loader.exec_module(qa)
video=P/'edit/render/current.mp4'
if not video.exists():
 video=P/'out/贝强_针织袜子鞋_品牌片.mp4'
root=P/'edit/qa/current'
meta=qa.probe_video(video);meta['source']=qa.source_identity(video)
meta['source']['sha256']=hashlib.sha256(video.read_bytes()).hexdigest()
timeline=json.loads((P/'edit/timeline.json').read_text(encoding='utf-8'));seconds=timeline['duration_seconds'];fps=timeline['fps']
assert meta['frame_count']==timeline['total_frames'] and meta['fps']==fps and abs(meta['duration']-seconds)<.001
root.mkdir(parents=True,exist_ok=True)
cache=root/'_cache'/meta['source']['source_id']
# Sample destinations are rebuildable and remain inside this project's QA directory.
for folder in [root/'frames',root/'focused/cuts',root/'focused/action']:
 if folder.exists():
  assert folder.resolve().is_relative_to(P.resolve()) and not folder.is_symlink()
  for old in folder.glob('*.jpg'):old.unlink()
times=[round(.05+i*(seconds-.10)/23,3) for i in range(24)]
frames=qa.extract_frame_set(video,times,root/'frames',cache)
qa.create_contact_sheet(frames,root/'contact_sheet.jpg',f'{seconds:g}-second complete film / 24 time points')
meta['sampling']={'strategy':'uniform','sample_count':24,'times':times}
(root/'video_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'sampling_manifest.json').write_text(json.dumps({'source_id':meta['source']['source_id'],'frames':frames},ensure_ascii=False,indent=2),encoding='utf-8')
cuts=sorted([s['from']/fps for s in timeline['scenes'][1:]]+[s['from']/fps+c/fps for s in timeline['scenes'] for c in s.get('internal_cuts',[])])
cutframes=qa.extract_frame_set(video,[round(c+d/24,3) for c in cuts for d in [-1,0,1]],root/'focused/cuts',cache)
qa.create_contact_sheet(cutframes,root/'cut_sheet.jpg',f'All {len(cuts)} cuts / before, first and after frames')
actimes=[0,.25,.5,.95,1,1.3,2.45,2.5,2.625,2.75,3,3.375,4.4,4.55,5,5.7,6.3,6.9,7.45,8.2,9.2,10.1,11.6,12.5,13.3,14.3,15.5,16.5,17.4,17.6,18.1,18.6,19.4,19.6,19.875,21.5,23.7]
action=qa.extract_frame_set(video,actimes,root/'focused/action',cache)
qa.create_contact_sheet(action,root/'action_sheet.jpg','Aperture, typography, tactile event, both legs and final reading')
(root/'cut_manifest.json').write_text(json.dumps({'source_id':meta['source']['source_id'],'frames':cutframes+action},ensure_ascii=False,indent=2),encoding='utf-8')

def decode(path,width=216,height=384):
 raw=subprocess.check_output([qa.FFMPEG,'-v','error','-i',str(path),'-vf',f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0xede5d8','-an','-pix_fmt','rgb24','-f','rawvideo','-'])
 return np.frombuffer(raw,dtype=np.uint8).reshape(-1,height,width,3)
film=decode(video)
ranges=[(Path(s['src']).stem,s['from'],s['from']+s['frames'],s.get('sourceFrame',0)) for s in timeline['scenes'] if s.get('video')]
usage=[]
for name,start,end,source_start in ranges:
 source=decode(P/'public/dynamic'/f'{name}.mp4')
 # Text lives at the top; comparison covers the entire lower subject area.
 a=film[start:end,88:];b=source[source_start:source_start+end-start,88:]
 err=np.abs(a.astype(float)-b.astype(float)).mean(axis=(1,2,3))
 usage.append({'source':name,'film_frames':[start,end],'source_frames':[source_start,source_start+end-start],
 'used_seconds':(end-start)/24,'mean_absolute_pixel_difference':round(float(err.mean()),4),
 'maximum_frame_mean_difference':round(float(err.max()),4),'comparison_within_tolerance':bool(err.max()<12)})
 assert err.max()<12,(name,float(err.max()))
diff=np.abs(np.diff(film.astype(np.int16),axis=0)).mean(axis=(1,2,3))
tech={'source_id':meta['source']['source_id'],'sha256':meta['source']['sha256'],
 'decoded_frames':len(film),'duration':seconds,'fps':fps,
 'near_black_frames':np.where(film.mean(axis=(1,2,3))<3)[0].tolist(),
 'exact_duplicate_adjacent_frames':np.where(diff==0)[0].tolist(),
 'intentional_static_hold_frames':[timeline['scenes'][-1]['from']+10,timeline['total_frames']],
 'actual_video_usage':usage,'new_paid_seconds_used':sum(u['used_seconds'] for u in usage),'motion_seconds_total':sum(u['used_seconds'] for u in usage),'current_edit_paid_submissions':0,
 'limits':'Decoding and source correspondence verify frame delivery and retention, not subjective continuous playback or audio listening.'}
(root/'technical-audit.json').write_text(json.dumps(tech,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(tech,ensure_ascii=False))
