import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(tag='div') { this.tagName=tag.toUpperCase(); this.children=[]; this.dataset={}; this.style={}; this.value=''; this._text=''; this.checked=false; }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text+this.children.map(c=>c.textContent).join(''); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this._text=''; this.children=[]; this.append(...items); }
  insertBefore(item,before) { const index=this.children.indexOf(before); this.children.splice(index<0?this.children.length:index,0,item); }
  setAttribute(key,value) { this[key]=value; }
  add(option) { this.append(option); }
  get options() { return this.children; }
  get selectedOptions() { return this.children.filter(child=>child.value===this.value); }
}
const walk = node => [node,...node.children.flatMap(walk)];

test('客户资料包支持编辑关联与移除登记',async()=>{
  const nav=new Element('nav'),page=new Element(),pageName=new Element(),calls=[];
  const items=[{id:'r1',title:'鞋厂介绍',path:'04_客户开发/factory.pdf',object_ids:['customer:1']},{id:'r2',title:'通用介绍',path:'04_客户开发/shared.pdf',object_ids:[]}];
  const data={csrf_token:'test',objects:[{kind:'customer',id:'customer:1',title:'买家甲'},{kind:'customer',id:'customer:2',title:'买家乙'}]};
  const location={hash:'#/library?customer=customer%3A1'}, context={console,URLSearchParams,location,history:{replaceState(_a,_b,value){location.hash=value;}},window:{confirm:()=>true},
    Option:function(title,value){const option=new Element('option');option.textContent=title;option.value=value;return option;},
    document:{querySelector:()=>nav,getElementById:id=>id==='page'?page:pageName,createElement:tag=>new Element(tag),createTextNode:value=>{const e=new Element('text');e.textContent=value;return e;}}};
  context.fetch=async(url,options={})=>{
    const body=options.body ? JSON.parse(options.body) : null; calls.push({url,body}); let value;
    if(url==='/api/desk/bootstrap')value=data;
    else if(url==='/api/library' && body) {value={id:'r3',...body};items.unshift(value);}
    else if(url==='/api/library')value={items:structuredClone(items)};
    else if(url==='/api/library/candidates')value={items:[]};
    else if(url==='/api/library/candidates?q=BQ001')value={items:[{name:'BQ001 · 主图',path:'01_产品资产/BQ001/shoe.jpg'}]};
    else if(url==='/api/library/update') {const index=items.findIndex(x=>x.id===body.id);items[index]={...items[index],title:body.title,object_ids:body.object_ids};value=items[index];}
    else if(url==='/api/library/remove') {const index=items.findIndex(x=>x.id===body.id);items.splice(index,1);value={removed:body.id};}
    else throw Error(url);
    return {ok:true,json:async()=>structuredClone(value)};
  };
  vm.createContext(context);vm.runInContext(fs.readFileSync(new URL('./web/library.js',import.meta.url),'utf8'),context);
  await context.window.renderCustomerLibrary();
  assert.match(page.textContent,/该客户资料/);assert.match(page.textContent,/共用资料/);
  const resource=walk(page).find(e=>e.tagName==='ARTICLE'&&e.textContent.includes('鞋厂介绍'));
  resource.children.find(e=>e.textContent==='编辑名称和客户').onclick();
  const form=walk(page).find(e=>e.tagName==='FORM');
  const title=walk(form).find(e=>e['aria-label']==='资料名称'); title.value='鞋厂介绍新版';
  const second=walk(form).find(e=>e.tagName==='INPUT'&&e.value==='customer:2');second.checked=true;
  await form.onsubmit({preventDefault(){}});
  assert.equal(calls.find(c=>c.url==='/api/library/update').body.title,'鞋厂介绍新版');
  assert.deepEqual([...calls.find(c=>c.url==='/api/library/update').body.object_ids],['customer:1','customer:2']);
  const revised=walk(page).find(e=>e.tagName==='ARTICLE'&&e.textContent.includes('鞋厂介绍新版'));
  await revised.children.find(e=>e.textContent==='移除记录').onclick();
  assert.equal(calls.find(c=>c.url==='/api/library/remove').body.id,'r1');
  assert.doesNotMatch(page.textContent,/鞋厂介绍新版/); assert.match(page.textContent,/通用介绍/);
  const add=walk(page).find(e=>e.tagName==='BUTTON'&&e.textContent==='关联原资料');add.onclick();
  const addForm=walk(page).find(e=>e.tagName==='FORM');
  const keyword=walk(addForm).find(e=>e['aria-label']==='搜索已有材料'); keyword.value='BQ001';
  await walk(addForm).find(e=>e.tagName==='BUTTON'&&e.textContent==='查找已有材料').onclick();
  const picker=walk(addForm).find(e=>e['aria-label']==='选择已有材料');picker.value='01_产品资产/BQ001/shoe.jpg';picker.onchange();
  await addForm.onsubmit({preventDefault(){}});
  const saved=calls.find(c=>c.url==='/api/library'&&c.body);assert.equal(saved.body.path,'01_产品资产/BQ001/shoe.jpg');
  assert.deepEqual([...saved.body.object_ids],['customer:1']);
});
