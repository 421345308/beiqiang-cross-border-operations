"""生成本地申请准备包。不会注册、上传、签章或提交任何外部申请。"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import platform
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Polygon
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from application_content import DESIGN, GUIDE, MANUAL, TEMPLATE, SOFTWARE_NAME, SOFTWARE_VERSION

BASE = Path(__file__).resolve().parent
OUT = BASE / '申请材料'
OWNER_PATH = BASE / '.local/申请主体/主体信息.json'
CORE = ['app.py', 'index.html', 'style.css', 'client.js', 'login.html', 'login.js', 'doudian_adapter.py']
STAMP = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
FONT = 'Song'
WIDTH, HEIGHT = A4


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def p(text, size=10.5, leading=17.5, **kw):
    style = ParagraphStyle('body', fontName=FONT, fontSize=size, leading=leading,
                           wordWrap='CJK', textColor=colors.black, spaceAfter=8, **kw)
    return Paragraph(html.escape(text).replace('\n', '<br/>'), style)


def heading(text):
    return p(text, size=14, leading=22, spaceBefore=12, keepWithNext=True)


def grid(rows, widths=(130, 380)):
    table = Table([[p(str(x), size=9.5, leading=15) for x in row] for row in rows],
                  colWidths=widths, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E9ECEF')),
        ('GRID', (0, 0), (-1, -1), .5, colors.HexColor('#D9D9D9')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return table


def header_footer(c, doc):
    c.setFont(FONT, 9)
    c.setFillColor(colors.black)
    c.drawString(42, HEIGHT - 28, f'{SOFTWARE_NAME} {SOFTWARE_VERSION}')
    c.drawRightString(WIDTH - 42, HEIGHT - 28, str(doc.page))
    c.setFont(FONT, 8)
    c.drawString(42, 26, '本地申请准备材料  正式提交前核实主体与签章')


def architecture():
    d = Drawing(505, 172)
    boxes = [(0, 102, '本机浏览器', '表单与结果展示'), (180, 102, 'Python业务服务', '校验、事务与日志'),
             (360, 102, 'SQLite业务数据库', 'SKU、流水与订单'),
             (180, 24, '产品身份台账', '只读引用型号')]
    for x, y, a, b in boxes:
        d.add(Rect(x, y, 145, 54, fillColor=colors.white, strokeColor=colors.black))
        d.add(String(x + 72.5, y + 34, a, textAnchor='middle', fontName=FONT, fontSize=10))
        d.add(String(x + 72.5, y + 15, b, textAnchor='middle', fontName=FONT, fontSize=9))
    for x1, y1, x2, y2 in [(145, 129, 180, 129), (325, 129, 360, 129), (252, 78, 252, 102)]:
        d.add(Line(x1, y1, x2, y2, strokeColor=colors.black))
        if y1 == y2:
            d.add(Polygon([x2, y2, x2-6, y2+3, x2-6, y2-3], fillColor=colors.black))
        else:
            d.add(Polygon([x2, y2, x2-3, y2-6, x2+3, y2-6], fillColor=colors.black))
    d.add(String(0, 7, '离线抖店适配模块独立验证；当前没有平台网络连接。', fontName=FONT, fontSize=9))
    return d


def pdf_document(filename, title, chapters, owner, *, pictures=False, paginate=False, extra=None):
    story = [p(title, size=20, leading=29, spaceBefore=5),
             p(f'软件名称 {SOFTWARE_NAME}    版本 {SOFTWARE_VERSION}', size=11),
             p('拟申请主体 ' + owner['company_name'], size=10),
             p('本文件按实际代码编写。正式登记表及平台表单由相应系统生成，尚未注册、签章或提交。', size=9.5)]
    if extra:
        story.extend(extra)
    if paginate:
        story.extend([heading('文档目录'),
                      grid([['章节', '起始页']] + [[section[0], str(i + 2)] for i, section in enumerate(chapters)],
                           widths=(420, 85)),
                      heading('适用范围'),
                      p('本手册对应V1.0本机单操作员软件。截图为独立演示库，正式库首次使用须由负责人设置密码并核对实际业务资料。'),
                      p('材料整理日期：' + STAMP[:10] + '。这不是软件开发完成日期或登记受理日期。', size=9),
                      PageBreak()])
    for i, section in enumerate(chapters):
        label, texts = section[:2]
        if paginate and i:
            story.append(PageBreak())
        section_story = [heading(label if label[0].isdigit() else f'{i + 1}  {label}')]
        section_story.extend(p(t) for t in texts)
        if label.startswith('4.1'):
            section_story.extend([Spacer(1, 8), architecture()])
        if pictures and len(section) > 2:
            file = OUT / section[2]
            if not file.exists():
                raise FileNotFoundError(f'缺少实际截图：{file.name}')
            image = Image(str(file))
            scale = min(500 / image.imageWidth, 330 / image.imageHeight)
            image.drawWidth, image.drawHeight = image.imageWidth * scale, image.imageHeight * scale
            section_story.extend([Spacer(1, 8), image, p('图示为实际运行的演示库界面，数据不代表真实商品或交易。', size=9)])
        if (pictures and len(section) > 2) or label.startswith('4.1'):
            story.append(KeepTogether(section_story))
        else:
            story.extend(section_story)
    SimpleDocTemplate(str(OUT / filename), pagesize=A4, leftMargin=42, rightMargin=42,
                      topMargin=48, bottomMargin=44, title=title, author=owner['company_name']).build(
                          story, onFirstPage=header_footer, onLaterPages=header_footer)
    return story


def fit_source_line(text, width, size=8.5):
    current = ''
    for char in text.expandtabs(4):
        if current and pdfmetrics.stringWidth(current + char, FONT, size) > width:
            yield current
            current = char
        else:
            current += char
    yield current


def source_pdf(owner):
    rows = []
    for name in CORE:
        for i, line in enumerate((BASE / name).read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            for part_index, part in enumerate(fit_source_line(line, WIDTH - 104)):
                rows.append((name, str(i) if part_index == 0 else '续', part))
    output = OUT / '02_源程序鉴别材料.pdf'
    c = canvas.Canvas(str(output), pagesize=A4)
    c.setTitle(f'{SOFTWARE_NAME} {SOFTWARE_VERSION} 源程序鉴别材料')
    c.setAuthor(owner['company_name'])
    pages = []
    for offset in range(0, len(rows), 50):
        chunk = rows[offset:offset + 50]
        page = offset // 50 + 1
        c.setFont(FONT, 9)
        c.drawString(35, HEIGHT - 26, f'{SOFTWARE_NAME} {SOFTWARE_VERSION}')
        c.drawRightString(WIDTH - 35, HEIGHT - 26, str(page))
        c.setFont(FONT, 7.5)
        c.drawString(35, HEIGHT - 44, '文件：' + ' / '.join(dict.fromkeys(x[0] for x in chunk)))
        y = HEIGHT - 67
        for _, number, text in chunk:
            c.setFont(FONT, 7)
            c.drawRightString(61, y, number)
            c.setFont(FONT, 8.5)
            c.drawString(69, y, text)
            y -= 13.4
        c.setFont(FONT, 7)
        c.drawString(35, 28, f'拟申请主体：{owner["company_name"]}  原始文件与SHA256校验另附')
        pages.append({'page': page, 'body_lines': len(chunk), 'source_files': sorted({x[0] for x in chunk})})
        c.showPage()
    c.save()
    if len(pages) >= 60:
        raise ValueError('源码超过60页，须按当前交存要求重新选择连续前后部分')
    return pages


def editable_html(filename, title, chapters):
    body = [f'<h1>{html.escape(title)}</h1>', f'<p>{SOFTWARE_NAME} {SOFTWARE_VERSION}</p>']
    for section in chapters:
        body.append('<h2>' + html.escape(section[0]) + '</h2>')
        body.extend('<p>' + html.escape(text) + '</p>' for text in section[1])
        if len(section) > 2 and (OUT / section[2]).exists():
            data = base64.b64encode((OUT / section[2]).read_bytes()).decode('ascii')
            body.append(f'<img alt="实际演示界面" src="data:image/jpeg;base64,{data}">')
    document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>' + html.escape(title) + '</title><style>body{font:16px/1.8 "Microsoft YaHei",sans-serif;color:#111;max-width:900px;margin:40px auto;padding:0 24px}h1{font-size:28px}h2{font-size:21px;margin-top:30px}img{max-width:100%}@media print{body{margin:0;padding:0}h2{break-after:avoid}img{break-inside:avoid}}</style><body contenteditable="true">' + ''.join(body) + '</body></html>'
    (OUT / filename).write_text(document, encoding='utf-8')


def official_requirements(owner):
    sources = [
        ('抖店商家后台系统类目管理规范', 'https://op.jinritemai.com/docs/guide-docs/1608/7924', '页面更新2025-12-04、2025-12-15生效；企业、官方旗舰店、电商OMS/ERP软著、真实研发支出。'),
        ('抖店自用型应用入驻指南', 'https://op.jinritemai.com/docs/guide-docs/140/583', '账号认证、类目资质、应用、店铺授权和令牌是不同步骤。'),
        ('官方功能说明模板', 'https://bytedance.larkoffice.com/docx/Hz0Hd5xORoX9BIx15UDc53Odn8g', '2026-10-15实际读取：1概述、2接口用途、3功能、4架构/截图/软著/对接源码。'),
        ('国家版权局计算机软件著作权登记办法', 'https://www.ncac.gov.cn/xxfb/flfg/bmgz/202410/t20241015_869486.html', '申请表、程序和文档、主体及相关证明。通常前后连续各30页；不足60页提交全部。程序每页不少于50行、文档不少于30行，特定情形及图示例外按官方要求。'),
        ('北京政务服务登记材料要求', 'https://banshi.beijing.gov.cn/pubtask/task/1/110000000000/3e283672-76be-4c8c-98e8-0bebe9bd06bf.html?locationCode=110000000000&serverType=1002', '用于核对A4纵向、软件名版本一致、页码及系统生成正式表；不把地方初审时限当全国发证承诺。'),
        ('财政部财税〔2017〕20号', 'https://www.mof.gov.cn/zcsjtsgb/gfxwj/201703/t20170315_3583497.htm', '2017-04-01起停征软件著作权登记费。代理和云资源是独立商业费用。'),
        ('中国版权保护中心', 'https://www.ccopyright.com.cn/', '官方办理机构；本轮访问受限，未取得登录后当前完整表单。'),
        ('版权登记系统', 'https://register.ccopyright.com.cn/', '2026-10-15Chrome正常访问显示403地区访问限制；没有开始实名或提交。'),
        ('抖店API调用指南', 'https://op.jinritemai.com/docs/guide-docs/10/23', '核对官方网关、公共参数、POST JSON体及HMAC-SHA256。新版语言示例与老指南存在时间戳及特殊字符说明差异，真实联调时以对应接口当前SDK和调试结果为准。'),
        ('抖店较新语言调用示例', 'https://op.jinritemai.com/docs/guide-docs/10/812', '官方语言示例用于交叉核对签名拼接；本系统没有复用整套第三方SDK或实际发送请求。'),
    ]
    sections = [
        ('实际店铺与主体', [f'已核店铺{owner["shop_name"]}，shop_id {owner["shop_id"]}，类型为{owner["shop_type"]}。店铺、开发者认证公司与所给执照名称和信用代码一致；资质列表暂无数据。',
                        '开发者认证通过只说明账号层认证，不代表商家后台系统类目已开放。当前店铺类型不符合现行公开规范的官方旗舰店条件，未取得例外证明。']),
        ('可选后续路径', ['先请平台针对真实企业店明确可申请类目或例外依据；未获准入确认前，不建议为申请而购买云资源或代办证书。该事项需要用户在正常工单或客服渠道处理，本轮未发送外部咨询。',
                     '店铺后台的升级页可见官方旗舰店路径，但页面要求知名或成熟品牌及自有/一级独占授权品牌；有入口不等于本店达标。本轮仅查看，未点击开始变更。',
                     '如果目前目标只是快速上品，可另行评估抖店服务市场的合规上货工具或ERP授权方案；这不等于获得自己的AppKey，也不能用第三方聚合接口替代自研资质。未替你购买或授权任何应用。']),
        ('软著准备与提交顺序', ['本包已备实际代码、完整程序鉴别材料、图文用户手册、设计说明及填报信息稿。软件名版本统一为电商商品与订单管理系统 V1.0。代码少于60页，提交全部，不重复凑页。',
                        '负责人确认申请主体、真实开发关系、权利取得及范围、完成日期和发表状态。源码按授权公开同步后应据实际记录核对发表状态，不能默认未发表。',
                        '由负责人完成版权登记账号机构实名及经办人验证。用正式系统生成申请表，真实签字盖章，按页面上传并保存受理/补正/证书。缺失数据均留空。',
                        '登记办法规定自受理起60日内审查，补正通常须按通知在30日内办理；前期准备时间另计，不能保证某天拿证。']),
        ('官方模板逐栏状态', ['1.1名称与术语、1.2业务场景、1.3技术栈及本地资源状态已写；接口人与手机号、真实团队规模待提供。',
                        '2.1接口及调用用途、3.1主要功能、4.1实际架构图、4.2主界面、4.3子功能全景截图、4.5离线适配源码截图已写。',
                        '4.2已补实际本机登录页，正式库首次密码由负责人设置。4.4证书待真实取得；离线源码不能代替真实联调。']),
        ('成本与抖店云', ['版权登记费停征，当前开发和材料准备未购买代办、云服务器或付费调用。真实研发支出证明仍缺，不能用代码行数或模拟账单代替。',
                       '日后可以通过SSH管理抖店云服务器并让程序在云服务器上执行调用；需要真正拥有实例、应用和店铺授权，并按平台云端识别和部署要求配置。仅在本机打开SSH、使用SDK或换请求域名，不等于已经在抖店云调用。当前系统实际运行在本机。']),
    ]
    editable_html('官方要求核对.html', '官方要求、准入差异与办理路径（2026-10-15核对）', sections)
    path = OUT / '官方要求核对.html'
    doc = path.read_text(encoding='utf-8')
    citations = '<h2>官方来源与核对范围</h2><ul>' + ''.join(
        '<li><a href="' + html.escape(url) + '">' + html.escape(title) + '</a>：' + html.escape(note) + '</li>'
        for title, url, note in sources) + '</ul>'
    path.write_text(doc.replace('</body>', citations + '</body>'), encoding='utf-8')
    write_json(OUT / '官方来源.json', {'checked_on': '2026-10-15', 'sources': sources})


def main():
    OUT.mkdir(exist_ok=True)
    owner = json.loads(OWNER_PATH.read_text(encoding='utf-8'))
    official_requirements(owner)
    pdfmetrics.registerFont(TTFont(FONT, 'C:/Windows/Fonts/simsun.ttc', subfontIndex=0))
    hashes = {name: digest(BASE / name) for name in CORE}
    files = [{'name': name, 'sha256': hashes[name],
              'physical_lines': len((BASE / name).read_text(encoding='utf-8').splitlines()),
              'nonblank_lines': sum(bool(x.strip()) for x in (BASE / name).read_text(encoding='utf-8').splitlines())}
             for name in CORE]
    environment = {'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
                   'os': platform.system() + ' ' + platform.release(), 'architecture': platform.machine()}
    fields = {
        '材料状态': '填报准备稿，非官方申请表，尚未提交',
        '软件全称': SOFTWARE_NAME, '版本号': SOFTWARE_VERSION,
        '著作权人候选': owner['company_name'], '统一社会信用代码': owner['credit_code'],
        '住所': owner['registered_address'], '成立日期': owner['established_on'],
        '开发方式': None, '权利取得方式': None, '权利范围': None,
        '开发完成日期': None, '首次发表状态及日期': None,
        '联系人': owner['contact_name'], '联系电话': owner['contact_phone'], '邮箱': owner['contact_email'],
        '真实开发记录': '工作台于2026-10-14开始本轮系统开发；2026-10-15继续测试与材料准备。主体与权属尚待负责人确认。',
        '开发目的': '统一管理电商商品SKU、价格、库存依据与本地订单，减少重复录入和数量错误。',
        '主要功能': '型号引用、SKU登记、CSV导入导出、库存流水、本地订单预留、取消返还、发货凭证和操作日志。',
        '技术特点': 'Python标准库与SQLite事务；整数分价格快照；库存不足整单回滚；本地来源与CSRF校验；演示正式数据库隔离。',
        '编程语言': ['Python', 'JavaScript', 'HTML', 'CSS'], '材料生成环境': environment,
        '应用测试环境': 'Windows；Python 3.11.7；SQLite 3.41.2；Chrome浏览器。详细结果见验收记录。',
        '软件分类候选': '应用软件；批发和零售业商品、库存及订单管理，以正式表单可选项为准。',
        '开发工具及环境': 'Windows文件工作区、AI辅助编码、Python解释器与unittest、本地Chrome浏览器验收；没有套用外部完整ERP源码。',
        '运行支持软件': 'Python 3.11及以上，支持现代JavaScript的浏览器；SQLite随Python标准库提供，无外部数据库服务。',
        '硬件要求': '有可写本地磁盘的Windows计算机；以实际部署机的处理器、内存和磁盘信息补填，未做最低硬件性能认证。',
        '源程序量_非空物理行': sum(x['nonblank_lines'] for x in files),
        '源程序量_物理总行': sum(x['physical_lines'] for x in files),
        '源码计数与校验': files,
        '发表状态提醒': '源码若按工作台授权公开同步，需据实际公开记录核实发表状态，不能直接填写未发表。',
        '平台接入状态': '抖店未连接，无AppKey、授权或线上发品回执。',
    }
    write_json(OUT / '01_软著填报信息稿.json', fields)
    write_json(OUT / '09_抖店实际表单填报稿.json', {
        '状态': '按2026-10-15登录后的实际表单整理，仅本地准备，未填入平台或上传',
        '应用类型': '电商后台应用', '一级类目': '电商商家自研', '二级类目': '商家后台系统',
        '系统功能说明书': '05_抖店系统功能说明书.pdf',
        '商家研发系统支出证明': None, '软件著作权证书': None,
        '著作权人': None, '登记号': None, '候选著作权人': owner['company_name'],
        '绑定店铺shop_id': owner['shop_id'],
        '备注说明候选_200字内': '开发者、店铺及所给营业执照企业名称和信用代码一致。当前店铺为企业店，须先确认自研类目准入路径，未将店铺类型填作官方旗舰店。',
        '对接业务方向_200字内': '其他：用于本店商品、SKU、库存及订单管理，拟对接商品类目属性、商品创建编辑及详情回读。当前本机系统与离线协议模块已开发，真实接口调用待资质和店铺授权后联调。',
        '登录界面和功能界面截图_最多5份建议': ['登录界面.jpg','商品界面.jpg','库存界面.jpg','订单界面.jpg','操作记录界面.jpg'],
        '原页面要求': {'支出证明': '含公司主体信息的真实证明，最多5份', '软著': '电商管理系统、国家版权登记、有效可查询，最多5份',
                       '著作权人和登记号及shop_id': '各30字以内', '备注和业务方向': '各200字以内', '截图': '登录及主要功能全景，最多5份'},
        '主体一致性': '开发者账号和店铺主体已从登录页面核对一致，证书著作权人仍待真实登记',
        '准入未解决': '企业店不满足公开规范的官方旗舰店条件，没有豁免或通过承诺',
    })
    pages = source_pdf(owner)
    pdf_document('03_用户操作手册.pdf', '用户操作手册', MANUAL, owner, pictures=True, paginate=True)
    pdf_document('04_软件设计说明书.pdf', '软件设计说明书', DESIGN, owner)
    shop_extra = [p(f'已核店铺：{owner["shop_name"]}；shop_id：{owner["shop_id"]}；店铺类型：{owner["shop_type"]}。'),
                  p('重要准入状态：当前企业店不满足公开自研类目仅面向官方旗舰店的条件，尚无平台豁免证明。', size=10),
                  p('依据：官方模板 https://bytedance.larkoffice.com/docx/Hz0Hd5xORoX9BIx15UDc53Odn8g （2026-10-15实际读取）。以下按原栏目编写准备稿，非平台已签章表单。', size=9)]
    pdf_document('05_抖店系统功能说明书.pdf', '商家自研后台系统功能说明书', TEMPLATE, owner,
                 pictures=True, extra=shop_extra)
    pdf_document('08_登记及提交操作指引.pdf', '软著登记及抖店资质提交指引', GUIDE, owner)
    missing = [
        ('机构与经办人实名认证', '登记账号、经办人姓名和有效身份材料、手机及邮箱验证；以实际页面为准。'),
        ('权属与开发方式确认', '由负责人确认实际开发关系、权利取得方式、权利范围、完成日期和发表状态。'),
        ('正式申请表及签章', '由登记系统生成申请表；按页面要求使用真实签字或公章。'),
        ('研发联系人与团队', '开发者与店铺及所给执照主体已核一致；仍需技术接口人及手机号、真实研发团队规模。'),
        ('研发支出证明', '包含公司主体的真实账单或平台认可的其他凭证，当前尚未提供。'),
        ('软著证书与登记号', '登记审查通过后取得；本包不含虚构证书或号码。'),
        ('抖店店铺类型准入', '实际为企业店；现行公开规范仅面向官方旗舰店。需平台确认可行路径或真实满足升级条件，不能视为已豁免。'),
        ('真实平台接入', '本机登录和离线协议模块已实现；真实接口授权联调及正式平台回执尚未完成。当前是本机单操作员工具。'),
    ]
    identity = [
        ('营业执照转录核对', [f'拟申请主体：{owner["company_name"]}。统一社会信用代码：{owner["credit_code"]}。',
                            f'类型：{owner["company_type"]}。成立日期：{owner["established_on"]}。法定代表人：{owner["legal_representative"]}。',
                            f'登记住所：{owner["registered_address"]}。',
                            f'已登录店铺：{owner["shop_name"]}；shop_id：{owner["shop_id"]}；类型：{owner["shop_type"]}；主体：{owner["shop_company"]}；执照有效期：{owner["license_term"]}。',
                            '营业执照来自用户原图，店铺字段来自登录后的主体信息页，两者名称及信用代码一致；正式申报前逐字核对原件，未作工商存续或关联关系认证。']),
        ('企业原件与签章', ['营业执照原图已留在本地申请主体目录；根据当时登记要求准备清晰主体证明及真实盖章件。',
                         '若机构认证要求管理员身份证明、授权书、邮箱或手机验证，应由负责人提供与完成；不借用他人身份，不自动选择法定代表人作为经办人。',
                         '盖章签名栏应在真实确认后完成。本包没有生成公章图片、签名字样、官方编号或虚构研发支出。']),
        ('尚缺项目', [label + '：' + detail for label, detail in missing]),
    ]
    pdf_document('06_企业认证与签章材料清单.pdf', '企业认证与签章材料清单', identity, owner)
    development = [
        ('已发生的开发事实', ['负责人在本轮对话中要求从零准备实际系统与自研申请材料，程序由工作台AI辅助编写，并进行本地测试。',
                          '实际运行代码包括app.py、index.html、style.css、client.js、login.html、login.js及doudian_adapter.py；功能为本机登录、商品SKU、库存流水、本地订单及离线接口准备。未把GitHub旧SDK整体复制为申请软件。',
                          '公司主体由负责人提供营业执照后确定为候选；不把工作台所属公司的名称直接当作本次申请人，也不虚构两家公司关联关系。']),
        ('权属确认内容', ['请确认本项目由哪一主体组织开发、承担开发责任，是否存在职务、委托或合作开发关系，以及各参与方的实际约定。',
                       '开发方式、权利取得方式和权利范围按真实关系填写。不能仅凭生成代码自动断言已经满足公司独立开发或平台自研口径。',
                       '如需提供项目任务书、职务开发或委托开发证明，应由真实当事人确认并签章。本文件是核对稿，不充当已经成立的劳动、委托或转让合同。']),
        ('负责人核对栏', ['软件名称与版本：电商商品与订单管理系统 V1.0。',
                       '申请主体确认：____________________。开发方式确认：____________________。',
                       '参与人员及关系：________________________________________________。',
                       '权利取得与范围：________________________________________________。',
                       '开发完成日期：________________。首次发表状态及日期：________________。',
                       '负责人签字或企业盖章：________________。真实确认日期：________________。']),
    ]
    pdf_document('07_开发事实与权属确认稿.pdf', '开发事实与权属确认稿', development, owner)
    for name, title, content in [('用户操作手册.html', '用户操作手册', MANUAL),
                                  ('软件设计说明书.html', '软件设计说明书', DESIGN),
                                  ('抖店系统功能说明书.html', '商家自研后台系统功能说明书', TEMPLATE)]:
        editable_html(name, title, content)
    full_source = '\n\n'.join(f'# ===== {name} =====\n' + (BASE / name).read_text(encoding='utf-8') for name in CORE)
    (OUT / '源程序全集.txt').write_text(full_source, encoding='utf-8')
    write_json(OUT / '源码校验清单.json', {'software': SOFTWARE_NAME, 'version': SOFTWARE_VERSION,
                                        'generated_at': STAMP, 'files': files, 'source_pdf_pages': pages})
    write_json(OUT / '材料状态.json', {'generated_at': STAMP, 'ready_for_official_submission': False,
                                    'system_development': '实现与后端验证完成，界面截图状态见验收记录',
                                    'missing': [{'item': x, 'detail': y} for x, y in missing]})
    links = [(p.name, p.name) for p in sorted(OUT.glob('*.pdf'))]
    review = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>自研资质准备验收入口</title>
<style>body{{font:16px/1.8 'Microsoft YaHei',sans-serif;background:#f4f6f8;color:#15263c;max-width:1000px;margin:40px auto;padding:24px}}section{{background:white;padding:26px;margin-bottom:18px;border-radius:10px}}h1{{font-size:28px}}a{{color:#195b85}}li{{margin:9px 0}}.status{{color:#946520}}</style>
<h1>自研资质准备验收入口</h1><p>软件 {SOFTWARE_NAME} {SOFTWARE_VERSION} · 拟申请主体 {html.escape(owner['company_name'])}</p>
<section><h2>先看系统</h2><p><a href="http://127.0.0.1:8766/">打开本地演示系统</a>。账号admin，演示密码Demo-Only-8766。DEMO资料全部为测试数据；尚未连接抖店。</p><p>17项后端与离线协议检查，最终结果见验收记录；界面验证登录与退出、商品、库存、预留、取消、CSV导入、发货凭证和日志。</p><p><a href="09_抖店实际表单填报稿.json">抖店实际表单填报稿及5份截图建议</a> · <a href="源程序与验证.zip">源码与验证包</a></p></section>
<section><h2>申请准备材料</h2><ul>''' + ''.join(f'<li><a href="{html.escape(file)}">{html.escape(label)}</a></li>' for file, label in links) + '''</ul><p><a href="01_软著填报信息稿.json">软著填报信息稿</a> · <a href="源码校验清单.json">源程序校验</a> · <a href="源程序全集.txt">完整源程序文本</a></p><p><a href="用户操作手册.html">可编辑手册</a> · <a href="软件设计说明书.html">可编辑设计说明</a> · <a href="抖店系统功能说明书.html">可编辑抖店说明</a></p></section>
<section><h2>官方要求与路径</h2><p><a href="官方要求核对.html">查看官方依据、实际店铺核对与后续步骤</a> · <a href="验收记录.json">测试及文件验收记录</a> · <a href="公开同步记录.json">代码公开同步记录（供核对发表状态）</a></p></section>
<section><h2>正式提交前仍需完成</h2><ul>''' + ''.join(f'<li><b>{html.escape(x)}</b>：{html.escape(y)}</li>' for x, y in missing) + '''</ul><p class="status">材料已经准备不等于已经登记或获得抖店资质。本包没有签章、证书、官方受理号或平台发布回执。</p></section></html>'''
    (OUT / '负责人验收.html').write_text(review, encoding='utf-8')
    print(json.dumps({'pdf_count': len(links), 'source_pages': len(pages), 'source_nonblank_lines': sum(x['nonblank_lines'] for x in files),
                      'submission_ready': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
