"""Render an inspectable local retail-video job. Never generates or publishes media.

Each shot is rendered once with its final typography, then concatenated losslessly.
All paths resolve from the manifest's workspace_root; originals stay read-only.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,re

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def call(args):return subprocess.check_output(args,encoding='utf-8').strip()

def ass_time(sec):
    cs=round(sec*100);return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'

def write_ass(path,shot,w,h,fps):
    def clean(s):
        assert '{' not in s and '}' not in s
        return s.replace('\n',r'\N')
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Note,Microsoft YaHei,22,&H00474747,&H00474747,&H00FFFFFF,&H00000000,0,0,0,0,100,100,1,0,1,1,0,7,44,90,42,1
Style: Title,Microsoft YaHei,42,&H00262626,&H00262626,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,1,0,1,1.5,0,7,44,90,100,1
Style: Detail,Microsoft YaHei,25,&H00474747,&H00474747,&H00FFFFFF,&H00000000,0,0,0,0,100,100,1,0,1,1.2,0,7,44,90,163,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    end=ass_time(shot['frames']/fps)
    for style,txt in [('Note',shot.get('disclosure','')),('Title',shot.get('title','')),('Detail',shot.get('detail',''))]:
        if txt:header+=f'Dialogue: 0,0:00:00.00,{end},{style},,0,0,0,,{clean(txt)}\n'
    path.write_text(header,encoding='utf-8-sig')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['validate','render']);ap.add_argument('manifest',type=Path);a=ap.parse_args()
    job=json.loads(a.manifest.read_text(encoding='utf-8'));root=Path(job['workspace_root']);out=root/job['output'];work=out.parent/('render_'+out.stem)
    fps=job['fps'];w,h=job['width'],job['height'];assert fps>0 and w%2==h%2==0
    assert job['product_evidence'] and job['creative_change']
    sources={}
    for i,s in enumerate(job['shots']):
        path=root/s['source'];assert path.is_file(),path;assert s['frames']>0
        if s['kind']=='video':assert s['end_frame']-s['start_frame']==s['frames']
        else:assert s['kind']=='image'
        sha=digest(path);assert sha==s['source_sha256'],f'Source changed: {path}';sources[s['source']]=sha
    audio=root/job['audio'];assert audio.is_file();assert digest(audio)==job['audio_sha256']
    total=sum(s['frames'] for s in job['shots']);assert total==job['expected_frames']
    # The workspace media directory is an intentional E-drive junction.
    assert out.resolve().is_relative_to((root/'05_内容与视频/01_贝强商品视频').resolve())
    print(json.dumps({'validated':True,'shots':len(job['shots']),'frames':total,'duration':total/fps,'no_paid_generation':True},ensure_ascii=False),flush=True)
    if a.mode=='validate':return
    assert not out.exists(),'Existing result is immutable; use a new output revision.'
    work.mkdir(parents=True,exist_ok=True)
    clips=[]
    for i,s in enumerate(job['shots']):
        clip=work/f'{i:02}.mp4';sub=work/f'{i:02}.ass';write_ass(sub,s,w,h,fps)
        args=['ffmpeg','-v','error']
        if s['kind']=='image':args+=['-loop','1','-framerate',str(fps)]
        args+=['-i',str(root/s['source'])]
        if s['kind']=='video':vf=f"trim=start_frame={s['start_frame']}:end_frame={s['end_frame']},setpts=PTS-STARTPTS,"
        else:vf=''
        vf+=f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,fps={fps},subtitles={sub.name}"
        subprocess.run(args+['-vf',vf,'-frames:v',str(s['frames']),'-an','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-r',str(fps),'-video_track_timescale','12288',str(clip)],cwd=work,check=True)
        clips.append(clip)
    concat=work/'concat.txt';concat.write_text(''.join(f"file '{c.name}'\n" for c in clips),encoding='utf-8')
    subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(concat),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(total/fps),'-movflags','+faststart',str(out)],check=True)
    metadata=json.loads(call(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(out)]));v=next(s for s in metadata['streams'] if s['codec_type']=='video');assert int(v['nb_frames'])==total
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(out),'-f','null','NUL'],capture_output=True,text=True,encoding='utf-8');assert decoded.returncode==0 and not decoded.stderr.strip()
    meter=subprocess.run(['ffmpeg','-hide_banner','-i',str(out),'-af','loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','NUL'],capture_output=True,text=True,encoding='utf-8');stats=json.loads(re.search(r'\{\s*"input_i".*?\}',meter.stderr,re.S).group())
    result={'job_id':job['job_id'],'output':job['output'],'output_sha256':digest(out),'frames':total,'duration':float(metadata['format']['duration']),'dimensions':[w,h],'fps':fps,'source_hashes':sources,'audio_sha256':digest(audio),'full_decode_errors':False,'integrated_lufs':float(stats['input_i']),'true_peak_dbtp':float(stats['input_tp']),'video_regeneration_count':0,'audio_generation_count':0,'visual_review':'PENDING','published':False}
    (out.parent/'render_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
