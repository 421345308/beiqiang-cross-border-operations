"""本地验收：运行功能检查、核验材料、生成PDF预览；不上传任何内容。"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pdfplumber
from PIL import Image, ImageDraw
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
OUT = BASE / '申请材料'
QA = BASE / '.local/pdf-qa'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app-python', required=True)
    parser.add_argument('--pdftoppm', required=True)
    parser.add_argument('--reuse-tests', action='store_true', help='仅材料变化时复用已通过且源码校验一致的测试结果')
    args = parser.parse_args()
    tested_files = ['app.py','index.html','style.css','client.js','login.html','login.js',
                    'doudian_adapter.py','test_app.py','test_adapter.py']
    current_hashes = {x: sha(BASE / x) for x in tested_files}
    if args.reuse_tests:
        prior_hashes = json.loads((BASE / '.local/检查源码校验.json').read_text(encoding='utf-8'))
        log = (BASE / '.local/功能检查.txt').read_text(encoding='utf-8')
        if prior_hashes != current_hashes or 'Ran 17 tests' not in log or '\nOK\n' not in log:
            raise RuntimeError('既有测试结果与当前源码不匹配，不可复用')
    else:
        test = subprocess.run([args.app_python, '-X', 'utf8', '-m', 'unittest', '-v', 'test_app', 'test_adapter'],
                              cwd=BASE, capture_output=True, encoding='utf-8')
        (BASE / '.local/功能检查.txt').write_text(test.stdout + test.stderr, encoding='utf-8')
        if test.returncode or 'Ran 17 tests' not in test.stderr:
            raise RuntimeError('功能检查未全部通过，详见本地输出')
        (BASE / '.local/检查源码校验.json').write_text(json.dumps(current_hashes,indent=2), encoding='utf-8')
    manifest = json.loads((OUT / '源码校验清单.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        if sha(BASE / entry['name']) != entry['sha256']:
            raise ValueError('代码已变化，请重新生成材料：' + entry['name'])
    pages_meta = manifest['source_pdf_pages']
    assert len(pages_meta) < 60
    assert all(x['body_lines'] == 50 for x in pages_meta[:-1])
    report = []
    images = []
    for path in sorted(OUT.glob('*.pdf')):
        reader = PdfReader(path)
        assert reader.pages
        issues = []
        text_lines = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                assert abs(page.width - 595.276) < 1 and abs(page.height - 841.89) < 1
                text = page.extract_text() or ''
                assert '电商商品与订单管理系统' in text and 'V1.0' in text
                if any(c['x0'] < 0 or c['x1'] > page.width + .5 or c['top'] < 0 or c['bottom'] > page.height + .5
                       for c in page.chars):
                    issues.append(f'第{i}页字符超页面边界')
                text_lines.append(len(text.splitlines()))
        if issues:
            raise ValueError(path.name + ': ' + '; '.join(issues))
        prefix_dir = QA / path.stem
        prefix_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run([args.pdftoppm, '-r', '110', '-png', str(path), str(prefix_dir / 'page')],
                       check=True, capture_output=True)
        preview_files = sorted(prefix_dir.glob('page-*.png'))
        assert len(preview_files) == len(reader.pages)
        images.extend((path.name, img) for img in preview_files)
        report.append({'file': path.name, 'pages': len(reader.pages), 'a4_portrait': True,
                       'software_name_version_on_every_page': True, 'no_text_outside_page': True,
                       'extracted_text_lines_per_page': text_lines, 'sha256': sha(path), 'bytes': path.stat().st_size})
    for start in range(0, len(images), 6):
        batch = images[start:start+6]
        sheet = Image.new('RGB', (1260, 3 * 914), '#dce1e7')
        draw = ImageDraw.Draw(sheet)
        for j, (name, path) in enumerate(batch):
            im = Image.open(path).convert('RGB')
            im.thumbnail((610, 868))
            x, y = (j % 2) * 630 + 10, (j // 2) * 914 + 34
            sheet.paste(im, (x, y))
            draw.text((x, y-23), f'{images.index((name,path))+1:02d} | {path.parent.name[:2]} | {path.name}', fill='black')
        sheet.save(QA / f'contact-{start//6+1:02d}.jpg', quality=90)
    with zipfile.ZipFile(OUT / '源程序与验证.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in [x['name'] for x in manifest['files']] + ['test_app.py', 'test_adapter.py', 'README.md', '启动演示.ps1', 'SKU导入模板.csv']:
            archive.write(BASE / file, file)
    screenshots = [{'file': path.name, 'sha256': sha(path), 'bytes': path.stat().st_size}
                   for path in sorted(OUT.glob('*.jpg'))]
    value = {'verified_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
             'tests': {'count': 17, 'passed': True, 'python': args.app_python, 'log': '.local/功能检查.txt'},
             'ui': {'environment': 'Chrome；全部操作仅DEMO库；无平台调用',
                    'verified_actions': ['本机登录与退出', 'SKU创建', '库存调整', '订单预留', '取消返还', 'CSV导入且初始库存0',
                                         '发货凭证且不再次扣库存', '可读操作日志', '源码浏览页'], 'screenshots': screenshots},
             'source_manifest_matches_current_files': True, 'pdf': report,
             'tested_source_sha256': current_hashes,
             'visual_review': '待人工逐页复核渲染图；完成后原地更新',
             'official_submission': False, 'platform_api_calls': 0, 'copyright_certificate': False}
    (OUT / '验收记录.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'tests_passed': 17, 'pdfs': len(report), 'pages': len(images),
                      'contact_sheets': (len(images)+5)//6}, ensure_ascii=False))


if __name__ == '__main__':
    main()
