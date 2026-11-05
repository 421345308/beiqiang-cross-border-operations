"""Read-only creation catalog over original project records and official LibTV CLI."""
from pathlib import Path
import hashlib
import os
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

    @staticmethod
    def _project_context(content):
        """Expose original sections for review and agent continuation, without inferring state."""
        sections=[]
        current=None
        fenced=False
        for number,line in enumerate(content.splitlines(),1):
            if line.lstrip().startswith(('```','~~~')):
                fenced=not fenced
            heading=None if fenced else re.match(r'^(#{1,6})\s+(.+?)\s*#*$',line)
            if heading:
                if current is not None:
                    current['content']='\n'.join(current.pop('_lines')).strip()
                    sections.append(current)
                current={'title':heading.group(2).strip(),'level':len(heading.group(1)),
                         'line':number,'_lines':[]}
            elif current is not None:
                current['_lines'].append(line)
        if current is not None:
            current['content']='\n'.join(current.pop('_lines')).strip()
            sections.append(current)
        labels={'goal':('目标','本轮交付','项目定位'),
                'progress':('当前状态','当前进度','当前结果','最新进展'),
                'next_actions':('下一步','下一动作','后续行动','待办'),
                'acceptance':('验收','完成依据','交付标准')}
        context={key:[dict(section) for section in sections
                      if any(label in section['title'] for label in names)]
                 for key,names in labels.items()}
        return sections,context

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
                decoded=unquote(ref.split('#')[0])
                if ':' in decoded or any(ord(c)<32 for c in decoded):continue
                # Normalize the project-relative Markdown path lexically first.
                # Resolving it directly would lose the trusted 成片 junction's
                # workspace identity and expose an unusable absolute E: path.
                asset=Path(os.path.abspath(path.parent/decoded))
                if not asset.is_relative_to(self.root) or asset.suffix.lower() not in MEDIA:continue
                relative=asset.relative_to(self.root).as_posix()
                finished=self.root/'05_内容与视频'/'成片'
                if asset.is_relative_to(finished):
                    # The media service checks the explicitly configured root,
                    # nested junctions, private paths and real file signatures.
                    # HTML is intentionally not served as media.
                    from media_assets import MediaAssets, MediaError
                    try:media=MediaAssets(self.root).resolve(relative)
                    except (MediaError,OSError,ValueError):continue
                    assets.append({'path':media['path'],'name':media['name'],'type':asset.suffix.lower()[1:]})
                else:
                    try:allowed=any(asset.resolve().is_relative_to(root) for root in self.allowed_roots) and asset.is_file()
                    except (OSError,RuntimeError,ValueError):continue
                    if allowed:assets.append({'path':relative,'name':asset.name,'type':asset.suffix.lower()[1:]})
            links=[]
            for url in re.findall(r'https://[^\s<>\)\]"\x27]+',content):
                from urllib.parse import urlsplit
                host=urlsplit(url).hostname or ''
                if host=='liblib.art' or host.endswith('.liblib.art') or host=='libtv.ai' or host.endswith('.libtv.ai'):
                    if url not in links:links.append(url)
            sections,context=self._project_context(content)
            return {**row,'sections':sections,'project_context':context,'content':content,'assets':assets,'links':links,'notice':'文件存在不代表观看验收或正式发布；状态以原项目为准。'}
        raise ValueError('找不到创作项目')

    def libtv_projects(self,workspace_id='0',page=1):
        if self.adapter is None:
            from connectors.libtv.adapter import Adapter
            self.adapter=Adapter()
        return self.adapter.execute('projects',workspace_id=workspace_id,page=page,page_size=20)

    def libtv_execute(self, operation, **arguments):
        """Only free canvas/text operations; no model or media generation."""
        if operation not in ('project','nodes','workspaces','create_project','create_text_node'):
            raise ValueError('仅支持读取画布、创建画布和添加文字节点')
        if self.adapter is None:
            from connectors.libtv.adapter import Adapter
            self.adapter=Adapter()
        return self.adapter.execute(operation, **arguments)
