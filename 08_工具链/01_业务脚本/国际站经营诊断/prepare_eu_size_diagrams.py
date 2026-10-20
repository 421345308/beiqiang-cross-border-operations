"""Create native editable SKU diagrams, without synthetic shoe photos or conversions.

Only exact live matches to the known unsupported historical chart are selected.
Output remains unreviewed until every chart and its data have been inspected.
"""
from pathlib import Path
from collections import defaultdict
import json,hashlib,re,sys,os
sys.path.insert(0,str(Path(__file__).parent));import revise_catalog_content as s

def main():
    os.environ['MPLBACKEND']='Agg'
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch,Circle
    plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none'})
    audit=s.load(s.BASE/'历史尺码图来源复核.json');plans={x['family']:x for x in s.load(s.PLAN_FILE)['items']};groups={};raw=s.ROOT/'99_临时区/商品质量全店复核/历史尺码图'
    for match in audit['exact_matches']:
        if match['requires_visual_classification']or match['status']!='approved'or match['display']!='Y':continue
        pid=match['id'];got=s.load(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid/'formal_get.json');p=got['response']['product'];axes={str(a['attribute_id']):{str(v['value_id']):v['system_value_name']for v in a['values']}for a in p['product_sku']['sku_attributes']};matrix=defaultdict(set)
        for row in p['product_sku']['skus']:
            values=json.loads(row['attr2_value']);color=axes['191288010'][str(values['191288010'])];eu=axes['222038415'][str(values['222038415'])];m=re.fullmatch(r'(?:EU\s*|Size\s*)?(\d+(?:\.5)?)',eu);assert m,(pid,eu);matrix[color].add(m.group(1))
        matrix={c:sorted(v,key=float)for c,v in sorted(matrix.items())};sig=hashlib.sha256(json.dumps(matrix,sort_keys=True).encode()).hexdigest()[:8];key=match['family']+'_尺码图_'+sig;group=groups.setdefault(key,{'family':match['family'],'matrix':matrix,'ids':[],'old_by_id':{},'bad_url':match['url'],'source_snapshots':{}});assert group['bad_url']==match['url'];group['ids'].append(pid);group['old_by_id'][pid]=[r['image_url']for r in p['struct_detail']['detail_image']['images']];group['source_snapshots'][pid]={'at':got['observed_at_utc'],'file':s.rel(s.ROOT/'02_Alibaba运营/05_扩品工程/数据/目录对账/当前平台目录/商品'/pid/'formal_get.json'),'sku_count':len(p['product_sku']['skus'])}
    entries=[]
    for key,g in groups.items():
        assert not any((s.BASE/'图库重做'/key).glob('商品/*/update_once.json')),'Existing submission: do not regenerate or overwrite its evidence'
        cp=plans[g['family']];asset=(s.ROOT/cp['source_evidence'][0]).parent/'02_详情页';asset.mkdir(parents=True,exist_ok=True);stem='eu_size_selection_'+key.rsplit('_',1)[1];svg=asset/(stem+'.svg');png=asset/(stem+'.png');matrix=g['matrix'];sizes=sorted({eu for v in matrix.values()for eu in v},key=float);assert len(matrix)<=9 and len(sizes)<=16
        rowh=min(98,620/(len(matrix)+1));height=330+rowh*(len(matrix)+1)+190
        fig=plt.figure(figsize=(10,height/120),dpi=120,facecolor='#f4f7fb');ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,1200);ax.set_ylim(height,0);ax.axis('off');ax.add_patch(FancyBboxPatch((36,36),1128,height-72,boxstyle='round,pad=0,rounding_size=32',facecolor='white',edgecolor='none'))
        ax.text(80,103,'BEIQIANG',fontsize=16,fontweight='bold',color='#0a2548',va='center');ax.plot([80,156],[133,133],lw=4,color='#ff7b16');ax.text(80,204,'EU Size Selection',fontsize=36,fontweight='bold',color='#0a2548',va='center');ax.text(80,255,'Colour and size combinations for this style',fontsize=16,color='#556579',va='center')
        left=80;labelw=260;right=1120;cell=(right-left-labelw)/len(sizes);top=330;rowh=min(98,620/(len(matrix)+1));font_size=12 if len(sizes)>11 else 15
        ax.add_patch(FancyBboxPatch((left,top),right-left,rowh,boxstyle='round,pad=0,rounding_size=12',facecolor='#0a2548',edgecolor='none'));ax.text(left+20,top+rowh/2,'Colour',fontsize=16,fontweight='bold',color='white',va='center')
        for j,eu in enumerate(sizes):ax.text(left+labelw+(j+.5)*cell,top+rowh/2,eu,fontsize=font_size,fontweight='bold',color='white',ha='center',va='center')
        for i,(color,available)in enumerate(matrix.items()):
            y=top+(i+1)*rowh;ax.add_patch(FancyBboxPatch((left,y+4),right-left,rowh-8,boxstyle='round,pad=0,rounding_size=10',facecolor='#f0f5fa'if i%2==0 else'#fafbfd',edgecolor='none'));label=color.replace('Size ','');ax.text(left+20,y+rowh/2,label,fontsize=11 if len(label)>24 else 14,color='#182c46',va='center')
            for j,eu in enumerate(sizes):
                if eu in available:ax.add_patch(Circle((left+labelw+(j+.5)*cell,y+rowh/2),6,facecolor='#ff7b16',edgecolor='none'))
                else:ax.plot([left+labelw+(j+.5)*cell-5,left+labelw+(j+.5)*cell+5],[y+rowh/2]*2,color='#bac6d3',lw=1.5)
        bottom=top+(len(matrix)+1)*rowh;ax.add_patch(Circle((92,bottom+70),6,facecolor='#ff7b16'));ax.text(116,bottom+70,'Listed colour / EU size combination',fontsize=15,color='#253d59',va='center');ax.text(80,bottom+125,'Choose your colour and EU size when placing an enquiry.',fontsize=14,color='#556579',va='center');fig.savefig(svg,format='svg');fig.savefig(png,dpi=120);plt.close(fig)
        folder=s.BASE/'图库重做'/key;source=folder/'生成依据.json';s.save(source,{'kind':'NATIVE_EDITABLE_DATA_DIAGRAM','matrix':matrix,'snapshots':g['source_snapshots'],'confirmed_unit':'EU, using exact SKU/source labels and existing owner confirmation; no US conversion or foot length generated.','source_evidence':cp['source_evidence'],'SVG':s.rel(svg),'PNG':s.rel(png)})
        plan={'family':g['family'],'execution_key':key,'kind':'detail_slot','reviewed':False,'reviewer':None,'ids':sorted(set(g['ids'])),'assets':{'EU':{'state':'REVIEW_PENDING','file':s.rel(png),'sha256':s.sha(png),'native_svg':s.rel(svg)}},'detail_replacements_by_url':{g['bad_url']:'EU'},'expected_old_by_id':g['old_by_id'],'source_evidence':cp['source_evidence']+[s.rel(source),s.rel(s.BASE/'历史尺码图来源复核.json')],'reason':'Exact live byte/pixel match to known formula-generated US/foot-length table. Replace only this known picture by exact current colour/EU matrix, preserving all other product content.'};s.save(folder/'计划.json',plan);entries.append({'key':key,'family':g['family'],'ids':plan['ids'],'file':s.rel(png),'matrix':matrix})
    s.save(s.BASE/'EU尺码图执行.json',{'at':s.now(),'state':'PREVIEW_NOT_APPROVED','groups':entries,'ids':len({pid for e in entries for pid in e['ids']})})
    from PIL import Image,ImageOps,ImageDraw
    for start in range(0,len(entries),12):
        chunk=entries[start:start+12];sheet=Image.new('RGB',(1600,((len(chunk)+3)//4)*425),'white');draw=ImageDraw.Draw(sheet)
        for i,e in enumerate(chunk):
            x=(i%4)*400;y=(i//4)*425;im=ImageOps.contain(Image.open(s.ROOT/e['file']),(395,395));sheet.paste(im,(x,y+25));draw.text((x+5,y+4),e['family']+' '+str(len(e['ids']))+' IDs',fill='black')
        sheet.save(raw/('EU新图复核_'+str(start//12+1)+'.jpg'),quality=97)
    print(json.dumps({'groups':len(entries),'ids':len({pid for e in entries for pid in e['ids']})}))

if __name__=='__main__':main()
