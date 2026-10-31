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
    except Exception:
        app.db.close()
        raise
    return app


def invoke(business, area, operation, *, object_id=None, kind='', query='', title=None, content=None, artifact_id=None):
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
    args = parser.parse_args(argv)
    app = None
    try:
        content = None
        if args.area == 'artifacts' and args.operation == 'save':
            content = args.content_file.read_text(encoding='utf-8-sig') if args.content_file else sys.stdin.read()
        app = open_business(args.root, args.state)
        result = invoke(app.business, args.area, args.operation, object_id=getattr(args, 'object_id', None),
                        kind=getattr(args, 'kind', ''), query=getattr(args, 'query', ''),
                        title=getattr(args, 'title', None), content=content,
                        artifact_id=getattr(args, 'artifact_id', None))
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
