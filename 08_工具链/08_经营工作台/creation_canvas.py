"""Project-bound local canvas; project records and media remain in place."""
import json
import math
import uuid
from workspaces import WorkspaceConflict as CanvasConflict

class CreationCanvas:
    def __init__(self, app):
        self.app=app
        with app.lock:
            app.db.execute('CREATE TABLE IF NOT EXISTS creation_canvases (object_id TEXT PRIMARY KEY, data TEXT NOT NULL, version TEXT NOT NULL)')
            app.db.commit()

    def get(self, object_id):
        project=self.app.creation.get_project(object_id)
        with self.app.lock:
            row=self.app.db.execute('SELECT data,version FROM creation_canvases WHERE object_id=?',(object_id,)).fetchone()
        if row:
            return {**json.loads(row[0]),'object_id':object_id,'version':row[1]}
        summary=next((line.strip().replace('**','') for line in project.get('summary','').splitlines() if line.strip() and not line.lstrip().startswith(('#','|','---'))),'')
        nodes=[{'id':'brief','type':'creation','position':{'x':60,'y':80},'data':{'title':project['title'],'content':summary[:200]}}]
        for index,asset in enumerate(project.get('assets',[])[:8]):
            nodes.append({'id':'asset-'+str(index),'type':'asset','position':{'x':420+(index%3)*260,'y':80+(index//3)*200},
                          'data':{'title':asset['name'],'media_path':asset['path'],'kind':asset['type']}})
        return {'object_id':object_id,'title':project['title'],'nodes':nodes,'edges':[],'version':''}

    def save(self, body):
        if not isinstance(body,dict):raise ValueError('画布内容格式错误')
        object_id=body.get('object_id');project=self.app.creation.get_project(object_id)
        nodes,edges=body.get('nodes'),body.get('edges')
        if not isinstance(nodes,list) or not isinstance(edges,list):raise ValueError('画布节点或连线格式错误')
        ids=set()
        for node in nodes:
            if not isinstance(node,dict) or not isinstance(node.get('id'),str) or not node['id'] or node['id'] in ids or node.get('type') not in ('creation','text','asset') or not isinstance(node.get('data'),dict):raise ValueError('画布节点格式错误')
            pos=node.get('position')
            if not isinstance(pos,dict) or any(type(pos.get(axis)) not in (int,float) or not math.isfinite(pos[axis]) for axis in ('x','y')):raise ValueError('画布节点位置无效')
            ids.add(node['id'])
        for edge in edges:
            if not isinstance(edge,dict) or not isinstance(edge.get('id'),str) or edge.get('source') not in ids or edge.get('target') not in ids:raise ValueError('画布连线缺少对应节点')
        payload={'title':project['title'],'nodes':nodes,'edges':edges}
        encoded=json.dumps(payload,ensure_ascii=False,allow_nan=False)
        if len(encoded)>500000:raise ValueError('画布内容过长')
        with self.app.lock:
            row=self.app.db.execute('SELECT version FROM creation_canvases WHERE object_id=?',(object_id,)).fetchone()
            if (row[0] if row else '') != body.get('version',''):raise CanvasConflict('这份画布已被其他页面更新，请重新打开')
            version=uuid.uuid4().hex
            self.app.db.execute('INSERT OR REPLACE INTO creation_canvases VALUES (?,?,?)',(object_id,encoded,version));self.app.db.commit()
        return {**payload,'object_id':object_id,'version':version}
