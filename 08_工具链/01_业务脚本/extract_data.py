import json

output_file = r'C:\Users\spq\.accio\accounts\1760686603\agents\DID-D464A3-34D464A3U1779082-4596-E2100A\agent-core\tool-results\CID-45686603U1785673-1F9B91-9948-6F76A5\bash_call_00_gNkMB086kvH8oHRsoJaS4741.txt'
with open(output_file, 'r', encoding='utf-8') as f:
    raw = f.read()

data = json.loads(raw)

for pid, value in data.items():
    try:
        inner = json.loads(value)
        inner_data = json.loads(inner['data'])
        basic = inner_data.get('basicInfo', {})
        title = basic.get('productTitle', 'N/A')
        keywords = basic.get('productKeywords', '')
        images = basic.get('images', [])
        img_count = len(images)
        attrs = basic.get('attr', [])
        toe = ''
        upper = ''
        features = []
        model = ''
        for a in attrs:
            if a['attrName'] == 'Toe Style':
                toe = a['attrValue']
            if a['attrName'] == 'Upper Material':
                upper = a['attrValue']
            if a['attrName'] == 'Feature':
                features.append(a['attrValue'])
            if a['attrName'] == 'Model Number':
                model = a['attrValue']
        feats = ','.join(features)
        print(f'{pid}|{model}|{title}|{keywords}|{toe}|{upper}|{img_count}|{feats}')
    except Exception as e:
        print(f'{pid}|ERROR|{str(e)[:100]}')
