"""Explicit local document references; bytes are available only after registration."""
import json, uuid, mimetypes
from pathlib import Path
from urllib.parse import quote

class ResourceLibrary:
    def __init__(self, app):
        self.app=app
        app.db.execute('CREATE TABLE IF NOT EXISTS resource_library (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        app.db.commit()
    def candidates(self, query=''):
        query=str(query or '').strip().casefold()
        result=[]
        for directory in ('04_客户开发/.local/网站询盘','04_客户开发/06_报价与产品册/国际B2B精选册/交付','00_总控台/产品中心'):
            base=self.app.root/directory
            if not base.is_dir(): continue
            for path in base.rglob('*'):
                if len(result)>=400: break
                if 'pdf-qa' in path.parts: continue
                if path.suffix.lower() not in ('.pdf','.docx','.xlsx','.pptx','.jpg','.jpeg','.png','.webp'): continue
                relative=path.relative_to(self.app.root).as_posix()
                if query and query not in relative.casefold(): continue
                try: self.locate(relative)
                except (ValueError,OSError): continue
                result.append({'name':path.name,'path':relative})
        # 产品图片沿用产品中心已有索引，按款号搜索，不重复扫描媒体库。
        if len(query)>=2:
            for product in self.app.business.list_objects(kind='product',q=query)[:10]:
                detail=self.app.business.get_object(product['id'])
                for asset in detail.get('assets',[]):
                    relative=asset.get('path','')
                    if Path(relative).suffix.lower() not in ('.jpg','.jpeg','.png','.webp'): continue
                    try: self.locate(relative)
                    except (ValueError,OSError): continue
                    if not any(row['path']==relative for row in result):
                        result.append({'name':f"{product['title']} · {Path(relative).name}",'path':relative})
                    if len(result)>=60: break
                if len(result)>=60: break
        return sorted(result,key=lambda r:(not r['path'].lower().endswith('.pdf'),r['name']))
    def locate(self, value):
        if not isinstance(value,str) or not value.strip(): raise ValueError('请选择或填写原文件路径')
        value=value.strip().replace('\\','/')
        rel=Path(value)
        if rel.is_absolute() or '..' in rel.parts or ':' in value: raise ValueError('请选择工作区内的资料')
        if not rel.parts or rel.parts[0] not in ('00_总控台','01_产品资产','04_客户开发','07_知识库与Skills'): raise ValueError('请选择产品、客户或知识资料')
        if any(p.lower() in ('credentials','secrets','auth') or '凭证' in p for p in rel.parts): raise ValueError('该文件不属于业务资料')
        try: path=(self.app.root/rel).resolve(strict=True)
        except (FileNotFoundError,OSError): raise ValueError('原文件不存在或暂时无法访问，请检查文件路径') from None
        if not path.is_relative_to(self.app.root.resolve()):
            # 产品目录可由 Windows Junction 指向 E 盘，沿用现有媒体定位规则。
            if rel.parts[0]!='01_产品资产' or not getattr(self.app,'media',None): raise ValueError('资料不在工作区内')
            try: path=self.app.media._locate(value)[0]
            except ValueError: raise ValueError('该产品图片暂时无法读取') from None
        if not path.is_file(): raise ValueError('资料不在工作区内')
        if path.suffix.lower() not in ('.pdf','.png','.jpg','.jpeg','.webp','.docx','.xlsx','.pptx','.txt','.md','.csv'): raise ValueError('请选择 PDF、图片或常见办公文档')
        return path
    def list(self):
        with self.app.lock: return [json.loads(r[0]) for r in self.app.db.execute('SELECT data FROM resource_library ORDER BY rowid DESC')]
    def for_object(self, object_id):
        if not isinstance(object_id,str) or not object_id.startswith(('customer:', 'prospect:')): raise ValueError('请选择客户或候选客户')
        return [row for row in self.list() if not row['object_ids'] or object_id in row['object_ids']]

    def read_for_object(self, object_id, rid, start=0, limit=12000):
        if type(start) is not int or start<0 or type(limit) is not int or not 1<=limit<=20000: raise ValueError('读取范围无效')
        item=next((row for row in self.for_object(object_id) if row['id']==rid),None)
        if not item: raise ValueError('资料不属于当前客户或共用资料')
        path=self.locate(item['path']); suffix=path.suffix.lower()
        if suffix in ('.jpg','.jpeg','.png','.webp'):
            return {'id':rid,'title':item['title'],'path':item['path'],'kind':'image','content':None}
        if suffix=='.pdf':
            try: from pypdf import PdfReader
            except ImportError: raise ValueError('读取PDF需要安装 pypdf') from None
            reader=PdfReader(path); pages=reader.pages[:30]
            content='\n\n'.join((page.extract_text() or '') for page in pages)
            pages_total=len(reader.pages)
        elif suffix in ('.txt','.md','.csv'):
            content=path.read_text(encoding='utf-8-sig');pages_total=None
        else:
            return {'id':rid,'title':item['title'],'path':item['path'],'kind':'document','content':None}
        return {'id':rid,'title':item['title'],'path':item['path'],'kind':'text','content':content[start:start+limit],
                'start':start,'totalChars':len(content),'nextStart':start+limit if start+limit<len(content) else None,
                'pages_total':pages_total,'pages_read':min(pages_total,30) if pages_total is not None else None}
    def _fields(self, body, existing=None):
        ids=body.get('object_ids', existing['object_ids'] if existing else [])
        valid={o['id'] for o in self.app.business.list_objects()}
        if not isinstance(ids,list) or any(not isinstance(i,str) or i not in valid for i in ids):
            raise ValueError('请选择现有客户或商品；无关联对象时为共用资料')
        title=body.get('title',existing['title'] if existing else '')
        if not isinstance(title,str): raise ValueError('请填写资料名称')
        title=title.strip()
        if existing and not title: raise ValueError('资料名称不能为空')
        if len(title)>160: raise ValueError('资料名称请控制在160字以内')
        return title,list(dict.fromkeys(ids))

    def add(self, body):
        if not isinstance(body,dict): raise ValueError('资料内容格式不正确')
        path=body.get('path','')
        resolved=self.locate(path)
        path=Path(path.strip().replace('\\','/')).as_posix()
        title,ids=self._fields(body)
        item={'id':uuid.uuid4().hex,'title':title or Path(path).stem,'path':path,'object_ids':ids}
        with self.app.lock:
            for row in self.app.db.execute('SELECT data FROM resource_library'):
                previous=json.loads(row[0])
                try: duplicate=self.locate(previous['path'])==resolved
                except (ValueError,OSError): duplicate=previous['path']==path
                if duplicate: raise ValueError('这份文件已在资料包中，请编辑已有资料的名称或关联客户')
            self.app.db.execute('INSERT INTO resource_library VALUES (?,?)',(item['id'],json.dumps(item,ensure_ascii=False)))
            self.app.db.commit()
        return item

    def update(self, body):
        if not isinstance(body,dict): raise ValueError('资料内容格式不正确')
        with self.app.lock:
            row=self.app.db.execute('SELECT data FROM resource_library WHERE id=?',(body.get('id',''),)).fetchone()
            if not row: raise ValueError('资料记录不存在，请刷新后再试')
            item=json.loads(row[0])
            title,ids=self._fields(body,item)
            item.update(title=title,object_ids=ids)
            self.app.db.execute('UPDATE resource_library SET data=? WHERE id=?',(json.dumps(item,ensure_ascii=False),item['id']))
            self.app.db.commit()
        return item

    def remove(self, rid):
        if not isinstance(rid,str) or not rid: raise ValueError('请选择要移除的资料')
        with self.app.lock:
            result=self.app.db.execute('DELETE FROM resource_library WHERE id=?',(rid,))
            if not result.rowcount: raise ValueError('资料记录不存在，请刷新后再试')
            self.app.db.commit()
        return {'removed':rid}

    def serve(self, handler, rid):
        item=next((r for r in self.list() if r['id']==rid),None)
        if not item: raise ValueError('资料不存在')
        path=self.locate(item['path']); data=path.read_bytes()
        handler.send_response(200)
        handler.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        handler.send_header('Content-Disposition',"inline; filename*=UTF-8''"+quote(path.name))
        handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Cache-Control','private, no-store')
        handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data)
