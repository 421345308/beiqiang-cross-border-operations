"""One formatter for copy/factory field-stage navigation in existing dossiers."""
from pathlib import Path
import os
from urllib.parse import quote

def annotate(content,selected,dossier_path,root):
 text=content.decode('utf8')if isinstance(content,bytes)else content
 rows=[];product_id=Path(dossier_path).parent.name;parent=Path(dossier_path).parent
 for listing in selected['listings']:
  if listing['product_id']!=product_id:continue
  optimization=listing.get('optimization',{})
  company_bundle=optimization.get('company_bundle')
  stages=[('buyer_copy','商品亮点' if company_bundle else '亮点与FAQ')]
  stages.append(('company_bundle','通用FAQ、公司简介与六张工厂图') if company_bundle else ('factory_gallery','共享工厂图'))
  for key,label in stages:
   stage=listing.get('optimization',{}).get(key)
   if not stage:continue
   rows.append(f"- {listing['id']} · {label}：`{stage.get('state','')}`；公开：`{stage.get('public_status','NOT_CHECKED')}`。{stage.get('next_action','')}")
   paths=list(stage.get('evidence',[]))
   if stage.get('associated_fields_resolution'):paths.append(stage['associated_fields_resolution'])
   for path in dict.fromkeys(paths):
    url=quote(Path(os.path.relpath(root/path,root/parent)).as_posix(),safe='/.:_-');rows.append(f'  - [{Path(path).name}]({url})')
 if rows:text=text.replace('## 其他原始/正式证据','## 本轮字段优化\n\n'+'\n'.join(rows)+'\n\n## 其他原始/正式证据')
 return text.encode('utf8')
