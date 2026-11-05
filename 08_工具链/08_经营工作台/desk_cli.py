"""Desktop agents use the same business objects and artifacts as the local UI.

Examples: desk_cli.py objects list --kind product
          desk_cli.py objects get product:MODEL
          desk_cli.py artifacts list --object-id product:MODEL
          desk_cli.py artifacts save product:MODEL --title 选款方案 < draft.md
No HTTP token, server startup or model invocation is needed.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent


def open_business(root=None, state=None):
    from business import Business
    folder = Path(state or HERE / '.local').resolve()
    folder.mkdir(parents=True, exist_ok=True)
    app = SimpleNamespace(root=Path(root or HERE.parents[1]).resolve(), state=folder,
                          lock=threading.RLock(), db=sqlite3.connect(folder / 'runs.sqlite3', timeout=30))
    try:
        app.business = Business(app)
        from customer_workspace import CustomerWorkspace
        from inquiry_intake import InquiryIntake
        app.customer_workspace = CustomerWorkspace(app)
        app.inquiry_intake = InquiryIntake(app)
        from creation import Creation
        from creation_canvas import CreationCanvas
        app.creation = Creation(app.root)
        app.creation_canvas = CreationCanvas(app)
        from media_assets import MediaAssets
        from resource_library import ResourceLibrary
        app.media = MediaAssets(app.root)
        from product_creation import ProductCreation
        app.product_creation = ProductCreation(app)
        app.library = ResourceLibrary(app)
        from gmail_sync import GmailService
        app.gmail = GmailService(app)
    except Exception:
        app.db.close()
        raise
    return app


def invoke(business, area, operation, *, object_id=None, kind='', query='', title=None, content=None, artifact_id=None, material_id=None, start=0, shop=None, page=1, page_size=100, project_id=None, media_path=None, version=None):
    if area == 'capabilities' and operation == 'list':
        from desk_mcp import TOOLS
        term = query.casefold().strip()
        matched = [tool for tool in TOOLS if not term or term in (tool['name'] + ' ' + tool['description']).casefold()]
        return {'interface': 'business MCP, scoped to current object', 'availability': 'unknown',
                'cost': 'unknown', 'notice': '工具定义不证明连接、权限或额度可用；调用时返回实际状态。',
                'capabilities': matched}
    if area == 'product-creation':
        service = business.app.product_creation
        if operation == 'options':return service.options(object_id)
        if operation == 'add':
            if version is None:raise ValueError('请先读取画布并提供其version')
            return service.add_to_canvas(object_id, project_id, media_path, version)
        raise ValueError('不支持的商品素材动作')
    if area == 'douyin':
        from douyin_agent import read_store
        if operation=='live':return read_store(shop,operation,page=page,page_size=page_size)
        return read_store(shop,operation)
    if area == 'materials':
        if operation=='list':return {'materials':business.app.library.for_object(object_id)}
        if operation=='read':return business.app.library.read_for_object(object_id,material_id,start=start)
        raise ValueError('不支持的资料包动作')
    if area == 'canvas':
        canvas = business.app.creation_canvas
        if operation == 'get':return canvas.get(object_id)
        if operation == 'save':
            try:body = json.loads(content)
            except (ValueError, TypeError):raise ValueError('画布保存需要JSON正文，包含version、nodes和edges')
            if not isinstance(body,dict) or not {'version','nodes','edges'} <= set(body):raise ValueError('画布保存须明确version、nodes和edges；先读取现有画布')
            if body.get('object_id',object_id) != object_id:raise ValueError('画布对象与命令目标不一致')
            return canvas.save({**body,'object_id':object_id})
        raise ValueError('不支持的画布动作')
    website_object = isinstance(object_id, str) and object_id.startswith('customer:website-')
    customer_listing = area == 'objects' and operation == 'list' and kind in ('', 'customer')
    status = None
    if (website_object and operation in ('get', 'save')) or customer_listing:
        status = business.refresh_website(wait=True)
        if website_object and status.get('state') != 'ready':
            raise ValueError('网站询盘原来源暂不可读，请稍后重试；未创建替代客户记录。')
    if area == 'objects' and operation == 'list':
        result = {'objects': business.list_objects(kind=kind, q=query)}
        if status is not None:
            result['website_status'] = business.website_status()
        return result
    if area == 'objects' and operation == 'get':
        return business.get_object(object_id)
    if area == 'artifacts' and operation == 'list':
        return {'artifacts': business.list_artifacts(object_id=object_id)}
    if area == 'artifacts' and operation == 'save':
        return business.save_artifact(object_id, title, content, artifact_id=artifact_id)
    raise ValueError('不支持的业务动作')


def main(argv=None):
    # Stable JSON/Markdown encoding for desktop-agent pipes on Windows.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--state', type=Path)
    areas = parser.add_subparsers(dest='area', required=True)
    capabilities = areas.add_parser('capabilities').add_subparsers(dest='operation', required=True)
    capabilities.add_parser('list').add_argument('--query', default='')
    douyin=areas.add_parser('douyin').add_subparsers(dest='operation', required=True)
    for operation in ('check','snapshot'):
        douyin.add_parser(operation).add_argument('--shop',choices=('brand','legacy'),required=True)
    live=douyin.add_parser('live');live.add_argument('--shop',choices=('brand','legacy'),required=True);live.add_argument('--page',type=int,default=1);live.add_argument('--page-size',type=int,default=100)
    objects = areas.add_parser('objects').add_subparsers(dest='operation', required=True)
    listing = objects.add_parser('list')
    listing.add_argument('--kind', default='')
    listing.add_argument('--query', default='')
    objects.add_parser('get').add_argument('object_id')
    artifacts = areas.add_parser('artifacts').add_subparsers(dest='operation', required=True)
    artifacts.add_parser('list').add_argument('--object-id')
    save = artifacts.add_parser('save')
    save.add_argument('object_id')
    save.add_argument('--title', required=True)
    save.add_argument('--content-file', type=Path, help='省略时从stdin读取Markdown正文')
    save.add_argument('--artifact-id', help='明确更新同一份既有成果')
    materials = areas.add_parser('materials').add_subparsers(dest='operation', required=True)
    materials.add_parser('list').add_argument('object_id')
    material_read=materials.add_parser('read');material_read.add_argument('object_id');material_read.add_argument('material_id');material_read.add_argument('--start',type=int,default=0)
    canvas = areas.add_parser('canvas').add_subparsers(dest='operation', required=True)
    canvas.add_parser('get').add_argument('object_id')
    canvas_save = canvas.add_parser('save')
    canvas_save.add_argument('object_id')
    canvas_save.add_argument('--content-file', type=Path, help='省略时stdin读取含version/nodes/edges的JSON')
    product_creation = areas.add_parser('product-creation').add_subparsers(dest='operation', required=True)
    product_creation.add_parser('options').add_argument('object_id')
    add_media = product_creation.add_parser('add')
    add_media.add_argument('object_id')
    add_media.add_argument('--project-id', required=True)
    add_media.add_argument('--media-path', required=True)
    add_media.add_argument('--version', required=True, help='先读取画布；空版本用 --version ""')
    args = parser.parse_args(argv)
    app = None
    try:
        content = None
        if args.area in ('artifacts','canvas') and args.operation == 'save':
            content = args.content_file.read_text(encoding='utf-8-sig') if args.content_file else sys.stdin.read()
        app = open_business(args.root, args.state)
        result = invoke(app.business, args.area, args.operation, object_id=getattr(args, 'object_id', None),
                        kind=getattr(args, 'kind', ''), query=getattr(args, 'query', ''),
                        title=getattr(args, 'title', None), content=content,
                        artifact_id=getattr(args, 'artifact_id', None),material_id=getattr(args,'material_id',None),start=getattr(args,'start',0),shop=getattr(args,'shop',None),page=getattr(args,'page',1),page_size=getattr(args,'page_size',100),project_id=getattr(args,'project_id',None),media_path=getattr(args,'media_path',None),version=getattr(args,'version',None))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except ValueError as exc:
        from agent_jobs import clean
        print(json.dumps({'error': clean(str(exc))}, ensure_ascii=False))
        return 1
    except (OSError, sqlite3.Error):
        print(json.dumps({'error': '本地资料文件或数据库无法访问，请核对路径和工作台状态。'}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({'error': '业务服务内部错误，未确认保存成功，请核对原对象成果。'}, ensure_ascii=False))
        return 1
    finally:
        if app is not None:
            app.db.close()


if __name__ == '__main__':
    raise SystemExit(main())
