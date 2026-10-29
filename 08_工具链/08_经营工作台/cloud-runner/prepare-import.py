"""Prepare only the four explicitly allowed private snapshots for owner-reviewed import."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parent
ROOT = APP.parents[1]
OUTPUT = APP / '.local' / 'cloud-import.json'
SOURCES = (
    '00_总控台/当前状态.md',
    '00_总控台/全渠道增长总控.md',
    '04_客户开发/获客研究与送达率治理.md',
    '02_Alibaba运营/02_单品优化记录/BQ系列持续优化_2026-09-14/主推采购承接.md',
)
TASK_FIELDS = ('title', 'status', 'owner', 'result', 'next', 'dependency', 'source')

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def prepare():
    server = load(APP / 'server.py', 'workbench_import_reader')
    parser = load(ROOT / '08_工具链/06_工作区维护/build_b2b_workbench.py', 'workbench_import_sources')
    declared = [p.relative_to(parser.ROOT).as_posix() for p in parser.SOURCES]
    if set(declared) != set(SOURCES) - {'00_总控台/全渠道增长总控.md'}:
        raise ValueError('Task generator sources changed; review the explicit import boundary first')
    # Use the existing read methods without constructing SQLite/state or loading run history.
    reader = object.__new__(server.Workbench)
    reader.root, reader.parser, reader.sources = ROOT, parser, declared
    reader.token = ''
    reader.runs = lambda: []
    bootstrap = reader.bootstrap()
    tasks = [{key: task[key] for key in TASK_FIELDS} for task in bootstrap['tasks']]
    if len(tasks) > 30 or any(task['source'] not in SOURCES for task in tasks):
        raise ValueError('Task cards exceed the cloud import scope')
    documents = []
    for source in SOURCES:
        content = server.normalized(reader.path(source).read_text(encoding='utf-8-sig'))
        if len(content.encode('utf-16-le')) // 2 > 100000:
            raise ValueError('A document exceeds the backend character limit')
        documents.append({'path': source, 'content': content})
    package = {'documents': documents, 'tasks': tasks, 'goals': bootstrap['goals']}
    # UI accepts these three keys only; action/import is added after owner confirmation.
    data = json.dumps(package, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(data) > 340000:
        raise ValueError('Snapshot package exceeds the UI 340000-byte limit; nothing exported')
    return data, len(documents), len(tasks)

def main():
    data, documents, tasks = prepare()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(data)
    print(json.dumps({'documents': documents, 'tasks': tasks, 'bytes': len(data),
                      'ui_limit_bytes': 340000, 'path': str(OUTPUT)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
