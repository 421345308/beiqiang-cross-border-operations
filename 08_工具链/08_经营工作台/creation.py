"""Read-only creation catalog over original project records and official LibTV CLI."""
from pathlib import Path
import hashlib
import re

MEDIA={'.mp4','.webm','.mov','.png','.jpg','.jpeg','.wav','.mp3','.html'}
class Creation:
    def __init__(self,root,adapter=None):
        self.root=Path(root).resolve()
        self.base=(self.root/'05_内容与视频').resolve()
        self.allowed_roots=[self.base]+[(self.base/name).resolve() for name in ('01_贝强商品视频','02_TikTok运营','03_通用AI视频实验','04_社交媒体运营')]
        self.adapter=adapter

    def _records(self):
        # Follow existing navigation only; never walk media/dependency trees.
        queue=[self.base/'README.md']
        queue += [self.base/name/'README.md' for name in ('01_贝强商品视频','02_TikTok运营','03_通用AI视频实验','04_社交媒体运营')]
        seen=set(); records=set()
        from urllib.parse import unquote
        while queue and len(seen)<100:
            index=queue.pop(0)
            if index in seen:continue
            seen.add(index)
            if not index.is_file() or index.stat().st_size>1000000:continue
            content=index.read_text(encoding='utf-8-sig')
            for ref in re.findall(r'\]\(([^)]+)\)',content):
                if '://' in ref:continue
                target=(index.parent/unquote(ref.split('#')[0])).absolute()
                if not any(target.resolve().is_relative_to(root) for root in self.allowed_roots):continue
                if target.name in ('PROJECT.md','PROJECT_GUIDE.md') and target.is_file():records.add(target)
                elif target.name in ('README.md','VIDEO_INDEX.md') and target not in seen:queue.append(target)
        return sorted(records)

    def _summary(self,path):
        relative=path.relative_to(self.root).as_posix()
        content=path.read_text(encoding='utf-8-sig')
        title=next((line.lstrip('# ').strip() for line in content.splitlines() if line.startswith('# ')),path.parent.name)
        return {'id':'creation:'+hashlib.sha256(relative.encode()).hexdigest()[:24],'title':title,'source':relative,'kind':'creation','summary':content[:1000],'status':'见原项目记录','updated_at':path.stat().st_mtime}

    def list_projects(self,q=''):
        if not isinstance(q,str):raise ValueError('查询格式无效')
        rows=[self._summary(p) for p in self._records()]
        return [r for r in rows if q.casefold() in (r['title']+' '+r['source']+' '+r['summary']).casefold()]

    def get_project(self,project_id):
        for path in self._records():
            row=self._summary(path)
            if row['id']!=project_id:continue
            content=path.read_text(encoding='utf-8-sig')
            assets=[]
            from urllib.parse import unquote
            for ref in re.findall(r'\]\(([^)]+)\)',content)[:200]:
                if '://' in ref:continue
                asset=(path.parent/unquote(ref.split('#')[0])).absolute()
                if not any(asset.resolve().is_relative_to(root) for root in self.allowed_roots) or asset.suffix.lower() not in MEDIA:continue
                if asset.is_file():assets.append({'path':asset.relative_to(self.root).as_posix(),'name':asset.name,'type':asset.suffix.lower()[1:]})
            links=[]
            for url in re.findall(r'https://[^\s<>\)\]"\x27]+',content):
                from urllib.parse import urlsplit
                host=urlsplit(url).hostname or ''
                if host=='liblib.art' or host.endswith('.liblib.art') or host=='libtv.ai' or host.endswith('.libtv.ai'):
                    if url not in links:links.append(url)
            return {**row,'content':content,'assets':assets,'links':links,'notice':'文件存在不代表观看验收或正式发布；状态以原项目为准。'}
        raise ValueError('找不到创作项目')

    def libtv_projects(self,workspace_id='0',page=1):
        if self.adapter is None:
            from connectors.libtv.adapter import Adapter
            self.adapter=Adapter()
        return self.adapter.execute('projects',workspace_id=workspace_id,page=page,page_size=20)
