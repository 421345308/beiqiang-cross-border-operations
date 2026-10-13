"""Serial reviewed-image pipeline; stop on the first failed stage, never retry writes."""
from pathlib import Path
import subprocess,sys,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE=ROOT/'02_Alibaba运营/05_扩品工程/执行记录/HR实源替换'
def main():
    for family in sys.argv[1:]:
        manifest=json.loads((BASE/family/'素材清单.json').read_text(encoding='utf8'))
        assert manifest['state']=='VISUAL_PASS','Image review pending; stop before any upload/prepare/submit'
        for mode in ['bank','prepare','submit']:
            subprocess.run([sys.executable,str(HERE/'replace_hr_real_sources.py'),mode,family],cwd=ROOT,check=True)
if __name__=='__main__':main()
